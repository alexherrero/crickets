#!/usr/bin/env python3
"""recoverability_classifier.py — the mechanical subset of the developer-safety
recoverability doctrine (`skills/recoverability/SKILL.md`), R2.2 /
PLAN-r2-enforcement-and-sync task 4.

The doctrine's own scenario table splits into two different kinds of claim:

  - Facts git can answer today: is this ref's tip reachable from any OTHER
    ref after a delete? Does this tag already exist on the remote (has it
    been "published")? Would pushing actually discard any commit the remote
    currently holds (a fast-forward never does)?
  - Judgment calls no git command can answer: has a human already relied on
    this exact branch state ("shared" vs "your own")? Is a database
    migration actually reversible?

This module classifies ONLY the first kind. `Verdict.NEEDS_JUDGMENT` is
returned for anything genuinely outside git's reach — never a guess dressed
up as a confident verdict. The `recoverability` skill's own judgment stays
authoritative for everything this module can't resolve; nothing here
overrides or replaces it — it exists to give the mechanically-checkable
subset of the doctrine an executable answer, which is the piece
`recoverability` skill's own prose form leaves permanently unverifiable.

Stdlib-only; shells out to `git` read-only (never mutates the repo).

CLI (CONS-2 task 8, the Consolidation arc's crickets-slim lane): `main()`
below wires `classify_push` behind an actual command line, so the
`recoverability` skill's push-classification guidance has a real mechanism to
invoke instead of relying on prose judgment alone for the mechanically-
checkable part of the call. `classify_ref_delete` / `classify_tag_overwrite`
stay library-only for now — the skill's push guidance is what this task
names; wiring the other two verdicts behind a CLI is a separate, un-scoped
follow-up if ever warranted, not folded in here.
"""
from __future__ import annotations

import argparse
import enum
import subprocess
import sys
from pathlib import Path


class Verdict(enum.Enum):
    RECOVERABLE = "recoverable"
    UNRECOVERABLE = "unrecoverable"
    NEEDS_JUDGMENT = "needs-judgment"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True,
    )


def classify_ref_delete(repo_root: Path, sha: str, *, exclude_ref: str | None = None) -> Verdict:
    """Deleting a ref currently pointing at `sha`.

    RECOVERABLE if `sha` stays reachable from some OTHER ref (a branch, a
    tag, or a remote-tracking ref) after the delete — it can be restored
    with `git push origin <sha>:refs/heads/<name>` or similar.
    UNRECOVERABLE if `sha` becomes unreachable except via reflog (a
    time-limited, per-clone-only safety net, not a real one) — the
    doctrine's "sole-ref delete of unmerged work" case.

    `exclude_ref` is the ref about to be deleted itself (so its own
    reachability doesn't count as "some other ref").
    """
    result = _git(repo_root, "for-each-ref", "--format=%(refname)", "--contains", sha)
    if result.returncode != 0:
        return Verdict.NEEDS_JUDGMENT
    refs = [r for r in result.stdout.splitlines() if r.strip()]
    if exclude_ref:
        refs = [r for r in refs if r != exclude_ref]
    return Verdict.RECOVERABLE if refs else Verdict.UNRECOVERABLE


def classify_tag_overwrite(repo_root: Path, tag: str, *, remote: str = "origin") -> Verdict:
    """Creating or overwriting `tag`.

    UNRECOVERABLE if `tag` already exists on `remote` — it has been
    "published" and downstream tools may have pinned against it (the
    doctrine's "overwriting an already-published tag" case).
    RECOVERABLE if it's local-only so far — nothing downstream has seen it,
    so moving or replacing it can't silently break a pinned install.
    """
    result = _git(repo_root, "ls-remote", "--tags", remote, f"refs/tags/{tag}")
    if result.returncode != 0:
        return Verdict.NEEDS_JUDGMENT
    return Verdict.UNRECOVERABLE if result.stdout.strip() else Verdict.RECOVERABLE


def classify_push(repo_root: Path, *, local_sha: str, remote_sha: str | None) -> Verdict:
    """Pushing `local_sha` onto a branch whose remote tip is `remote_sha`
    (`None` if the branch doesn't exist on the remote yet — a brand-new
    push, always RECOVERABLE).

    RECOVERABLE if `remote_sha` is an ancestor of `local_sha` (a
    fast-forward — nothing the remote currently holds gets discarded).

    Otherwise this is a history-rewriting force-push. Whether the discarded
    commits are genuinely "shared" (another contributor has already based
    work on them) is the doctrine's real dividing line between "force-push
    to your own un-shared branch" (recoverable) and "rewrites published
    shared history" (unrecoverable) — and that fact is NOT derivable from
    local git state alone (nothing records who else has fetched a branch).
    Returns NEEDS_JUDGMENT rather than guessing; the skill's own judgment
    (does another contributor's work depend on this branch?) decides.
    """
    if remote_sha is None or local_sha == remote_sha:
        return Verdict.RECOVERABLE
    result = _git(repo_root, "merge-base", "--is-ancestor", remote_sha, local_sha)
    if result.returncode == 0:
        return Verdict.RECOVERABLE  # fast-forward: remote_sha is an ancestor of local_sha
    if result.returncode == 1:
        return Verdict.NEEDS_JUDGMENT  # would rewrite history — "shared" is a judgment call
    return Verdict.NEEDS_JUDGMENT  # malformed/unknown SHA or similar git-level error


# ── CLI ──────────────────────────────────────────────────────────────────────
# The functions above are the library surface `test_recoverability_classifier.py`
# exercises directly. Everything below resolves the SHAs `classify_push` needs
# from an actual repo + branch name, so a caller (the `recoverability` skill's
# own guidance, or a human) can ask "is THIS push recoverable?" without first
# hand-computing `local_sha`/`remote_sha` itself.

_EXIT_CODES = {
    Verdict.RECOVERABLE: 0,
    Verdict.UNRECOVERABLE: 1,
    Verdict.NEEDS_JUDGMENT: 2,
}


def _current_branch(repo_root: Path) -> str | None:
    """The current local branch, or None if unresolvable (detached HEAD, not a
    git repo, etc.) — the caller decides how to fail on that."""
    result = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return None if branch in ("", "HEAD") else branch


def _resolve_remote_sha(repo_root: Path, remote: str, branch: str) -> str | None:
    """The SHA `<remote>/<branch>` currently points at, or None if the branch
    doesn't exist there yet (a brand-new push) or the remote is unreachable —
    both fold into `classify_push`'s existing `remote_sha=None` → RECOVERABLE
    case, which is correct: an unreachable remote can't be a push target
    either, so there's nothing on it to discard."""
    result = _git(repo_root, "ls-remote", "--heads", remote, branch)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the `recoverability` skill's push classification.

    Usage: `recoverability_classifier.py push [--repo PATH] [--branch NAME]
    [--remote NAME] [--remote-branch NAME]`. Prints the verdict
    (`recoverable` / `unrecoverable` / `needs-judgment`) to stdout and exits
    0 / 1 / 2 to match; exits 3 on a usage/git error the caller must fall back
    to the doctrine's own conservative default for (treat as unrecoverable —
    SKILL.md's own words), never silently skip the check.
    """
    parser = argparse.ArgumentParser(
        prog="recoverability_classifier.py",
        description="Classify a git push as recoverable / unrecoverable / "
                     "needs-judgment — the mechanical subset of the "
                     "recoverability doctrine (see ../skills/recoverability/SKILL.md).",
    )
    parser.add_argument("command", choices=["push"],
                         help="what to classify — only 'push' is wired to a CLI today")
    parser.add_argument("--repo", default=Path("."), type=Path,
                         help="repo root (default: current directory)")
    parser.add_argument("--branch", default=None,
                         help="local branch being pushed (default: current branch)")
    parser.add_argument("--remote", default="origin",
                         help="remote name (default: origin)")
    parser.add_argument("--remote-branch", default=None,
                         help="remote branch name, if different from --branch")
    args = parser.parse_args(argv)

    branch = args.branch or _current_branch(args.repo)
    if branch is None:
        print("recoverability_classifier: cannot resolve the local branch "
              "(detached HEAD?) — pass --branch explicitly", file=sys.stderr)
        return 3
    local_result = _git(args.repo, "rev-parse", branch)
    if local_result.returncode != 0:
        print(f"recoverability_classifier: cannot resolve local branch "
              f"{branch!r}: {local_result.stderr.strip()}", file=sys.stderr)
        return 3
    local_sha = local_result.stdout.strip()
    remote_branch = args.remote_branch or branch
    remote_sha = _resolve_remote_sha(args.repo, args.remote, remote_branch)

    verdict = classify_push(args.repo, local_sha=local_sha, remote_sha=remote_sha)
    print(verdict.value)
    return _EXIT_CODES[verdict]


if __name__ == "__main__":
    sys.exit(main())
