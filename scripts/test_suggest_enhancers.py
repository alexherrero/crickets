#!/usr/bin/env python3
"""Tests for scripts/suggest_enhancers.py (crickets v3.x ④ part 3)."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


se = _load("suggest_enhancers")

# A synthetic marketplace: `sf` (enhancer) enhances `wf` (enhancee, no enhances).
_MK = {"plugins": [
    {"name": "wf"},
    {"name": "sf", "enhances": [{"group": "wf", "capability": "review"}]},
    {"name": "other"},
]}
# string-shorthand variant
_MK_STR = {"plugins": [{"name": "wf"}, {"name": "sf", "enhances": ["wf"]}]}


class TestSuggestEnhancers(unittest.TestCase):
    def test_suggests_missing_enhancer(self):
        # enhancee installed WITHOUT its enhancer → suggest the enhancer
        sugs = se.suggestions(_MK, ["wf"])
        self.assertEqual(sugs, [{"enhancer": "sf", "enhancee": "wf"}])

    def test_no_suggestion_when_both_installed(self):
        self.assertEqual(se.suggestions(_MK, ["wf", "sf"]), [])

    def test_no_suggestion_when_neither_installed(self):
        self.assertEqual(se.suggestions(_MK, []), [])

    def test_no_suggestion_when_only_enhancer_installed(self):
        # the enhancer is present but its enhancee is not — nothing to suggest
        self.assertEqual(se.suggestions(_MK, ["sf"]), [])

    def test_string_shorthand_enhances(self):
        self.assertEqual(se.suggestions(_MK_STR, ["wf"]),
                         [{"enhancer": "sf", "enhancee": "wf"}])

    def test_format_tips_mentions_both(self):
        out = se.format_tips([{"enhancer": "sf", "enhancee": "wf"}])
        self.assertIn("sf", out)
        self.assertIn("wf", out)

    def test_real_marketplace_partial_set(self):
        # the REAL committed marketplace: with developer-workflows installed but
        # not developer-safety, the real enhances:[developer-workflows] edge drives
        # a developer-safety suggestion.
        mk_path = _ROOT / "dist" / "claude-code" / ".claude-plugin" / "marketplace.json"
        mk = json.loads(mk_path.read_text(encoding="utf-8"))
        sugs = se.suggestions(mk, ["developer-workflows"])
        self.assertIn({"enhancer": "developer-safety",
                       "enhancee": "developer-workflows"}, sugs)
        # full set → no suggestion for developer-safety
        full = [p["name"] for p in mk["plugins"]]
        self.assertEqual(
            [s for s in se.suggestions(mk, full) if s["enhancer"] == "developer-safety"],
            [])


if __name__ == "__main__":
    unittest.main()
