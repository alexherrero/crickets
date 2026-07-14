#!/usr/bin/env python3
"""Red/green fixture coverage for check-wiki.py rules (a) through (k) that had
no dedicated test before (R2.4 task 1). Rules (l), (m), (n), (o), (p) already
have their own fixture-based test files (test_check_wiki_readme.py,
test_check_wiki_sections.py, test_check_wiki_shape.py); rule (j) is covered in
test_check_wiki_nav.py. Coverage before this file was incidental — whatever
the live wiki happened to exercise — rather than one deliberate violating
fixture and one deliberate passing fixture per rule.

Each rule gets its own TestCase with a `test_*_fires` (red) and
`test_*_passes` (green) method, calling the rule function directly (the same
pattern the existing check-wiki test files use) rather than invoking the CLI
end-to-end — faster and pins the exact fixture that trips (or doesn't trip)
each rule.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
CHECK_WIKI_SRC = SCRIPTS / ".." / "src" / "wiki" / "scripts" / "check-wiki.py"

# Manifest of which test file exercises each rule's red+green pair, both
# directions confirmed by direct reading at authoring time (2026-07-05):
# rule -> the file(s) whose tests assert both a firing and a passing fixture.
_RULE_COVERAGE_MANIFEST = {
    "a": "test_check_wiki_rules.py (RuleALocationTest)",
    "b": "test_check_wiki_rules.py (RuleBModeBlockTest)",
    "c": "test_check_wiki_rules.py (RuleCTutorialShapeTest)",
    "d": "test_check_wiki_rules.py (RuleDHowtoShapeTest)",
    "e": "test_check_wiki_rules.py (RuleEReferenceShapeTest)",
    "g": "test_check_wiki_rules.py (RuleGFilenameTest, RuleGUniqueTest)",
    "h": "test_check_wiki_rules.py (RuleHLinksResolveTest)",
    "i": "test_check_wiki_rules.py (RuleIOrphanTest)",
    "j": "test_check_wiki_nav.py (NavRuleJTest)",
    "k": "test_check_wiki_rules.py (RuleKWordCountTest)",
    "l": "test_check_wiki_readme.py (RootDocGovernanceTest)",
    "m": "test_check_wiki_sections.py (RuleMSectionOrderTest)",
    "n": "test_check_wiki_sections.py (RuleNHeadingVariantTest)",
    "o": "test_check_wiki_sections.py",
    "p": "test_check_wiki_shape.py",
    "q": "test_check_wiki_rules.py (RuleQTopnoteLengthTest)",
}


class RuleCoverageCompletenessTest(unittest.TestCase):
    """Mechanized version of task 1's 'a rule with only one direction covered
    is flagged as a gap' requirement: extract every rule letter check-wiki.py
    can actually emit and diff it against the coverage manifest above. If a
    future rule ships with no fixture test at all — the most severe case of
    "not fully covered" — this fails red instead of silently passing."""

    def test_every_emitted_rule_letter_has_a_manifest_entry(self):
        src = CHECK_WIKI_SRC.read_text(encoding="utf-8")
        emitted = set(re.findall(r'emit\(\s*issues\s*,[^)]*?,\s*"([a-z])"', src, re.DOTALL))
        self.assertTrue(emitted, "extraction found no rule letters — regex likely broke")
        manifest_rules = set(_RULE_COVERAGE_MANIFEST)
        missing = emitted - manifest_rules
        self.assertEqual(missing, set(),
                         f"check-wiki.py emits rule(s) {sorted(missing)} with no "
                         f"fixture coverage manifest entry — add red+green tests")
        stale = manifest_rules - emitted
        self.assertEqual(stale, set(),
                         f"manifest lists rule(s) {sorted(stale)} that check-wiki.py "
                         f"no longer emits — the rule was removed or renamed")


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


cw = _load("check_wiki_rules_under_test", "../src/wiki/scripts/check-wiki.py")

_WIKI_ROOT = Path("/wiki")  # a nominal root — rule functions never touch disk here


def _heads(text: str):
    return cw.parse_headings(text.splitlines())


class RuleALocationTest(unittest.TestCase):
    def test_page_outside_mode_dir_fires(self):
        p = _WIKI_ROOT / "random-notes" / "Foo.md"
        issues = []
        cw.rule_a_location(p, _WIKI_ROOT, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "a")
        self.assertEqual(issues[0].severity, "hard")

    def test_page_inside_mode_dir_passes(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        issues = []
        cw.rule_a_location(p, _WIKI_ROOT, issues)
        self.assertEqual(issues, [])

    def test_structural_page_exempt_regardless_of_location(self):
        p = _WIKI_ROOT / "Home.md"
        issues = []
        cw.rule_a_location(p, _WIKI_ROOT, issues)
        self.assertEqual(issues, [])


class RuleBModeBlockTest(unittest.TestCase):
    def test_missing_note_block_fires(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        lines = ["# Foo", "", "No note block here.", ""]
        issues = []
        cw.rule_b_mode_block(p, "how-to", lines, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "b")
        self.assertIn("missing", issues[0].message)

    def test_note_block_missing_required_field_fires(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        lines = ["# Foo", "", "> [!NOTE]", "> **Goal:** do the thing.", ""]
        issues = []
        cw.rule_b_mode_block(p, "how-to", lines, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "b")
        self.assertIn("Prereqs", issues[0].message)

    def test_complete_note_block_passes(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        lines = ["# Foo", "", "> [!NOTE]",
                 "> **Goal:** do the thing.", "> **Prereqs:** none.", ""]
        issues = []
        cw.rule_b_mode_block(p, "how-to", lines, issues)
        self.assertEqual(issues, [])

    def test_non_howto_tutorial_mode_exempt(self):
        p = _WIKI_ROOT / "reference" / "Foo.md"
        issues = []
        cw.rule_b_mode_block(p, "reference", ["# Foo"], issues)
        self.assertEqual(issues, [])


class RuleCTutorialShapeTest(unittest.TestCase):
    def test_missing_both_required_h2s_fires_twice(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        heads = _heads("# Foo\n\n## Overview\n\nSome prose.\n")
        issues = []
        cw.rule_c_tutorial_shape(p, "tutorial", heads, issues)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i.rule == "c" for i in issues))

    def test_conforming_tutorial_passes(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        heads = _heads("# Foo\n\n## Step 1 — Do the thing\n\n## What you learned\n")
        issues = []
        cw.rule_c_tutorial_shape(p, "tutorial", heads, issues)
        self.assertEqual(issues, [])

    def test_non_tutorial_mode_exempt(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        issues = []
        cw.rule_c_tutorial_shape(p, "how-to", [], issues)
        self.assertEqual(issues, [])


class RuleDHowtoShapeTest(unittest.TestCase):
    def test_no_steps_and_banned_heading_fires_twice(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        text = "# Foo\n\n## Why\n\nBecause reasons.\n"
        heads = _heads(text)
        issues = []
        cw.rule_d_howto_shape(p, "how-to", heads, text.splitlines(), issues)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i.rule == "d" for i in issues))

    def test_steps_heading_no_banned_heading_passes(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        text = "# Foo\n\n## Steps\n\n1. Do the thing.\n"
        heads = _heads(text)
        issues = []
        cw.rule_d_howto_shape(p, "how-to", heads, text.splitlines(), issues)
        self.assertEqual(issues, [])

    def test_numbered_list_without_steps_heading_also_passes(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        text = "# Foo\n\n1. Do the thing.\n2. Do the next thing.\n"
        heads = _heads(text)
        issues = []
        cw.rule_d_howto_shape(p, "how-to", heads, text.splitlines(), issues)
        self.assertEqual(issues, [])


class RuleEReferenceShapeTest(unittest.TestCase):
    def test_no_table_or_fence_near_h1_fires(self):
        p = _WIKI_ROOT / "reference" / "Foo.md"
        text = "# Foo\n\n" + "\n".join(f"prose line {n}" for n in range(30))
        heads = _heads(text)
        issues = []
        cw.rule_e_reference_shape(p, "reference", text.splitlines(), heads, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "e")

    def test_table_near_h1_passes(self):
        p = _WIKI_ROOT / "reference" / "Foo.md"
        text = "# Foo\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        heads = _heads(text)
        issues = []
        cw.rule_e_reference_shape(p, "reference", text.splitlines(), heads, issues)
        self.assertEqual(issues, [])

    def test_combined_plugin_page_exempt_even_without_table(self):
        p = _WIKI_ROOT / "reference" / "Foo.md"
        text = "# Foo\n\n## Architecture\n\nprose\n\n## Reference\n\nmore prose\n"
        heads = _heads(text)
        issues = []
        cw.rule_e_reference_shape(p, "reference", text.splitlines(), heads, issues)
        self.assertEqual(issues, [])


class RuleGFilenameTest(unittest.TestCase):
    def test_underscore_filename_fires(self):
        p = _WIKI_ROOT / "how-to" / "bad_name.md"
        issues = []
        cw.rule_g_filename(p, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "g")

    def test_camelcase_dashes_filename_passes(self):
        p = _WIKI_ROOT / "how-to" / "Good-Name.md"
        issues = []
        cw.rule_g_filename(p, issues)
        self.assertEqual(issues, [])

    def test_structural_page_exempt(self):
        p = _WIKI_ROOT / "_Sidebar.md"
        issues = []
        cw.rule_g_filename(p, issues)
        self.assertEqual(issues, [])


class RuleGUniqueTest(unittest.TestCase):
    def test_case_insensitive_collision_fires_for_both(self):
        paths = [_WIKI_ROOT / "how-to" / "Foo.md", _WIKI_ROOT / "reference" / "foo.md"]
        issues = []
        cw.rule_g_unique(paths, _WIKI_ROOT, issues)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i.rule == "g" for i in issues))

    def test_distinct_stems_pass(self):
        paths = [_WIKI_ROOT / "how-to" / "Foo.md", _WIKI_ROOT / "reference" / "Bar.md"]
        issues = []
        cw.rule_g_unique(paths, _WIKI_ROOT, issues)
        self.assertEqual(issues, [])


class RuleHLinksResolveTest(unittest.TestCase):
    def test_dangling_wiki_link_fires(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        text = "See [Bar](Nonexistent) for details."
        issues = []
        cw.rule_h_links_resolve(p, text, {"Foo"}, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "h")

    def test_resolving_wiki_link_passes(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        text = "See [Bar](RealPage) for details."
        issues = []
        cw.rule_h_links_resolve(p, text, {"Foo", "RealPage"}, issues)
        self.assertEqual(issues, [])


class RuleIOrphanTest(unittest.TestCase):
    def test_howto_with_no_reference_link_fires(self):
        howto = _WIKI_ROOT / "how-to" / "Foo.md"
        modes = {howto: "how-to"}
        link_graph = {"Foo": set()}  # links to nothing
        stem_to_mode = {}
        issues = []
        cw.rule_i_orphan(modes, link_graph, stem_to_mode, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "i")
        self.assertIn("reference", issues[0].message)

    def test_howto_linking_to_reference_passes(self):
        howto = _WIKI_ROOT / "how-to" / "Foo.md"
        modes = {howto: "how-to"}
        link_graph = {"Foo": {"Bar"}}
        stem_to_mode = {"Bar": "reference"}
        issues = []
        cw.rule_i_orphan(modes, link_graph, stem_to_mode, issues)
        self.assertEqual(issues, [])

    def test_reference_page_with_no_inbound_links_fires(self):
        ref = _WIKI_ROOT / "reference" / "Bar.md"
        modes = {ref: "reference"}
        issues = []
        cw.rule_i_orphan(modes, {}, {}, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "i")
        self.assertIn("orphan", issues[0].message)

    def test_reference_page_with_inbound_link_passes(self):
        ref = _WIKI_ROOT / "reference" / "Bar.md"
        modes = {ref: "reference"}
        link_graph = {"Foo": {"Bar"}}
        issues = []
        cw.rule_i_orphan(modes, link_graph, {}, issues)
        self.assertEqual(issues, [])


class RuleKWordCountTest(unittest.TestCase):
    def test_over_cap_fires_soft(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        text = "word " * 700  # WORD_CAPS["how-to"] == 600
        issues = []
        cw.rule_k_word_count(p, "how-to", text, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "k")
        self.assertEqual(issues[0].severity, "soft")

    def test_under_cap_passes(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        text = "word " * 100
        issues = []
        cw.rule_k_word_count(p, "how-to", text, issues)
        self.assertEqual(issues, [])

    def test_mode_with_no_cap_never_fires(self):
        p = _WIKI_ROOT / "architecture" / "Foo.md"
        text = "word " * 5000
        issues = []
        cw.rule_k_word_count(p, "index", text, issues)
        self.assertEqual(issues, [])


class RuleQTopnoteLengthTest(unittest.TestCase):
    def test_over_cap_fires_soft(self):
        p = _WIKI_ROOT / "explanation" / "Foo.md"
        lines = ["# Foo", "", "> [!NOTE]",
                 "> " + ("word " * 70).strip(), ""]
        issues = []
        cw.rule_q_topnote_length(p, "explanation", lines, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "q")
        self.assertEqual(issues[0].severity, "soft")

    def test_under_cap_passes(self):
        p = _WIKI_ROOT / "explanation" / "Foo.md"
        lines = ["# Foo", "", "> [!NOTE]",
                 "> **Status: launched.** A short framing sentence.", ""]
        issues = []
        cw.rule_q_topnote_length(p, "explanation", lines, issues)
        self.assertEqual(issues, [])

    def test_non_explanation_mode_exempt(self):
        p = _WIKI_ROOT / "how-to" / "Foo.md"
        lines = ["# Foo", "", "> [!NOTE]",
                 "> " + ("word " * 70).strip(), ""]
        issues = []
        cw.rule_q_topnote_length(p, "how-to", lines, issues)
        self.assertEqual(issues, [])

    def test_no_note_block_passes(self):
        p = _WIKI_ROOT / "explanation" / "Foo.md"
        lines = ["# Foo", "", "No note block here.", ""]
        issues = []
        cw.rule_q_topnote_length(p, "explanation", lines, issues)
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
