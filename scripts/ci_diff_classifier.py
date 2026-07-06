#!/usr/bin/env python3
"""Classify a PR's changed-file list as docs-only or code-touching — the
job-level, diff-aware diet inside `ci-all`'s `aggregate` job (PLAN-per-plan-ci
task 1). Conservative rule, unchanged from the retired trigger-level diet
(crickets-conventions.md's `ci` amendment): every changed file must match
`wiki/**` or `*.md`, or the diff counts as code and the full matrix runs.

Job-level, not trigger-level, on purpose (Fable rider 3, Locked design
calls): a required `pull_request` check can't carry a trigger-level
`paths-ignore` without risking a docs-only PR's check never reporting at
all, which blocks that PR's merge forever. This script only decides whether
the aggregate job's own wait-and-verify step runs; the check itself always
fires.

    ci_diff_classifier.py <file1> [<file2> ...]
    # exit 0: docs-only (the aggregate job's wait step may skip)
    # exit 1: code-touching (the aggregate job must wait for the full matrix)
    # exit 2: usage error (no files given at all — never silently "docs-only")

Stdlib-only.
"""
from __future__ import annotations

import sys

_DOCS_DIR_PREFIXES = ("wiki/",)
_DOCS_SUFFIXES = (".md",)


def is_docs_only(files: list[str]) -> bool:
    """True iff every file matches `wiki/**` or `*.md`. Empty input is never
    docs-only — an empty diff isn't a meaningful "skip the matrix" signal,
    and treating it as skippable would be the one case where "conservative"
    actually means the opposite (fail open on a caller bug that lost the
    file list)."""
    if not files:
        return False
    return all(
        f.startswith(_DOCS_DIR_PREFIXES) or f.endswith(_DOCS_SUFFIXES)
        for f in files
    )


def main(argv: list[str]) -> int:
    files = argv[1:]
    if not files:
        sys.stderr.write("ci_diff_classifier.py: at least one file argument is required\n")
        return 2
    return 0 if is_docs_only(files) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
