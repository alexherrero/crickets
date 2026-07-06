#!/usr/bin/env python3
# wiki_watch_detect.py — change-detection + durable idempotency for the wiki-watcher
# (wiki-maintenance part 4/5, the wiki-watcher (W1), task 2).
#
# Turns "what changed in the watched repo + its active PLAN/design/ROADMAP" into an
# idempotent CANDIDATE FEED the dispatch step (task 3) consumes. Three pieces:
#
#   1. Significance pre-filter (PURE)  — a deterministic path-glob NOISE filter:
#      drop lockfiles / *.pyc / __pycache__ / dist/ / node_modules / the OUTPUT
#      wiki/ (watching it would feed the documenter's own writes back in — the
#      QA-Reliability loop the design calls out), keep code + PLAN/design/ROADMAP.
#      This is the coarse gate; the fine doc-worthiness JUDGMENT is task 4.
#
#   2. Durable state (cursors + pending/dispatched) under _harness/wiki-watch/ —
#      modeled on harness_memory's read_cursor/write_cursor/plan_done_promotion
#      high-water-mark idempotency, extended to per-source cursors + a per-token
#      dispatched-set + retry/backoff bookkeeping. The cursor only advances once a
#      token is fully processed, so a change is NEVER dropped; the dispatched-set
#      means a re-run / restart NEVER double-dispatches.
#
#   3. The git + content probes (IMPURE) that produce the raw deltas, and the
#      state-dir resolver (vault in vault-mode via harness_memory vault-state-path,
#      repo-local <repo>/.harness/wiki-watch/ otherwise — DC-W6).
#
# The PURE core (significance + candidate computation + backoff + state I/O over an
# explicit dir) is deterministically unit-tested (DC-W8). The git/vault probes are
# exercised against a throwaway temp git repo.
#
# Stdlib-only; matches the established skill/script convention.

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import wiki_watch_config as cfg  # sibling group script (locator + vault-path helpers)

# ----------------------------------------------------------------------------
# 1. Significance pre-filter (PURE)
# ----------------------------------------------------------------------------

# Path SEGMENTS that mark generated / vendored / transient trees. A path is noise
# if any of its segments is one of these. `wiki` is here on purpose: it is the
# documenter's OUTPUT — watching it would loop the watcher onto its own writes.
_NOISE_DIR_PARTS = {
    ".git", "__pycache__", "node_modules", "dist", "build", "out",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".tox", ".cache", "vendor", ".next", "target", "coverage", "wiki",
}
_NOISE_SUFFIXES = {
    ".pyc", ".pyo", ".pyd", ".so", ".o", ".class", ".map", ".min.js",
    ".min.css", ".lock", ".log", ".tmp", ".swp", ".bak",
}
_NOISE_BASENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "Gemfile.lock", "composer.lock", ".DS_Store", "Thumbs.db",
}


def is_significant(path: str) -> bool:
    """True iff `path` (repo-relative, posix or native) is doc-relevant enough to
    be a CANDIDATE — i.e. not obvious noise. Coarse + deterministic; the fine
    doc-worthiness judgment happens later (task 4). Permissive by design: keep
    anything not on the noise lists."""
    if not path or not path.strip():
        return False
    pp = PurePosixPath(path.replace("\\", "/"))
    parts = set(pp.parts)
    if parts & _NOISE_DIR_PARTS:
        return False
    name = pp.name
    if name in _NOISE_BASENAMES:
        return False
    # Match compound suffixes (.min.js) before single ones.
    lname = name.lower()
    for suf in _NOISE_SUFFIXES:
        if lname.endswith(suf):
            return False
    return True


def filter_significant(paths) -> list[str]:
    """Keep only the significant paths, order-preserving + de-duplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        if is_significant(p):
            out.append(p)
    return out


def _matches_watch_sources(path: str, watch_sources) -> bool:
    """True iff `path` falls under any watch source. "." matches everything; a
    source ending in "/" (or naming a dir) matches by prefix; otherwise exact /
    prefix match. Pure."""
    norm = path.replace("\\", "/")
    for src in watch_sources:
        s = src.replace("\\", "/").strip()
        if s in (".", "", "./"):
            return True
        s = s.rstrip("/")
        if norm == s or norm.startswith(s + "/"):
            return True
    return False


# ----------------------------------------------------------------------------
# 2. Durable state — cursors + pending/dispatched + retry/backoff (PURE I/O over
#    an explicit state dir)
# ----------------------------------------------------------------------------

_CURSORS_FILE = "cursors.json"
_PENDING_FILE = "pending.json"

# Exponential backoff (seconds) for a failing candidate: base * 2^(count-1),
# capped. Pure — `now` is always injected by callers for deterministic tests.
_BACKOFF_BASE_S = 60
_BACKOFF_CAP_S = 3600


def backoff_seconds(failure_count: int) -> int:
    """Seconds to wait before retrying after `failure_count` consecutive failures
    (count>=1). 1->60, 2->120, 3->240, …, capped at 3600."""
    if failure_count < 1:
        return 0
    return min(_BACKOFF_CAP_S, _BACKOFF_BASE_S * (2 ** (failure_count - 1)))


@dataclass
class SourceState:
    """Per-source durable state. `cursor` is the last FULLY-processed token (git
    SHA / content hash); `token` is the token currently mid-processing; `dispatched`
    are paths already dispatched under `token`; `failures` is {path: {count, last}}
    for retry/backoff."""
    cursor: str = ""
    token: str = ""
    dispatched: list[str] = field(default_factory=list)
    failures: dict = field(default_factory=dict)


class WikiWatchState:
    """Read/modify/write the cursors + pending state under a state dir. All writes
    go through `save()`; nothing is written until a caller saves (mirrors the
    cursor-only-advances-when-done discipline)."""

    def __init__(self, state_dir: Path | str):
        self.dir = Path(state_dir)
        self._cursors: dict[str, str] = {}
        self._pending: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        self._cursors = _read_json(self.dir / _CURSORS_FILE, {})
        self._pending = _read_json(self.dir / _PENDING_FILE, {})

    def source(self, key: str) -> SourceState:
        cursor = self._cursors.get(key, "")
        pend = self._pending.get(key, {})
        return SourceState(
            cursor=cursor if isinstance(cursor, str) else "",
            token=pend.get("token", "") if isinstance(pend, dict) else "",
            dispatched=list(pend.get("dispatched", []) or []) if isinstance(pend, dict) else [],
            failures=dict(pend.get("failures", {}) or {}) if isinstance(pend, dict) else {},
        )

    def mark_dispatched(self, key: str, token: str, path: str) -> None:
        """Record that `path` under `token` was dispatched (so a restart before the
        cursor advances will not re-dispatch it). Clears any failure record."""
        pend = self._pending.setdefault(key, {})
        if pend.get("token") != token:
            pend["token"] = token
            pend["dispatched"] = []
            pend["failures"] = {}
        if path not in pend["dispatched"]:
            pend["dispatched"].append(path)
        pend.get("failures", {}).pop(path, None)

    def record_failure(self, key: str, token: str, path: str, now: float) -> None:
        """Increment the failure count + stamp the time for `path` under `token`
        (drives backoff eligibility)."""
        pend = self._pending.setdefault(key, {})
        if pend.get("token") != token:
            pend["token"] = token
            pend["dispatched"] = []
            pend["failures"] = {}
        failures = pend.setdefault("failures", {})
        rec = failures.setdefault(path, {"count": 0, "last": 0.0})
        rec["count"] = int(rec.get("count", 0)) + 1
        rec["last"] = float(now)

    def advance_cursor(self, key: str, token: str) -> None:
        """Mark `token` fully processed: set the cursor and clear the pending
        record. The high-water mark — a change before this token never resurfaces."""
        self._cursors[key] = token
        self._pending.pop(key, None)

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        _write_json(self.dir / _CURSORS_FILE, self._cursors)
        _write_json(self.dir / _PENDING_FILE, self._pending)


def _read_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
    return data


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------
# Candidate computation (PURE given the state + injected changed paths)
# ----------------------------------------------------------------------------

@dataclass
class Candidate:
    source: str
    token: str
    path: str


def compute_candidates(
    state: SourceState, *, token: str, changed_paths,
    watch_sources=None, now: float = 0.0, failures_eligible: bool = True,
) -> list[Candidate]:
    """Given a source's durable state, the current `token`, and the raw
    `changed_paths` (deltas since `state.cursor`), return the candidate feed.

    Drops: (a) the unchanged case (token == cursor -> []); (b) paths outside
    `watch_sources`; (c) insignificant noise; (d) paths already dispatched under
    this token (no double-dispatch); (e) when `failures_eligible`, paths still in
    backoff (now < last + backoff(count)).

    PURE — `now` and the backoff schedule are explicit, so restart/retry behavior
    is fully deterministic in tests.
    """
    if token and token == state.cursor:
        return []
    paths = changed_paths
    if watch_sources is not None:
        paths = [p for p in paths if _matches_watch_sources(p, watch_sources)]
    significant = filter_significant(paths)
    out: list[Candidate] = []
    for p in significant:
        if p in state.dispatched and state.token == token:
            continue  # already dispatched under this exact token
        if failures_eligible and _in_backoff(state, token, p, now):
            continue
        out.append(Candidate(source="", token=token, path=p))
    return out


def _in_backoff(state: SourceState, token: str, path: str, now: float) -> bool:
    if state.token != token:
        return False
    rec = state.failures.get(path)
    if not rec:
        return False
    count = int(rec.get("count", 0))
    if count < 1:
        return False
    return now < float(rec.get("last", 0.0)) + backoff_seconds(count)


# ----------------------------------------------------------------------------
# 3a. Git + content probes (IMPURE)
# ----------------------------------------------------------------------------

def _git(repo_root: Path | str, *args: str) -> Optional[str]:
    """Run a read-only git command in `repo_root`; return stdout (stripped) or None
    on any failure (not a repo, git missing, non-zero exit)."""
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def git_current_head(repo_root: Path | str) -> Optional[str]:
    """The repo's current HEAD commit SHA, or None when not a git repo / no commits."""
    return _git(repo_root, "rev-parse", "HEAD")


def _is_commit(repo_root: Path | str, ref: str) -> bool:
    """True iff `ref` resolves to a reachable commit in the repo. Used to detect a
    STALE cursor (a SHA orphaned by rebase / amend / force-push / squash / GC /
    shallow re-fetch) so we never confuse 'diff failed' with 'nothing changed'."""
    return _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") is not None


def git_changed_files(
    repo_root: Path | str, since: str, *, include_uncommitted: bool = True,
) -> list[str]:
    """Repo-relative paths changed between `since` (a commit SHA; "" = from the
    repo's first commit) and HEAD. With include_uncommitted, also union the
    working-tree + staged changes so an in-progress edit is seen before it is
    committed. Returns [] on any git failure (graceful).

    FAIL-SAFE on a stale/unreachable `since` (orphaned by a history rewrite): rather
    than let `git diff <stale>..HEAD` fail silently to [] — which would DROP every
    change and blind the watcher permanently (idempotency invariant #1) — we treat an
    unresolvable cursor like an absent one and re-surface the whole tree. A re-dispatch
    is tolerated (the dispatched-set dedups); a silent drop is not."""
    head = git_current_head(repo_root)
    if head is None:
        return []
    out: set[str] = set()
    have_since = bool(since) and _is_commit(repo_root, since)
    if have_since and since != head:
        diff = _git(repo_root, "diff", "--name-only", f"{since}..{head}")
        if diff:
            out.update(line for line in diff.splitlines() if line.strip())
    elif not have_since:
        # No cursor yet OR a stale/unreachable cursor: everything tracked at HEAD is
        # "new" to the watcher (fail-safe toward re-surfacing, never dropping).
        listing = _git(repo_root, "ls-tree", "-r", "--name-only", head)
        if listing:
            out.update(line for line in listing.splitlines() if line.strip())
    if include_uncommitted:
        wt = _git(repo_root, "status", "--porcelain")
        if wt:
            for line in wt.splitlines():
                # porcelain: "XY <path>" (or "XY <old> -> <new>" for renames)
                entry = line[3:].strip()
                if " -> " in entry:
                    entry = entry.split(" -> ", 1)[1]
                if entry:
                    out.add(entry.strip().strip('"'))
    return sorted(out)


def content_token(path: Path | str) -> str:
    """A change token for a non-git source file (vault PLAN.md / ROADMAP.md / a
    design doc): sha256 of its bytes, or "" when absent. Lets the watcher detect
    edits to files that change outside git."""
    p = Path(path)
    if not p.is_file():
        return ""
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


# ----------------------------------------------------------------------------
# 3b. State-dir resolution (IMPURE — vault via harness_memory, else repo-local)
# ----------------------------------------------------------------------------

_STATE_LEAF = "wiki-watch"


def resolve_state_dir(repo_root: Path | str, *, prefer_vault: bool = True) -> Path:
    """Where cursors / pending / audit live (DC-W6).

    Vault mode: shell out to agentm's `harness_memory.py vault-state-path
    wiki-watch --project-root <repo>` -> <vault>/projects/<slug>/_harness/wiki-watch.
    Falls back to the repo-local <repo>/.harness/wiki-watch/ when agentm is
    unreachable, the vault is unavailable, or prefer_vault is False. Never raises.
    """
    repo_root = Path(repo_root)
    if prefer_vault:
        script = cfg.find_agentm_script("harness_memory.py")
        if script is not None:
            try:
                res = subprocess.run(
                    [sys.executable, str(script), "vault-state-path", _STATE_LEAF,
                     "--project-root", str(repo_root)],
                    capture_output=True, text=True, timeout=30,
                )
            except (OSError, subprocess.SubprocessError):
                res = None
            if res is not None and res.returncode == 0:
                out = (res.stdout or "").strip()
                if out:
                    return Path(out)
    return repo_root / ".harness" / _STATE_LEAF


# ----------------------------------------------------------------------------
# CLI — debugging / the task-4 cycle driver
# ----------------------------------------------------------------------------

def _emit(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="wiki_watch_detect",
        description="Detect doc-worthy changes in a watched repo (idempotent feed).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sig = sub.add_parser("significant", help="filter a path list to significant ones")
    p_sig.add_argument("paths", nargs="*")

    p_state = sub.add_parser("state-dir", help="print the resolved state dir for a repo")
    p_state.add_argument("repo_root")
    p_state.add_argument("--local", action="store_true", help="force repo-local mode")

    p_changed = sub.add_parser("changed", help="git-changed files in a repo since a cursor")
    p_changed.add_argument("repo_root")
    p_changed.add_argument("--since", default="")

    args = parser.parse_args(argv)

    if args.cmd == "significant":
        _emit({"significant": filter_significant(args.paths)})
        return 0
    if args.cmd == "state-dir":
        _emit({"state_dir": str(resolve_state_dir(args.repo_root, prefer_vault=not args.local))})
        return 0
    if args.cmd == "changed":
        _emit({"changed": git_changed_files(args.repo_root, args.since)})
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
