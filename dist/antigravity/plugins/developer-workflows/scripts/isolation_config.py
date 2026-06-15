#!/usr/bin/env python3
"""Isolation-mode reader and worktree-detection helpers for the developer-workflows loop.

Mirrors the graceful-reader pattern established by _read_vault_project():
any IO/parse error collapses to the safe default — never raises.

Precedence cascade: command-arg (--no-isolate) > project.json > code-default-ON.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

_DEFAULT_MODE = "worktree-per-plan"
_DEFAULT_INTEGRATION = "pull-request"
_ALLOWED_MODES = frozenset({"worktree-per-plan", "direct", "worktree-per-task"})
_ALLOWED_INTEGRATIONS = frozenset({"pull-request", "direct-push"})


# ── config reader ────────────────────────────────────────────────────────────

def read_isolation(root: str | os.PathLike) -> dict:
    """Read the isolation block from .harness/project.json.

    Returns {'mode': ..., 'integration': ...}, defaulting to
    'worktree-per-plan' / 'pull-request' on any error (missing file, bad
    JSON, wrong type, absent key — every failure path collapses to the safe
    default rather than raising, mirroring _read_vault_project).
    """
    pj = Path(root) / ".harness" / "project.json"
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _defaults()
        block = data.get("isolation", {})
        if not isinstance(block, dict):
            return _defaults()
    except Exception:
        return _defaults()

    mode = block.get("mode", _DEFAULT_MODE)
    integration = block.get("integration", _DEFAULT_INTEGRATION)

    return {
        "mode": mode if mode in _ALLOWED_MODES else _DEFAULT_MODE,
        "integration": integration if integration in _ALLOWED_INTEGRATIONS else _DEFAULT_INTEGRATION,
    }


def _defaults() -> dict:
    return {"mode": _DEFAULT_MODE, "integration": _DEFAULT_INTEGRATION}


# ── worktree-detection helpers ───────────────────────────────────────────────

def resolve_main_worktree(project_root: str | os.PathLike) -> Path:
    """Return the MAIN working-tree root (the root of the repo, never a worktree).

    Uses `git rev-parse --git-common-dir` which returns:
      - ".git"  (relative) in the MAIN working tree
      - an absolute path to the main .git  in any worktree

    In a worktree the common dir's parent is the main tree. In the main tree,
    we resolve project_root directly. Graceful-skip: any error → resolved
    project_root (safe: spawns beside cwd, never inside it).
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return Path(project_root).resolve()
        common = r.stdout.strip()
        if not common:
            return Path(project_root).resolve()
        if os.path.isabs(common):
            # Inside a worktree: common points to the main .git
            return Path(common).resolve().parent
        # Main tree: common == ".git" (relative to project_root)
        return Path(project_root).resolve()
    except Exception:
        return Path(project_root).resolve()


def is_inside_worktree(project_root: str | os.PathLike) -> bool:
    """True iff project_root is inside a git worktree (not the main tree).

    The invariant: in the main tree, `git rev-parse --git-common-dir` returns
    the relative ".git"; in any worktree it returns an absolute path to the
    main tree's .git directory. Graceful-skip: any error → False (assume main
    tree, never refuse a spawn based on a probe failure).
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return False
        return os.path.isabs(r.stdout.strip())
    except Exception:
        return False


# ── precedence cascade ───────────────────────────────────────────────────────

def should_auto_isolate(root: str | os.PathLike, *,
                        arg_no_isolate: bool = False) -> bool:
    """Resolve whether the loop should auto-spawn a worktree for this plan.

    Precedence: command-arg > project.json field > code-default-ON.

    Returns False when:
      - arg_no_isolate is True (command-arg wins)
      - is_inside_worktree(root) is True (single-owner guard — the loop owns
        isolation OR defers to an existing worktree, never both)
      - project.json isolation.mode is 'direct' or 'worktree-per-task'
        (only 'worktree-per-plan' triggers auto-spawn)

    Returns True (default-ON) when:
      - no command-arg override
      - not inside an existing worktree
      - mode == 'worktree-per-plan' (config or code default)
    """
    if arg_no_isolate:
        return False
    if is_inside_worktree(root):
        return False
    config = read_isolation(root)
    return config["mode"] == "worktree-per-plan"


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    """CLI: isolation_config.py check [--no-isolate] [--project-root <path>]

    Exit 0: should auto-spawn a worktree.
    Exit 1: should NOT auto-spawn (arg override, inside worktree, or mode=direct).
    Exit 2: usage error.

    Also: isolation_config.py read [--project-root <path>]
    Prints the isolation block as JSON; always exits 0.
    """
    import argparse
    import json as _json
    p = argparse.ArgumentParser(prog="isolation_config.py")
    sub = p.add_subparsers(dest="cmd")

    chk = sub.add_parser("check")
    chk.add_argument("--no-isolate", action="store_true")
    chk.add_argument("--project-root", default=".")

    rd = sub.add_parser("read")
    rd.add_argument("--project-root", default=".")

    ns = p.parse_args(argv[1:])
    if ns.cmd == "check":
        result = should_auto_isolate(ns.project_root, arg_no_isolate=ns.no_isolate)
        return 0 if result else 1
    if ns.cmd == "read":
        cfg = read_isolation(ns.project_root)
        import sys as _sys
        _sys.stdout.write(_json.dumps(cfg) + "\n")
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
