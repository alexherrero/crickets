#!/usr/bin/env python3
"""Detect queue/archive files stranded on the repo-side `.harness/` tier while
the resolver's active root is somewhere else (R2.5 task 12).

`resolve_plan.resolve()`'s new vault-mismatch guard (task 12's other half)
refuses NEW resolutions that would silently land repo-side while a vault-backed
memory layer is configured and reachable. This module is the complementary
drift *detector*: it catches files that ALREADY landed on the wrong tier —
either from before the guard existed, or from a standalone session whose
`.harness/` later became stale once the project adopted a vault-backed layer.
Four separate sessions hit exactly this drift with no warning before task 12.

Deliberately narrow: it only ever inspects the ONE well-known alternate
location this bug lands on, `<project_root>/.harness/` — never an exhaustive
filesystem scan. When the repo-side `.harness/` genuinely IS the resolved
root (the correct standalone case), there is nothing to flag.

Fixture-only by design (no live-repo battery gate): a real, long-lived crickets
checkout can carry legitimate PRE-vault-cutover archives under its repo-side
`.harness/` that were never meant to move — a wired `check-all.sh` gate
scanning real disk state would false-positive on that history forever. This
stays a pure, hermetic function exercised only against fixtures in
`test_harness_root_drift.py`, auto-discovered by check-all's `unit tests` gate
— the same "battery check" meaning every other fixture in this plan used.
"""
from __future__ import annotations

import os
from pathlib import Path

_QUEUE_GLOB = "queued-plans/*.md"
_ARCHIVE_GLOB = "PLAN.archive.*.md"


def find_harness_root_drift(
    project_root: "str | os.PathLike", resolved_root: "str | os.PathLike"
) -> list[Path]:
    """Queue/archive files under `<project_root>/.harness/` when the resolver's
    current active root (`resolved_root`, the directory a `resolve_plan.resolve()`
    call's PLAN path lives in) is a DIFFERENT directory.

    Returns the empty list when repo-side `.harness/` and `resolved_root` are
    the same directory (the correct standalone case — nothing has drifted), or
    when no matching files sit under repo-side `.harness/` at all. Otherwise
    returns every `queued-plans/*.md` and `PLAN.archive.*.md` file found there,
    sorted, so a caller can name them in a diagnostic rather than just count them.
    """
    repo_side = (Path(project_root).expanduser() / ".harness").resolve()
    resolved = Path(resolved_root).expanduser().resolve()
    if repo_side == resolved:
        return []
    if not repo_side.is_dir():
        return []
    drifted = list(repo_side.glob(_QUEUE_GLOB)) + list(repo_side.glob(_ARCHIVE_GLOB))
    return sorted(drifted)


def main(argv: list[str]) -> int:
    """CLI: harness_root_drift.py <project_root> <resolved_root>

    Exit 0: no drift. Exit 1: drift found, each stranded file printed on stdout.
    A manual/doctor-style check, not wired into check-all.sh by design (see the
    module docstring) — real repos can carry legitimate pre-vault-cutover
    archives this would otherwise false-positive on forever.
    """
    import argparse

    p = argparse.ArgumentParser(prog="harness_root_drift.py")
    p.add_argument("project_root")
    p.add_argument("resolved_root")
    ns = p.parse_args(argv[1:])

    drifted = find_harness_root_drift(ns.project_root, ns.resolved_root)
    if not drifted:
        return 0
    for f in drifted:
        print(f)
    return 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
