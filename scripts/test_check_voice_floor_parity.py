#!/usr/bin/env python3
"""Tests for check-voice-floor-parity.py (PLAN-r3-voice-mechanism task 4).

Locks: the current (post-promotion) floor is a superset of the rule pack, a
synthetic pre-promotion fixture (missing load-bearing/powerful/cutting-edge)
fails red — reproducing the lag this task fixed — and `--report` forces 0.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_voice_floor_parity", _SCRIPTS / "check-voice-floor-parity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_voice_floor_parity"] = mod
    spec.loader.exec_module(mod)
    return mod


parity = _load()

_PRE_PROMOTION_FIXTURE = """# Base style guide — house voice

## Voice

- **Second person, direct.**

## Banned

- **Machine-checkable terms.**
  banned: groundbreaking, deeply, vital, crucial, truly, delve, pioneering, transformative, visionary, this journey, it should be noted that, it is worth mentioning, arguably, essentially, first-class, seamless, robust, leverage, comprehensive

## Structure

- **High-level over exhaustive.**
"""


class TestCurrentFloorIsSuperset(unittest.TestCase):
    def test_no_missing_terms_against_shipped_pack(self):
        missing = parity.missing_terms()
        self.assertEqual(missing, set(), f"floor lags the rule pack: {missing}")

    def test_main_exits_zero_on_current_floor(self):
        self.assertEqual(parity.main([]), 0)


class TestPrePromotionFixtureFailsRed(unittest.TestCase):
    """Reproduces the exact lag Task 4 fixed (load-bearing/powerful/cutting-edge
    missing from the floor) — the parity check must have caught this."""

    def test_fixture_missing_the_three_promoted_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "base-style-guide.md"
            fixture.write_text(_PRE_PROMOTION_FIXTURE)
            missing = parity.missing_terms(fixture)
            self.assertEqual(missing, {"load-bearing", "powerful", "cutting-edge"})

    def test_main_exits_nonzero_on_pre_promotion_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "base-style-guide.md"
            fixture.write_text(_PRE_PROMOTION_FIXTURE)
            rc = parity.main(["--base-style-guide", str(fixture)])
            self.assertEqual(rc, 1)

    def test_report_flag_forces_zero_even_on_lagging_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "base-style-guide.md"
            fixture.write_text(_PRE_PROMOTION_FIXTURE)
            rc = parity.main(["--base-style-guide", str(fixture), "--report"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
