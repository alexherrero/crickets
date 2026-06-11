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
_MANIFEST_PATH = _SKILL_SCRIPTS.parent / "templates" / "component-overview.md"


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


class TestManifestParser(unittest.TestCase):
    """Task 3 — the block-list `sections:` reader (the inline-list parsers can't)."""

    def test_reads_block_list_in_manifest_order(self):
        names = composer._parse_manifest_sections(_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            names,
            ["intro", "how-it-works", "component-composition", "see-also"],
            "the real component-overview manifest's sections, in document order",
        )

    def test_tolerates_inline_list(self):
        # A future manifest may use the inline form; the reader accepts both.
        txt = "---\npage-template: x\nsections: [a, b, c]\n---\nbody\n"
        self.assertEqual(composer._parse_manifest_sections(txt), ["a", "b", "c"])

    def test_absent_sections_yields_empty(self):
        self.assertEqual(composer._parse_manifest_sections("---\npage-template: x\n---\nbody\n"), [])

    def test_no_frontmatter_yields_empty(self):
        self.assertEqual(composer._parse_manifest_sections("just a body, no frontmatter\n"), [])

    def test_block_list_stops_at_next_key(self):
        # A key after the block list must not be swallowed as a section.
        txt = "---\nsections:\n  - a\n  - b\nother-key: v\n---\nbody\n"
        self.assertEqual(composer._parse_manifest_sections(txt), ["a", "b"])


class TestComposePage(unittest.TestCase):
    """Task 3 — compose_page() assembles the manifest under the H1, deterministically."""

    _MANIFEST = _MANIFEST_PATH.read_text(encoding="utf-8")
    _TITLE = "Build & Distribution"

    @staticmethod
    def _pinned_voice():
        # A fixed voice — the determinism seam: the proof pins voice rather than
        # reading the live, mutable vault (parent Risk #3).
        return style_resolver.ResolvedStyle(
            base_text="Plain, present-tense prose.", lessons=[], provenance=[]
        )

    def _compose(self, **kw):
        return composer.compose_page(self._MANIFEST, title=self._TITLE, **kw)

    def test_emits_h1_then_four_sections_in_manifest_order(self):
        out = self._compose(resolved_style=self._pinned_voice())
        self.assertTrue(out.startswith(f"# {self._TITLE}\n"), "the page leads with the # {title} H1")
        # The four section bodies, located by their distinctive markers, appear in
        # manifest order: intro (bold lead, no heading) → how-it-works → how-it-fits
        # → see-also.
        i_intro = out.index("**<Project>**")
        i_how = out.index("## How it works")
        i_fits = out.index("## How it fits")
        i_see = out.index("## See also")
        self.assertLess(i_intro, i_how)
        self.assertLess(i_how, i_fits)
        self.assertLess(i_fits, i_see)

    def test_voice_comment_positioned_after_h1(self):
        out = self._compose(resolved_style=self._pinned_voice())
        self.assertEqual(out.count(style_resolver._BLOCK_OPEN), 1, "voice emitted once")
        # H1 → voice → first section body.
        self.assertLess(out.index(f"# {self._TITLE}"), out.index(style_resolver._BLOCK_OPEN))
        self.assertLess(out.index(style_resolver._BLOCK_OPEN), out.index("**<Project>**"))

    def test_is_deterministic_byte_identical_across_runs(self):
        # The load-bearing proof: same (manifest, library, title, pinned voice,
        # lang=en) → byte-identical output. This is byte-reproduction without a
        # brittle committed golden (the plan's Risk: a golden breaks on any library
        # or voice edit) — determinism is asserted directly, run-to-run.
        rs = self._pinned_voice()
        first = self._compose(resolved_style=rs)
        second = self._compose(resolved_style=rs)
        self.assertEqual(first, second, "compose_page must be deterministic")

    def test_concatenates_section_bodies_verbatim(self):
        # Round-trip: each stripped parse_section().body appears verbatim in the
        # assembled page — the composer concatenates, it does not rewrite.
        out = self._compose(resolved_style=self._pinned_voice())
        for name in ("intro", "how-it-works", "component-composition", "see-also"):
            body = section_schema.parse_section(
                (_SECTIONS_DIR / f"{name}.md").read_text(encoding="utf-8")
            ).body.strip()
            self.assertIn(body, out, f"{name}: body must appear verbatim in the composed page")

    def test_opinion_stripped_placeholders_survive(self):
        out = self._compose(resolved_style=self._pinned_voice())
        self.assertNotIn("<!-- SECTION", out, "no section opinion comment leaks into the page")
        self.assertIn("<Project>", out, "author-fill placeholders survive (the output contract)")

    def test_bare_page_when_voice_empty(self):
        # Empty voice → assembled page with no voice block (the graceful path).
        empty = style_resolver.ResolvedStyle(base_text="   ", lessons=[], provenance=[])
        out = self._compose(resolved_style=empty)
        self.assertNotIn(style_resolver._BLOCK_OPEN, out)
        self.assertTrue(out.startswith(f"# {self._TITLE}\n\n"))
        self.assertIn("## How it works", out, "sections are still assembled without voice")

    def test_lang_seam_threads_through_to_loader(self):
        # compose_page's lang flows to load_section_body; a non-en value is
        # rejected there, and the rejection propagates (the reserved seam is not
        # silently honored end-to-end).
        with self.assertRaises(NotImplementedError):
            composer.compose_page(self._MANIFEST, title=self._TITLE, lang="es")


if __name__ == "__main__":
    unittest.main()
