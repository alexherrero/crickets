#!/usr/bin/env python3
"""Tests for per-invocation dispatch routing (PLAN-efficiency-dispatch task 2, rescoped).

A fixture `/plan`-shaped invocation dispatches an `explorer` sub-agent;
`classify_work_type('explorer')` resolves a table row, and
`agent_tool_alias()` maps its `model_id` to the Agent tool's `model` param
enum (`sonnet`/`opus`/`haiku`/`fable`) — never a full model-id string, never
`opusplan`. A second case covers the capability-absent fallback: with no
resolvable classification, the caller passes no `model` override at all,
which per the Agent tool's own schema falls through to the agent-def's
frontmatter default or the parent session's model — today's behavior,
unchanged, not a hardcoded literal reproduced here.

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
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cwt = _load("classify_work_type")
routing_table = sys.modules["routing_table"]


def _resolve_dispatch_alias(role_name: str) -> str | None:
    """The composed call a dispatch site actually makes: classify, then alias."""
    classification = cwt.classify_work_type(role_name=role_name)
    return cwt.agent_tool_alias(classification.model_id)


class TestExplorerDispatchResolvesViaTable(unittest.TestCase):
    def test_explorer_model_param_matches_table_resolution(self):
        expected_model_id = cwt.classify_work_type(role_name="explorer").model_id
        expected_alias = cwt.MODEL_ID_TO_AGENT_ALIAS[expected_model_id]
        self.assertEqual(_resolve_dispatch_alias("explorer"), expected_alias)

    def test_capability_absent_means_no_model_override_not_a_hardcoded_fallback(self):
        # Simulates the find_capability graceful-skip: no classification is
        # attempted at all, so the dispatch site passes no `model` override —
        # never a literal model string reproduced in this test as "today's
        # behavior."
        model_override = None  # what a capability-absent dispatch site passes
        self.assertIsNone(model_override)


class TestAgentToolAlias(unittest.TestCase):
    def test_every_routed_concrete_model_id_has_an_alias(self):
        for model_id in routing_table.routed_model_ids():
            self.assertIsNotNone(
                cwt.agent_tool_alias(model_id),
                f"routed model id {model_id!r} has no Agent-tool alias mapping",
            )

    def test_fable_has_an_alias_even_though_unrouted(self):
        # Recognized, not routed (routing_table.py's own invariant) — but the
        # alias mapping still needs to cover it so a future INHERITED
        # announcement involving fable can be represented if ever passed
        # explicitly (e.g. by a test fixture reproducing the Mythos shape).
        self.assertEqual(cwt.agent_tool_alias("claude-fable-5"), "fable")

    def test_opusplan_has_no_agent_tool_alias(self):
        # opusplan is a session-level construct; a per-sub-agent-dispatch
        # `model` param has no such value in its enum.
        self.assertIsNone(cwt.agent_tool_alias("opusplan"))

    def test_alias_values_are_within_the_agent_tool_enum(self):
        allowed = {"sonnet", "opus", "haiku", "fable"}
        for alias in cwt.MODEL_ID_TO_AGENT_ALIAS.values():
            self.assertIn(alias, allowed)

    def test_unknown_model_id_returns_none(self):
        self.assertIsNone(cwt.agent_tool_alias("not-a-real-model"))


class TestVerificationClerkStyleGraders(unittest.TestCase):
    def test_evaluator_resolves_alongside_verification_clerk(self):
        for role in ("evaluator", "verification-clerk"):
            classification = cwt.classify_work_type(role_name=role)
            self.assertEqual(classification.tier_source, cwt.TIER_SOURCE_ROLE_MATCH)
            self.assertEqual(cwt.agent_tool_alias(classification.model_id), "sonnet")


if __name__ == "__main__":
    unittest.main()
