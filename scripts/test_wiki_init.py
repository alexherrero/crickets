"""test_wiki_init.py — the wiki-init scaffold plan (task 1: pure gap-fill)."""
import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        for s, base in [("get-started", "Get-Started"), ("do", "Do"),
                        ("reference", "Reference"), ("why", "Why-It-Works")]:
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
        self.assertIn("[Do](Do)", wi.render_folder_sidebar("do"))

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


class TestProvisionCI(unittest.TestCase):
    GATE = SCRIPTS / "check-wiki.py"

    def test_drops_both_workflows_and_vendors_gate(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            wi.provision_ci(target)
            wf = target / ".github" / "workflows"
            self.assertTrue((wf / "wiki-sync.yml").is_file())
            self.assertTrue((wf / "wiki-lint.yml").is_file())
            gate = target / ".github" / "scripts" / "check-wiki.py"
            self.assertEqual(gate.read_bytes(), self.GATE.read_bytes())  # vendored = plugin gate

    def test_workflow_gap_fill_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            wf = target / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "wiki-sync.yml").write_text("USER EDITED", encoding="utf-8")
            result = wi.provision_ci(target)
            self.assertEqual((wf / "wiki-sync.yml").read_text(encoding="utf-8"), "USER EDITED")
            self.assertTrue((wf / "wiki-lint.yml").is_file())            # missing one dropped
            self.assertEqual([p.name for p in result["skipped"]], ["wiki-sync.yml"])

    def test_default_run_does_not_re_vendor_present_gate(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            wi.provision_ci(target)
            gate = target / ".github" / "scripts" / "check-wiki.py"
            gate.write_text("STALE", encoding="utf-8")
            r = wi.provision_ci(target)                                  # gate present -> skip
            self.assertIsNone(r["gate"])
            self.assertEqual(gate.read_text(encoding="utf-8"), "STALE")  # untouched

    def test_resync_gate_revendors_even_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            wi.provision_ci(target)
            gate = target / ".github" / "scripts" / "check-wiki.py"
            gate.write_text("STALE", encoding="utf-8")
            wi.provision_ci(target, resync_gate=True)
            self.assertEqual(gate.read_bytes(), self.GATE.read_bytes())

    def test_plan_ci_reports_then_converges(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            p = wi.plan_ci(target)
            self.assertEqual(set(p["workflows"]), {"wiki-sync.yml", "wiki-lint.yml"})
            self.assertTrue(p["gate"])
            wi.provision_ci(target)
            p2 = wi.plan_ci(target)
            self.assertEqual(p2["workflows"], [])     # all present
            self.assertFalse(p2["gate"])              # gate present


class TestCostWarning(unittest.TestCase):
    """The non-public Actions-minutes warning (operator-locked requirement)."""

    def test_public_is_silent(self):
        self.assertIsNone(wi.cost_warning("public"))

    def test_private_warns(self):
        w = wi.cost_warning("private")
        self.assertIsNotNone(w)
        self.assertIn("private", w)
        self.assertIn("billed", w)

    def test_internal_warns(self):
        self.assertIn("internal", wi.cost_warning("internal"))

    def test_unknown_warns_conservatively(self):
        w = wi.cost_warning("unknown")
        self.assertIsNotNone(w)
        self.assertIn("Could not determine", w)

    def test_detect_visibility_lowercases_gh_output(self):
        v = wi.detect_visibility(Path("."), fetch=lambda root: "PRIVATE\n")
        self.assertEqual(v, "private")

    def test_detect_visibility_unknown_when_gh_fails(self):
        def boom(root):
            raise FileNotFoundError("gh not installed")
        self.assertEqual(wi.detect_visibility(Path("."), fetch=boom), "unknown")


class TestMainCostGate(unittest.TestCase):
    """main() surfaces the warning before the workflow write and the
    confirmation gate stops a declined non-public run."""

    def _run(self, argv, stdin_input=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            if stdin_input is not None:
                with mock.patch("builtins.input", return_value=stdin_input):
                    rc = wi.main(argv)
            else:
                rc = wi.main(argv)
        return rc, out.getvalue()

    def test_preview_private_prints_warning_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            rc, text = self._run(
                ["--root", str(wiki), "--visibility", "private", "--preview"])
            self.assertEqual(rc, 0)
            self.assertIn("billed", text)
            self.assertFalse((Path(td) / ".github").exists())   # nothing written

    def test_preview_public_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            _, text = self._run(
                ["--root", str(wiki), "--visibility", "public", "--preview"])
            self.assertNotIn("billed", text)

    def test_decline_writes_no_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            rc, text = self._run(
                ["--root", str(wiki), "--visibility", "private"], stdin_input="n")
            self.assertEqual(rc, 0)
            self.assertIn("aborted", text)
            self.assertFalse((Path(td) / ".github" / "workflows").exists())

    def test_yes_private_warns_but_writes(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            rc, text = self._run(
                ["--root", str(wiki), "--visibility", "private", "--yes"])
            self.assertEqual(rc, 0)
            self.assertIn("billed", text)                       # still informed
            wf = Path(td) / ".github" / "workflows"
            self.assertTrue((wf / "wiki-sync.yml").is_file())   # but proceeded
            self.assertTrue((wf / "wiki-lint.yml").is_file())

    def test_no_ci_skips_warning_even_when_private(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            _, text = self._run(
                ["--root", str(wiki), "--visibility", "private", "--no-ci", "--yes"])
            self.assertNotIn("billed", text)                    # no workflows → no bill
            self.assertFalse((Path(td) / ".github").exists())


class TestRealWikiSmoke(unittest.TestCase):
    """Integration smoke: running wiki-init against crickets' OWN wiki is a
    no-op that never clobbers operator content (design Migrations note).
    crickets is the canonical reference for the intent-group IA, so SECTION_META
    mirrors its landing basenames — the run converges to nothing to do."""
    WIKI = REPO / "wiki"

    def _sections(self, root):
        return sorted(d.name for d in root.iterdir() if d.is_dir())

    def test_real_wiki_run_is_noop(self):
        existing = {p.relative_to(self.WIKI).as_posix()
                    for p in self.WIKI.rglob("*") if p.is_file()}
        plan = wi.compute_scaffold_plan(existing, self._sections(self.WIKI))
        # True no-op: SECTION_META is reconciled to crickets' own landing
        # basenames (do -> Do, why -> Why-It-Works, …), so every section's landing
        # + sidebar already exists. An empty plan also means apply can't clobber.
        self.assertEqual([it.relpath for it in plan], [])

    def test_apply_on_real_wiki_copy_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "wiki"
            shutil.copytree(self.WIKI, copy)
            before = {p.relative_to(copy).as_posix(): p.read_bytes()
                      for p in copy.rglob("*") if p.is_file()}
            sections = self._sections(copy)
            plan = wi.compute_scaffold_plan(set(before), sections)
            written = wi.apply_scaffold(copy, plan, sections, "crickets")
            for rel, data in before.items():                      # never clobbered
                self.assertEqual((copy / rel).read_bytes(), data, f"clobbered {rel}")
            added = {p.relative_to(copy).as_posix() for p in written}
            self.assertEqual(added, {it.relpath for it in plan})  # only the gaps
            self.assertTrue(added.isdisjoint(before))             # additive only


if __name__ == "__main__":
    unittest.main()
