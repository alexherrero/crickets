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
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DW_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"
_TA_SCRIPTS = _ROOT / "src" / "tokens" / "scripts"


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


class TestRoutedThroughOpinionResolveNotDirectImport(unittest.TestCase):
    """PLAN-wave-d-opinion-wiring task 2: escalation_tripwire.py discovers
    tokens/scripts via opinion_resolve('efficient')['implements'], not a
    hardcoded _HERE.parent.parent / "tokens" / "scripts" relative path."""

    def test_ta_scripts_assigned_from_the_resolver_function_not_a_literal(self):
        # The old code assigned _TA_SCRIPTS directly from a fixed relative-
        # path literal on its own line; the new code assigns it from calling
        # _resolve_efficient_implements_dir(), which tries the opinion
        # registry first and only falls back to a same-repo literal (a
        # separately-named _FALLBACK_TA_SCRIPTS constant) when the registry
        # is unresolvable. Checked as the exact _TA_SCRIPTS assignment line,
        # not a bare substring search, since the docstring's own prose
        # legitimately names the old path shape when explaining the
        # migration -- a substring check would false-positive on that.
        src = (_DW_SCRIPTS / "escalation_tripwire.py").read_text(encoding="utf-8")
        self.assertIn("_TA_SCRIPTS = _resolve_efficient_implements_dir()", src)

    def test_source_calls_opinion_resolve_for_efficient(self):
        src = (_DW_SCRIPTS / "escalation_tripwire.py").read_text(encoding="utf-8")
        self.assertIn("opinion_resolve", src)
        self.assertIn("efficient", src)

    def test_fixture_classification_unchanged_after_migration(self):
        # The migration changes HOW tokens/scripts is discovered, never WHAT
        # classify_work_type resolves for a given role -- same fixture role,
        # same tier/model_id/effort as the pre-migration direct-import path.
        counter = et.FailureCounter()
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "escalation"
            result = None
            for i in range(3):
                result = et.check_and_maybe_fire(
                    counter, "task-42", "Fix the widget", "unit tests",
                    f"err {i}", dest, work_type="worker-build",
                )
            manifest = json.loads((dest / "prompts.json").read_text(encoding="utf-8"))
            label = manifest["prompts"][0]["label"]
            self.assertEqual(label["tier"], "T1-Execute")
            self.assertEqual(label["model_id"], "opusplan")

    def test_falls_back_to_same_repo_path_when_opinion_resolver_unresolvable(self):
        # CI (and any machine without a sibling agentm checkout) must still
        # find THIS repo's own src/tokens/scripts -- that lookup never
        # depended on agentm before this migration and must not regress now
        # that the opinion registry is the primary discovery mechanism.
        with mock.patch.object(et, "_find_opinion_resolver", return_value=None):
            result = et._resolve_efficient_implements_dir()
        self.assertIsNotNone(result)
        self.assertTrue(result.is_dir())
        self.assertEqual(result.name, "scripts")
        self.assertEqual(result.parent.name, "tokens")

    def test_registry_lookup_and_same_repo_fallback_agree(self):
        # Whenever the opinion resolver IS reachable, its implements: pointer
        # must resolve to the identical directory the fallback would have
        # used -- proves the registry lookup isn't a parallel path that could
        # silently diverge from the same-repo truth.
        resolved = et._resolve_efficient_implements_dir()
        self.assertEqual(resolved, et._FALLBACK_TA_SCRIPTS)


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
