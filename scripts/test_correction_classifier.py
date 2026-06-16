#!/usr/bin/env python3
"""Tests for scripts/correction_classifier.py.

Load-bearing assertions:
  (a) universal contract conflict → kernel-defect, contract leverage (the /release double-gate case)
  (b) universal low-leverage → kernel-defect, low leverage (auto-apply)
  (c) personal preference → operator-tuning, leverage=None
  (d) apply_operator_tuning writes to the overlay path and does NOT touch src/
"""
import importlib.util
import shutil
import tempfile
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "scripts" / "correction_classifier.py"


def _load():
    spec = importlib.util.spec_from_file_location("correction_classifier", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load()


class TestKernelDefectClassification(unittest.TestCase):
    """Universal contract conflict → kernel-defect."""

    def test_universal_contract_conflict_is_kernel_defect_contract_leverage(self):
        # Models the /release double-gate dogfood seed: shipped text contradicts
        # the global auto-push policy — a universal contract, a contract-level change.
        result = mod.classify(universality=True, is_contract_change=True)
        self.assertEqual(result.disposition, mod.Disposition.KERNEL_DEFECT)
        self.assertEqual(result.leverage, mod.Leverage.CONTRACT)
        self.assertIn("one-tap ratify", result.rationale)

    def test_universal_low_leverage_is_kernel_defect_auto_apply(self):
        result = mod.classify(universality=True, is_contract_change=False)
        self.assertEqual(result.disposition, mod.Disposition.KERNEL_DEFECT)
        self.assertEqual(result.leverage, mod.Leverage.LOW)
        self.assertIn("auto-apply", result.rationale)


class TestOperatorTuningClassification(unittest.TestCase):
    """Personal preference → operator-tuning; no src/ mutation."""

    def test_personal_preference_is_operator_tuning(self):
        result = mod.classify(universality=False)
        self.assertEqual(result.disposition, mod.Disposition.OPERATOR_TUNING)
        self.assertIsNone(result.leverage)

    def test_personal_preference_contract_change_still_operator_tuning(self):
        # Even a "contract-level" phrasing of a personal preference stays operator-tuning
        # if the preference is not universal.
        result = mod.classify(universality=False, is_contract_change=True)
        self.assertEqual(result.disposition, mod.Disposition.OPERATOR_TUNING)

    def test_operator_tuning_writes_only_vault_overlay_not_src(self):
        """apply_operator_tuning must write the overlay and leave src/ untouched."""
        tmp = Path(tempfile.mkdtemp(prefix="correction-tuning-"))
        try:
            overlay = tmp / "_harness" / "improvement_memory.md"
            entry = mod.CorrectionEntry(
                timestamp="2026-06-16 00:00",
                summary="prefer one-sentence summaries",
                did="wrote a five-paragraph status update",
                should="write at most two sentences",
                artifact="src/developer-workflows/commands/release.md",
                correction_class=mod.CorrectionClass.RULE,
            )
            # Capture src/ mtime before the call.
            src_path = _ROOT / "src"
            src_mtime_before = src_path.stat().st_mtime if src_path.exists() else None

            mod.apply_operator_tuning(overlay, entry)

            # Overlay must be written.
            self.assertTrue(overlay.exists(), "vault overlay file should be created")
            content = overlay.read_text(encoding="utf-8")
            self.assertIn("prefer one-sentence summaries", content)

            # src/ mtime must be unchanged.
            if src_mtime_before is not None:
                src_mtime_after = src_path.stat().st_mtime
                self.assertEqual(
                    src_mtime_before,
                    src_mtime_after,
                    "apply_operator_tuning must not touch src/",
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
