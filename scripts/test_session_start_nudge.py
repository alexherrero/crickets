#!/usr/bin/env python3
"""Tests for session-start tier + advisor nudge (PLAN-efficiency-dispatch task 7).

A fixture session whose live model doesn't match the active plan's staged
tier hint reports the mismatch and states advisor availability; it never
switches the session's model. No mismatch (or no hint set at all — the
common case) -> silent.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "developer-workflows" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ssn = _load("session_start_nudge")

_PLAN_WITH_HINT = """\
# Plan: fixture

## Tasks

### 1. Done already
- **What:** stuff
- **Status:** [x]

### 2. Next up
- **What:** more stuff
- **Work-type (optional):** worker-build
- **Tier hint (auto, only present when Work-type is set):** T1-Execute · opusplan · medium (tier-source: ROLE-MATCH)
- **Status:** [ ]

### 3. Later
- **What:** even more
- **Status:** [ ]
"""

_PLAN_NO_HINT = """\
# Plan: fixture

## Tasks

### 1. Only task
- **What:** stuff
- **Status:** [ ]
"""


class TestNextUncheckedTaskTierHintModel(unittest.TestCase):
    def test_extracts_the_model_from_the_first_unchecked_task(self):
        self.assertEqual(ssn.next_unchecked_task_tier_hint_model(_PLAN_WITH_HINT), "opusplan")

    def test_returns_none_when_no_task_declares_a_hint(self):
        self.assertIsNone(ssn.next_unchecked_task_tier_hint_model(_PLAN_NO_HINT))

    def test_returns_none_for_empty_plan_text(self):
        self.assertIsNone(ssn.next_unchecked_task_tier_hint_model(""))


class TestSessionStartNudge(unittest.TestCase):
    def test_mismatch_reports_both_models_advisory_only(self):
        line = ssn.session_start_nudge("claude-sonnet-5", "claude-opus-4-8")
        self.assertIn("claude-sonnet-5", line)
        self.assertIn("claude-opus-4-8", line)
        self.assertIn("Advisory only", line)
        self.assertIn("never auto-switches", line)

    def test_no_mismatch_is_silent(self):
        self.assertEqual(ssn.session_start_nudge("claude-sonnet-5", "claude-sonnet-5"), "")

    def test_no_hint_at_all_is_silent(self):
        self.assertEqual(ssn.session_start_nudge("claude-sonnet-5", None), "")

    def test_no_live_model_known_is_silent_not_a_false_mismatch(self):
        self.assertEqual(ssn.session_start_nudge(None, "claude-opus-4-8"), "")

    def test_advisor_line_included_when_configured(self):
        line = ssn.session_start_nudge("claude-sonnet-5", "claude-sonnet-5", advisor_model="claude-opus-4-8")
        self.assertIn("Advisor available", line)
        self.assertIn("claude-opus-4-8", line)

    def test_advisor_line_omitted_when_not_configured(self):
        line = ssn.session_start_nudge("claude-sonnet-5", "claude-sonnet-5", advisor_model=None)
        self.assertEqual(line, "")

    def test_both_mismatch_and_advisor_can_render_together(self):
        line = ssn.session_start_nudge("claude-sonnet-5", "claude-opus-4-8", advisor_model="claude-opus-4-8")
        self.assertIn("NOTE", line)
        self.assertIn("Advisor available", line)


class TestNeverMutatesTheSession(unittest.TestCase):
    def test_signature_has_no_model_mutating_parameter(self):
        sig = inspect.signature(ssn.session_start_nudge)
        for name in sig.parameters:
            self.assertNotIn("switch", name.lower())
            self.assertNotIn("set_model", name.lower())

    def test_module_defines_no_model_switching_function(self):
        suspicious = [
            name for name in dir(ssn)
            if callable(getattr(ssn, name)) and ("switch" in name.lower() or "set_model" in name.lower())
        ]
        self.assertEqual(suspicious, [])


if __name__ == "__main__":
    unittest.main()
