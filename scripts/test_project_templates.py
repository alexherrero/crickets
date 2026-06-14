#!/usr/bin/env python3
"""Tests for the github-projects board-sync templates (crickets #41, task 2).

Each template is a single-line markdown body fragment carrying `{{placeholder}}`
tokens. These are the six locked per-type templates (×lifecycle stages) from the
approved v4-41 design. The design's approved shapes are the golden expected sets
here; task 4's renderer fills them, so a drift between template and schema would
silently break the render path. Three invariants:

  1. The template set is exactly the 16 required files (no missing / no stray).
  2. Each file's `{{placeholder}}` set matches its per-type expected schema.
  3. Every placeholder partitions into the disjoint RENDERER / MODEL vocabulary
     (rule 6: deterministic helper owns structure; model owns human sentences).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_TEMPLATES = _ROOT / "src" / "github-projects" / "templates"

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")

# Per-type expected placeholder sets — the approved v4-41 shapes (golden).
EXPECTED: dict[str, set[str]] = {
    "task-kickoff": {"goal", "done_when"},
    "task-progress": {"date", "sha", "commit_url", "progress"},
    "task-closeout": {"outcome", "landed_link", "date"},
    "plan-kickoff": {"goal", "done_when"},
    "plan-progress": {"date", "task_link", "progress"},
    "plan-closeout": {"outcome", "shipped_link", "date"},
    "feature-kickoff": {"goal", "why_matters"},
    "feature-progress": {"date", "plan_goal", "version"},
    "feature-closeout": {"outcome", "release_links", "deferred"},
    "sub-feature-kickoff": {"goal", "why_matters"},
    "sub-feature-progress": {"date", "plan_goal", "version"},
    "sub-feature-closeout": {"outcome", "release_links", "deferred"},
    "version": {"about"},
    "backlog-item": {"what", "why_matters", "priority", "priority_reason"},
    "backlog-item-promotion": {"promoted_link", "date"},
    "idea": {"spark", "promote_target"},
}

# Rule 6 partition: the deterministic helper owns these (dates, SHAs, links it
# resolves from stable ids); the model supplies the human sentences in the rest.
# (The deferral link is no longer a template placeholder — _closeout_values folds
# the resolved `→ <link>` into the `deferred` value so the prose survives an
# absent/unmaterialized target; see project_sync.py DEFECT-1 fix.)
RENDERER = {
    "date", "sha", "commit_url", "landed_link", "shipped_link",
    "task_link", "version", "release_links", "promoted_link",
}
MODEL = {
    "goal", "done_when", "progress", "outcome", "why_matters", "plan_goal",
    "about", "what", "priority", "priority_reason", "spark", "promote_target",
    "deferred",
}


def _placeholders(name: str) -> set[str]:
    text = (_TEMPLATES / f"{name}.md").read_text(encoding="utf-8")
    return set(_PLACEHOLDER.findall(text))


class TestTemplateSet(unittest.TestCase):
    def test_exactly_the_required_files(self):
        found = {p.stem for p in _TEMPLATES.glob("*.md")}
        self.assertEqual(found, set(EXPECTED), "template file set drifted from schema")

    def test_no_non_markdown_files(self):
        extras = [p.name for p in _TEMPLATES.iterdir() if p.suffix != ".md"]
        self.assertEqual(extras, [], f"unexpected non-template files: {extras}")


class TestPlaceholderSchema(unittest.TestCase):
    def test_each_template_matches_expected(self):
        for name, expected in EXPECTED.items():
            with self.subTest(template=name):
                self.assertEqual(_placeholders(name), expected)

    def test_no_template_is_empty(self):
        for name in EXPECTED:
            with self.subTest(template=name):
                body = (_TEMPLATES / f"{name}.md").read_text(encoding="utf-8").strip()
                self.assertTrue(body, f"{name}.md is empty")


class TestVocabularyPartition(unittest.TestCase):
    def test_renderer_and_model_are_disjoint(self):
        self.assertEqual(RENDERER & MODEL, set())

    def test_partition_covers_every_placeholder(self):
        used = set().union(*EXPECTED.values())
        self.assertEqual(used, RENDERER | MODEL,
                         "a placeholder is used that isn't classified renderer/model")

    def test_every_placeholder_is_classified(self):
        vocab = RENDERER | MODEL
        for name, placeholders in EXPECTED.items():
            with self.subTest(template=name):
                unknown = placeholders - vocab
                self.assertEqual(unknown, set(), f"{name}: unclassified {unknown}")


if __name__ == "__main__":
    unittest.main()
