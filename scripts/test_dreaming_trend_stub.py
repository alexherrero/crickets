#!/usr/bin/env python3
"""Tests for src/tokens/scripts/dreaming_trend_stub.py (PLAN-wave-d-tokens-
and-privacy task 3) -- the correctly-gated-dark dreaming-pass efficiency-
trend review hook.

Acceptance criterion (named explicitly in the plan): with no dreaming-pass
infrastructure present, the hook returns a clean no-op -- not an error, not a
silent partial implementation. This is a dark-check, not a feature test.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "tokens" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SRC / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


stub = _load("dreaming_trend_stub")


class DreamingPassAvailabilityTests(unittest.TestCase):
    def test_dreaming_pass_is_unavailable_today(self):
        # Wave-E's dreaming pass is designed, not built -- this must be False
        # until that infrastructure actually exists.
        self.assertFalse(stub.dreaming_pass_available())


class ReviewEfficiencyTrendDarkCheckTests(unittest.TestCase):
    """The acceptance criterion: correctly-gated-dark, not broken."""

    def test_noop_with_no_records(self):
        result = stub.review_efficiency_trend()
        self.assertFalse(result.ran)
        self.assertEqual(result.reason, "dreaming-pass-unavailable")

    def test_noop_even_with_records_present(self):
        # Records existing (task 1 has landed and accumulated real
        # session-cost entries) must not change the outcome -- the gate is on
        # the dreaming pass's existence, not on data availability.
        records = [{"model": "claude-sonnet-5", "cost_usd": 0.05}]
        result = stub.review_efficiency_trend(records)
        self.assertFalse(result.ran)
        self.assertEqual(result.reason, "dreaming-pass-unavailable")

    def test_never_raises(self):
        # A dark-check must never error -- that would read as "broken", not
        # "correctly gated".
        try:
            stub.review_efficiency_trend([{"anything": "goes"}])
            stub.review_efficiency_trend(None)
            stub.review_efficiency_trend([])
        except Exception as e:  # pragma: no cover
            self.fail(f"review_efficiency_trend raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
