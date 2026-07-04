#!/usr/bin/env python3
"""Tests for src/token-audit/scripts/classify_work_type.py (PLAN-efficiency-automation task 2).

Three-step resolution: persona-declared -> role-name match -> the fixed
UNCLASSIFIED-DEFAULT. The fuzz case is the direct Mythos-incident guard: an
unmatched role must never resolve to claude-fable-5 or a session-inherited
value, over a wide random sample, not just the seeded cases.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import random
import string
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


cwt = _load("classify_work_type")
routing_table = sys.modules["routing_table"]


class TestPersonaDeclaredWinsOutright(unittest.TestCase):
    def test_declared_resolves_without_consulting_role_table(self):
        # role_name deliberately garbage — if it were consulted, this would
        # fall through to UNCLASSIFIED-DEFAULT instead of the declared value.
        result = cwt.classify_work_type(
            role_name="not-a-real-role-xyz",
            declared={"model": "claude-opus-4-8", "effort": "max", "tier": "T3-Architect"},
        )
        self.assertEqual(result.model_id, "claude-opus-4-8")
        self.assertEqual(result.effort, "max")
        self.assertEqual(result.tier, "T3-Architect")
        self.assertEqual(result.tier_source, cwt.TIER_SOURCE_FRONTMATTER)

    def test_declared_wins_even_when_role_name_also_matches(self):
        # role_name matches "explorer" (-> mechanical-log-scraping), but a
        # declaration is present, so the role-name table must not be
        # consulted at all — the declared value must win, unmodified.
        result = cwt.classify_work_type(
            role_name="explorer",
            declared={"model": "claude-opus-4-8", "effort": "high", "tier": "T2-Author"},
        )
        self.assertEqual(result.model_id, "claude-opus-4-8")
        self.assertEqual(result.tier_source, cwt.TIER_SOURCE_FRONTMATTER)
        self.assertIsNone(result.work_type)


class TestRoleNameMatch(unittest.TestCase):
    ROLE_NAMES = (
        "explorer",
        "adversarial-reviewer",
        "cross-model-reviewer",
        "documenter",
        "verification-clerk",
    )

    def test_every_ad_hoc_role_resolves_to_a_table_row(self):
        for role in self.ROLE_NAMES:
            result = cwt.classify_work_type(role_name=role)
            self.assertEqual(result.tier_source, cwt.TIER_SOURCE_ROLE_MATCH)
            self.assertIn(result.work_type, routing_table.TABLE)
            row = routing_table.TABLE[result.work_type]
            self.assertEqual(result.tier, row.tier)
            self.assertEqual(result.model_id, row.model_id)
            self.assertEqual(result.effort, row.effort)

    def test_work_type_key_matches_directly(self):
        result = cwt.classify_work_type(role_name="worker-build")
        self.assertEqual(result.tier_source, cwt.TIER_SOURCE_ROLE_MATCH)
        self.assertEqual(result.work_type, "worker-build")


class TestUnclassifiedDefault(unittest.TestCase):
    def test_unmatched_role_resolves_to_fixed_default(self):
        result = cwt.classify_work_type(role_name="totally-unknown-role")
        self.assertEqual(result.tier, cwt.UNCLASSIFIED_DEFAULT_TIER)
        self.assertEqual(result.model_id, cwt.UNCLASSIFIED_DEFAULT_MODEL_ID)
        self.assertEqual(result.effort, cwt.UNCLASSIFIED_DEFAULT_EFFORT)
        self.assertEqual(result.tier_source, cwt.TIER_SOURCE_UNCLASSIFIED_DEFAULT)

    def test_no_input_at_all_resolves_to_fixed_default(self):
        result = cwt.classify_work_type()
        self.assertEqual(result.tier_source, cwt.TIER_SOURCE_UNCLASSIFIED_DEFAULT)

    def test_fuzz_never_resolves_to_fable_or_inherited(self):
        rng = random.Random(0)
        known = set(cwt.ROLE_TO_WORK_TYPE) | set(routing_table.TABLE)
        for _ in range(100):
            length = rng.randint(1, 20)
            candidate = "".join(rng.choice(string.ascii_letters + "-_") for _ in range(length))
            if candidate in known:
                continue
            result = cwt.classify_work_type(role_name=candidate)
            self.assertNotEqual(result.model_id, "claude-fable-5")
            self.assertEqual(result.tier_source, cwt.TIER_SOURCE_UNCLASSIFIED_DEFAULT)
            self.assertEqual(result.model_id, cwt.UNCLASSIFIED_DEFAULT_MODEL_ID)


if __name__ == "__main__":
    unittest.main()
