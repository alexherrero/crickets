#!/usr/bin/env python3
"""Structural spec for the developer-workflows phase-aware model routing (Part D task 1).

Locks the load-bearing facts:

  * The three role agent defs carry the correct `model:` frontmatter field:
    - worker     → claude-sonnet-4-6 (T1 executor; opusplan plan→execute split)
    - researcher → claude-sonnet-4-6 (lighter; read-only / research)
    - tech-lead  → claude-sonnet-4-6 (lighter; planning / authoring)
  * All five execution/planning commands contain a one-line routing nudge
    stating the recommended model (not just any mention of a model name):
    - work, bugfix     → Opus 4.8 nudge
    - plan, review, design → Sonnet 4.6 nudge

`generate.py check` separately proves `dist/` mirrors the source.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_AGENTS = _ROOT / "src" / "developer-workflows" / "agents"
_COMMANDS = _ROOT / "src" / "developer-workflows" / "commands"

sys.path.insert(0, str(_HERE))
from src_model import read_frontmatter  # noqa: E402

_ROUTING_NUDGE_MARKER = "Recommended model for this phase:"

_AGENT_ROUTING = {
    "worker": "claude-sonnet-4-6",
    "researcher": "claude-sonnet-4-6",
    "tech-lead": "claude-sonnet-4-6",
}

_COMMAND_ROUTING = {
    "work": "claude-opus-4-8",
    "bugfix": "claude-opus-4-8",
    "plan": "claude-sonnet-4-6",
    "review": "claude-sonnet-4-6",
    "design": "claude-sonnet-4-6",
}


class TestAgentModelFrontmatter(unittest.TestCase):
    """Each role agent def declares the correct model: field."""

    def _fm(self, name: str) -> dict:
        return read_frontmatter(_AGENTS / f"{name}.md") or {}

    def test_worker_model_is_sonnet(self):
        fm = self._fm("worker")
        self.assertEqual(
            fm.get("model"), "claude-sonnet-4-6",
            "worker.md: expected model: claude-sonnet-4-6 (T1 executor; opusplan plan→execute split)",
        )

    def test_researcher_model_is_sonnet(self):
        fm = self._fm("researcher")
        self.assertEqual(
            fm.get("model"), "claude-sonnet-4-6",
            "researcher.md: expected model: claude-sonnet-4-6 (read-only research)",
        )

    def test_tech_lead_model_is_sonnet(self):
        fm = self._fm("tech-lead")
        self.assertEqual(
            fm.get("model"), "claude-sonnet-4-6",
            "tech-lead.md: expected model: claude-sonnet-4-6 (planning/authoring)",
        )

    def test_all_routing_models_match_policy(self):
        for name, expected in _AGENT_ROUTING.items():
            with self.subTest(agent=name):
                fm = self._fm(name)
                self.assertEqual(
                    fm.get("model"), expected,
                    f"{name}.md: expected model: {expected}",
                )


class TestCommandRoutingNudge(unittest.TestCase):
    """Each command prompt contains a routing nudge line naming the correct model."""

    def _text(self, name: str) -> str:
        return (_COMMANDS / f"{name}.md").read_text(encoding="utf-8")

    def _assert_nudge(self, name: str, expected_model: str) -> None:
        text = self._text(name)
        self.assertIn(
            _ROUTING_NUDGE_MARKER, text,
            f"{name}.md: missing routing nudge line '{_ROUTING_NUDGE_MARKER}'",
        )
        self.assertIn(
            expected_model, text,
            f"{name}.md: routing nudge present but does not name expected model {expected_model!r}",
        )

    def test_work_nudge_is_opus(self):
        self._assert_nudge("work", "claude-opus-4-8")

    def test_bugfix_nudge_is_opus(self):
        self._assert_nudge("bugfix", "claude-opus-4-8")

    def test_plan_nudge_is_sonnet(self):
        self._assert_nudge("plan", "claude-sonnet-4-6")

    def test_review_nudge_is_sonnet(self):
        self._assert_nudge("review", "claude-sonnet-4-6")

    def test_design_nudge_is_sonnet(self):
        self._assert_nudge("design", "claude-sonnet-4-6")

    def test_all_command_nudges_match_policy(self):
        for name, expected in _COMMAND_ROUTING.items():
            with self.subTest(command=name):
                self._assert_nudge(name, expected)


if __name__ == "__main__":
    unittest.main()
