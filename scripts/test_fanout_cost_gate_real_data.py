#!/usr/bin/env python3
"""PLAN-wave-d-tokens-and-privacy task 2 / PLAN-observability-ledger tasks
1 + 3: confirm the fan-out cost gate now has real data.

Before the writer existed: fanout_cost_gate.estimate_per_agent_cost() always
took the fallback path (pricing.cost_usd over a fixed usage profile) --
there was no writer, so observed_records was always empty in practice.
After: a real session close appends a `session-cost` telemetry event via
session_cost_writer.capture_session_cost(), and session_cost_reader.
load_observed_records() reads that event log back into the exact shape
estimate_per_agent_cost() consumes -- so the SAME code, called with real
data, now takes the observed-average path instead of the fallback.

**Retargeted (PLAN-observability-ledger tasks 1 and 3).** Both the write
side (task 1) and the read side (task 3) now target the device-local event
log instead of the vault -- this file routes through the real, repointed
`session_cost_reader.py`, not a manual JSON parse.

This test asserts the CODE PATH taken (which branch inside
estimate_per_agent_cost fired), not merely that the gate ran without error --
per the plan's own verification wording.

stdlib only -- no pytest.
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
_SRC = _ROOT / "src" / "tokens" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


fcg = _load("fanout_cost_gate_realdata_test", _SRC / "fanout_cost_gate.py")
pricing = sys.modules["pricing"]
writer = _load("session_cost_writer_for_gate_test", _SRC / "session_cost_writer.py")
reader = _load("session_cost_reader_for_gate_test", _SRC / "session_cost_reader.py")


def _fixture_transcript(tmp: Path, model: str, cost_shape: dict) -> Path:
    line = json.dumps({
        "type": "assistant", "timestamp": "2026-07-06T10:00:00Z",
        "message": {"model": model, "usage": cost_shape},
    })
    p = tmp / "session.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    return p


class BeforeWriterFallbackPathTests(unittest.TestCase):
    """No observed data -> the fallback (pricing-profile) path fires."""

    def test_empty_observed_records_takes_fallback_path(self):
        est = fcg.estimate_per_agent_cost("claude-sonnet-5", observed_records=[])
        expected_fallback = pricing.cost_usd(fcg.DEFAULT_AGENT_USAGE_PROFILE, "claude-sonnet-5")
        self.assertAlmostEqual(est, expected_fallback, places=6)

    def test_no_matching_model_in_observed_records_takes_fallback_path(self):
        # Records exist, but none for the dispatched model -> still fallback.
        records = [{"model": "claude-opus-4-8", "cost_usd": 9.99}]
        est = fcg.estimate_per_agent_cost("claude-sonnet-5", observed_records=records)
        expected_fallback = pricing.cost_usd(fcg.DEFAULT_AGENT_USAGE_PROFILE, "claude-sonnet-5")
        self.assertAlmostEqual(est, expected_fallback, places=6)
        self.assertNotAlmostEqual(est, 9.99, places=2)

    def test_no_events_yet_yields_empty_records_and_gate_falls_back(self):
        # An event log directory with nothing in it yet -- the "before any
        # real session" state.
        tmp = tempfile.TemporaryDirectory()
        try:
            telemetry_root = Path(tmp.name) / "telemetry"
            telemetry_root.mkdir()
            records = reader.load_observed_records(telemetry_root=telemetry_root)
            self.assertEqual(records, [])
            est = fcg.estimate_per_agent_cost("claude-sonnet-5", observed_records=records)
            expected_fallback = pricing.cost_usd(fcg.DEFAULT_AGENT_USAGE_PROFILE, "claude-sonnet-5")
            self.assertAlmostEqual(est, expected_fallback, places=6)
        finally:
            tmp.cleanup()


class AfterWriterRealAveragePathTests(unittest.TestCase):
    """A genuine session-cost event lands, gets read back, and the gate's
    estimate now reflects it -- not the fallback profile."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.telemetry_root = self.tmp / "telemetry"

    def tearDown(self):
        self._tmp.cleanup()

    def test_gate_estimate_reflects_real_captured_session(self):
        # 1. A real session closes; the writer captures its cost.
        transcript = _fixture_transcript(
            self.tmp, "claude-sonnet-5",
            {"input_tokens": 1_000_000, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 0},
        )
        # Chosen so cost_usd is unambiguously distinct from the fallback
        # profile's estimate (1M input tokens @ $2/MTok = $2.00 flat).
        written = writer.capture_session_cost(
            transcript, telemetry_root=self.telemetry_root, root=self.tmp,
        )
        self.assertEqual(len(written), 1)

        # 2. Load that real record back.
        records = reader.load_observed_records(telemetry_root=self.telemetry_root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["model"], "claude-sonnet-5")
        self.assertAlmostEqual(records[0]["cost_usd"], 2.00, places=2)

        # 3. The gate, given those records, takes the REAL-AVERAGE path --
        #    not DEFAULT_AGENT_USAGE_PROFILE's fallback estimate.
        est = fcg.estimate_per_agent_cost("claude-sonnet-5", observed_records=records)
        fallback = pricing.cost_usd(fcg.DEFAULT_AGENT_USAGE_PROFILE, "claude-sonnet-5")
        self.assertAlmostEqual(est, 2.00, places=2)
        self.assertNotAlmostEqual(est, fallback, places=2)

    def test_gate_result_end_to_end_uses_observed_cost(self):
        transcript = _fixture_transcript(
            self.tmp, "claude-opus-4-8",
            {"input_tokens": 1_000_000, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 0},
        )
        writer.capture_session_cost(transcript, telemetry_root=self.telemetry_root, root=self.tmp)
        records = reader.load_observed_records(telemetry_root=self.telemetry_root)

        result = fcg.fanout_cost_gate(3, "claude-opus-4-8", observed_records=records)
        # 3 agents x $5.00/agent (1M input tokens @ $5/MTok) = $15.00.
        self.assertAlmostEqual(result.estimated_cost_usd, 15.00, places=2)


if __name__ == "__main__":
    unittest.main()
