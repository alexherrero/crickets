#!/usr/bin/env python3
"""Tests for src/token-audit/scripts/routing_table.py (PLAN-efficiency-automation task 1).

Every seeded work-type must resolve to (tier, model_id, effort); every
concrete (alias-resolved) model id in the table must be a key in pricing.py's
PRICING dict — the parity guard that keeps the routing table and the pricing
table from ever disagreeing about how a model's name is spelled.
`claude-fable-5` must be a recognized id that zero work-types route to (the
"recognized, not routed" invariant — see routing_table.py's module docstring).

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "token-audit" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pricing = _load("pricing")


routing_table = _load("routing_table")


class TestRoutingTable(unittest.TestCase):
    SEEDED_WORK_TYPES = (
        "research-adversarial-audit",
        "roadmap-architecture-priority",
        "author-roadmap-shaped",
        "author-transcription-shaped",
        "worker-build",
        "wiki-mechanical-plus",
        "mechanical-log-scraping",
    )

    def test_every_seeded_work_type_resolves_to_a_row(self):
        for wt in self.SEEDED_WORK_TYPES:
            row = routing_table.TABLE[wt]
            self.assertTrue(row.tier)
            self.assertTrue(row.model_id)
            self.assertTrue(row.effort)

    def test_every_model_id_is_a_pricing_key(self):
        pricing_keys = set(pricing.PRICING.keys())
        for wt, row in routing_table.TABLE.items():
            for concrete in routing_table.concrete_model_ids(row.model_id):
                self.assertIn(
                    concrete, pricing_keys,
                    f"{wt}: resolved model id {concrete!r} not in pricing.PRICING",
                )

    def test_fable_is_recognized_but_unrouted(self):
        self.assertIn("claude-fable-5", pricing.PRICING)
        self.assertIn("claude-fable-5", routing_table.RECOGNIZED_UNROUTED)
        self.assertIn("claude-fable-5", routing_table.all_recognized_model_ids())
        self.assertNotIn("claude-fable-5", routing_table.routed_model_ids())
        for row in routing_table.TABLE.values():
            self.assertNotEqual(row.model_id, "claude-fable-5")

    def test_opusplan_alias_resolves_to_opus_and_sonnet(self):
        row = routing_table.TABLE["worker-build"]
        self.assertEqual(row.model_id, "opusplan")
        self.assertEqual(
            set(routing_table.concrete_model_ids(row.model_id)),
            {"claude-opus-4-8", "claude-sonnet-5"},
        )

    def test_version_is_set(self):
        self.assertTrue(routing_table.VERSION)


if __name__ == "__main__":
    unittest.main()
