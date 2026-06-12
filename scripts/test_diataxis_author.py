#!/usr/bin/env python3
"""Tests for the diataxis-author dispatch — manifest compose vs verbatim monolith
(src/wiki-maintenance/skills/diataxis-author/scripts/author.py) — crickets
wiki-composer part 3/4 (author-wiring).

Covers author-wiring Task 1: template-driven page-type validation (validity is
"a templates/<page-type>.md exists", not a hardcoded enum); the compose-vs-verbatim
routing keyed on `sections:` presence; and the byte-identical monolith path (the
non-regression guarantee). Task 2 adds the component-overview placement proof
(`architecture/<kebab>/<base>.md` with the four section bodies in manifest order);
the other three manifest page-types stay recognized-but-deferred, failing closed at
placement rather than being misplaced.

Deterministic-only: every author/dispatch call injects a fixed ``resolved_style``
(the determinism seam), so the proofs exercise the pipeline rather than a live,
mutable vault — and are immune to the sys.modules clobbering that ``unittest
discover`` causes across the sibling diataxis test files.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class TestComponentOverviewPlacement(unittest.TestCase):
    """Task 2 — component-overview places end-to-end and composes its sections.

    The proof slice that morphs Task 1's fail-closed test: placement is now wired.
    The target is grounded in wiki_init's universal component layout
    (``architecture/<slug>/<Overview>.md``, wiki_init.py:215) — the folder is always
    the kebab slug; the basename follows the operator's ``filename_style``."""

    def test_places_under_architecture_kebab_folder_camelcase_basename(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            res = author.author_page(
                "Code Review", "component-overview", wiki_root=w,
                resolved_style=_empty_style(),
            )
            self.assertEqual(
                Path(res["target"]), w / "architecture" / "code-review" / "Code-Review.md",
                "kebab folder + default CamelCase-With-Dashes basename (wiki_init layout)",
            )
            self.assertEqual(res["filename"], "Code-Review.md")
            self.assertEqual(res["mode"], "component-overview")
            self.assertTrue(Path(res["target"]).exists(), "the page is written to disk")

    def test_composed_page_has_h1_and_four_sections_in_manifest_order(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            res = author.author_page(
                "Code Review", "component-overview", wiki_root=w,
                resolved_style=_empty_style(),
            )
            written = Path(res["target"]).read_text(encoding="utf-8")
            self.assertTrue(written.startswith("# Code Review\n"), "leads with the # <slug> H1")
            self.assertNotIn("page-template:", written, "manifest frontmatter consumed, not emitted")
            self.assertNotIn("sections:", written, "the sections: list is consumed too")
            i_intro = written.index("**<Project>**")
            i_how = written.index("## How it works")
            i_fits = written.index("## How it fits")
            i_see = written.index("## See also")
            self.assertLess(i_intro, i_how)
            self.assertLess(i_how, i_fits)
            self.assertLess(i_fits, i_see)

    def test_filename_style_changes_basename_but_folder_stays_kebab(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            res = author.author_page(
                "Code Review", "component-overview", wiki_root=w,
                filename_style="kebab-case", resolved_style=_empty_style(),
            )
            self.assertEqual(
                Path(res["target"]), w / "architecture" / "code-review" / "code-review.md",
                "folder stays kebab; basename follows filename_style",
            )

    def test_existing_target_refuses_without_overwrite_then_rewrites_with_it(self):
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            author.author_page(
                "Code Review", "component-overview", wiki_root=w, resolved_style=_empty_style()
            )
            with self.assertRaises(FileExistsError):
                author.author_page(
                    "Code Review", "component-overview", wiki_root=w, resolved_style=_empty_style()
                )
            res = author.author_page(
                "Code Review", "component-overview", wiki_root=w,
                overwrite=True, resolved_style=_empty_style(),
            )
            self.assertEqual(res["action"], "authored")


class TestDeferredManifestTypesFailClosed(unittest.TestCase):
    """Task 2 — the other three manifest page-types are recognized but their
    placement is deferred; they fail closed at ``_manifest_target`` rather than
    being misplaced. (``home`` collides with release-time ``Home.md`` ownership;
    ``section-index``'s target is per-section under the live taxonomy migration;
    ``plugin-home``'s ``architecture/plugins/`` is a repo-specific layout, not
    wiki_init's universal component placement.)"""

    def test_deferred_manifest_types_raise_not_implemented(self):
        for pt in ("home", "plugin-home", "section-index"):
            with tempfile.TemporaryDirectory() as td:
                w = _mkwiki(td)
                with self.assertRaises(NotImplementedError, msg=f"{pt} placement is deferred") as cm:
                    author.author_page(
                        "Whatever", pt, wiki_root=w, resolved_style=_empty_style()
                    )
                self.assertIn(pt, str(cm.exception), "the deferral names the page-type")


class TestFailClosedEdges(unittest.TestCase):
    """Task 3 — every edge halts with a specific message, never a partial/misplaced page."""

    def test_unknown_page_type_lists_valid_types(self):
        # (a) — enforced since Task 1; re-asserted here as a Task-3 fail-closed edge.
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            with self.assertRaises(ValueError) as cm:
                author.author_page("X", "nonsuch", wiki_root=w, resolved_style=_empty_style())
            self.assertIn("unknown page-type", str(cm.exception))
            self.assertIn("how-to", str(cm.exception), "the error lists the valid page-types")

    def test_manifest_with_a_bogus_section_fails_closed_naming_manifest_and_section(self):
        # (b) — a manifest naming a section with no library file halts with the
        # page-type (manifest) + the missing section, propagated from compose_page's
        # loader (not swallowed into a partial page). A synthetic component-overview
        # manifest names a section absent from the shipped library: placement resolves
        # (component-overview is wired), so the failure surfaces at compose time.
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            tmpl_dir = Path(td) / "templates"
            tmpl_dir.mkdir()
            (tmpl_dir / "component-overview.md").write_text(
                "---\npage-template: component-overview\nsections: [does-not-exist]\n---\n",
                encoding="utf-8",
            )
            with mock.patch.object(author, "_TEMPLATES_DIR", tmpl_dir):
                with self.assertRaises(FileNotFoundError) as cm:
                    author.author_page(
                        "Code Review", "component-overview", wiki_root=w,
                        resolved_style=_empty_style(),
                    )
            msg = str(cm.exception)
            self.assertIn("component-overview", msg, "names the manifest (page-type)")
            self.assertIn("does-not-exist", msg, "names the missing section")

    def test_each_deferred_manifest_type_message_names_its_specific_reason(self):
        # (c) — the deferred trio each halt with their OWN deferral reason, not a
        # generic "not wired" (the operator sees why, per _DEFERRED_MANIFEST_REASONS).
        reasons = {"home": "Home.md", "section-index": "taxonomy", "plugin-home": "plugins"}
        for pt, needle in reasons.items():
            with tempfile.TemporaryDirectory() as td:
                w = _mkwiki(td)
                with self.assertRaises(NotImplementedError) as cm:
                    author.author_page("X", pt, wiki_root=w, resolved_style=_empty_style())
                msg = str(cm.exception)
                self.assertIn(pt, msg, f"{pt}: names the page-type")
                self.assertIn(needle, msg, f"{pt}: names its specific deferral reason")


class TestCommandSurface(unittest.TestCase):
    """Task 3 — --mode widens to template-validated page-types; deferred types are
    reachable via the CLI but fail clean; --intent stays monolith-only."""

    def test_parse_args_accepts_every_template_page_type(self):
        # The four-monolith --mode hardcode is gone: --mode now accepts any page-type
        # with a template (all eight), including the manifests Task 1+2 recognize.
        for pt in _MONOLITHS + _MANIFESTS:
            ns = author._parse_args(["Some slug", "--mode", pt])
            self.assertEqual(ns.mode, pt, f"--mode {pt} accepted (template-validated)")

    def test_main_fails_clean_on_a_deferred_manifest_type(self):
        # A deferred type is reachable via --mode now, but main() catches the
        # NotImplementedError → exit 1 + ERROR (with the reason), no traceback, no
        # page written. Proves widening the surface didn't open a misplacement path.
        with tempfile.TemporaryDirectory() as td:
            w = _mkwiki(td)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = author.main(["Some Home", "--mode", "home", "--wiki-root", str(w)])
            self.assertEqual(rc, 1, "deferred type exits non-zero, not a crash")
            self.assertIn("ERROR", err.getvalue())
            self.assertIn("Home.md", err.getvalue(), "the clean error carries the reason")
            self.assertFalse(list(w.rglob("*.md")), "no page written for a deferred type")


if __name__ == "__main__":
    unittest.main()
