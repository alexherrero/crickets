#!/usr/bin/env python3
"""Tests for check-wiki.py rule (p) — the shape axis.

A reference page should be lookup-shaped (tables / quick-ref); an explanation
page should read as prose. rule_p warns (soft) when an explanation is
table-dominated (a fact-dump — fenced diagrams / code don't count against it) or
a reference is mostly prose / over a prose-word ceiling. The combined
plugin-reference hybrid (## Architecture + ## Reference) is exempt.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


cw = _load("check_wiki_shape_under_test", "../src/wiki-maintenance/scripts/check-wiki.py")


def _run(mode: str, text: str):
    """Run rule_p_shape over a body; return only its ('p') issues."""
    lines = text.splitlines()
    heads = cw.parse_headings(lines)
    issues: list = []
    cw.rule_p_shape(Path("wiki/X.md"), mode, lines, text, heads, issues)
    return [i for i in issues if i.rule == "p"]


def _table(rows: int) -> str:
    return "\n".join(["| a | b |", "|---|---|"] + [f"| {i} | {i} |" for i in range(rows)])


class ContentShapeTest(unittest.TestCase):
    def test_counts_tables_fences_prose(self):
        text = "# H\n\nprose one\nprose two\n\n| a | b |\n|---|---|\n\n```\ncode\n```\n"
        table, fence, prose = cw.content_shape(text.splitlines())
        self.assertEqual((table, fence, prose), (2, 3, 2))

    def test_combined_plugin_page_detected(self):
        yes = cw.parse_headings("# X\n## Architecture\n## Reference\n".splitlines())
        self.assertTrue(cw.is_combined_plugin_page(yes))
        no = cw.parse_headings("# X\n## What's here\n".splitlines())
        self.assertFalse(cw.is_combined_plugin_page(no))


class ExplanationShapeTest(unittest.TestCase):
    def test_table_dominated_explanation_warns(self):
        text = "# Why X\n\nA short intro.\n\n" + _table(14) + "\n"
        flags = _run("explanation", text)
        self.assertTrue(flags, "a table-dominated explanation should warn")
        self.assertIn("tables", flags[0].message)

    def test_diagram_heavy_explanation_does_not_warn(self):
        # a fenced ASCII diagram + prose, no tables → narrative, not a fact-dump
        diagram = "```\n" + "\n".join(["  [box] -> [box]"] * 20) + "\n```"
        prose = "\n".join(f"Sentence {i} explaining the why at length." for i in range(14))
        self.assertEqual(_run("explanation", f"# Why X\n\n{prose}\n\n{diagram}\n"), [],
                          "fenced diagrams/code must not count as lookup on an explanation")


class ReferenceShapeTest(unittest.TestCase):
    def test_prose_heavy_reference_warns(self):
        prose = "\n".join(f"Narrative line {i} with several words in it." for i in range(20))
        flags = _run("reference", f"# Ref\n\n{prose}\n")
        self.assertTrue(any("prose" in f.message for f in flags))

    def test_lookup_shaped_reference_ok(self):
        text = "# Ref\n\nOne short lead line.\n\n" + _table(16) + "\n"
        self.assertEqual(_run("reference", text), [])

    def test_reference_over_word_cap_warns(self):
        # lookup-shaped (a big table, so the ratio check is satisfied) but heavy on
        # prose words → only the prose-word ceiling fires
        prose = "\n".join(["alpha beta gamma delta epsilon zeta eta theta iota kappa"] * 100)
        text = "# Ref\n\n" + _table(20) + "\n\n" + prose + "\n"
        flags = _run("reference", text)
        self.assertTrue(any("words of prose" in f.message for f in flags))

    def test_combined_plugin_page_exempt(self):
        prose = "\n".join(f"Narrative line {i} explaining it." for i in range(20))
        text = f"# Plugin\n\n## Architecture\n\n{prose}\n\n## Reference\n\n" + _table(4) + "\n"
        self.assertEqual(_run("reference", text), [],
                          "the combined ## Architecture + ## Reference hybrid is exempt")


if __name__ == "__main__":
    unittest.main()
