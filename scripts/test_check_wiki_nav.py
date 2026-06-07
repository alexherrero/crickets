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


cw = _load("check_wiki_nav_under_test", "check-wiki.py")


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


if __name__ == "__main__":
    unittest.main()
