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
import subprocess
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
_PII_SCANNER_NAME = "check-no-pii.sh"


def _find_pii_scanner(repo_root: str) -> "Path | None":
    """Locate crickets' check-no-pii.sh via the same discovery cascade
    `templates/hooks/pre-push` uses, or None. Candidates, first hit wins:
      1. $AGENT_TOOLKIT_PATH/scripts/check-no-pii.sh  (explicit override)
      2. ~/Antigravity/crickets/scripts/check-no-pii.sh  (conventional clone)
      3. <repo_root>/../crickets/scripts/check-no-pii.sh  (sibling-of-repo)
    """
    candidates: list[Path] = []
    toolkit = os.environ.get("AGENT_TOOLKIT_PATH", "").strip()
    if toolkit:
        candidates.append(Path(os.path.expanduser(toolkit)) / "scripts" / _PII_SCANNER_NAME)
    candidates.append(Path.home() / "Antigravity" / "crickets" / "scripts" / _PII_SCANNER_NAME)
    candidates.append(Path(repo_root) / ".." / "crickets" / "scripts" / _PII_SCANNER_NAME)
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return None


def _bash_works() -> bool:
    """True iff `bash` on PATH actually executes. On Windows, System32's WSL
    stub shadows Git Bash in subprocess PATH resolution and exits nonzero with
    no distro installed — a scanner we cannot run is a scanner we don't have."""
    try:
        r = subprocess.run(["bash", "-c", "exit 0"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _diff_base(repo_root: str) -> str | None:
    """The merge-base with the default branch, for scoping the PII scan to
    what's actually about to be pushed. Tries `origin/main` first (the base
    a host-created worktree actually forked from), falling back to local
    `main`. None on any failure — the caller falls back to `--all`."""
    for ref in ("origin/main", "main"):
        r = subprocess.run(["git", "merge-base", "HEAD", ref], cwd=repo_root,
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def _pii_guard(repo_root: str) -> bool:
    """True iff the PII scan passes. Fail-open when the real scanner
    (check-no-pii.sh) can't be found OR can't be executed (no functional
    bash) — the pre-push git hook is the mandatory enforcer; this is a
    defense-in-depth pre-check, not the sole gate.

    Scoped to `--diff <merge-base>..HEAD`, matching the real enforcer (the
    pre-push hook) — NOT `--all`. `--all` scans the entire working tree,
    including pre-existing content this finalize call never touched; a repo
    that already has one `--all`-mode false positive anywhere (a checksum
    file whose hex digits happen to contain a phone-number-shaped substring,
    for instance) would permanently block every finalize call, forever, on
    content nobody is actually about to push. Falls back to `--all` only if
    the merge-base can't be resolved at all (never silently skips the guard).
    """
    scanner = _find_pii_scanner(repo_root)
    if scanner is None:
        return True
    if not _bash_works():
        return True
    base = _diff_base(repo_root)
    args = ["bash", str(scanner), "--diff", f"{base}..HEAD"] if base else \
           ["bash", str(scanner), "--all"]
    try:
        r = subprocess.run(args, cwd=repo_root, capture_output=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


def finalize_unit(
    slug: str, repo_root: str, *,
    branch: str | None = None,
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
      4. default → push `branch` + open PR (armed for auto-merge)

    PII guard runs BEFORE any push (inherited from pr_helpers contract).

    `branch` is the actual branch name the worktree landed on — since the host's
    own worktree primitive (`EnterWorktree` / New-Worktree-Mode) owns naming now,
    this is no longer derivable from `slug` alone (it used to be the fixed
    `worker/<slug>` `spawn_worker.py` always produced). Callers that know the real
    branch (the `/work` / `/bugfix` auto-spawn flow) MUST pass it. The
    `worker/<slug>` fallback below only serves callers with no worktree at all
    (direct mode) or legacy call sites that haven't been updated — the branch name
    is irrelevant on the direct-push path since `finalize_direct` never reads it.
    """
    config = read_isolation(repo_root)
    # Direct when: explicit --no-pr flag, integration=direct-push, OR mode=direct
    # (mode=direct means no worktree was spawned, so finalize_unit is a no-op PR
    # boundary — but be defensive: fall back to direct push rather than opening a PR
    # on behalf of a non-isolated run).
    use_direct = no_pr or config["integration"] == "direct-push" or config["mode"] == "direct"

    branch = branch or f"{_BRANCH_PREFIX}{slug}"
    pr_title = title or f"{branch}: plan complete"
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
    p.add_argument("--branch", default=None,
                   help="the actual worktree branch name (from EnterWorktree); "
                        "falls back to the legacy worker/<slug> guess if omitted")
    p.add_argument("--project-root", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--body", default=None)
    p.add_argument("--no-pr", action="store_true",
                   help="skip PR, push directly (command-arg override)")
    ns = p.parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()

    result = finalize_unit(ns.slug, root, branch=ns.branch, title=ns.title,
                           body=ns.body, no_pr=ns.no_pr)

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
