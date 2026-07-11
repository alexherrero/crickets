#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/fanout_announcement.py (PLAN-efficiency-dispatch task 4;
fleet cost-gate wiring added by the fanout-cost-gate-wiring plan).

A fixture multi-agent dispatch prints exactly one announcement line per
dispatch group (role · count · model · tier source); tier source correctly
reports table row / agent frontmatter / UNCLASSIFIED-DEFAULT / INHERITED
per fixture case. An inheriting dispatch at a frontier-tier (T3/T4) session
model triggers a loud warning + a confirmation pause, never proceeds
silently. With token-audit absent, the announcement still prints, using
degraded frontmatter/inherited source labels — never silent.

A fleet-sized dispatch (agent_count >= 4) also runs the fanout cost gate;
a blocked result surfaces via the same `pause_required` flag, independent of
(and coexisting with) the inheritance-pause mechanism. Graceful-skip when
the tokens capability is unresolvable.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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


class TestCostGateThreshold(unittest.TestCase):
    """`needs_cost_gate_pause` only consults the gate at agent_count >= 4."""

    def test_below_threshold_never_invokes_the_gate(self):
        with mock.patch.object(fa, "run_fanout_cost_gate") as gate:
            paused, msg = fa.needs_cost_gate_pause(3, "claude-opus-4-8")
        gate.assert_not_called()
        self.assertFalse(paused)
        self.assertIsNone(msg)

    def test_at_threshold_invokes_the_gate_with_count_and_model(self):
        fake_result = SimpleNamespace(proceed=False, message="CONFIRM-OR-BLOCK: fixture")
        with mock.patch.object(fa, "run_fanout_cost_gate", return_value=fake_result) as gate:
            paused, msg = fa.needs_cost_gate_pause(4, "claude-opus-4-8")
        gate.assert_called_once_with(4, "claude-opus-4-8")
        self.assertTrue(paused)
        self.assertEqual(msg, fake_result.message)

    def test_above_threshold_also_invokes_the_gate(self):
        fake_result = SimpleNamespace(proceed=True, message="")
        with mock.patch.object(fa, "run_fanout_cost_gate", return_value=fake_result) as gate:
            paused, msg = fa.needs_cost_gate_pause(50, "claude-sonnet-5")
        gate.assert_called_once_with(50, "claude-sonnet-5")
        self.assertFalse(paused)
        self.assertIsNone(msg)


class TestCostGateBlockSurfacesViaPauseRequired(unittest.TestCase):
    def test_blocked_gate_result_sets_pause_required_and_cost_gate_warning(self):
        a = fa.DispatchAnnouncement(role="fleet", agent_count=6, model="claude-opus-4-8", tier_source=fa.TIER_SOURCE_TABLE_ROW)
        fake_result = SimpleNamespace(proceed=False, message="CONFIRM-OR-BLOCK: 6 agents over budget")
        with mock.patch.object(fa, "run_fanout_cost_gate", return_value=fake_result):
            result = fa.announce_dispatch(a)
        self.assertTrue(result.pause_required)
        self.assertEqual(result.cost_gate_warning, fake_result.message)
        self.assertIsNone(result.warning)  # not an inheritance pause

    def test_proceeding_gate_result_does_not_pause(self):
        a = fa.DispatchAnnouncement(role="fleet", agent_count=6, model="claude-sonnet-5", tier_source=fa.TIER_SOURCE_TABLE_ROW)
        fake_result = SimpleNamespace(proceed=True, message="")
        with mock.patch.object(fa, "run_fanout_cost_gate", return_value=fake_result):
            result = fa.announce_dispatch(a)
        self.assertFalse(result.pause_required)
        self.assertIsNone(result.cost_gate_warning)


class TestCostGateGracefulSkip(unittest.TestCase):
    """`tokens` capability unresolvable -> the gate is simply not consulted;
    announce_dispatch() behaves exactly as it did before this wiring."""

    def test_needs_cost_gate_pause_gracefully_skips_when_gate_unresolvable(self):
        with mock.patch.object(fa, "run_fanout_cost_gate", return_value=None):
            paused, msg = fa.needs_cost_gate_pause(50, "claude-opus-4-8")
        self.assertFalse(paused)
        self.assertIsNone(msg)

    def test_run_fanout_cost_gate_returns_none_when_capability_absent(self):
        with mock.patch.object(fa, "_HAS_COST_GATE", False):
            result = fa.run_fanout_cost_gate(50, "claude-opus-4-8")
        self.assertIsNone(result)

    def test_announce_dispatch_unaffected_by_fleet_size_when_gate_absent(self):
        a = fa.DispatchAnnouncement(role="fleet", agent_count=50, model="claude-opus-4-8", tier_source=fa.TIER_SOURCE_TABLE_ROW)
        with mock.patch.object(fa, "_HAS_COST_GATE", False):
            result = fa.announce_dispatch(a)
        self.assertFalse(result.pause_required)
        self.assertIsNone(result.cost_gate_warning)
        self.assertTrue(result.announcement_line)


class TestCostGateDiscoveryCascade(unittest.TestCase):
    """Mirrors escalation_tripwire.py's own discovery-cascade test shape."""

    def test_falls_back_to_same_repo_path_when_opinion_resolver_unresolvable(self):
        with mock.patch.object(fa, "_find_opinion_resolver", return_value=None):
            result = fa._resolve_tokens_scripts_dir()
        self.assertIsNotNone(result)
        self.assertTrue(result.is_dir())
        self.assertEqual(result.name, "scripts")
        self.assertEqual(result.parent.name, "tokens")

    def test_registry_lookup_and_same_repo_fallback_agree(self):
        resolved = fa._resolve_tokens_scripts_dir()
        self.assertEqual(resolved, fa._FALLBACK_TOKENS_SCRIPTS)

    def test_real_tokens_capability_wires_end_to_end_in_this_repo(self):
        # No mocking -- proves the actual cross-plugin discovery + call works,
        # since src/tokens/scripts genuinely exists in this repo.
        self.assertTrue(fa._HAS_COST_GATE)
        result = fa.run_fanout_cost_gate(112, "claude-fable-5")
        self.assertIsNotNone(result)
        self.assertFalse(result.proceed)


class TestBothPauseMechanismsCoexist(unittest.TestCase):
    """Inheritance-pause and cost-gate-pause are independent: either, both,
    or neither can fire on a given dispatch, and neither masks the other."""

    def test_both_fire_together_without_masking(self):
        a = fa.DispatchAnnouncement(role="unnamed-fanout", agent_count=112, model="claude-fable-5", tier_source=fa.TIER_SOURCE_INHERITED)
        fake_result = SimpleNamespace(proceed=False, message="CONFIRM-OR-BLOCK: fixture")
        with mock.patch.object(fa, "run_fanout_cost_gate", return_value=fake_result):
            result = fa.announce_dispatch(a, session_tier="T4-Deep")
        self.assertTrue(result.pause_required)
        self.assertIsNotNone(result.warning)
        self.assertIn("Mythos", result.warning)
        self.assertIsNotNone(result.cost_gate_warning)
        self.assertEqual(result.cost_gate_warning, fake_result.message)

    def test_only_inheritance_fires_when_fleet_is_small(self):
        a = fa.DispatchAnnouncement(role="x", agent_count=1, model="claude-fable-5", tier_source=fa.TIER_SOURCE_INHERITED)
        result = fa.announce_dispatch(a, session_tier="T3-Architect")
        self.assertTrue(result.pause_required)
        self.assertIsNotNone(result.warning)
        self.assertIsNone(result.cost_gate_warning)

    def test_only_cost_gate_fires_when_not_inheriting(self):
        a = fa.DispatchAnnouncement(role="fleet", agent_count=6, model="claude-opus-4-8", tier_source=fa.TIER_SOURCE_TABLE_ROW)
        fake_result = SimpleNamespace(proceed=False, message="CONFIRM-OR-BLOCK: fixture")
        with mock.patch.object(fa, "run_fanout_cost_gate", return_value=fake_result):
            result = fa.announce_dispatch(a)
        self.assertTrue(result.pause_required)
        self.assertIsNone(result.warning)
        self.assertIsNotNone(result.cost_gate_warning)

    def test_neither_fires_on_a_small_non_inheriting_dispatch(self):
        a = fa.DispatchAnnouncement(role="x", agent_count=1, model="claude-sonnet-5", tier_source=fa.TIER_SOURCE_TABLE_ROW)
        result = fa.announce_dispatch(a, session_tier="T4-Deep")
        self.assertFalse(result.pause_required)
        self.assertIsNone(result.warning)
        self.assertIsNone(result.cost_gate_warning)

    def test_no_regression_existing_inheritance_only_dispatch_still_works(self):
        # Same shape as TestSilentInheritancePause's own non-frontier case,
        # re-asserted here with the new cost_gate_warning field checked too.
        a = fa.DispatchAnnouncement(role="x", agent_count=1, model="claude-sonnet-5", tier_source=fa.TIER_SOURCE_INHERITED)
        result = fa.announce_dispatch(a, session_tier="T1-Execute")
        self.assertFalse(result.pause_required)
        self.assertIsNone(result.warning)
        self.assertIsNone(result.cost_gate_warning)
        self.assertTrue(result.announcement_line)


if __name__ == "__main__":
    unittest.main()
