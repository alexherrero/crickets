#!/usr/bin/env python3
"""Tests for the phase-command routing nudge (PLAN-efficiency-dispatch task 1, rescoped).

Task 0 found command (`kind: command`) frontmatter has no observable effect
on the turn's model — the prose nudge (`> **Recommended model for this
phase:**`) is the mechanism actually in use. This test computes each
command's expected model from `classify_work_type` + `routing_table.py`
(never a hand-typed literal in this file) and asserts the nudge text names
it — the anti-drift guard the rescoped task targets at the mechanism Task 0
proved live, not the one proved dead.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_COMMANDS = _ROOT / "src" / "development-lifecycle" / "commands"
# design.md re-homed to the design plugin (PLAN-wave-a-renames-2 task 4).
_DESIGN_COMMANDS = _ROOT / "src" / "design" / "commands"
_TA_SCRIPTS = _ROOT / "src" / "tokens" / "scripts"

_ROUTING_NUDGE_MARKER = "Recommended model for this phase:"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _TA_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cwt = _load("classify_work_type")

# command name -> what classify_work_type resolves it to; the test asserts
# the nudge text contains THAT resolution, not a value typed here twice.
_PHASE_COMMANDS = ("plan", "review", "design", "spec", "interview-me", "work", "bugfix")


class TestCommandRoutingNudgeMatchesTable(unittest.TestCase):
    def _nudge_text(self, command: str) -> str:
        # design/spec/interview-me re-homed to the design plugin (task 4).
        base = _DESIGN_COMMANDS if command in ("design", "spec", "interview-me") else _COMMANDS
        return (base / f"{command}.md").read_text(encoding="utf-8")

    def test_every_phase_command_has_a_classifiable_work_type(self):
        for command in _PHASE_COMMANDS:
            result = cwt.classify_work_type(role_name=command)
            self.assertEqual(
                result.tier_source, cwt.TIER_SOURCE_ROLE_MATCH,
                f"{command}: expected a table row, got {result.tier_source}",
            )

    def test_nudge_names_the_resolved_model(self):
        for command in _PHASE_COMMANDS:
            expected_model = cwt.classify_work_type(role_name=command).model_id
            text = self._nudge_text(command)
            self.assertIn(_ROUTING_NUDGE_MARKER, text, f"{command}.md: missing routing nudge line")
            self.assertIn(
                expected_model, text,
                f"{command}.md: nudge does not name the table-resolved model {expected_model!r}",
            )

    def test_work_and_bugfix_resolve_to_opusplan(self):
        for command in ("work", "bugfix"):
            self.assertEqual(cwt.classify_work_type(role_name=command).model_id, "opusplan")

    def test_authoring_commands_resolve_to_sonnet_5(self):
        for command in ("plan", "review", "design", "spec", "interview-me"):
            self.assertEqual(cwt.classify_work_type(role_name=command).model_id, "claude-sonnet-5")


if __name__ == "__main__":
    unittest.main()
