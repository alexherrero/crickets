#!/usr/bin/env python3
"""Bind an already-created host worktree to a named plan (host-native worktree flow).

`EnterWorktree` (Claude Code) / New-Worktree-Mode (Antigravity) own worktree
*creation* now — this script only does what's left once the worktree already
exists: the LC-6 pre-flight-reconcile defense-in-depth guard, the worktree-local
`.harness/active-plan` marker write, and the LC-2 `vault_project` divergent-override
copy. It replaces `spawn_worker.py`'s post-creation responsibilities; the git
`worktree add` / rollback / locking / concurrency-cap machinery that script also
carried is gone — the host primitive owns that now (host-native primitives only,
per this plan's own constraint).

    worktree_marker.py write <worktree-path> <slug> <plan-path> [--project-root <root>]

Exit codes:
    0 — marker written. `.harness/project.json` is also written into the
        worktree whenever the original repo has one, as a copy of the
        original's full project.json (so `isolation_config.read_isolation()`
        and every other plugin that reads this file — e.g. github-projects'
        board-sync, which needs `vault_project` / `github` / `fields` /
        `items_source` — resolve the same way inside the worktree as outside
        it; `.harness/` is gitignored, so a freshly host-created worktree
        otherwise has no project.json at all), with `vault_project` refreshed
        on top iff that override diverges from the origin basename (LC-2,
        unchanged).
    2 — loud: empty slug, worktree path does not exist / is not a directory,
        the path exists but is NOT a registered git worktree of `root` (the
        fake-slot guard — see `_is_registered_worktree` below), or the marker
        write itself failed. Never a partial write: the pre-flight check runs
        before any write.
    3 — pre-flight reconcile no-op (LC-6): the resolved plan's declared
        `expected_artifacts` already exist under `--project-root` — the lane is
        already shipped. Nothing written. The caller holds a worktree bound to
        nothing; it must exit/remove it, not proceed.

Stdlib-only; mirrors `spawn_worker.py`'s LC-2/LC-6 helpers verbatim (relocated,
not rewritten) so their own test coverage carries over unchanged in intent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import preflight_reconcile  # noqa: E402
import resolve_plan  # noqa: E402


# ── LC-2: vault_project divergent-override copy (relocated from spawn_worker.py) ──

def _git(args: list[str], root: str | os.PathLike) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, timeout=30,
    )


def _origin_basename(root: str | os.PathLike) -> str | None:
    """The `origin` remote URL's repo basename, or None if unset / no remote.

    Best-effort: any failure (no remote, missing git, a >30s hang) collapses to
    None — never raises.
    """
    try:
        r = _git(["remote", "get-url", "origin"], root)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    url = r.stdout.strip().rstrip("/")
    if not url:
        return None
    last = re.split(r"[/:]", url)[-1]
    if last.endswith(".git"):
        last = last[: -len(".git")]
    return last or None


def _registered_worktree_paths(root: str | os.PathLike) -> set[str] | None:
    """Every path `git worktree list --porcelain` reports for `root`'s repo,
    resolved so a symlinked/relative path still matches. None iff the registry
    itself couldn't be read (git missing, a >30s hang, or a non-zero exit) —
    callers must treat that as "can't verify", never as "not registered".
    """
    try:
        r = _git(["worktree", "list", "--porcelain"], root)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    paths: set[str] = set()
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            p = line[len("worktree "):].strip()
            try:
                paths.add(str(Path(p).resolve()))
            except OSError:
                paths.add(p)
    return paths


def _is_registered_worktree(worktree_path: str | os.PathLike,
                            root: str | os.PathLike) -> bool | None:
    """True iff `worktree_path` is a real, git-registered worktree of `root`.

    The fake-slot guard: a host worktree primitive can leave a plain directory
    behind a slot path instead of an actual `git worktree add`-created checkout
    (observed live — a directory that never appears in `git worktree list`, so
    every git command run inside it silently walks up to `root`'s own `.git`
    and operates on the SHARED checkout). Binding a plan marker into a fake
    slot would make `/work` believe it has isolation it doesn't have. Returns
    None (not False) when the registry itself is unreadable — an unverifiable
    slot is refused by the caller exactly like a confirmed-fake one, never
    silently trusted (mirrors `worktree_shepherd.is_safe_to_reclaim`'s "never
    guess safe on an unreadable repo").
    """
    registered = _registered_worktree_paths(root)
    if registered is None:
        return None
    try:
        resolved = str(Path(worktree_path).resolve())
    except OSError:
        resolved = str(worktree_path)
    return resolved in registered


def _read_vault_project(root: str | os.PathLike) -> str | None:
    """`vault_project` from `<root>/.harness/project.json`, or None if absent/malformed.

    Any read/parse error (missing file, bad JSON, non-object document, non-string
    value) collapses to None — the fallback is optional, never fatal.
    """
    pj = Path(root) / ".harness" / "project.json"
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        val = data.get("vault_project") if isinstance(data, dict) else None
    except Exception:
        return None
    return val if isinstance(val, str) and val.strip() else None


def _needs_vault_project_copy(root: str | os.PathLike) -> bool:
    """True iff a `vault_project` override would diverge from the origin basename."""
    vp = _read_vault_project(root)
    if not vp:
        return False
    origin = _origin_basename(root)
    return origin is None or vp != origin


def _worktree_project_json(root: str | os.PathLike) -> dict | None:
    """The `.harness/project.json` content to write into the new worktree, or
    None if there's nothing worth carrying over.

    `.harness/` is gitignored, so a freshly host-created worktree has NO
    project.json at all — any code that later runs `isolation_config.
    read_isolation()` from inside it (finalize_unit.py at close-out, for
    instance) would see the code-default (`direct`) instead of the ORIGINAL
    repo's real `isolation.mode` / `isolation.integration`, silently
    mis-resolving the very setting that got the worktree spawned in the first
    place. Other plugins read the same file too (github-projects' board-sync
    needs `vault_project` / `github` / `fields` / `items_source`), so the fix
    is to carry over a COPY of the original's full project.json rather than
    a fresh dict built from an allowlist of keys — a minimal rebuild silently
    drops whatever the allowlist forgot. `vault_project` is refreshed on top
    of the copy only when it diverges from the origin basename (LC-2,
    unchanged from before); the rest of the original document rides along
    verbatim.
    """
    pj = Path(root) / ".harness" / "project.json"
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        data = None

    if not isinstance(data, dict):
        return None

    out = dict(data)
    if _needs_vault_project_copy(root):
        out["vault_project"] = _read_vault_project(root)
    return out or None


# ── core ────────────────────────────────────────────────────────────────────

def write_marker(worktree_path: str | os.PathLike, slug: str,
                 plan_path: str | os.PathLike, root: str | os.PathLike) -> tuple[int, str, str]:
    """Bind `worktree_path` to `slug`. Pure core, no git-worktree mutation.

    `plan_path` is the already-resolved `PLAN-<slug>.md` (the caller — `/work`
    step 1 — already ran `resolve_plan.py` to get here; this never re-resolves).
    `root` is the ORIGINAL repo root (not the worktree) — LC-2's vault_project /
    origin lookups and LC-6's artifact-existence check both read against it.
    """
    norm = resolve_plan._normalize_plan_name(slug)
    if not norm:
        return (2, "", f"[worktree_marker] a named plan slug is required (got {slug!r}).\n")

    wt = Path(worktree_path)
    if not wt.is_dir():
        return (2, "", f"[worktree_marker] worktree path does not exist: {wt}\n")

    # Fake-slot guard: refuse to bind a plan into a directory that isn't
    # actually a git-registered worktree of `root`. Trusting the host
    # primitive's return value without checking it back against `git worktree
    # list` is exactly how a session ends up silently sharing the parent
    # checkout instead of an isolated one (see _is_registered_worktree).
    registered = _is_registered_worktree(wt, root)
    if registered is not True:
        reason = ("git worktree list --porcelain does not list it" if registered is False
                  else "its worktree registry could not be read")
        return (2, "",
                f"[worktree_marker] refusing to bind: {wt} exists on disk but {reason} — "
                f"it is not confirmed to be a real, isolated git worktree of {root}. Binding "
                f"a plan here would silently operate on the parent checkout instead. Verify "
                f"with `git -C {root} worktree list --porcelain` and re-create the slot via "
                f"the host's worktree primitive before retrying.\n")

    # LC-6 defense-in-depth: refuse before any write if the plan already shipped.
    shipped, present = preflight_reconcile.already_shipped(plan_path, root)
    if shipped:
        return (preflight_reconcile.SHIPPED_NOOP, "",
                preflight_reconcile.shipped_message(slug, present))

    try:
        marker_dir = wt / ".harness"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "active-plan").write_text(f"{norm}\n", encoding="utf-8")

        project_json = _worktree_project_json(root)
        if project_json is not None:
            (marker_dir / "project.json").write_text(
                json.dumps(project_json, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        return (2, "", f"[worktree_marker] marker write failed ({exc}).\n")

    return (0, f"{wt}\n", "")


# ── CLI ────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="worktree_marker.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="bind an already-created worktree to a named plan")
    w.add_argument("worktree_path")
    w.add_argument("slug")
    w.add_argument("plan_path")
    w.add_argument("--project-root", default=None)
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    rc, out, err = write_marker(ns.worktree_path, ns.slug, ns.plan_path, root)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
