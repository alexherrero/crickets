#!/usr/bin/env python3
"""Tests for check-wiki.py rule (j) — the curated-Home / complete-_Sidebar contract.

`_Sidebar.md` must be the complete sitemap (references every content page); since
the sidebar renders on every wiki page, that is the no-orphan guarantee. `Home.md`
is curated — it is NOT required to list every page, so a landing page can surface
only what a reader acts on.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


cw = _load("check_wiki_nav_under_test", "../src/wiki-maintenance/scripts/check-wiki.py")


class NavRuleJTest(unittest.TestCase):
    def _wiki(self, sidebar_stems, *, home=True, sidebar=True) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        if home:
            (root / "Home.md").write_text("# Home\n\nWelcome.\n", encoding="utf-8")
        if sidebar:
            body = "\n".join(f"- [{s}]({s})" for s in sidebar_stems)
            (root / "_Sidebar.md").write_text(
                "**[Home](Home)**\n\n" + body + "\n", encoding="utf-8")
        return root

    def _modes(self, root, pairs):
        # pairs: list of (relpath, mode)
        return {root / rel: mode for rel, mode in pairs}

    # ── the curated-Home contract ────────────────────────────────────────

    def test_page_not_on_home_but_in_sidebar_is_fine(self):
        root = self._wiki(["Foo", "Bar"])  # neither linked from Home's body
        modes = self._modes(root, [("how-to/Foo.md", "how-to"),
                                   ("reference/Bar.md", "reference")])
        issues = []
        cw.rule_j_home_sidebar(root, modes, issues)
        self.assertEqual(issues, [], "Home is curated — pages need not be listed on Home")

    def test_page_missing_from_sidebar_fires(self):
        root = self._wiki(["Foo"])  # Bar absent from the sitemap
        modes = self._modes(root, [("how-to/Foo.md", "how-to"),
                                   ("reference/Bar.md", "reference")])
        issues = []
        cw.rule_j_home_sidebar(root, modes, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "j")
        self.assertEqual(issues[0].severity, "hard")
        self.assertEqual(issues[0].path.name, "_Sidebar.md")
        self.assertIn("Bar", issues[0].message)

    def test_complete_sidebar_passes(self):
        root = self._wiki(["Foo", "Bar", "Baz"])
        modes = self._modes(root, [("how-to/Foo.md", "how-to"),
                                   ("reference/Bar.md", "reference"),
                                   ("explanation/Baz.md", "explanation")])
        issues = []
        cw.rule_j_home_sidebar(root, modes, issues)
        self.assertEqual(issues, [])

    def test_structural_pages_not_required(self):
        root = self._wiki([])  # empty sitemap
        modes = self._modes(root, [("Home.md", None), ("_Sidebar.md", None)])
        issues = []
        cw.rule_j_home_sidebar(root, modes, issues)
        self.assertEqual(issues, [])

    # ── existence ────────────────────────────────────────────────────────

    def test_home_missing_emits(self):
        root = self._wiki(["Foo"], home=False)
        modes = self._modes(root, [("how-to/Foo.md", "how-to")])
        issues = []
        cw.rule_j_home_sidebar(root, modes, issues)
        self.assertTrue(any("Home.md is missing" in i.message for i in issues))

    def test_sidebar_missing_emits_and_skips_completeness(self):
        root = self._wiki(["Foo"], sidebar=False)
        modes = self._modes(root, [("how-to/Foo.md", "how-to")])
        issues = []
        cw.rule_j_home_sidebar(root, modes, issues)
        self.assertTrue(any("_Sidebar.md is missing" in i.message for i in issues))
        # No completeness errors when the sidebar is absent (can't compute).
        self.assertFalse(any("complete sitemap" in i.message for i in issues))


class ExtractWikiLinksFenceTest(unittest.TestCase):
    """rule (h) resolves wiki-internal links by basename — but a link-shaped
    literal inside a fenced code block or an inline code span is illustrative
    markup (a template, a usage example), not a navigable reference. Extracting
    it makes rule (h) false-positive on an unresolvable target. These guard the
    documented code-span/fence exemption that parse_headings / word_count / rule_o
    already honor.
    """

    def _pages(self, text):
        return [page for _, _, page in cw.extract_wiki_links(text)]

    def test_plain_prose_link_is_extracted(self):
        self.assertEqual(self._pages("see [Foo](Foo) for more"), ["Foo"])

    def test_link_inside_fenced_block_is_skipped(self):
        text = "intro\n\n```\n[label](Unresolvable)\n```\n\noutro\n"
        self.assertEqual(self._pages(text), [],
                         "a link inside a fence is illustrative, not navigable")

    def test_link_inside_inline_code_span_is_skipped(self):
        self.assertEqual(self._pages("the literal `[x](Nope)` is an example"), [])

    def test_template_literal_with_placeholder_target_is_skipped(self):
        # The exact GitHub-Projects.md Task-lifecycle regression: a {{placeholder}}
        # link target inside a code fence must not be reported as a broken link.
        text = (
            "The thread:\n\n```\n"
            "**② {{date}}** ([`{{sha}}`]({{commit_url}})): {{progress}}\n"
            "```\n"
        )
        self.assertEqual(self._pages(text), [])

    def test_links_resume_after_closing_fence(self):
        text = "```\n[A](InFence)\n```\n\nthen [B](RealPage) here\n"
        self.assertEqual(self._pages(text), ["RealPage"],
                         "fence toggling must restore extraction after it closes")

    def test_external_links_still_skipped(self):
        text = "[home](https://example.com) and [anchor](#sec) and [Foo](Foo)"
        self.assertEqual(self._pages(text), ["Foo"])


if __name__ == "__main__":
    unittest.main()
