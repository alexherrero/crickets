#!/usr/bin/env python3
"""Tests for status_line_meter.py's budget readout (PLAN-efficiency-automation task 5).

Fixture session-cost records span a 5h window and a week; the pure
`budget_readout()` renders the correct window/weekly sums against a
configured ceiling; no ceiling configured -> "" (omitted, never an error
string). `_read_budget_ceiling()` / `_read_session_cost_records()` are the
impure edges (env vars, a JSONL log path) and are tested separately for
graceful-degradation on missing config/file.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "tokens" / "scripts"


def _load_slm():
    spec = importlib.util.spec_from_file_location("status_line_meter", _SRC / "status_line_meter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


slm = _load_slm()

_NOW = 1_800_000_000.0  # fixed "now" epoch for deterministic window math
_5H = 5 * 3600
_WEEK = 7 * 24 * 3600


def _rec(cost_usd, age_seconds):
    return {"model": "claude-sonnet-5", "tokens_by_kind": {}, "cost_usd": cost_usd, "timestamp": _NOW - age_seconds}


class TestBudgetReadoutPure(unittest.TestCase):
    """budget_readout() over fixture records + a fixed 'now'."""

    RECORDS = [
        _rec(0.10, age_seconds=60),           # inside 5h window
        _rec(0.20, age_seconds=_5H - 1),       # inside 5h window (just barely)
        _rec(0.05, age_seconds=_5H + 60),      # outside 5h, inside week
        _rec(0.30, age_seconds=_WEEK - 1),     # inside week (just barely)
        _rec(0.15, age_seconds=_WEEK + 60),    # outside week entirely
    ]

    def test_no_ceiling_configured_omits_readout(self):
        self.assertEqual(slm.budget_readout(self.RECORDS, None, _NOW), "")
        self.assertEqual(slm.budget_readout(self.RECORDS, {}, _NOW), "")

    def test_window_and_weekly_sums_against_ceiling(self):
        ceiling = {"window_5h": 1.00, "weekly": 5.00}
        readout = slm.budget_readout(self.RECORDS, ceiling, _NOW)
        # window: 0.10 + 0.20 = 0.30 ; weekly: 0.10+0.20+0.05+0.30 = 0.65
        self.assertIn("5h $0.30/$1.00", readout)
        self.assertIn("wk $0.65/$5.00", readout)

    def test_renders_only_configured_ceiling_keys(self):
        window_only = slm.budget_readout(self.RECORDS, {"window_5h": 1.00}, _NOW)
        self.assertIn("5h", window_only)
        self.assertNotIn("wk", window_only)

        weekly_only = slm.budget_readout(self.RECORDS, {"weekly": 5.00}, _NOW)
        self.assertNotIn("5h", weekly_only)
        self.assertIn("wk", weekly_only)

    def test_empty_records_with_ceiling_renders_zero_sums(self):
        readout = slm.budget_readout([], {"window_5h": 1.00, "weekly": 5.00}, _NOW)
        self.assertIn("$0.00/$1.00", readout)
        self.assertIn("$0.00/$5.00", readout)

    def test_malformed_record_is_skipped_not_an_error(self):
        malformed = [{"cost_usd": "not-a-number", "timestamp": _NOW}, {"cost_usd": 0.10}]
        readout = slm.budget_readout(malformed, {"window_5h": 1.00}, _NOW)
        self.assertIn("$0.00/$1.00", readout)


class TestReadBudgetCeiling(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("CRICKETS_BUDGET_5H", "CRICKETS_BUDGET_WEEKLY")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_unconfigured_returns_none(self):
        self.assertIsNone(slm._read_budget_ceiling())

    def test_configured_returns_dict(self):
        os.environ["CRICKETS_BUDGET_5H"] = "10"
        os.environ["CRICKETS_BUDGET_WEEKLY"] = "50"
        ceiling = slm._read_budget_ceiling()
        self.assertEqual(ceiling, {"window_5h": 10.0, "weekly": 50.0})

    def test_garbage_value_returns_none_not_an_error(self):
        os.environ["CRICKETS_BUDGET_5H"] = "not-a-number"
        self.assertIsNone(slm._read_budget_ceiling())


class TestReadSessionCostRecords(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        self.assertEqual(slm._read_session_cost_records(Path("/nonexistent/nowhere.jsonl")), [])

    def test_reads_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "log.jsonl"
            p.write_text(
                json.dumps({"cost_usd": 0.1, "timestamp": 100}) + "\n"
                + json.dumps({"cost_usd": 0.2, "timestamp": 200}) + "\n"
            )
            records = slm._read_session_cost_records(p)
            self.assertEqual(len(records), 2)

    def test_malformed_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "log.jsonl"
            p.write_text("not json\n" + json.dumps({"cost_usd": 0.1, "timestamp": 100}) + "\n")
            records = slm._read_session_cost_records(p)
            self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
