#!/usr/bin/env python3
"""Check that all git tags point to commits reachable from main.

Exits 0 when all tags are main-reachable (or no tags exist, or main doesn't exist).
Exits 1 when any tag points to a commit not reachable from main.

This is the code-side backstop for the concurrent-release coordination guarantee:
tagging a worker/plan-branch tip is the force-push-on-shared-tag trap — two concurrent
plans racing to tag the same ref name would create/overwrite a tag pointing at a branch
tip, not a main commit. This check makes that violation visible even if branch
protection is misconfigured.

The /release command is the single tag writer (it tags main HEAD after CI-green);
this gate confirms that invariant holds after the fact.

Run standalone:
    python3 scripts/check_tag_reachability.py
Or via check-all.sh (the "tag-reachability" gate).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(args: list[str], *, cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd)


def _main_ref(*, cwd: str | Path | None = None) -> str | None:
    """Return the first resolvable main ref name, or None (graceful-skip)."""
    for ref in ("main", "origin/main"):
        if _run(["git", "rev-parse", "--verify", ref], cwd=cwd).returncode == 0:
            return ref
    return None


def list_tags(*, cwd: str | Path | None = None) -> list[str]:
    """Return the list of tag names in the repo."""
    r = _run(["git", "tag", "--list"], cwd=cwd)
    return [t for t in r.stdout.splitlines() if t.strip()] if r.returncode == 0 else []


def resolve_tag_commit(tag: str, *, cwd: str | Path | None = None) -> str | None:
    """Return the commit SHA a tag points to (dereferencing annotated tags)."""
    r = _run(["git", "rev-list", "-n1", tag], cwd=cwd)
    sha = r.stdout.strip()
    return sha if r.returncode == 0 and sha else None


def is_reachable_from_main(sha: str, main_ref: str, *, cwd: str | Path | None = None) -> bool:
    """Return True if sha is an ancestor of main_ref (reachable from main HEAD)."""
    return _run(["git", "merge-base", "--is-ancestor", sha, main_ref], cwd=cwd).returncode == 0


def check_tag_reachability(*, cwd: str | Path | None = None) -> list[tuple[str, str]]:
    """Return (tag, sha) pairs for tags NOT reachable from main.

    Returns [] when all tags pass, no tags exist, or neither 'main' nor 'origin/main'
    resolves (graceful-skip for fresh repos, CI shallow clones, or non-main default
    branch names).
    """
    main_ref = _main_ref(cwd=cwd)
    if main_ref is None:
        return []
    tags = list_tags(cwd=cwd)
    if not tags:
        return []
    off_main = []
    for tag in tags:
        sha = resolve_tag_commit(tag, cwd=cwd)
        if sha is None:
            continue
        if not is_reachable_from_main(sha, main_ref, cwd=cwd):
            off_main.append((tag, sha))
    return off_main


def main() -> int:
    off_main = check_tag_reachability()
    if off_main:
        print("tag-reachability: FAIL")
        print()
        print("The following tags point to commits NOT reachable from main:")
        for tag, sha in off_main:
            print(f"  {tag} -> {sha[:12]}")
        print()
        print("Tags must only be created from commits reachable from main.")
        print("Tagging a worker/plan-branch tip is the force-push-on-shared-tag trap.")
        return 1
    print("tag-reachability: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
