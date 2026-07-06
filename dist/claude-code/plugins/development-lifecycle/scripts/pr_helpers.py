#!/usr/bin/env python3
"""PR/direct-commit helpers for the developer-workflows loop.

Duplicated from wiki-maintenance/scripts/wiki_watch_dispatch.py (the three
git/gh executor functions + supporting types). Probe #3 (worktree-per-plan
plan task 3) determined that cross-plugin import is structurally unavailable
at runtime (plugin version dirs diverge: developer-workflows 0.17.x vs
wiki-maintenance 0.2.x). This is therefore a deliberate duplicate, pinned
byte-identical on the contract surface by test_pr_helpers_drift.py.

THE CONTRACT (must not drift from wiki_watch_dispatch.py):
  - PII guard runs BEFORE any push — this is the ordering invariant
  - finalize_pr:  add → commit → pii-guard → push → pr-create → pr-merge-auto
    (steps order; the auto-merge arm is development-lifecycle-only — it does
    NOT flip .ok on failure, since a PR that opened but failed to arm still
    did its own job. wiki_watch_dispatch.py's copy has no such step; the drift
    test only pins the PII-before-push ordering, not step-for-step parity, so
    this divergence is within contract.)
  - finalize_direct: add → commit → pii-guard → push             (steps order)
  - DispatchResult carries .steps for audit/test inspection

If wiki_watch_dispatch.py's functions change in a way that breaks this
ordering, test_pr_helpers_drift.py will fail — the drift test is the
enforcement point.

Stdlib-only; matches the established skill/script convention.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional

Runner = Callable[[list, str], tuple[int, str]]


def _default_runner(cmd: list, cwd: str) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return (2, str(exc))


@dataclass
class DispatchResult:
    ok: bool
    action: str
    reason: str = ""
    branch: Optional[str] = None
    pr_url: Optional[str] = None
    commit: Optional[str] = None
    steps: list = field(default_factory=list)


def check_gh_available(runner: Optional[Runner] = None, cwd: str = ".") -> bool:
    """True iff the `gh` CLI is on PATH AND authenticated."""
    if shutil.which("gh") is None:
        return False
    run = runner or _default_runner
    rc, _ = run(["gh", "auth", "status"], cwd)
    return rc == 0


def prepare_branch(repo_root: str, branch: str, *, runner: Optional[Runner] = None) -> DispatchResult:
    """Create + switch to the PR feature branch (before authoring).
    Graceful-skip: any git failure returns ok=False, never raises."""
    run = runner or _default_runner
    rc, out = run(["git", "checkout", "-B", branch], repo_root)
    steps = [("checkout", rc)]
    if rc != 0:
        return DispatchResult(ok=False, action="pr", reason=f"branch create failed: {out}",
                              branch=branch, steps=steps)
    return DispatchResult(ok=True, action="pr", branch=branch, steps=steps)


def finalize_pr(
    repo_root: str, branch: str, *, title: str, body: str,
    pii_guard: Callable[[str], bool], runner: Optional[Runner] = None,
) -> DispatchResult:
    """After authoring on `branch`: commit -> PII GUARD -> push -> open PR.

    The PII guard runs BEFORE any push (the order is the contract); a failed
    guard aborts before the push. Every step graceful-skips (no raise).

    "Nothing to commit" is NOT a failure here — under the one-task-one-commit
    discipline (`/work` step 9), every task's own work is already committed by
    the time the plan's final task reaches this finalize step, so there is
    routinely nothing left to add. Only a genuine commit failure (a non-zero
    rc whose output isn't git's own "nothing to commit" message — a failing
    pre-commit hook, for instance) is fatal.
    """
    run = runner or _default_runner
    steps: list = []

    rc, out = run(["git", "add", "-A"], repo_root); steps.append(("add", rc))
    rc, out = run(["git", "commit", "-m", title], repo_root); steps.append(("commit", rc))
    if rc != 0 and "nothing to commit" not in out:
        return DispatchResult(ok=False, action="pr", reason=f"commit failed: {out}",
                              branch=branch, steps=steps)
    commit = _head_sha(run, repo_root)

    # PII guard MUST precede the push — the pre-push hook is the enforcer;
    # this is the in-engine pre-check so we never push flagged content.
    pii_ok = pii_guard(repo_root)
    steps.append(("pii-guard", 0 if pii_ok else 1))
    if not pii_ok:
        return DispatchResult(ok=False, action="pr", reason="PII guard blocked the push",
                              branch=branch, commit=commit, steps=steps)

    rc, out = run(["git", "push", "-u", "origin", branch], repo_root); steps.append(("push", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="pr", reason=f"push failed: {out}",
                              branch=branch, commit=commit, steps=steps)

    rc, out = run(["gh", "pr", "create", "--title", title, "--body", body,
                   "--head", branch], repo_root)
    steps.append(("pr-create", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="pr", reason=f"gh pr create failed: {out}",
                              branch=branch, commit=commit, steps=steps)
    pr_url = out.strip() or None

    # Arm auto-merge immediately after opening — "Allow auto-merge" (a one-time
    # repo setting) makes this available but does not merge anything on its own;
    # this is the actual arm. Non-fatal: a PR that opened but failed to arm still
    # succeeded at its own job (the operator can arm it manually), so this does
    # NOT flip `ok` to False — it's recorded in `steps` for the caller to surface.
    merge_rc, merge_out = run(["gh", "pr", "merge", "--auto", "--squash", branch], repo_root)
    steps.append(("pr-merge-auto", merge_rc))
    reason = "" if merge_rc == 0 else f"opened but auto-merge arm failed: {merge_out}"

    return DispatchResult(ok=True, action="pr", reason=reason, branch=branch,
                          commit=commit, pr_url=pr_url, steps=steps)


def finalize_direct(
    repo_root: str, *, message: str, pii_guard: Callable[[str], bool],
    runner: Optional[Runner] = None,
) -> DispatchResult:
    """Direct-commit opt-in: commit on current branch -> PII GUARD -> push.

    Same PII-before-push ordering as finalize_pr; graceful-skip on any failure.
    "Nothing to commit" is not a failure — see finalize_pr's docstring.
    """
    run = runner or _default_runner
    steps: list = []
    rc, out = run(["git", "add", "-A"], repo_root); steps.append(("add", rc))
    rc, out = run(["git", "commit", "-m", message], repo_root); steps.append(("commit", rc))
    if rc != 0 and "nothing to commit" not in out:
        return DispatchResult(ok=False, action="direct", reason=f"commit failed: {out}",
                              steps=steps)
    commit = _head_sha(run, repo_root)
    pii_ok = pii_guard(repo_root)
    steps.append(("pii-guard", 0 if pii_ok else 1))
    if not pii_ok:
        return DispatchResult(ok=False, action="direct", reason="PII guard blocked the push",
                              commit=commit, steps=steps)
    rc, out = run(["git", "push"], repo_root); steps.append(("push", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="direct", reason=f"push failed: {out}",
                              commit=commit, steps=steps)
    return DispatchResult(ok=True, action="direct", commit=commit, steps=steps)


def _head_sha(run: Runner, repo_root: str) -> Optional[str]:
    rc, out = run(["git", "rev-parse", "HEAD"], repo_root)
    return out.strip() if rc == 0 and out.strip() else None
