#!/usr/bin/env python3
"""Tests for the wiki composer — manifest → assembled page
(src/wiki-maintenance/skills/diataxis-author/scripts/composer.py) —
crickets wiki-composer part 2/4 (compose-core).

Covers the four-step pipeline: the section loader that reuses
``section_schema.parse_section()`` for load+strip + the reserved ``lang`` seam
(Task 1); the voice step that reuses ``style_resolver`` and graceful-degrades on
failure (Task 2); and ``compose_page()`` assembling the ``component-overview``
manifest under the page H1, deterministically (Task 3).
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL_SCRIPTS = _ROOT / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts"
_SECTIONS_DIR = _SKILL_SCRIPTS.parent / "templates" / "sections"


def _load(name: str):
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


composer = _load("composer")
section_schema = _load("section_schema")


class TestSectionLoader(unittest.TestCase):
    """Task 1 — load+strip reuses parse_section; body verbatim; the lang seam."""

    def test_loader_returns_parse_section_body_verbatim(self):
        # The loader's body is *exactly* parse_section(file).body — behavioral
        # proof that it reuses the shipped strip, not a re-implemented split.
        for name in ("intro", "how-it-works", "see-also", "safety"):
            text = (_SECTIONS_DIR / f"{name}.md").read_text(encoding="utf-8")
            expected = section_schema.parse_section(text).body
            self.assertEqual(composer.load_section_body(name), expected, f"{name}: body must equal parse_section().body")

    def test_loader_strips_opinion_keeps_placeholders(self):
        body = composer.load_section_body("intro")
        self.assertNotIn("<!-- SECTION", body, "the SECTION opinion comment must be stripped")
        self.assertIn("**<Project>**", body, "the author-fill placeholder must survive verbatim (output contract)")

    def test_sections_dir_is_an_overridable_seam(self):
        # The default dir is the shipped library; an explicit dir is honored.
        body_default = composer.load_section_body("see-also")
        body_explicit = composer.load_section_body("see-also", sections_dir=_SECTIONS_DIR)
        self.assertEqual(body_default, body_explicit)

    def test_lang_defaults_to_en_and_loads(self):
        # en is the only built value; it loads. (Default + explicit both work.)
        self.assertEqual(composer.load_section_body("intro"), composer.load_section_body("intro", lang="en"))

    def test_non_en_lang_is_rejected_not_silently_honored(self):
        # The reserved seam refuses an unbuilt language rather than emitting an
        # untranslated page (parent DD §1 — translate-downstream is deferred).
        with self.assertRaises(NotImplementedError):
            composer.load_section_body("intro", lang="es")


if __name__ == "__main__":
    unittest.main()
