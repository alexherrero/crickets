#!/usr/bin/env python3
"""Correction-quality gate — composition seam for MASTER #20's bounded evaluator.

Single-interface contract: CorrectionQualityEvaluator.evaluate(entry) → EvaluationResult.

Interim implementation: ChecklistEvaluator runs an explicit checklist against the
correction entry and returns a pass/fail verdict with per-item results.  When MASTER #20's
bounded evaluator ships it plugs in as a drop-in replacement at this seam — no contract
change, no second evaluator primitive defined here.

The gate is called by the ship path (correction_ship.py) before disposition to ensure
a kernel-defect classification is warranted.  The interim checklist surface is human-
judgment-driven: the questions guide the operator's ratify decision for contract-level
changes (Leverage.CONTRACT in correction_classifier.py).

Composition seam pattern (MASTER #20 compatibility):
  from correction_quality_gate import CorrectionQualityEvaluator, EvaluationResult
  evaluator = ChecklistEvaluator()      # interim
  # evaluator = Master20Evaluator(...)  # future drop-in — same interface
  result = evaluator.evaluate(entry)
  if not result.passes:
      raise SystemExit(f"quality gate failed: {result.verdict}")
"""
from typing import List, Optional


class EvaluationResult:
    """Outcome of a correction quality evaluation."""

    def __init__(self, passes, verdict, items=None):
        self.passes = passes          # bool
        self.verdict = verdict        # str — summary
        self.items = items or []      # list of (question: str, passed: bool, note: str)

    def __repr__(self):
        status = "PASS" if self.passes else "FAIL"
        return f"EvaluationResult({status}: {self.verdict})"


class CorrectionQualityEvaluator:
    """Abstract composition seam — MASTER #20 bounded evaluator will satisfy this interface.

    Subclasses must implement evaluate(entry) → EvaluationResult.
    The interface is deliberately minimal so #20 can slot in without touching callers.
    """

    def evaluate(self, entry):
        """Evaluate the correction entry against quality criteria.

        Args:
            entry: CorrectionEntry from correction_classifier.py.

        Returns:
            EvaluationResult(passes, verdict, items).
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Interim implementation: explicit checklist + human-judgment notes
# ---------------------------------------------------------------------------

_CHECKLIST = [
    (
        "universal",
        "Would every operator want this correction applied to the shipped plugin? "
        "(Yes → kernel-defect; No → operator-tuning, stop here.)",
    ),
    (
        "artifact-wrong",
        "Is the shipped artifact objectively wrong, or does it contradict a "
        "standing contract (e.g. global push policy, recoverability gate)?",
    ),
    (
        "no-tuning",
        "Is this correction free of personal-preference content that would not "
        "apply to all operators?",
    ),
    (
        "leverage-clear",
        "Is the leverage level clear? (contract change → one-tap ratify; "
        "prompt-wording / default / doc → auto-apply)",
    ),
    (
        "no-pii",
        "Does the correction entry contain no PII, vault paths, or operator-private "
        "content that could land in committed source?",
    ),
]


class ChecklistEvaluator(CorrectionQualityEvaluator):
    """Interim evaluator: runs the explicit checklist against a correction entry.

    All items must pass for the result to pass.  The 'notes' dict may supply
    per-item rationale (keyed by item key) for the audit log.
    """

    def evaluate(self, entry, notes=None):
        """Evaluate entry against the checklist.

        Args:
            entry: CorrectionEntry.
            notes: optional dict[str, str] mapping checklist-item keys to rationale.

        Returns:
            EvaluationResult — passes iff all checklist items are answered affirmatively
            (all notes present and non-empty for each item).
        """
        if notes is None:
            notes = {}

        items = []
        all_pass = True
        for key, question in _CHECKLIST:
            note = notes.get(key, "")
            passed = bool(note.strip())
            items.append((question, passed, note))
            if not passed:
                all_pass = False

        verdict = (
            "all checklist items answered — kernel-defect classification confirmed"
            if all_pass
            else "one or more checklist items unanswered — resolve before shipping"
        )
        return EvaluationResult(passes=all_pass, verdict=verdict, items=items)
