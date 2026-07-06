#!/usr/bin/env python3
"""Tests for staged per-task tier hints (PLAN-efficiency-dispatch task 6).

A staged task declaring a known work-type gets its tier-hint field
populated by `classify_work_type.render_tier_hint()`, never left blank or
hand-typed — the same anti-drift discipline task 1 applied to command
nudges, applied here to plan-authoring.

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
_PLAN_MD = _ROOT / "src" / "development-lifecycle" / "commands" / "plan.md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cwt = _load("classify_work_type")


class TestRenderTierHint(unittest.TestCase):
    def test_known_work_type_renders_tier_model_effort(self):
        hint = cwt.render_tier_hint("worker-build")
        self.assertIn("T1-Execute", hint)
        self.assertIn("opusplan", hint)
        self.assertIn("medium", hint)

    def test_hint_names_the_tier_source(self):
        hint = cwt.render_tier_hint("mechanical-log-scraping")
        self.assertIn("tier-source", hint)
        self.assertIn(cwt.TIER_SOURCE_ROLE_MATCH, hint)

    def test_unmatched_work_type_renders_the_unclassified_default_not_blank(self):
        hint = cwt.render_tier_hint("not-a-real-work-type")
        self.assertTrue(hint)
        self.assertIn(cwt.TIER_SOURCE_UNCLASSIFIED_DEFAULT, hint)

    def test_never_returns_empty_string(self):
        for work_type in ("worker-build", "explorer", "garbage-input", ""):
            self.assertTrue(cwt.render_tier_hint(work_type))


class TestPlanTemplateDocumentsTheField(unittest.TestCase):
    def test_plan_md_template_shows_the_optional_tier_hint_field(self):
        text = _PLAN_MD.read_text(encoding="utf-8")
        self.assertIn("Tier hint", text)
        self.assertIn("render_tier_hint", text)


if __name__ == "__main__":
    unittest.main()
