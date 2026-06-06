#!/usr/bin/env python3
# wiki_watch_cycle.py — the single-cycle driver for the wiki-watcher
# (wiki-maintenance part 4/5, the wiki-watcher (W1), task 4).
#
# Ties tasks 1-3 into ONE idempotent `poll -> detect -> significance -> (plan)
# dispatch -> audit` cycle the operator drives on a loop (DC-W3: W1 is a single-
# cycle engine + operator-driven loop, NOT a daemon). One invocation = one cycle.
# Cooldown-gated (the auto_orchestration should_fire/record_fire ledger pattern) +
# cursor-backed (task 2) so re-running it — Claude `/loop` or cron — never drops or
# double-dispatches a change.
#
# DIVISION OF LABOR. The deterministic ENGINE lives here (Python, unit-tested):
# enablement + cooldown gate, candidate detection, the significance JUDGMENT's
# deterministic floor, the dispatch PLAN, and the saw/decided audit. It returns a
# CycleReport. The AGENT half lives in the wiki-watch SKILL (prose): refine the
# borderline ("judge") candidates with doc-worthiness judgment, spawn the
# `documenter` to author, run finalize_pr/finalize_direct, then call back into
# `mark_and_audit_dispatch` + `finalize_cycle` to advance the cursor. Keeping the
# cursor advance OUT of run_cycle is what makes the engine safe to re-run.
#
# run_cycle takes injectable probes (enabled / run_config / wiki_target / token /
# changed_paths / state_dir), so the whole cycle is unit-tested end-to-end with
# stubbed tasks 1-3 (DC-W8). The significance floor is fixture-validated.
#
# Stdlib-only; matches the established skill/script convention.

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import wiki_watch_config as cfg
import wiki_watch_detect as det
import wiki_watch_dispatch as dsp

_SOURCE_KEY = "repo"           # one git cursor per watched repo
DEFAULT_COOLDOWN_S = 900       # 15-min default gap between cycles per repo


# ----------------------------------------------------------------------------
# Cooldown ledger (mirrors auto_orchestration.should_fire / record_fire)
# ----------------------------------------------------------------------------

_FIRE_FILE = "fire-ledger.json"


def should_fire(ledger: dict, key: str, now: float, cooldown_s: float) -> bool:
    """True iff `key` is outside its cooldown window. A non-positive cooldown means
    'always eligible'. Mirrors auto_orchestration.should_fire (epoch seconds here)."""
    if cooldown_s <= 0:
        return True
    last = ledger.get("last_fire", {}).get(key)
    if last is None:
        return True
    try:
        return (now - float(last)) >= cooldown_s
    except (TypeError, ValueError):
        return True


def record_fire(ledger: dict, key: str, now: float) -> dict:
    ledger.setdefault("last_fire", {})[key] = float(now)
    return ledger


def load_fire_ledger(state_dir: Path | str) -> dict:
    data = det._read_json(Path(state_dir) / _FIRE_FILE, {})
    if not isinstance(data, dict):
        return {"last_fire": {}}
    data.setdefault("last_fire", {})
    if not isinstance(data["last_fire"], dict):
        data["last_fire"] = {}
    return data


def save_fire_ledger(state_dir: Path | str, ledger: dict) -> None:
    d = Path(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    det._write_json(d / _FIRE_FILE, ledger)


# ----------------------------------------------------------------------------
# Significance judgment — the DETERMINISTIC FLOOR (fixture-validated)
# ----------------------------------------------------------------------------

# Doc-source files are doc-worthy by default (the watcher's whole point). Code is
# borderline -> defer to the LLM judge. Tests / CI / config are minor -> skip
# (start conservative: flag less, miss-then-tune — parent risk note).
_CODE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala", ".sh",
    ".ps1", ".lua", ".ex", ".exs", ".clj",
}
_MINOR_SUFFIXES = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".txt", ".csv",
}
_DOC_SOURCE_BASENAMES = {"plan.md", "roadmap.md", "readme.md", "changelog.md",
                         "agents.md", "claude.md"}
_DOC_SOURCE_DIR_PARTS = {"designs", "decisions", "docs", "adr", "rfc", "rfcs"}
_ADR_RE = re.compile(r"^\d{3,4}[-_]")  # 0007-foo.md / 042_bar.md
_TEST_RE = re.compile(r"(^|/)(tests?|spec|__tests__|e2e)(/|$)|(^|/)test_|_test\.|\.spec\.|\.test\.")


def classify_significance(path: str) -> str:
    """'doc-source' | 'code' | 'minor'. Deterministic + fixture-validated."""
    pp = PurePosixPath(path.replace("\\", "/"))
    name = pp.name.lower()
    parts = {p.lower() for p in pp.parts}

    # Tests / CI are minor regardless of suffix.
    if _TEST_RE.search(pp.as_posix()) or ".github" in parts or ".gitlab" in parts:
        return "minor"

    if name in _DOC_SOURCE_BASENAMES:
        return "doc-source"
    if parts & _DOC_SOURCE_DIR_PARTS:
        return "doc-source"
    if name.endswith(".md"):
        if _ADR_RE.match(pp.name) or pp.name.isupper() or "design" in name or "rfc" in name:
            return "doc-source"
        return "doc-source"  # a tracked .md that survived the noise filter is a doc

    suf = pp.suffix.lower()
    if suf in _CODE_SUFFIXES:
        return "code"
    if suf in _MINOR_SUFFIXES:
        return "minor"
    return "minor"


def recommend(path: str) -> str:
    """The default recommendation from the deterministic floor:
    'dispatch' (doc-source — certain) | 'judge' (code — defer to the LLM) |
    'skip' (minor — start conservative). The skill may promote a 'judge' to
    dispatch after its doc-worthiness judgment."""
    cls = classify_significance(path)
    return {"doc-source": "dispatch", "code": "judge", "minor": "skip"}[cls]


# ----------------------------------------------------------------------------
# The cycle
# ----------------------------------------------------------------------------

@dataclass
class CycleReport:
    repo_root: str
    slug: str = ""
    skipped: bool = False
    reason: str = ""
    token: str = ""
    wiki_target: str = ""
    dispatch_mode: str = ""
    candidates: list = field(default_factory=list)   # {path, classification, recommendation}
    plan: dict = field(default_factory=dict)          # {action, branch, reason}
    state_dir: str = ""
    audit_path: str = ""

    def to_dict(self) -> dict:
        return {
            "repo_root": self.repo_root, "slug": self.slug, "skipped": self.skipped,
            "reason": self.reason, "token": self.token, "wiki_target": self.wiki_target,
            "dispatch_mode": self.dispatch_mode, "candidates": self.candidates,
            "plan": self.plan, "state_dir": self.state_dir, "audit_path": self.audit_path,
        }


def _skip(repo_root, reason, **extra) -> CycleReport:
    return CycleReport(repo_root=str(repo_root), skipped=True, reason=reason, **extra)


def run_cycle(
    repo_root: str | Path, *, slug: str = "", now: float = 0.0,
    cooldown_s: float = DEFAULT_COOLDOWN_S, respect_cooldown: bool = True,
    # injectable probes (None -> resolve via the real task-1/2 functions):
    enabled: Optional[bool] = None,
    run_config: "Optional[cfg.RunConfig]" = None,
    wiki_target: Optional[str] = None,
    state_dir: Optional[str | Path] = None,
    token: Optional[str] = None,
    changed_paths: Optional[list] = None,
    gh_available: Optional[bool] = None,
) -> CycleReport:
    """Run ONE deterministic cycle and return a CycleReport. Records the fire +
    saw/decided audit; does NOT advance the cursor or spawn the documenter (the
    skill does that, then calls mark_and_audit_dispatch + finalize_cycle).

    Resolution order for each input: use the injected value when given, else the
    real resolver. So tests drive the whole cycle by injecting deltas; production
    resolves live.
    """
    repo_root = Path(repo_root)

    # 1. Device enablement (opt-in).
    if enabled is None:
        enabled = cfg.read_enablement()
    if not enabled:
        return _skip(repo_root, "wiki-watch disabled on this device (.agentm-config.json)")

    # 2. Per-repo run config (presence = opt-in).
    if run_config is None:
        run_config = cfg.read_run_config(repo_root)
    if run_config is None:
        return _skip(repo_root, "repo not configured (no .harness/wiki-watch.json marker)")

    # 3. State dir + cooldown gate.
    if state_dir is None:
        state_dir = det.resolve_state_dir(repo_root)
    state_dir = Path(state_dir)
    if respect_cooldown:
        ledger = load_fire_ledger(state_dir)
        if not should_fire(ledger, _SOURCE_KEY, now, cooldown_s):
            return _skip(repo_root, "within cooldown window", state_dir=str(state_dir))

    # 4. Wiki target.
    if wiki_target is None:
        repos = cfg.list_repos_via_registry()
        wiki_target = cfg.resolve_wiki_target_for_repo(
            repos, root_path=repo_root, slug=slug or None)
    if not wiki_target:
        return _skip(repo_root, "no wiki target (unregistered / no wiki_path)",
                     state_dir=str(state_dir))

    # 5. Current token (HEAD sha — commit-driven, idempotent).
    if token is None:
        token = det.git_current_head(repo_root) or ""
    if not token:
        return _skip(repo_root, "not a git repo / no commits", state_dir=str(state_dir))

    # 6. Detect candidates since the cursor.
    state = det.WikiWatchState(state_dir)
    src = state.source(_SOURCE_KEY)
    if changed_paths is None:
        changed_paths = det.git_changed_files(repo_root, src.cursor, include_uncommitted=False)
    candidates = det.compute_candidates(
        src, token=token, changed_paths=changed_paths,
        watch_sources=run_config.watch_sources, now=now)

    # Always record the fire (we ran a cycle) — cooldown is per-attempt, not
    # per-dispatch, so a no-candidate cycle still consumes the window.
    if respect_cooldown:
        ledger = load_fire_ledger(state_dir)
        record_fire(ledger, _SOURCE_KEY, now)
        save_fire_ledger(state_dir, ledger)

    cand_records = [
        {"path": c.path, "classification": classify_significance(c.path),
         "recommendation": recommend(c.path)}
        for c in candidates
    ]

    # 7. Dispatch plan (PR-vs-direct) — only meaningful if something is dispatchable.
    if gh_available is None:
        gh_available = dsp.check_gh_available()
    plan = dsp.plan_dispatch(run_config, gh_available=gh_available, slug=slug or repo_root.name,
                             token=token)

    # 8. Audit saw + decided (the skill appends 'dispatched' after acting).
    audit_path = dsp.append_audit(state_dir, dsp.audit_record(
        phase="saw", source=_SOURCE_KEY, ts=_iso(now), token=token,
        changed=list(changed_paths)))
    dsp.append_audit(state_dir, dsp.audit_record(
        phase="decided", source=_SOURCE_KEY, ts=_iso(now), token=token,
        candidates=cand_records, plan={"action": plan.action, "reason": plan.reason}))

    return CycleReport(
        repo_root=str(repo_root), slug=slug, token=token, wiki_target=wiki_target,
        dispatch_mode=run_config.dispatch_mode, candidates=cand_records,
        plan={"action": plan.action, "branch": plan.branch, "reason": plan.reason},
        state_dir=str(state_dir), audit_path=str(audit_path),
    )


def _iso(now: float) -> str:
    """Best-effort ISO timestamp string from an injected epoch (empty for now=0,
    the test sentinel). Avoids importing datetime into the pure path. A pathological
    `now` (inf / NaN / out-of-range) degrades to "" rather than raising out of
    run_cycle / the completion helpers."""
    if not now:
        return ""
    try:
        import datetime
        return datetime.datetime.utcfromtimestamp(now).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, ValueError, OSError):
        return ""


# ----------------------------------------------------------------------------
# Completion helpers — the skill calls these AFTER a successful documenter dispatch
# ----------------------------------------------------------------------------

def mark_and_audit_dispatch(
    state_dir: Path | str, token: str, path: str, *, result: dict, now: float = 0.0,
) -> None:
    """Record that `path` under `token` was dispatched (so a restart won't re-do it)
    and append the 'dispatched' audit record with the PR/commit links."""
    state = det.WikiWatchState(state_dir)
    state.mark_dispatched(_SOURCE_KEY, token, path)
    state.save()
    # Drop any keys that collide with audit_record's named params, so a stray
    # result field (e.g. {"phase": ...}) can't raise a TypeError out of this
    # "never-fails" completion helper.
    safe = {k: v for k, v in (result or {}).items() if k not in ("phase", "source", "ts")}
    dsp.append_audit(state_dir, dsp.audit_record(
        phase="dispatched", source=_SOURCE_KEY, ts=_iso(now), token=token, path=path,
        **safe))


def record_dispatch_failure(state_dir: Path | str, token: str, path: str, now: float) -> None:
    state = det.WikiWatchState(state_dir)
    state.record_failure(_SOURCE_KEY, token, path, now)
    state.save()


def finalize_cycle(state_dir: Path | str, token: str) -> None:
    """Advance the cursor to `token` (all candidates processed). The high-water
    mark — changes up to `token` never resurface."""
    state = det.WikiWatchState(state_dir)
    state.advance_cursor(_SOURCE_KEY, token)
    state.save()


# ----------------------------------------------------------------------------
# CLI — the skill invokes `run --repo <root>` and reads the JSON report
# ----------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="wiki_watch_cycle",
        description="Run one wiki-watch cycle (poll -> detect -> significance -> plan).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run one cycle, print the JSON report")
    p_run.add_argument("--repo", required=True)
    p_run.add_argument("--slug", default="")
    p_run.add_argument("--cooldown", type=float, default=DEFAULT_COOLDOWN_S)
    p_run.add_argument("--no-cooldown", action="store_true",
                       help="ignore the cooldown gate (manual/forced run)")
    p_run.add_argument("--now", type=float, default=None)

    p_sig = sub.add_parser("classify", help="classify paths (significance floor)")
    p_sig.add_argument("paths", nargs="*")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        now = args.now
        if now is None:
            import time
            now = time.time()
        report = run_cycle(args.repo, slug=args.slug, now=now, cooldown_s=args.cooldown,
                           respect_cooldown=not args.no_cooldown)
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 1 if report.skipped else 0

    if args.cmd == "classify":
        print(json.dumps(
            {p: {"classification": classify_significance(p), "recommendation": recommend(p)}
             for p in args.paths}, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
