#!/usr/bin/env python3
"""Tests for scripts/correction_ship.py — ship path ordering invariants.

Load-bearing assertions:
  (a) gate-suite runs BEFORE ci-check in the step sequence (gate before CI)
  (b) ci-check runs BEFORE tag (CI-before-tag invariant — the wake-on-CI contract)
  (c) defer-bump mode skips version bump, tag, and gh-release (DEFER-BUMP-ONLY)
  (d) full mode includes all 9 steps in correct order
"""
import importlib.util
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "scripts" / "correction_ship.py"


def _load():
    spec = importlib.util.spec_from_file_location("correction_ship", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load()

# Steps that must appear in both full and defer-bump modes.
_ALWAYS_STEPS = ["gate-suite", "regen-dist", "commit", "push", "ci-check"]
# Steps deferred in defer-bump mode.
_DEFERRED_STEPS = ["bump-version", "update-changelog", "tag", "gh-release"]
# Full step order.
_FULL_ORDER = ["gate-suite", "bump-version", "update-changelog", "regen-dist",
               "commit", "push", "ci-check", "tag", "gh-release"]


class TestStepOrdering(unittest.TestCase):
    """Verify the CI-before-tag invariant in dry_run mode."""

    def _run_dry(self, **kwargs):
        o = mod.ShipOrchestrator(dry_run=True, **kwargs)
        return o.run()

    def test_gate_suite_before_ci_check(self):
        result = self._run_dry()
        steps = result.steps_taken
        self.assertIn("gate-suite", steps)
        self.assertIn("ci-check", steps)
        self.assertLess(
            steps.index("gate-suite"),
            steps.index("ci-check"),
            "gate-suite must run before ci-check",
        )

    def test_ci_check_before_tag_full_mode(self):
        result = self._run_dry()
        steps = result.steps_taken
        self.assertIn("ci-check", steps)
        self.assertIn("tag", steps)
        self.assertLess(
            steps.index("ci-check"),
            steps.index("tag"),
            "ci-check (wake-on-CI) must run before tag — never tag ahead of green CI",
        )

    def test_full_mode_includes_all_steps_in_order(self):
        result = self._run_dry()
        self.assertEqual(result.steps_taken, _FULL_ORDER,
                         "full mode must run all steps in the canonical order")

    def test_full_mode_no_steps_skipped(self):
        result = self._run_dry()
        self.assertEqual(result.steps_skipped, [],
                         "full mode must skip nothing")


class TestDeferBumpMode(unittest.TestCase):
    """DEFER-BUMP-ONLY: bump-version, tag, gh-release are skipped."""

    def _run_defer_dry(self):
        o = mod.ShipOrchestrator(dry_run=True, defer_bump=True)
        return o.run()

    def test_defer_bump_skips_version_bump_tag_release(self):
        result = self._run_defer_dry()
        for step in _DEFERRED_STEPS:
            self.assertIn(step, result.steps_skipped,
                          f"{step} must be skipped in defer-bump mode")

    def test_defer_bump_still_runs_gate_suite(self):
        result = self._run_defer_dry()
        self.assertIn("gate-suite", result.steps_taken)

    def test_defer_bump_still_runs_ci_check(self):
        result = self._run_defer_dry()
        self.assertIn("ci-check", result.steps_taken)

    def test_defer_bump_gate_before_ci(self):
        result = self._run_defer_dry()
        steps = result.steps_taken
        self.assertLess(
            steps.index("gate-suite"),
            steps.index("ci-check"),
            "gate-suite must run before ci-check even in defer-bump mode",
        )


if __name__ == "__main__":
    unittest.main()
