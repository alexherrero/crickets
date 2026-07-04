#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/advisor_rider.py (PLAN-efficiency-dispatch task 3).

A T0/T1 session's config carrying `advisorModel: claude-opus-4-8` validates;
the schema rejects an advisor weaker than the main session (the pairing
constraint); claude-fable-5 as advisor is flagged version-gated (>=2.1.170)
rather than silently allowed. A fixture session-start renders the
advisor-availability line correctly when configured, omits it cleanly when
not.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
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


ar = _load("advisor_rider")


class TestPairingConstraint(unittest.TestCase):
    def test_t0_t1_session_with_stronger_advisor_is_valid(self):
        result = ar.validate_advisor_rider("claude-haiku-4-5", "claude-opus-4-8")
        self.assertTrue(result.valid)
        self.assertIsNone(result.error)

    def test_advisor_weaker_than_main_session_is_rejected(self):
        result = ar.validate_advisor_rider("claude-opus-4-8", "claude-haiku-4-5")
        self.assertFalse(result.valid)
        self.assertIn("weaker", result.error)

    def test_equal_strength_pairing_is_valid(self):
        result = ar.validate_advisor_rider("claude-sonnet-5", "claude-sonnet-4-6")
        self.assertTrue(result.valid)

    def test_unrecognized_model_is_rejected(self):
        result = ar.validate_advisor_rider("claude-haiku-4-5", "not-a-real-model")
        self.assertFalse(result.valid)
        self.assertIn("unrecognized", result.error)


class TestFableAdvisorVersionGate(unittest.TestCase):
    def test_fable_advisor_below_min_version_rejected(self):
        result = ar.validate_advisor_rider("claude-haiku-4-5", "claude-fable-5", cli_version="2.1.100")
        self.assertFalse(result.valid)
        self.assertIn("2.1.170", result.error)

    def test_fable_advisor_at_or_above_min_version_accepted(self):
        result = ar.validate_advisor_rider("claude-haiku-4-5", "claude-fable-5", cli_version="2.1.170")
        self.assertTrue(result.valid)
        self.assertIsNone(result.warning)

    def test_fable_advisor_above_min_version_accepted(self):
        result = ar.validate_advisor_rider("claude-haiku-4-5", "claude-fable-5", cli_version="2.2.0")
        self.assertTrue(result.valid)

    def test_fable_advisor_unknown_cli_version_flagged_not_silently_allowed(self):
        result = ar.validate_advisor_rider("claude-haiku-4-5", "claude-fable-5", cli_version=None)
        self.assertTrue(result.valid)
        self.assertIsNotNone(result.warning)
        self.assertIn("2.1.170", result.warning)

    def test_non_fable_advisor_never_carries_the_version_warning(self):
        result = ar.validate_advisor_rider("claude-haiku-4-5", "claude-opus-4-8", cli_version=None)
        self.assertTrue(result.valid)
        self.assertIsNone(result.warning)


class TestAdvisorAvailabilityLine(unittest.TestCase):
    def test_renders_when_configured(self):
        line = ar.advisor_availability_line("claude-opus-4-8")
        self.assertIn("claude-opus-4-8", line)
        self.assertIn("Advisor available", line)

    def test_omitted_cleanly_when_not_configured(self):
        self.assertEqual(ar.advisor_availability_line(None), "")
        self.assertEqual(ar.advisor_availability_line(""), "")

    def test_line_states_advisory_only_never_auto_switches(self):
        line = ar.advisor_availability_line("claude-opus-4-8")
        self.assertIn("never auto-switches", line)


class TestReadAdvisorModel(unittest.TestCase):
    def test_missing_project_json_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(ar.read_advisor_model(d))

    def test_configured_value_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            harness = Path(d) / ".harness"
            harness.mkdir()
            (harness / "project.json").write_text(json.dumps({"advisorModel": "claude-opus-4-8"}))
            self.assertEqual(ar.read_advisor_model(d), "claude-opus-4-8")

    def test_malformed_json_returns_none_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            harness = Path(d) / ".harness"
            harness.mkdir()
            (harness / "project.json").write_text("{not valid json")
            self.assertIsNone(ar.read_advisor_model(d))

    def test_absent_key_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            harness = Path(d) / ".harness"
            harness.mkdir()
            (harness / "project.json").write_text(json.dumps({"isolation": {"mode": "direct"}}))
            self.assertIsNone(ar.read_advisor_model(d))


if __name__ == "__main__":
    unittest.main()
