#!/usr/bin/env python3
"""Periodic shepherd: reclaims safe orphaned worktrees, rebases stalled armed PRs.

Runs on the `agentm-runner` scheduler (a `.harness/jobs/<name>.yaml` manifest —
see agentm's `wiki/designs/agentm-runner.md`), not a bespoke cron
(worktree-native-flow task 5, Locked design calls). Two independent duties:

(a) **Orphan reclaim.** `doctor_worktrees.py`'s `ORPHANED` worktrees/branches
    (a branch with no worktree, or a worktree whose directory is gone) are
    reclaimed only when BOTH: old enough (age threshold — the originating
    session is presumed gone) AND provably safe (`is_safe_to_reclaim`: every
    commit on the branch is already on its remote copy, or the branch never
    diverged at all — nothing would be lost). Anything not provably safe is
    left alone and reported, never guessed at.

(b) **Stalled-PR rebase.** An armed PR that GitHub reports `BEHIND` its base
    branch (a sibling plan's PR merged first) gets `gh pr update-branch`; a
    resulting merge conflict is surfaced loudly in the report, never silently
    left stuck (Locked design calls, Fable rider 2).

    worktree_shepherd.py [--project-root <path>] [--age-days N] [--dry-run]

Stdlib-only except for `gh` (invoked via an injectable Runner, mirroring
pr_helpers.py's pattern — no real network calls from this module or its tests).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import doctor_worktrees as dw  # noqa: E402

_DEFAULT_AGE_THRESHOLD_SECONDS = 3 * 24 * 3600  # "a few days" per the plan


# ── shared runner shape (mirrors pr_helpers.Runner) ──────────────────────────

Runner = Callable[[list, str], tuple[int, str]]


def _default_runner(cmd: list, cwd: str) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return (2, str(exc))


def _git(args: list[str], root: str | os.PathLike) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, timeout=30,
    )


# ── (a) orphan reclaim ────────────────────────────────────────────────────────

def is_safe_to_reclaim(root: str | os.PathLike, branch: str) -> bool:
    """True iff removing `branch` loses nothing.

    Safe when every commit reachable from `branch` is already reachable from
    its remote copy (`origin/<branch>`) — `git rev-list branch ^origin/branch`
    is empty. If no remote copy exists at all (never pushed), safe only if the
    branch never diverged from where it forked (no unique commits to lose
    either way) — checked via `git rev-list branch ^main` against the local
    default integration ref. Any git error collapses to False (never guess
    "safe" on an unreadable repo).
    """
    has_remote = _git(["rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
                      root).returncode == 0
    if has_remote:
        r = _git(["rev-list", branch, f"^origin/{branch}"], root)
        if r.returncode != 0:
            return False
        return r.stdout.strip() == ""

    # No remote copy — safe only if the branch has no commits beyond the
    # current default branch (HEAD), i.e. it never diverged.
    r = _git(["rev-list", branch, "^HEAD"], root)
    if r.returncode != 0:
        return False
    return r.stdout.strip() == ""


@dataclass
class ReclaimReport:
    reclaimed: list = field(default_factory=list)       # list[WorkerWorktree]
    skipped_unsafe: list = field(default_factory=list)   # list[WorkerWorktree]
    skipped_too_young: list = field(default_factory=list)  # list[WorkerWorktree]


def _branch_age_seconds(root: str | os.PathLike, branch: str) -> float | None:
    """Seconds since `branch`'s tip commit, or None on any error (never guess an age)."""
    import time
    r = _git(["log", "-1", "--format=%ct", branch], root)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        committed_at = float(r.stdout.strip())
    except ValueError:
        return None
    return time.time() - committed_at


def reclaim_orphans(root: str | os.PathLike, *,
                    age_threshold_seconds: int = _DEFAULT_AGE_THRESHOLD_SECONDS,
                    dry_run: bool = False) -> ReclaimReport:
    """Reclaim every ORPHANED worktree/branch that is old enough AND safe.

    Pure orchestration over `doctor_worktrees.diagnose` (never re-derives
    classification). `dry_run=True` reports exactly what would be reclaimed
    without mutating anything — the report shape is identical either way.
    """
    report = ReclaimReport()
    for w in dw.diagnose(root):
        if w.status != dw.ORPHANED:
            continue
        age = _branch_age_seconds(root, w.branch)
        if age is None or age < age_threshold_seconds:
            report.skipped_too_young.append(w)
            continue
        if not is_safe_to_reclaim(root, w.branch):
            report.skipped_unsafe.append(w)
            continue
        report.reclaimed.append(w)
        if dry_run:
            continue
        if w.worktree:
            _git(["worktree", "remove", "--force", w.worktree], root)
        _git(["branch", "-D", w.branch], root)
    return report


# ── (b) stalled-PR rebase ─────────────────────────────────────────────────────

@dataclass
class UpdatedPR:
    pr_number: int
    branch: str
    url: str | None = None


@dataclass
class ConflictedPR:
    pr_number: int
    branch: str
    detail: str
    url: str | None = None


@dataclass
class StalledPRReport:
    updated: list = field(default_factory=list)      # list[UpdatedPR]
    conflicts: list = field(default_factory=list)     # list[ConflictedPR]


def shepherd_stalled_prs(repo_root: str, *, runner: Optional[Runner] = None) -> StalledPRReport:
    """Rebase every open PR GitHub reports as `BEHIND` its base branch.

    `gh pr list --json number,headRefName,mergeStateStatus,url` is the single
    source of truth for staleness — never inferred from local git state, since
    only GitHub knows the PR's actual base-branch relationship. A conflict from
    `gh pr update-branch` is recorded (not raised) so the caller can surface it
    loudly in its own report rather than the shepherd silently swallowing it.
    """
    run = runner or _default_runner
    report = StalledPRReport()

    rc, out = run(["gh", "pr", "list", "--json",
                  "number,headRefName,mergeStateStatus,url"], repo_root)
    if rc != 0:
        return report
    try:
        prs = json.loads(out)
    except (json.JSONDecodeError, TypeError):
        return report
    if not isinstance(prs, list):
        return report

    for pr in prs:
        if not isinstance(pr, dict) or pr.get("mergeStateStatus") != "BEHIND":
            continue
        number = pr.get("number")
        branch = pr.get("headRefName", "")
        url = pr.get("url")
        rc, out = run(["gh", "pr", "update-branch", str(number)], repo_root)
        if rc == 0:
            report.updated.append(UpdatedPR(pr_number=number, branch=branch, url=url))
        else:
            report.conflicts.append(ConflictedPR(pr_number=number, branch=branch,
                                                  detail=out, url=url))
    return report


# ── CLI ────────────────────────────────────────────────────────────────────

def _format(reclaim: ReclaimReport, stalled: StalledPRReport, *, dry_run: bool) -> str:
    lines = ["[worktree_shepherd] orphan reclaim" + (" (dry-run)" if dry_run else "") + ":"]
    if not (reclaim.reclaimed or reclaim.skipped_unsafe or reclaim.skipped_too_young):
        lines.append("  nothing orphaned.")
    for w in reclaim.reclaimed:
        verb = "would reclaim" if dry_run else "reclaimed"
        lines.append(f"  {verb}: {w.branch} ({w.worktree or '(no worktree)'})")
    for w in reclaim.skipped_unsafe:
        lines.append(f"  left alone (unsafe — unpushed commits): {w.branch}")
    for w in reclaim.skipped_too_young:
        lines.append(f"  left alone (too young): {w.branch}")

    lines.append("[worktree_shepherd] stalled-PR rebase:")
    if not (stalled.updated or stalled.conflicts):
        lines.append("  nothing stalled.")
    for u in stalled.updated:
        lines.append(f"  updated PR #{u.pr_number} ({u.branch}) — {u.url or ''}".rstrip())
    for c in stalled.conflicts:
        lines.append(f"  CONFLICT on PR #{c.pr_number} ({c.branch}): {c.detail} — {c.url or ''}".rstrip())
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="worktree_shepherd.py",
        description="Reclaim safe orphaned worktrees; rebase stalled armed PRs.",
    )
    p.add_argument("--project-root", default=None)
    p.add_argument("--age-days", type=float, default=3.0,
                   help="minimum age (days) before an orphan is reclaim-eligible")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    age_seconds = int(ns.age_days * 24 * 3600)

    reclaim = reclaim_orphans(root, age_threshold_seconds=age_seconds, dry_run=ns.dry_run)
    stalled = shepherd_stalled_prs(root)

    sys.stdout.write(_format(reclaim, stalled, dry_run=ns.dry_run))
    return 0  # a shepherd report, never a gate — conflicts are surfaced, not fatal


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
