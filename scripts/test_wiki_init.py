"""test_wiki_init.py — the wiki-init scaffold plan (task 1: pure gap-fill)."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "src" / "wiki-maintenance" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


wi = _load("wiki_init_under_test", SCRIPTS / "wiki_init.py")
cw = _load("check_wiki_for_init", SCRIPTS / "check-wiki.py")


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


class TestRender(unittest.TestCase):
    def test_landing_is_index_mode(self):
        text = wi.render_landing("get-started")
        self.assertIn("<!-- mode: index -->", text)
        self.assertIn("# Get started", text)

    def test_folder_sidebar_links_landing(self):
        self.assertIn("[How-to guides](How-To)", wi.render_folder_sidebar("do"))

    def test_root_sidebar_lists_home_and_landings(self):
        text = wi.render_root_sidebar(["get-started", "reference"], "Demo")
        self.assertIn("[Home](Home)", text)
        self.assertIn("[Get started](Get-Started)", text)
        self.assertIn("[Reference](Reference)", text)

    def test_home_is_curated_with_links(self):
        text = wi.render_home(["get-started", "why"], "Demo")
        self.assertIn("# Demo Wiki", text)
        self.assertIn("(Get-Started)", text)


class TestApply(unittest.TestCase):
    def test_apply_writes_only_the_plan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "wiki"
            root.mkdir()
            sections = ["reference"]
            plan = wi.compute_scaffold_plan(set(), sections)
            written = wi.apply_scaffold(root, plan, sections, "Demo")
            self.assertEqual({p.relative_to(root).as_posix() for p in written},
                             {"Home.md", "_Sidebar.md", "reference/Reference.md",
                              "reference/_Sidebar.md"})

    def test_apply_never_clobbers_existing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "wiki"
            (root / "reference").mkdir(parents=True)
            authored = root / "reference" / "Reference.md"
            authored.write_text("OPERATOR CONTENT", encoding="utf-8")
            existing = {"reference/Reference.md"}
            plan = wi.compute_scaffold_plan(existing, ["reference"])
            wi.apply_scaffold(root, plan, ["reference"], "Demo")
            self.assertEqual(authored.read_text(encoding="utf-8"), "OPERATOR CONTENT")

    def test_second_run_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "wiki"
            root.mkdir()
            sections = wi.DEFAULT_SECTIONS
            wi.apply_scaffold(root, wi.compute_scaffold_plan(set(), sections), sections, "Demo")
            existing = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(wi.compute_scaffold_plan(existing, sections), [])  # converged


class TestScaffoldPassesCheckWiki(unittest.TestCase):
    """The integration smoke: a freshly-scaffolded wiki/ has ZERO hard check-wiki
    issues — the scaffold is gate-passing by construction."""
    def _assert_clean(self, sections):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "wiki"
            root.mkdir()
            wi.apply_scaffold(root, wi.compute_scaffold_plan(set(), sections), sections, "Demo")
            hard = [i for i in cw.collect_issues(root) if i.severity == "hard"]
            self.assertEqual(
                hard, [],
                "scaffold has hard check-wiki issues:\n  "
                + "\n  ".join(f"[{i.rule}] {i.path.name}:{i.line}: {i.message}" for i in hard))

    def test_default_sections_scaffold_is_gate_clean(self):
        self._assert_clean(wi.DEFAULT_SECTIONS)

    def test_extended_sections_scaffold_is_gate_clean(self):
        self._assert_clean(["get-started", "do", "reference", "why", "designs", "decisions"])


if __name__ == "__main__":
    unittest.main()
