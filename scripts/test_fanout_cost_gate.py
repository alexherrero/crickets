#!/usr/bin/env python3
"""Tests for src/token-audit/scripts/fanout_cost_gate.py (PLAN-efficiency-automation task 6).

A fixture dispatch of N agents at a known model: the gate computes
N x per_agent_cost and compares against the configured budget share.
Over-budget -> confirm-or-block output states model x agent-count x
estimated cost verbatim, plus an explicit "local estimate, not real
Anthropic quota" disclaimer. Under-budget -> proceeds silently, no output.
The Mythos fixture (112 agents, Fable-priced) blocks by default.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "tokens" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


fcg = _load("fanout_cost_gate")
pricing = sys.modules["pricing"]


class TestFanoutCostGateKnownCost(unittest.TestCase):
    """N agents at a known per-agent cost — the direct fixture shape."""

    def test_over_budget_blocks_with_verbatim_details(self):
        result = fcg.fanout_cost_gate(
            10, "claude-opus-4-8", per_agent_cost=1.00, budget_share_usd=5.00,
        )
        self.assertFalse(result.proceed)
        self.assertEqual(result.estimated_cost_usd, 10.00)
        self.assertIn("10", result.message)
        self.assertIn("claude-opus-4-8", result.message)
        self.assertIn("$10.00", result.message)

    def test_message_states_local_estimate_disclaimer(self):
        result = fcg.fanout_cost_gate(
            10, "claude-opus-4-8", per_agent_cost=1.00, budget_share_usd=5.00,
        )
        self.assertIn("LOCAL ESTIMATE", result.message)
        self.assertIn("not Anthropic's actual remaining quota", result.message)

    def test_under_budget_proceeds_silently(self):
        result = fcg.fanout_cost_gate(
            3, "claude-sonnet-5", per_agent_cost=0.10, budget_share_usd=5.00,
        )
        self.assertTrue(result.proceed)
        self.assertEqual(result.message, "")
        self.assertAlmostEqual(result.estimated_cost_usd, 0.30, places=6)

    def test_exactly_at_budget_proceeds_silently(self):
        result = fcg.fanout_cost_gate(
            5, "claude-sonnet-5", per_agent_cost=1.00, budget_share_usd=5.00,
        )
        self.assertTrue(result.proceed)
        self.assertEqual(result.message, "")


class TestEstimatePerAgentCost(unittest.TestCase):
    def test_uses_observed_records_mean_when_present(self):
        records = [
            {"model": "claude-opus-4-8", "cost_usd": 1.00},
            {"model": "claude-opus-4-8", "cost_usd": 3.00},
            {"model": "claude-sonnet-5", "cost_usd": 0.05},  # different model, excluded
        ]
        est = fcg.estimate_per_agent_cost("claude-opus-4-8", observed_records=records)
        self.assertAlmostEqual(est, 2.00, places=6)

    def test_falls_back_to_pricing_profile_when_no_observed_records(self):
        est = fcg.estimate_per_agent_cost("claude-sonnet-5")
        expected = pricing.cost_usd(fcg.DEFAULT_AGENT_USAGE_PROFILE, "claude-sonnet-5")
        self.assertAlmostEqual(est, expected, places=6)


class TestMythosFixtureBlocksByDefault(unittest.TestCase):
    """The Mythos shape: 112 agents inheriting claude-fable-5, no budget config."""

    def test_112_fable_agents_blocks_with_default_budget_share(self):
        result = fcg.fanout_cost_gate(112, "claude-fable-5")
        self.assertFalse(result.proceed)
        self.assertIn("112", result.message)
        self.assertIn("claude-fable-5", result.message)
        self.assertIn("LOCAL ESTIMATE", result.message)

    def test_default_budget_share_is_a_finite_positive_number(self):
        self.assertGreater(fcg.DEFAULT_BUDGET_SHARE_USD, 0)


if __name__ == "__main__":
    unittest.main()
