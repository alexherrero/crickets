#!/usr/bin/env python3
"""Tests for scripts/correction_quality_gate.py.

Load-bearing assertions:
  (a) the seam is a single interface (CorrectionQualityEvaluator.evaluate)
  (b) the interim ChecklistEvaluator passes when all items have notes
  (c) the interim ChecklistEvaluator fails when any item is unanswered
  (d) a conforming substitute evaluator (the #20 drop-in shape) satisfies the seam
  (e) no second bounded-evaluator primitive is defined — ChecklistEvaluator IS the
      only concrete implementation in this module
"""
import importlib.util
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "scripts" / "correction_quality_gate.py"
_CLASSIFIER = _ROOT / "scripts" / "correction_classifier.py"


def _load(script):
    spec = importlib.util.spec_from_file_location(script.stem, script)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


gate = _load(_SCRIPT)
classifier = _load(_CLASSIFIER)

_ALL_NOTES = {
    "universal": "Both dogfood corrections affect every operator sharing the global push policy.",
    "artifact-wrong": "release.md Constraint 5 directly contradicts ~/.claude/CLAUDE.md push policy.",
    "no-tuning": "The recoverability gate is not a personal preference — it is a universal contract.",
    "leverage-clear": "Both corrections alter the command's external behavior contract → contract leverage.",
    "no-pii": "No vault paths or operator-private content in the correction entries.",
}


class TestSeamInterface(unittest.TestCase):
    """CorrectionQualityEvaluator is the single interface for the composition seam."""

    def test_seam_has_evaluate_method(self):
        self.assertTrue(hasattr(gate.CorrectionQualityEvaluator, "evaluate"),
                        "seam must define an evaluate() method")

    def test_evaluate_raises_not_implemented_on_base(self):
        seam = gate.CorrectionQualityEvaluator()
        entry = classifier.CorrectionEntry(
            timestamp="2026-06-16 00:00", summary="test",
            did="x", should="y", artifact="a",
            correction_class=classifier.CorrectionClass.RULE,
        )
        with self.assertRaises(NotImplementedError):
            seam.evaluate(entry)

    def test_only_one_concrete_evaluator_in_module(self):
        import inspect
        concrete = [
            name for name, obj in inspect.getmembers(gate, inspect.isclass)
            if issubclass(obj, gate.CorrectionQualityEvaluator)
            and obj is not gate.CorrectionQualityEvaluator
        ]
        self.assertEqual(len(concrete), 1,
                         f"exactly one concrete evaluator expected, found: {concrete}")
        self.assertEqual(concrete[0], "ChecklistEvaluator")


class TestChecklistEvaluatorPass(unittest.TestCase):
    """All checklist items answered → passes."""

    def _entry(self):
        return classifier.CorrectionEntry(
            timestamp="2026-06-14 10:00",
            summary="/release double-gate contradicts global auto-push policy",
            did="stopped and waited per Constraint 5",
            should="announce + proceed; summary is a record not a gate",
            artifact="src/developer-workflows/commands/release.md",
            correction_class=classifier.CorrectionClass.RULE,
            disposition=classifier.Disposition.KERNEL_DEFECT,
            leverage=classifier.Leverage.CONTRACT,
        )

    def test_all_items_answered_passes(self):
        ev = gate.ChecklistEvaluator()
        result = ev.evaluate(self._entry(), notes=_ALL_NOTES)
        self.assertTrue(result.passes)
        self.assertEqual(len(result.items), len(_ALL_NOTES))

    def test_result_includes_per_item_tuples(self):
        ev = gate.ChecklistEvaluator()
        result = ev.evaluate(self._entry(), notes=_ALL_NOTES)
        for question, passed, note in result.items:
            self.assertTrue(passed, f"item should pass: {question!r}")


class TestChecklistEvaluatorFail(unittest.TestCase):
    """Any unanswered item → fails."""

    def _entry(self):
        return classifier.CorrectionEntry(
            timestamp="2026-06-16 00:00", summary="incomplete",
            did="x", should="y", artifact="a",
            correction_class=classifier.CorrectionClass.RULE,
        )

    def test_empty_notes_fails(self):
        ev = gate.ChecklistEvaluator()
        result = ev.evaluate(self._entry(), notes={})
        self.assertFalse(result.passes)

    def test_partial_notes_fails(self):
        ev = gate.ChecklistEvaluator()
        partial = {"universal": "yes", "artifact-wrong": "yes"}
        result = ev.evaluate(self._entry(), notes=partial)
        self.assertFalse(result.passes)


class TestMaster20DropIn(unittest.TestCase):
    """A conforming substitute satisfies the seam — proves #20 can drop in."""

    def test_substitute_satisfies_seam(self):
        class _Stub(gate.CorrectionQualityEvaluator):
            def evaluate(self, entry, **_kw):
                return gate.EvaluationResult(passes=True, verdict="stub-pass")

        stub = _Stub()
        entry = classifier.CorrectionEntry(
            timestamp="2026-06-16 00:00", summary="stub",
            did="x", should="y", artifact="a",
            correction_class=classifier.CorrectionClass.RULE,
        )
        result = stub.evaluate(entry)
        self.assertTrue(result.passes)
        self.assertIsInstance(result, gate.EvaluationResult)


if __name__ == "__main__":
    unittest.main()
