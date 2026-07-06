#!/usr/bin/env python3
"""Tests for src/design/scripts/design_template.py + the abbreviated-design
template (crickets wave-c-design-and-conventions, task 2).

`/design` offers the abbreviated-design template as a selectable rung and
authoring through it produces a design doc matching today's AG shape-spec's
section structure.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "design" / "scripts"
_TEMPLATES = _ROOT / "src" / "design" / "templates"
_ABBREVIATED_TEMPLATE = _TEMPLATES / "abbreviated-design.md"
_ARCHITECTURE_TEMPLATE = _TEMPLATES / "architecture-hld.md"
_DESIGN_MD_COMMAND = _ROOT / "src" / "design" / "commands" / "design.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


design_template = _load("design_template_module", _SRC / "design_template.py")

_EXPECTED_ABBREVIATED_SECTIONS = [
    "Objective", "Overview", "Design", "Dependencies",
    "Risks & open questions", "References", "Amendment log",
]


class AbbreviatedTemplateShapeTests(unittest.TestCase):
    def test_template_declares_the_named_ag_shape_spec_sections(self):
        sections = design_template.extract_h2_sections(_ABBREVIATED_TEMPLATE)
        self.assertEqual(sections, _EXPECTED_ABBREVIATED_SECTIONS)

    def test_authoring_through_the_template_produces_a_matching_doc(self):
        # Simulates "authoring through the template": copy it to a target
        # path, fill each section's prompt with real prose (replacing the
        # italic prompt + HTML comment, exactly as /design author's own
        # Step 2 does for the full template), and confirm the authored
        # doc's section set still matches the template.
        with tempfile.TemporaryDirectory() as tmp:
            authored = Path(tmp) / "fixture-design.md"
            text = _ABBREVIATED_TEMPLATE.read_text(encoding="utf-8")
            # Strip the template's own scaffolding comment + italic prompts,
            # standing in for an author's real prose -- same section
            # headings survive, only the placeholder content changes.
            text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
            text = re.sub(r"^\*.*\*$", "Real authored content.", text, flags=re.MULTILINE)
            authored.write_text(text, encoding="utf-8")
            result = design_template.matches_template_sections(authored, _ABBREVIATED_TEMPLATE)
            self.assertTrue(result["matches"], result["missing"])

    def test_a_doc_missing_a_required_section_does_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            incomplete = Path(tmp) / "incomplete-design.md"
            text = _ABBREVIATED_TEMPLATE.read_text(encoding="utf-8")
            text = text.replace("## Risks & open questions\n", "")
            incomplete.write_text(text, encoding="utf-8")
            result = design_template.matches_template_sections(incomplete, _ABBREVIATED_TEMPLATE)
            self.assertFalse(result["matches"])
            self.assertIn("Risks & open questions", result["missing"])


class DesignCommandOffersRungsTests(unittest.TestCase):
    """/design offers the abbreviated-design template as a selectable rung."""

    def test_design_command_documents_a_rung_selector(self):
        text = _DESIGN_MD_COMMAND.read_text(encoding="utf-8")
        self.assertIn("--rung", text)
        self.assertIn("abbreviated-design.md", text)

    def test_design_command_documents_the_architecture_rung_too(self):
        text = _DESIGN_MD_COMMAND.read_text(encoding="utf-8")
        self.assertIn("architecture-hld.md", text)


if __name__ == "__main__":
    unittest.main()
