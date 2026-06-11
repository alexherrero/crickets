"""test_wiki_init.py — the wiki-init scaffold plan (task 1: pure gap-fill)."""
import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WI_PATH = REPO / "src" / "wiki-maintenance" / "scripts" / "wiki_init.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


wi = _load("wiki_init_under_test", WI_PATH)


class TestScaffoldPlan(unittest.TestCase):
    def _rels(self, plan):
        return [it.relpath for it in plan]

    def test_empty_yields_full_scaffold(self):
        plan = wi.compute_scaffold_plan(set(), ["get-started", "do", "reference", "why"])
        rels = self._rels(plan)
        self.assertIn("Home.md", rels)
        self.assertIn("_Sidebar.md", rels)
        for s, base in [("get-started", "Get-Started"), ("do", "How-To"),
                        ("reference", "Reference"), ("why", "Why")]:
            self.assertIn(f"{s}/{base}.md", rels)
            self.assertIn(f"{s}/_Sidebar.md", rels)
        self.assertEqual(len(plan), 2 + 2 * 4)   # 2 root + (landing + sidebar) * 4

    def test_default_sections(self):
        plan = wi.compute_scaffold_plan(set())   # default section set
        self.assertEqual(len(plan), 2 + 2 * len(wi.DEFAULT_SECTIONS))

    def test_partial_fills_only_gaps(self):
        existing = {"Home.md", "reference/Reference.md"}
        rels = self._rels(wi.compute_scaffold_plan(existing, ["reference"]))
        self.assertNotIn("Home.md", rels)                  # exists -> not planned
        self.assertNotIn("reference/Reference.md", rels)   # exists -> never clobbered
        self.assertIn("_Sidebar.md", rels)                 # missing
        self.assertIn("reference/_Sidebar.md", rels)       # missing

    def test_full_is_noop(self):
        sections = ["get-started"]
        full = {it.relpath for it in wi.planned_items(sections)}
        self.assertEqual(wi.compute_scaffold_plan(full, sections), [])

    def test_unknown_section_fallback_basename(self):
        rels = self._rels(wi.compute_scaffold_plan(set(), ["my-stuff"]))
        self.assertIn("my-stuff/My-Stuff.md", rels)        # title-cased fallback
        self.assertIn("my-stuff/_Sidebar.md", rels)

    def test_parse_sections(self):
        self.assertEqual(wi.parse_sections(None), wi.DEFAULT_SECTIONS)
        self.assertEqual(wi.parse_sections("a, b  c"), ["a", "b", "c"])
        self.assertEqual(wi.parse_sections(""), wi.DEFAULT_SECTIONS)


if __name__ == "__main__":
    unittest.main()
