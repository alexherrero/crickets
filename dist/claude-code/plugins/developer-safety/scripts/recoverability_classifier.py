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
"""
from __future__ import annotations

import enum
import subprocess
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
