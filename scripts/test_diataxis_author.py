#!/usr/bin/env python3
"""Tests for the diataxis-author dispatch — manifest compose vs verbatim monolith
(src/wiki-maintenance/skills/diataxis-author/scripts/author.py) — crickets
wiki-composer part 3/4 (author-wiring).

Covers author-wiring Task 1: template-driven page-type validation (validity is
"a templates/<page-type>.md exists", not a hardcoded enum); the compose-vs-verbatim
routing keyed on `sections:` presence; the byte-identical monolith path (the
non-regression guarantee); and the recognized-but-deferred manifest placement that
fails closed until Task 2 wires it.

Deterministic-only: every author/dispatch call injects a fixed ``resolved_style``
(the determinism seam), so the proofs exercise the pipeline rather than a live,
mutable vault — and are immune to the sys.modules clobbering that ``unittest
discover`` causes across the sibling diataxis test files.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL = _ROOT / "src" / "wiki-maintenance" / "skills" / "diataxis-author"
_SKILL_SCRIPTS = _SKILL / "scripts"
_TEMPLATES = _SKILL / "templates"


def _load(name: str):
    # The skill scripts import each other by bare name (they insert their own dir
    # on sys.path at import); make that dir importable for this test too.
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load in dependency order so the cross-imports — author's top-level `import
# composer`, composer's `import section_schema`, compose_voice's lazy `import
# style_resolver` — all bind the same sys.modules handles this test holds.
section_schema = _load("section_schema")
style_resolver = _load("style_resolver")
composer = _load("composer")
author = _load("author")


_MONOLITHS = ("how-to", "tutorial", "reference", "explanation")
_MANIFESTS = ("component-overview", "home", "plugin-home", "section-index")


def _empty_style():
    # Whitespace base + no lessons → compose's empty-guard → bare page. The pin
    # that makes the monolith path byte-identical to the verbatim template.
    return style_resolver.ResolvedStyle(base_text="   ", lessons=[], provenance=[])


def _nonempty_style():
    return style_resolver.ResolvedStyle(
        base_text="Be concise and concrete.", lessons=[], provenance=[]
    )


def _template(page_type: str) -> str:
    return (_TEMPLATES / f"{page_type}.md").read_text(encoding="utf-8")


def _mkwiki(td: str) -> Path:
    w = Path(td) / "wiki"
    w.mkdir(parents=True)
    return w


class TestTemplateDrivenValidation(unittest.TestCase):
    """Task 1 — page-type validity is template existence, not a hardcoded enum."""

    def test_valid_page_types_are_the_eight_templates_excluding_readme(self):
        got = author._valid_page_types()
        self.assertEqual(
            sorted(got), sorted(_MONOLITHS + _MANIFESTS),
            "every templates/<name>.md except README is an authorable page-type",
        )
        self.assertNotIn("README", got, "README is a doc, not an authorable page-type")

    def test_unknown_page_type_raises_value_error_listing_valid_types(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            with self.assertRaises(ValueError) as cm:
                author.author_page("X", "nonsuch", wiki_root=w, resolved_style=_empty_style())
            msg = str(cm.exception)
            self.assertIn("unknown page-type", msg)
            self.assertIn("how-to", msg, "the error lists the valid page-types")

    def test_readme_is_rejected_as_a_page_type(self):
        # README.md exists under templates/ but is a doc — _TEMPLATE_NON_PAGES
        # excludes it, so it is never an authorable page-type.
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            with self.assertRaises(ValueError):
                author.author_page("X", "README", wiki_root=w, resolved_style=_empty_style())


class TestDispatchRouting(unittest.TestCase):
    """Task 1 — _dispatch_content: manifest→compose_page, monolith→verbatim+voice."""

    def test_monolith_is_byte_identical_to_template_when_voice_pinned_empty(self):
        # The load-bearing non-regression proof: each monolith, voice pinned empty,
        # routes through compose_voice → empty-guard → the template, verbatim.
        for pt in _MONOLITHS:
            tmpl = _template(pt)
            out = author._dispatch_content(tmpl, slug="Whatever", resolved_style=_empty_style())
            self.assertEqual(out, tmpl, f"{pt}: monolith must emit the template byte-for-byte")

    def test_manifest_composes_sections_not_raw_manifest(self):
        # component-overview routes to compose_page: the manifest frontmatter is
        # consumed (the page leads with the # <title> H1, not `---`), and the four
        # section bodies appear in manifest order.
        out = author._dispatch_content(
            _template("component-overview"), slug="Code Review", resolved_style=_empty_style()
        )
        self.assertTrue(out.startswith("# Code Review\n"), "composed page leads with # <title>")
        self.assertNotIn("page-template:", out, "the manifest frontmatter is consumed, not emitted")
        i_intro = out.index("**<Project>**")
        i_how = out.index("## How it works")
        i_fits = out.index("## How it fits")
        i_see = out.index("## See also")
        self.assertLess(i_intro, i_how)
        self.assertLess(i_how, i_fits)
        self.assertLess(i_fits, i_see)

    def test_monolith_voice_lands_after_h1_with_nonempty_pin(self):
        # With a non-empty pin the monolith path injects the one voice convention
        # after the H1 — the same block compose_page uses (parent Risk #2).
        out = author._dispatch_content(
            _template("how-to"), slug="Whatever", resolved_style=_nonempty_style()
        )
        self.assertEqual(out.count(style_resolver._BLOCK_OPEN), 1, "voice injected exactly once")
        self.assertTrue(out.splitlines()[0].startswith("# "), "the H1 still leads the page")
        self.assertFalse(
            out.startswith(style_resolver._BLOCK_OPEN),
            "voice follows the H1 — it is not prepended above it",
        )
        self.assertIn("Be concise and concrete.", out, "the injected base voice text renders")


class TestMonolithEndToEnd(unittest.TestCase):
    """Task 1 — author_page writes the monolith path; placement + filename unchanged."""

    def test_author_page_writes_template_verbatim_when_voice_pinned_empty(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            res = author.author_page(
                "Install Foo", "how-to", wiki_root=w, resolved_style=_empty_style()
            )
            written = Path(res["target"]).read_bytes()
            template = (_TEMPLATES / "how-to.md").read_bytes()
            self.assertEqual(written, template, "empty-pinned monolith == template byte-for-byte")
            self.assertFalse(res["style_composed"], "empty voice → not composed")
            self.assertEqual(res["style_scopes"], [])

    def test_author_page_places_monolith_by_mode_dir_and_filename_style(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            res = author.author_page(
                "Install Foo", "how-to", wiki_root=w,
                filename_style="kebab-case", resolved_style=_empty_style(),
            )
            self.assertEqual(res["filename"], "install-foo.md")
            self.assertEqual(Path(res["target"]), w / "how-to" / "install-foo.md")
            self.assertEqual(res["mode"], "how-to")

    def test_existing_target_refuses_without_overwrite_then_rewrites_with_it(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            author.author_page("Dup", "how-to", wiki_root=w, resolved_style=_empty_style())
            with self.assertRaises(FileExistsError):
                author.author_page("Dup", "how-to", wiki_root=w, resolved_style=_empty_style())
            res = author.author_page(
                "Dup", "how-to", wiki_root=w, overwrite=True, resolved_style=_empty_style()
            )
            self.assertEqual(res["action"], "authored")


class TestManifestPlacementDeferredToTask2(unittest.TestCase):
    """Task 1 — manifest page-types are recognized but fail closed at placement.

    The dispatch routes manifests to compose at the *content* level (proven in
    TestDispatchRouting), but the end-to-end *placement* of the component-overview
    proof slice is Task 2 — so author_page fails closed here rather than misplacing
    a page. This test morphs in Task 2 when placement is wired."""

    def test_component_overview_fails_closed_at_placement(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            with self.assertRaises(NotImplementedError) as cm:
                author.author_page(
                    "Code Review", "component-overview", wiki_root=w,
                    resolved_style=_empty_style(),
                )
            self.assertIn(
                "Task 2", str(cm.exception),
                "the deferral names the task that wires placement",
            )


if __name__ == "__main__":
    unittest.main()
