#!/usr/bin/env python3
"""Amend-and-ship orchestration for kernel-defect corrections.

Runs the full developer-workflows plugin release cycle for a kernel-defect correction:

  1. gate-suite    — run check-all.sh (10 gates); correctness gate, never bypassed
  2. bump-version  — increment group.yaml semver (minor for behavior changes)
  3. update-changelog — prepend CHANGELOG entry with the correction's context
  4. regen-dist    — python3 scripts/generate.py; dist/ must match src/
  5. commit        — one logical commit (patch + release housekeeping)
  6. push          — push worker branch
  7. ci-check      — wake-on-CI: poll until the OS matrix is green; PARKS HERE
  8. tag            — git tag + push (points to main-reachable commit after /integrate-worker)
  9. gh-release    — gh release create

Governed by the autonomy doctrine: recoverable steps proceed announced; only genuinely
unrecoverable steps (published-tag overwrite, force-push shared history) stop for confirm.
wake-on-CI (step 7) is a correctness gate, not a human wait — it stays.

DEFER-BUMP-ONLY mode (--defer-bump):
  On a worker/ branch the serialized integrator owns version bump + tag + gh release.
  Pass --defer-bump to run only steps 1 (gate-suite) and skip 2, 8, 9; remaining steps
  still run so the patch is committed and pushed on the worker branch.

Usage:
    python3 scripts/correction_ship.py --help
    python3 scripts/correction_ship.py --dry-run          # dry-run: record steps, call nothing
    python3 scripts/correction_ship.py --defer-bump       # worker-branch mode
    python3 scripts/correction_ship.py                    # full ship (requires authed gh + CI)
"""
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ShipStep:
    name: str
    fn: Callable[[], None]


@dataclass
class ShipResult:
    steps_taken: List[str] = field(default_factory=list)
    steps_skipped: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class ShipOrchestrator:
    """Sequence-ordered orchestration for the kernel-defect amend & ship path.

    The step order encodes the CI-before-tag invariant:
        gate-suite → ... → ci-check → tag → gh-release

    Tests verify this invariant via the `result.steps_taken` list (dry_run=True),
    which records every step name without executing any external calls.
    """

    def __init__(self, *, dry_run: bool = False, defer_bump: bool = False) -> None:
        self.dry_run = dry_run
        self.defer_bump = defer_bump
        self._result = ShipResult()

    # ------------------------------------------------------------------
    # Step implementations (called only when dry_run=False)
    # ------------------------------------------------------------------

    def _run_gate_suite(self) -> None:
        r = subprocess.run(
            ["bash", "scripts/check-all.sh"],
            cwd=str(_ROOT),
            capture_output=False,
        )
        if r.returncode != 0:
            raise RuntimeError("gate-suite failed — fix gates before shipping")

    def _bump_version(self) -> None:
        raise NotImplementedError(
            "Version bump requires reading group.yaml and incrementing semver — "
            "implement with a semver library or manual group.yaml parse."
        )

    def _update_changelog(self) -> None:
        raise NotImplementedError(
            "CHANGELOG update requires a correction entry and a semver string — "
            "implement by prepending to CHANGELOG.md with Keep-a-Changelog format."
        )

    def _regen_dist(self) -> None:
        r = subprocess.run(
            ["python3", "scripts/generate.py"],
            cwd=str(_ROOT),
            capture_output=False,
        )
        if r.returncode != 0:
            raise RuntimeError("generate.py failed — dist/ not in sync")

    def _commit(self) -> None:
        raise NotImplementedError(
            "Commit step requires the correction slug and semver for the message — "
            "implement by staging and committing the patched src/ + dist/."
        )

    def _push(self) -> None:
        r = subprocess.run(
            ["git", "push"],
            cwd=str(_ROOT),
            capture_output=False,
        )
        if r.returncode != 0:
            raise RuntimeError("git push failed")

    def _ci_check(self) -> None:
        # Wake-on-CI: parks here until the OS matrix is green.
        # Implementation polls `gh run list --branch <current-branch>` and waits for
        # all checks to complete with success.  This is the correctness gate — it stays.
        raise NotImplementedError(
            "CI check requires gh CLI and branch name — "
            "implement by polling `gh run list` until all checks are green."
        )

    def _tag(self) -> None:
        raise NotImplementedError(
            "Tag step runs AFTER ci-check confirms green — "
            "implement as `git tag -a <version> -m <msg> && git push origin <tag>`."
        )

    def _gh_release(self) -> None:
        raise NotImplementedError(
            "gh release create — implement with the tag name + CHANGELOG excerpt."
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def _step(self, name: str, fn: Callable[[], None], skip: bool = False) -> None:
        if skip:
            self._result.steps_skipped.append(name)
            return
        self._result.steps_taken.append(name)
        if not self.dry_run:
            fn()

    def run(self) -> ShipResult:
        """Execute the ship sequence in order.

        Step order encodes the invariant: gate-suite BEFORE ci-check BEFORE tag.
        """
        try:
            self._step("gate-suite", self._run_gate_suite)
            self._step("bump-version", self._bump_version, skip=self.defer_bump)
            self._step("update-changelog", self._update_changelog, skip=self.defer_bump)
            self._step("regen-dist", self._regen_dist)
            self._step("commit", self._commit)
            self._step("push", self._push)
            self._step("ci-check", self._ci_check)  # PARKS HERE — never bypassed
            self._step("tag", self._tag, skip=self.defer_bump)
            self._step("gh-release", self._gh_release, skip=self.defer_bump)
        except Exception as exc:
            self._result.success = False
            self._result.error = str(exc)
        return self._result


def main(argv: list = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    dry_run = "--dry-run" in argv
    defer_bump = "--defer-bump" in argv

    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    orchestrator = ShipOrchestrator(dry_run=dry_run, defer_bump=defer_bump)
    result = orchestrator.run()

    if dry_run:
        print("dry-run: steps would run in order:", " → ".join(result.steps_taken))
        if result.steps_skipped:
            print("dry-run: steps skipped (defer-bump):", ", ".join(result.steps_skipped))
    elif not result.success:
        print(f"ship failed at step: {result.error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
