#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/fanout_announcement.py (PLAN-efficiency-dispatch task 4).

A fixture multi-agent dispatch prints exactly one announcement line per
dispatch group (role · count · model · tier source); tier source correctly
reports table row / agent frontmatter / UNCLASSIFIED-DEFAULT / INHERITED
per fixture case. An inheriting dispatch at a frontier-tier (T3/T4) session
model triggers a loud warning + a confirmation pause, never proceeds
silently. With token-audit absent, the announcement still prints, using
degraded frontmatter/inherited source labels — never silent.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


fa = _load("fanout_announcement")


class TestAnnouncementRendersOneLinePerGroup(unittest.TestCase):
    CASES = [
        ("explorer", 1, "claude-sonnet-5", fa.TIER_SOURCE_TABLE_ROW),
        ("worker", 1, "claude-sonnet-5", fa.TIER_SOURCE_AGENT_FRONTMATTER),
        ("totally-unknown-role", 1, "claude-sonnet-5", fa.TIER_SOURCE_UNCLASSIFIED_DEFAULT),
        ("some-role", 3, "claude-opus-4-8", fa.TIER_SOURCE_INHERITED),
    ]

    def test_each_fixture_case_renders_a_single_line_naming_all_four_fields(self):
        for role, count, model, tier_source in self.CASES:
            a = fa.DispatchAnnouncement(role=role, agent_count=count, model=model, tier_source=tier_source)
            line = fa.render_announcement(a)
            self.assertEqual(line.count("\n"), 0)
            self.assertIn(role, line)
            self.assertIn(str(count), line)
            self.assertIn(model, line)
            self.assertIn(tier_source, line)


class TestClassifierTierSourceMapping(unittest.TestCase):
    def test_role_match_maps_to_table_row(self):
        self.assertEqual(fa.announcement_tier_source("ROLE-MATCH"), fa.TIER_SOURCE_TABLE_ROW)

    def test_frontmatter_maps_to_agent_frontmatter(self):
        self.assertEqual(fa.announcement_tier_source("FRONTMATTER"), fa.TIER_SOURCE_AGENT_FRONTMATTER)

    def test_unclassified_default_passes_through(self):
        self.assertEqual(fa.announcement_tier_source("UNCLASSIFIED-DEFAULT"), fa.TIER_SOURCE_UNCLASSIFIED_DEFAULT)

    def test_none_maps_to_inherited(self):
        # No classifier consulted at all (e.g. token-audit absent) -> INHERITED,
        # never silent, never a made-up fifth label.
        self.assertEqual(fa.announcement_tier_source(None), fa.TIER_SOURCE_INHERITED)


class TestSilentInheritancePause(unittest.TestCase):
    def test_inherited_at_frontier_tier_requires_pause(self):
        for tier in ("T3-Architect", "T4-Deep"):
            self.assertTrue(fa.needs_inheritance_pause(fa.TIER_SOURCE_INHERITED, tier))

    def test_inherited_at_non_frontier_tier_does_not_pause(self):
        for tier in ("T0-Mechanical", "T1-Execute", "T2-Author", None):
            self.assertFalse(fa.needs_inheritance_pause(fa.TIER_SOURCE_INHERITED, tier))

    def test_non_inherited_source_never_pauses_regardless_of_tier(self):
        for source in (fa.TIER_SOURCE_TABLE_ROW, fa.TIER_SOURCE_AGENT_FRONTMATTER, fa.TIER_SOURCE_UNCLASSIFIED_DEFAULT):
            self.assertFalse(fa.needs_inheritance_pause(source, "T4-Deep"))

    def test_mythos_fixture_triggers_pause_not_silent_execution(self):
        # 112 agents, no explicit model, frontier-tier session — the Mythos shape.
        a = fa.DispatchAnnouncement(role="unnamed-fanout", agent_count=112, model="claude-fable-5", tier_source=fa.TIER_SOURCE_INHERITED)
        result = fa.announce_dispatch(a, session_tier="T4-Deep")
        self.assertTrue(result.pause_required)
        self.assertIsNotNone(result.warning)
        self.assertIn("Mythos", result.warning)
        self.assertIn("112", result.announcement_line)

    def test_announcement_always_present_even_when_pausing(self):
        a = fa.DispatchAnnouncement(role="x", agent_count=1, model="claude-fable-5", tier_source=fa.TIER_SOURCE_INHERITED)
        result = fa.announce_dispatch(a, session_tier="T3-Architect")
        self.assertTrue(result.announcement_line)

    def test_non_frontier_inheriting_dispatch_proceeds_without_pause_but_still_announces(self):
        a = fa.DispatchAnnouncement(role="x", agent_count=1, model="claude-sonnet-5", tier_source=fa.TIER_SOURCE_INHERITED)
        result = fa.announce_dispatch(a, session_tier="T1-Execute")
        self.assertFalse(result.pause_required)
        self.assertIsNone(result.warning)
        self.assertTrue(result.announcement_line)


class TestDegradedLabelsWithoutTokenAudit(unittest.TestCase):
    def test_degraded_dispatch_still_announces_never_silent(self):
        # token-audit absent: no classifier consulted, dispatch relied on the
        # agent-def's own frontmatter only.
        a = fa.DispatchAnnouncement(
            role="worker", agent_count=1, model="claude-sonnet-5",
            tier_source=fa.TIER_SOURCE_AGENT_FRONTMATTER,
        )
        result = fa.announce_dispatch(a)
        self.assertTrue(result.announcement_line)
        self.assertIn(fa.TIER_SOURCE_AGENT_FRONTMATTER, result.announcement_line)


if __name__ == "__main__":
    unittest.main()
