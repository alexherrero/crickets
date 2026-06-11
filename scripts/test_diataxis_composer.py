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

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

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
# Loaded here so sys.modules["style_resolver"] is this handle — composer's lazy
# `import style_resolver` binds the same object the voice tests patch.
style_resolver = _load("style_resolver")


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


class TestVoice(unittest.TestCase):
    """Task 2 — resolve voice reuses style_resolver; graceful-degrade like author_page()."""

    # A synthetic assembled page: an H1, a placeholder-bearing body, an H2 section.
    _PAGE = "# Sample Page\n\n**<Project>** is a thing.\n\n## How it works\n\nBody.\n"

    @staticmethod
    def _nonempty_style():
        # A fixed, non-empty ResolvedStyle — the determinism seam in action (the
        # proof pins voice rather than reading the live, mutable vault).
        return style_resolver.ResolvedStyle(
            base_text="Be concise and concrete.", lessons=[], provenance=[]
        )

    @staticmethod
    def _empty_style():
        # Whitespace-only base, no lessons → the empty-voice case.
        return style_resolver.ResolvedStyle(base_text="   ", lessons=[], provenance=[])

    def test_injected_voice_lands_once_after_h1(self):
        out = composer.compose_voice(self._PAGE, resolved_style=self._nonempty_style())
        self.assertEqual(
            out.count(style_resolver._BLOCK_OPEN), 1, "the voice comment is emitted exactly once"
        )
        # H1 stays first; the voice block follows it; the body follows the block —
        # exactly author_page()'s after-H1 positioning.
        self.assertLess(out.index("# Sample Page"), out.index(style_resolver._BLOCK_OPEN))
        self.assertLess(out.index(style_resolver._BLOCK_OPEN), out.index("## How it works"))
        self.assertIn("Be concise and concrete.", out, "the injected base voice text is rendered")
        self.assertIn("**<Project>**", out, "placeholders survive — voice guides, it does not rewrite")

    def test_empty_voice_returns_bare_page(self):
        out = composer.compose_voice(self._PAGE, resolved_style=self._empty_style())
        self.assertEqual(out, self._PAGE, "empty voice → page returned unchanged")
        self.assertNotIn(style_resolver._BLOCK_OPEN, out)

    def test_resolution_failure_degrades_to_bare_page(self):
        # No injection → compose_voice resolves live; force resolve_style to raise.
        # The degrade must swallow it and return the bare page (never raises).
        # Patch via the string target (not the module-level handle): under
        # `unittest discover`, a later test file re-_load()s style_resolver and
        # clobbers sys.modules, so the handle captured here can diverge from what
        # compose_voice's lazy `import style_resolver` binds. The string target
        # patches the live sys.modules entry both resolve through.
        with mock.patch("style_resolver.resolve_style", side_effect=RuntimeError("boom")):
            with contextlib.redirect_stderr(io.StringIO()):  # the degrade logs to stderr
                out = composer.compose_voice(self._PAGE)
        self.assertEqual(out, self._PAGE, "a resolver failure falls back to the bare page")
        self.assertNotIn(style_resolver._BLOCK_OPEN, out)

    def test_resolution_path_taken_and_scopes_threaded_when_not_injected(self):
        # Positive proof of the live path: with no injection, resolve_style is
        # called with the three scope args and its result is applied.
        rs = self._nonempty_style()
        with mock.patch("style_resolver.resolve_style", return_value=rs) as m:  # string target — see note above
            out = composer.compose_voice(
                self._PAGE, wiki_root=Path("/w"), vault_path=Path("/v"), project_slug="proj"
            )
        m.assert_called_once_with(wiki_root=Path("/w"), vault_path=Path("/v"), project_slug="proj")
        self.assertIn(style_resolver._BLOCK_OPEN, out, "the resolved voice is applied")
        self.assertLess(out.index("# Sample Page"), out.index(style_resolver._BLOCK_OPEN))


if __name__ == "__main__":
    unittest.main()
