#!/usr/bin/env python3
"""PLAN-wave-d-tokens-and-privacy task 2: confirm the fan-out cost gate now
has real data.

Before task 1 (session_cost_writer.py): fanout_cost_gate.estimate_per_agent_
cost() always took the fallback path (pricing.cost_usd over a fixed usage
profile) -- there was no writer, so observed_records was always empty in
practice. After task 1: a real session close writes a `kind: session-cost`
vault entry via session_cost_writer.capture_session_cost(), and
session_cost_reader.load_observed_records() reads it back into the exact
shape estimate_per_agent_cost() consumes -- so the SAME code, called with
real data, now takes the observed-average path instead of the fallback.

This test asserts the CODE PATH taken (which branch inside
estimate_per_agent_cost fired), not merely that the gate ran without error --
per the plan's own verification wording.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "tokens" / "scripts"

_AGENTM_PATH_MARKERS = ("/agentm/harness/", "/agentm/scripts/")
_REAL_BRIDGE_SYS_PATH_MARKER = "/agentm/harness/skills/memory/scripts"


def _purge_real_bridge_sys_path():
    sys.path[:] = [p for p in sys.path if _REAL_BRIDGE_SYS_PATH_MARKER not in p]


def _purge_agentm_modules(pre_existing_names):
    for name, mod in list(sys.modules.items()):
        if name in pre_existing_names:
            continue
        f = getattr(mod, "__file__", None)
        if f and any(marker in f for marker in _AGENTM_PATH_MARKERS):
            del sys.modules[name]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


fcg = _load("fanout_cost_gate_realdata_test", _SRC / "fanout_cost_gate.py")
pricing = sys.modules["pricing"]
reader = _load("session_cost_reader_for_gate_test", _SRC / "session_cost_reader.py")
writer = _load("session_cost_writer_for_gate_test", _SRC / "session_cost_writer.py")
analyzer = sys.modules["analyzer"]


def _fixture_transcript(tmp: Path, model: str, cost_shape: dict) -> Path:
    import json
    line = json.dumps({
        "type": "assistant", "timestamp": "2026-07-06T10:00:00Z",
        "message": {"model": model, "usage": cost_shape},
    })
    p = tmp / "session.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    return p


class BeforeTask1FallbackPathTests(unittest.TestCase):
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

    def test_no_vault_yet_reader_returns_empty_and_gate_falls_back(self):
        # session_cost_reader against a vault with no session-cost entries
        # yet -- the "before task 1 accumulates any real session" state.
        tmp = tempfile.TemporaryDirectory()
        try:
            vault = Path(tmp.name) / "vault"
            vault.mkdir()
            records = reader.load_observed_records(vault, project="crickets")
            self.assertEqual(records, [])
            est = fcg.estimate_per_agent_cost("claude-sonnet-5", observed_records=records)
            expected_fallback = pricing.cost_usd(fcg.DEFAULT_AGENT_USAGE_PROFILE, "claude-sonnet-5")
            self.assertAlmostEqual(est, expected_fallback, places=6)
        finally:
            tmp.cleanup()


class AfterTask1RealAveragePathTests(unittest.TestCase):
    """Real-bridge: a genuine session-cost write lands, gets read back, and
    the gate's estimate now reflects it -- not the fallback profile."""

    @classmethod
    def setUpClass(cls):
        cls._pre_existing_modules = set(sys.modules)
        if writer.load_save_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-data test skipped")

    @classmethod
    def tearDownClass(cls):
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.vault = self.tmp / "vault"
        self.vault.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_gate_estimate_reflects_real_captured_session_after_task_1(self):
        # 1. A real session closes; task 1's writer captures its cost.
        transcript = _fixture_transcript(
            self.tmp, "claude-sonnet-5",
            {"input_tokens": 1_000_000, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 0},
        )
        # Chosen so cost_usd is unambiguously distinct from the fallback
        # profile's estimate (1M input tokens @ $2/MTok = $2.00 flat).
        written = writer.capture_session_cost(transcript, vault_path=self.vault, project="crickets")
        self.assertEqual(len(written), 1)

        # 2. task 2's reader loads that real record back.
        records = reader.load_observed_records(self.vault, project="crickets")
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
        writer.capture_session_cost(transcript, vault_path=self.vault, project="crickets")
        records = reader.load_observed_records(self.vault, project="crickets")

        result = fcg.fanout_cost_gate(3, "claude-opus-4-8", observed_records=records)
        # 3 agents x $5.00/agent (1M input tokens @ $5/MTok) = $15.00.
        self.assertAlmostEqual(result.estimated_cost_usd, 15.00, places=2)


if __name__ == "__main__":
    unittest.main()
