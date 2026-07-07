#!/usr/bin/env python3
"""Tests for scripts/check-no-duplicate-diagnosis.py (PLAN-wave-d-cross-wiring
task 3 -- the portfolio-consistency gate).

Builds temp src/ fixtures and asserts check() flags a bespoke inline
category/confidence-scoring or ad hoc traceback-classification pattern
re-introduced into either consumer's markdown, while staying clean on the
now-recast wiring (a diagnose.py / diagnose() call, no inline reasoning).

Mirrors check-no-dangling-name.py's fixture-and-test style (Wave A).
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_no_duplicate_diagnosis", _HERE / "check-no-duplicate-diagnosis.py"
)
cndd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cndd)


class TestCheckNoDuplicateDiagnosis(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, rel_path: str, text: str) -> Path:
        p = self.src / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_clean_recast_wiring_passes(self) -> None:
        self._write(
            "maintenance/skills/dependabot-fixer/SKILL.md",
            "## Diagnose (call the shared `/diagnose` engine)\n\n"
            "Run `diagnose.py` and use the confidence-gate proxy over `outcome`.\n",
        )
        self._write(
            "development-lifecycle/commands/bugfix.md",
            "### 2. Analyze\n\nSeed from `diagnose.py`'s `hypotheses`, additive only.\n",
        )
        findings = cndd.check(src=self.src)
        self.assertEqual(findings, [])

    def test_flags_reintroduced_inline_confidence_gate_in_dependabot_fixer(self) -> None:
        self._write(
            "maintenance/skills/dependabot-fixer/SKILL.md",
            "## Diagnose (kept in scratch — do not write to disk yet)\n\n"
            "Produce: failure category, confidence (high/medium/low), proposed fix.\n"
            "**If confidence is low → abort, do not attempt.**\n",
        )
        findings = cndd.check(src=self.src)
        self.assertTrue(
            any("dependabot-fixer" in f for f in findings),
            f"expected a dependabot-fixer finding, got: {findings}",
        )

    def test_flags_reintroduced_inline_classification_in_bugfix(self) -> None:
        self._write(
            "development-lifecycle/commands/bugfix.md",
            "### 2. Analyze\n\n"
            "Produce: failure category, confidence (high/medium/low) from scratch.\n",
        )
        findings = cndd.check(src=self.src)
        self.assertTrue(
            any("bugfix.md" in f for f in findings),
            f"expected a bugfix.md finding, got: {findings}",
        )

    def test_missing_files_are_a_graceful_no_op(self) -> None:
        # Neither consumer file exists in this fixture tree -- nothing to check,
        # not an error.
        findings = cndd.check(src=self.src)
        self.assertEqual(findings, [])

    def test_documented_graceful_skip_fallback_is_not_flagged(self) -> None:
        # Mirrors the real recast shape: the engine IS called, and the old
        # inline category+confidence shape survives only as a documented
        # fallback for when diagnostics isn't installed -- not a regression.
        self._write(
            "maintenance/skills/dependabot-fixer/SKILL.md",
            "## Diagnose (call the shared `/diagnose` engine)\n\n"
            "Check availability first (graceful-skip).\n\n"
            "- **Exit 1** (diagnostics not installed) → fall back to the "
            "pre-recast behavior: produce failure category + confidence "
            "(high/medium/low) + proposed fix inline, abort on low confidence.\n"
            "- **Exit 0** → run `diagnose.py` against the captured log.\n",
        )
        findings = cndd.check(src=self.src)
        self.assertEqual(findings, [])

    def test_partial_recast_with_unconditional_inline_reasoning_is_flagged(self) -> None:
        # The engine is called, but the old inline shape ALSO still runs
        # unconditionally (no fallback framing) -- a genuine partial recast,
        # still a regression even though diagnose.py is present somewhere.
        self._write(
            "maintenance/skills/dependabot-fixer/SKILL.md",
            "## Diagnose\n\nRun `diagnose.py` against the captured log.\n\n"
            "Then also produce: failure category, confidence (high/medium/low), "
            "proposed fix, in case the engine is wrong.\n",
        )
        findings = cndd.check(src=self.src)
        self.assertTrue(
            any("dependabot-fixer" in f for f in findings),
            f"expected a dependabot-fixer finding, got: {findings}",
        )


if __name__ == "__main__":
    unittest.main()
