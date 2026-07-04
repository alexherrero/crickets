#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/escalation_tripwire.py (PLAN-efficiency-dispatch task 5).

A fixture task failing the same verification gate 3 consecutive attempts
fires the tripwire: a handoff-pack escalation entry is written (carrying
packed context + a tier-labeled prompt in the same machine-readable format
`/handoff-pack` emits), a loud announcement is returned. 2 consecutive
failures does not fire (boundary check). The tripwire never attempts to
change the session's own model.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DW_SCRIPTS = _ROOT / "src" / "developer-workflows" / "scripts"
_TA_SCRIPTS = _ROOT / "src" / "token-audit" / "scripts"


def _load(name: str, scripts_dir: Path):
    spec = importlib.util.spec_from_file_location(name, scripts_dir / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


_load("handoff_pack", _TA_SCRIPTS)
_load("classify_work_type", _TA_SCRIPTS)
et = _load("escalation_tripwire", _DW_SCRIPTS)


class TestFailureCounterBoundary(unittest.TestCase):
    def test_two_consecutive_failures_does_not_fire(self):
        counter = et.FailureCounter()
        counter.record_failure()
        counter.record_failure()
        self.assertFalse(counter.should_fire())

    def test_three_consecutive_failures_fires(self):
        counter = et.FailureCounter()
        for _ in range(3):
            counter.record_failure()
        self.assertTrue(counter.should_fire())

    def test_success_resets_the_counter(self):
        counter = et.FailureCounter()
        counter.record_failure()
        counter.record_failure()
        counter.record_success()
        counter.record_failure()
        counter.record_failure()
        self.assertFalse(counter.should_fire())  # only 2 since the reset


class TestFireTripwireWritesHandoffPack(unittest.TestCase):
    def test_three_failures_via_check_and_maybe_fire_writes_a_pack(self):
        counter = et.FailureCounter()
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "escalation"
            result = None
            for i in range(3):
                result = et.check_and_maybe_fire(
                    counter, "task-7", "Fix the parser", "unit tests",
                    f"AssertionError on attempt {i}", dest,
                )
            self.assertIsNotNone(result)
            self.assertTrue(result.fired)
            manifest = json.loads((dest / "prompts.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["prompts"]), 1)
            prompt = manifest["prompts"][0]
            self.assertIn("task-7", prompt["title"])
            self.assertIn("AssertionError on attempt 2", prompt["prompt_text"])
            for key in ("tier", "model_id", "effort"):
                self.assertIn(key, prompt["label"])

    def test_two_failures_via_check_and_maybe_fire_does_not_write_anything(self):
        counter = et.FailureCounter()
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "escalation"
            result = None
            for i in range(2):
                result = et.check_and_maybe_fire(
                    counter, "task-7", "Fix the parser", "unit tests", f"err {i}", dest,
                )
            self.assertIsNone(result)
            self.assertFalse(dest.exists())

    def test_announcement_is_loud_and_names_the_task_and_gate(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "escalation"
            result = et.fire_tripwire("task-9", "Add validation", "lint", "E501 line too long", dest)
            self.assertIn("task-9", result.announcement)
            self.assertIn("lint", result.announcement)
            self.assertIn("ESCALATION", result.announcement)


class TestNeverSelfSwitchesModel(unittest.TestCase):
    def test_fire_tripwire_signature_has_no_model_mutating_parameter(self):
        sig = inspect.signature(et.fire_tripwire)
        for name in sig.parameters:
            self.assertNotIn("model_override", name)
            self.assertNotIn("switch_model", name)

    def test_module_defines_no_model_switching_function(self):
        suspicious = [
            name for name in dir(et)
            if callable(getattr(et, name)) and ("switch" in name.lower() or "set_model" in name.lower())
        ]
        self.assertEqual(suspicious, [])

    def test_announcement_states_it_never_changes_its_own_model(self):
        with tempfile.TemporaryDirectory() as d:
            result = et.fire_tripwire("t", "title", "gate", "err", Path(d) / "e")
            self.assertIn("never changes its own model", result.announcement)


if __name__ == "__main__":
    unittest.main()
