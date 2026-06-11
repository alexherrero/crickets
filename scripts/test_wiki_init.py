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
        plan = wi.compute_scaffold_plan(set(), ["how-to", "reference", "explanation", "decisions"])
        rels = self._rels(plan)
        self.assertIn("Home.md", rels)
        self.assertIn("_Sidebar.md", rels)
        for s, base in [("how-to", "How-To"), ("reference", "Reference"),
                        ("explanation", "Explanation"), ("decisions", "Decisions")]:
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
        sections = ["how-to"]
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


class TestSevenSectionFrame(unittest.TestCase):
    """The static 7-section taxonomy frame + the two conditional slots
    (wiki-section-taxonomy 1/6 — static-frame)."""

    def test_default_sections_is_the_ordered_seven(self):
        self.assertEqual(
            wi.DEFAULT_SECTIONS,
            ["how-to", "reference", "architecture", "designs",
             "explanation", "decisions", "operational"])

    def test_renamed_entries_in_section_meta(self):
        # do -> how-to/How-To ; why -> explanation/Explanation (reversing the
        # earlier do->Do / why->Why-It-Works experiment).
        self.assertEqual(
            wi.section_meta("how-to"),
            ("How-To", "How-to", "Task-focused recipes for getting things done."))
        self.assertEqual(wi.section_meta("explanation")[:2], ("Explanation", "Explanation"))
        # the retired keys are gone from SECTION_META.
        for dead in ("get-started", "do", "why", "plugins"):
            self.assertNotIn(dead, wi.SECTION_META)

    def test_conditional_sections_are_architecture_and_operational(self):
        self.assertEqual(wi.CONDITIONAL_SECTIONS,
                         frozenset({"architecture", "operational"}))

    def test_neither_conditional_declared_yields_five_always_present(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS),
            ["how-to", "reference", "designs", "explanation", "decisions"])

    def test_both_conditionals_declared_yields_all_seven(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS, has_architecture=True, non_public=True),
            wi.DEFAULT_SECTIONS)

    def test_only_architecture_declared(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS, has_architecture=True),
            ["how-to", "reference", "architecture", "designs", "explanation", "decisions"])

    def test_only_operational_declared(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS, non_public=True),
            ["how-to", "reference", "designs", "explanation", "decisions", "operational"])


class TestRender(unittest.TestCase):
    def test_landing_is_index_mode(self):
        text = wi.render_landing("how-to")
        self.assertIn("<!-- mode: index -->", text)
        self.assertIn("# How-to", text)

    def test_folder_sidebar_links_landing(self):
        self.assertIn("[How-to](How-To)", wi.render_folder_sidebar("how-to"))

    def test_root_sidebar_lists_home_and_landings(self):
        text = wi.render_root_sidebar(["how-to", "reference"], "Demo")
        self.assertIn("[Home](Home)", text)
        self.assertIn("[How-to](How-To)", text)
        self.assertIn("[Reference](Reference)", text)

    def test_home_is_curated_with_links(self):
        text = wi.render_home(["how-to", "explanation"], "Demo")
        self.assertIn("# Demo Wiki", text)
        self.assertIn("(How-To)", text)


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
        self._assert_clean(["how-to", "reference", "designs", "explanation",
                            "decisions", "operational"])


class TestProvisionCI(unittest.TestCase):
    GATE = SCRIPTS / "check-wiki.py"

    def test_drops_workflow_and_vendors_gate(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            wi.provision_ci(target)
            wf = target / ".github" / "workflows"
            self.assertTrue((wf / "wiki-sync.yml").is_file())           # one lint-gates-publish workflow
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
            self.assertEqual([p.name for p in result["skipped"]], ["wiki-sync.yml"])
            self.assertEqual(result["workflows"], [])                    # nothing new dropped

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
            self.assertEqual(p["workflows"], ["wiki-sync.yml"])
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

    @unittest.expectedFailure
    def test_real_wiki_run_is_noop(self):
        # TRANSITIONAL RED (wiki-section-taxonomy, accepted "battery red 1→4").
        # static-frame (part 1) reshaped SECTION_META to the post-restructure
        # basenames (do -> how-to/How-To, why -> explanation/Explanation), but
        # crickets' OWN wiki still has the OLD folders (do/, why/, plugins/) until
        # crickets-dogfood (part 4) moves them. So `section_meta("why")` now falls
        # back to "Why" while the on-disk landing is "Why-It-Works" → the plan is
        # non-empty and this no-op assertion fails BY DESIGN in this window.
        #
        # RESTORE in crickets-dogfood (part 4): once crickets' wiki is on the new
        # frame, the run is a true no-op again — REMOVE this @expectedFailure. The
        # decorator self-alarms: a restored no-op turns this into an UNEXPECTED
        # SUCCESS (a unittest failure), forcing the cleanup. The assertion below is
        # unchanged — still the real no-op invariant, not a weakened one.
        existing = {p.relative_to(self.WIKI).as_posix()
                    for p in self.WIKI.rglob("*") if p.is_file()}
        plan = wi.compute_scaffold_plan(existing, self._sections(self.WIKI))
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
