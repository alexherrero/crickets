#!/usr/bin/env python3
"""Finalize a completed plan unit: push the worker branch and open a PR (or
fall back to direct push when `gh` is unavailable / integration is direct-push).

Called at the end of a `/work` or `/bugfix` session when all tasks are done.

    finalize_unit.py <slug> [--project-root <path>] [--title <text>] [--body <text>] [--no-pr]

Exit 0: finalization succeeded (PR opened, or direct push committed).
Exit 1: partial success — push landed but PR creation failed; or direct-push
        fallback announced (gh unavailable). Branch is on the remote.
Exit 2: hard failure — nothing pushed (push rejected, PII blocked, commit failed).

The gh-unavailable fallback is the contract: a completed unit of work MUST
reach the remote (push) even when gh is not available; only the PR-open step
is skipped, not the push. This is distinct from the wiki-watcher's skip-on-no-gh
behavior (wiki-watch PR is a mandatory human-merge gate; loop PR is not).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pr_helpers import (  # noqa: E402
    DispatchResult, Runner, check_gh_available,
    finalize_pr, finalize_direct,
)
from isolation_config import read_isolation  # noqa: E402

_BRANCH_PREFIX = "worker/"


def _pii_guard(repo_root: str) -> bool:
    """True iff the pre-push PII check passes. Runs pii-scrubber if available;
    falls back to True (the pre-push hook is the mandatory enforcer)."""
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "pii_scrubber", "--check"],
            cwd=repo_root, capture_output=True, timeout=30,
        )
        return r.returncode == 0
    except Exception:
        return True


def finalize_unit(
    slug: str, repo_root: str, *,
    title: str | None = None,
    body: str | None = None,
    no_pr: bool = False,
    runner: Runner | None = None,
    pii_guard_fn=_pii_guard,
) -> DispatchResult:
    """Finalize a completed plan unit.

    Precedence:
      1. no_pr=True (command-arg) → direct push, no PR
      2. isolation.integration == 'direct-push' (config) → direct push, no PR
      3. gh unavailable → fall back to direct push + announce the downgrade
      4. default → push worker/<slug> branch + open PR

    PII guard runs BEFORE any push (inherited from pr_helpers contract).
    """
    config = read_isolation(repo_root)
    # Direct when: explicit --no-pr flag, integration=direct-push, OR mode=direct
    # (mode=direct means no worktree was spawned, so finalize_unit is a no-op PR
    # boundary — but be defensive: fall back to direct push rather than opening a PR
    # on behalf of a non-isolated run).
    use_direct = no_pr or config["integration"] == "direct-push" or config["mode"] == "direct"

    branch = f"{_BRANCH_PREFIX}{slug}"
    pr_title = title or f"worker/{slug}: plan complete"
    pr_body = body or f"Automated PR for completed plan unit `{slug}`."

    if use_direct:
        return finalize_direct(repo_root, message=pr_title,
                               pii_guard=pii_guard_fn, runner=runner)

    if not check_gh_available(runner=runner, cwd=repo_root):
        result = finalize_direct(repo_root, message=pr_title,
                                 pii_guard=pii_guard_fn, runner=runner)
        if result.ok:
            result.reason = "gh unavailable — fell back to direct push (downgrade announced)"
        return result

    return finalize_pr(repo_root, branch,
                       title=pr_title, body=pr_body,
                       pii_guard=pii_guard_fn, runner=runner)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="finalize_unit.py",
        description="Finalize a completed plan unit (push + PR or fallback to direct push).",
    )
    p.add_argument("slug", help="plan slug (bare, e.g. 'my-plan')")
    p.add_argument("--project-root", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--body", default=None)
    p.add_argument("--no-pr", action="store_true",
                   help="skip PR, push directly (command-arg override)")
    ns = p.parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()

    result = finalize_unit(ns.slug, root, title=ns.title, body=ns.body, no_pr=ns.no_pr)

    if result.pr_url:
        sys.stdout.write(f"PR opened: {result.pr_url}\n")
    if result.commit:
        sys.stdout.write(f"commit: {result.commit}\n")
    if result.reason:
        level = "INFO" if result.ok else "ERROR"
        sys.stderr.write(f"[finalize_unit] {level}: {result.reason}\n")

    if result.ok:
        return 0
    # Use steps to distinguish "push landed" (exit 1, partial success — branch on
    # remote but PR failed or fallback announced) from "nothing pushed" (exit 2).
    push_landed = any(name == "push" and rc == 0 for name, rc in result.steps)
    return 1 if push_landed else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
