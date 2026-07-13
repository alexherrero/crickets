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
SCRIPTS = REPO / "src" / "wiki" / "scripts"


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
        plan = wi.compute_scaffold_plan(set(), ["how-to", "reference", "explanation", "designs"])
        rels = self._rels(plan)
        self.assertIn("Home.md", rels)
        self.assertIn("_Sidebar.md", rels)
        for s, base in [("how-to", "How-To"), ("reference", "Reference"),
                        ("explanation", "Explanation"), ("designs", "Designs")]:
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


class TestSixSectionFrame(unittest.TestCase):
    """The static 6-section taxonomy frame + the two conditional slots
    (wiki-section-taxonomy 1/6 — static-frame)."""

    def test_default_sections_is_the_ordered_six(self):
        self.assertEqual(
            wi.DEFAULT_SECTIONS,
            ["how-to", "reference", "architecture", "designs",
             "explanation", "operational"])

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

    def test_neither_conditional_declared_yields_four_always_present(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS),
            ["how-to", "reference", "designs", "explanation"])

    def test_both_conditionals_declared_yields_all_six(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS, has_architecture=True, non_public=True),
            wi.DEFAULT_SECTIONS)

    def test_only_architecture_declared(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS, has_architecture=True),
            ["how-to", "reference", "architecture", "designs", "explanation"])

    def test_only_operational_declared(self):
        self.assertEqual(
            wi.active_sections(wi.DEFAULT_SECTIONS, non_public=True),
            ["how-to", "reference", "designs", "explanation", "operational"])


class TestArchitectureManifest(unittest.TestCase):
    """The per-project Architecture manifest: reader + validation (fail closed),
    pillar-toggle expansion, component scaffolding, and absent-manifest
    suppression (wiki-section-taxonomy 2/6 — architecture-manifest)."""

    COMPONENTS_ONLY = """\
architecture:
  components:
    - slug: plugins
      title: Plugins
      summary: One folder per plugin.
      overview: Plugins
    - slug: customization-model
      title: Customization model
      summary: How a customization is declared.
      overview: Customization-Model
"""

    # --- task 1: reader + schema validation (fail closed) ---

    def test_components_only_parses_in_order(self):
        comps = wi.parse_architecture_manifest(self.COMPONENTS_ONLY)
        self.assertEqual([c.slug for c in comps], ["plugins", "customization-model"])
        self.assertEqual(
            comps[0], wi.Component("plugins", "Plugins", "One folder per plugin.", "Plugins"))

    def test_unknown_pillar_fails_closed(self):
        with self.assertRaises(wi.ManifestError):
            wi.parse_architecture_manifest("architecture:\n  pillars: [nope]\n")

    def test_missing_required_key_fails_closed(self):
        text = ("architecture:\n  components:\n    - slug: plugins\n"
                "      title: Plugins\n      summary: s\n")     # no overview
        with self.assertRaises(wi.ManifestError) as cm:
            wi.parse_architecture_manifest(text)
        self.assertIn("overview", str(cm.exception))

    def test_empty_doc_yields_no_architecture(self):
        self.assertEqual(wi.parse_architecture_manifest(""), [])
        self.assertEqual(wi.parse_architecture_manifest("architecture:\n"), [])

    def test_missing_top_level_key_fails_closed(self):
        with self.assertRaises(wi.ManifestError):
            wi.parse_architecture_manifest("something_else: 1\n")

    def test_non_list_pillars_fails_closed(self):
        with self.assertRaises(wi.ManifestError):
            wi.parse_architecture_manifest("architecture:\n  pillars: host-adapters\n")

    def test_read_absent_file_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(wi.read_architecture_manifest(Path(td)), [])

    def test_read_present_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "architecture.yml").write_text(self.COMPONENTS_ONLY, encoding="utf-8")
            comps = wi.read_architecture_manifest(root)
            self.assertEqual([c.slug for c in comps], ["plugins", "customization-model"])

    def test_read_malformed_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "architecture.yml").write_text(
                "architecture:\n  pillars: [nope]\n", encoding="utf-8")
            with self.assertRaises(wi.ManifestError):
                wi.read_architecture_manifest(root)

    # --- task 2: pillar-toggle expansion ---

    def test_pillars_expand_to_templates(self):
        comps = wi.parse_architecture_manifest(
            "architecture:\n  pillars: [host-adapters, distribution]\n")
        self.assertEqual([c.slug for c in comps], ["host-adapters", "distribution"])
        self.assertEqual(comps[0], wi.PILLAR_TEMPLATES["host-adapters"])
        self.assertEqual(comps[1].title, "Build & distribution")

    def test_known_pillars_are_the_three_recurring(self):
        self.assertEqual(set(wi.PILLAR_TEMPLATES),
                         {"host-adapters", "sibling-interface", "distribution"})

    def test_pillars_then_components_order(self):
        text = ("architecture:\n  pillars: [host-adapters]\n  components:\n"
                "    - slug: plugins\n      title: Plugins\n      summary: s\n"
                "      overview: Plugins\n")
        comps = wi.parse_architecture_manifest(text)
        self.assertEqual([c.slug for c in comps], ["host-adapters", "plugins"])

    def test_components_override_pillar_in_place(self):
        # a components entry sharing a pillar slug overrides the template's FIELDS
        # but keeps the pillar's POSITION (first-declared wins ordering).
        text = ("architecture:\n  pillars: [host-adapters, distribution]\n  components:\n"
                "    - slug: host-adapters\n      title: Host adapters (repo-specific)\n"
                "      summary: custom wording.\n      overview: Host-Adapters\n")
        comps = wi.parse_architecture_manifest(text)
        self.assertEqual([c.slug for c in comps], ["host-adapters", "distribution"])
        self.assertEqual(comps[0].title, "Host adapters (repo-specific)")
        self.assertEqual(comps[0].summary, "custom wording.")

    # --- task 3: component scaffolding + absent-manifest suppression ---

    def test_scaffold_plan_adds_component_folders_in_order(self):
        comps = wi.parse_architecture_manifest(self.COMPONENTS_ONLY)
        rels = [it.relpath for it in wi.compute_scaffold_plan(set(), ["architecture"], comps)]
        self.assertEqual(rels, [
            "Home.md", "_Sidebar.md",
            "architecture/Architecture.md", "architecture/_Sidebar.md",
            "architecture/plugins/Plugins.md", "architecture/plugins/_Sidebar.md",
            "architecture/customization-model/Customization-Model.md",
            "architecture/customization-model/_Sidebar.md",
        ])

    def test_scaffold_re_run_is_noop(self):
        comps = wi.parse_architecture_manifest(self.COMPONENTS_ONLY)
        full = {it.relpath for it in wi.planned_items(["architecture"], comps)}
        self.assertEqual(wi.compute_scaffold_plan(full, ["architecture"], comps), [])

    def test_absent_manifest_scaffolds_no_component_folders(self):
        rels = [it.relpath for it in wi.compute_scaffold_plan(set(), ["architecture"], [])]
        self.assertEqual([r for r in rels if r.startswith("architecture/")],
                         ["architecture/Architecture.md", "architecture/_Sidebar.md"])

    def test_arch_landing_is_index_mode_with_summary(self):
        c = wi.Component("plugins", "Plugins", "One folder per plugin.", "Plugins")
        text = wi.render_arch_landing(c)
        self.assertIn("<!-- mode: index -->", text)
        self.assertIn("# Plugins", text)
        self.assertIn("One folder per plugin.", text)

    def test_arch_folder_sidebar_links_overview(self):
        c = wi.Component("customization-model", "Customization model", "s", "Customization-Model")
        self.assertIn("[Customization model](Customization-Model)",
                      wi.render_arch_folder_sidebar(c))

    # --- main() wiring: manifest presence is conditional gate #1 ---

    def _run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = wi.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_main_scaffolds_architecture_when_manifest_present(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            wiki.mkdir()
            (wiki / "architecture.yml").write_text(self.COMPONENTS_ONLY, encoding="utf-8")
            rc, _, _ = self._run_main(
                ["--root", str(wiki), "--no-ci", "--yes", "--visibility", "public"])
            self.assertEqual(rc, 0)
            self.assertTrue((wiki / "architecture" / "Architecture.md").is_file())
            self.assertTrue((wiki / "architecture" / "plugins" / "Plugins.md").is_file())
            self.assertTrue((wiki / "architecture" / "customization-model"
                             / "Customization-Model.md").is_file())

    def test_main_suppresses_architecture_without_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            wiki.mkdir()
            rc, _, _ = self._run_main(
                ["--root", str(wiki), "--no-ci", "--yes", "--visibility", "public"])
            self.assertEqual(rc, 0)
            self.assertFalse((wiki / "architecture").exists())

    def test_main_malformed_manifest_fails_closed_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            wiki.mkdir()
            (wiki / "architecture.yml").write_text(
                "architecture:\n  pillars: [nope]\n", encoding="utf-8")
            rc, _, err = self._run_main(["--root", str(wiki), "--no-ci", "--yes"])
            self.assertEqual(rc, 1)
            self.assertIn("unknown pillar", err)
            self.assertFalse((wiki / "architecture").exists())   # nothing written
            self.assertFalse((wiki / "Home.md").exists())        # fail closed = no scaffold


class TestNestedArchitectureSidebar(unittest.TestCase):
    """The third nesting level: the root _Sidebar.md Architecture bullet expands
    into its declared components, in manifest order, each linking to its overview
    page (wiki-section-taxonomy 3/6 — render-and-gate task 1). Fixtures:
    no-manifest · single-component · recurring-pillars."""

    SECTIONS = ["how-to", "reference", "architecture", "designs",
                "explanation"]

    def test_no_components_keeps_architecture_a_flat_bullet(self):
        # no-manifest fixture: architecture present in sections but no components →
        # a flat top-level bullet, NO nested sub-block.
        text = wi.render_root_sidebar(self.SECTIONS, "Demo")        # components=None
        self.assertIn("- [Architecture](Architecture)", text)
        self.assertNotIn("  - [", text)                            # no indented sub-bullets

    def test_single_component_nests_under_architecture(self):
        comps = [wi.Component("plugins", "Plugins", "s", "Plugins")]
        text = wi.render_root_sidebar(self.SECTIONS, "Demo", comps)
        self.assertIn("- [Architecture](Architecture)", text)
        self.assertIn("  - [Plugins](Plugins)", text)              # two-space indent (GFM nesting)
        # the sub-bullet sits between the Architecture bullet and the next section.
        lines = text.splitlines()
        arch = lines.index("- [Architecture](Architecture)")
        self.assertEqual(lines[arch + 1], "  - [Plugins](Plugins)")
        self.assertEqual(lines[arch + 2], "- [Designs](Designs)")

    def test_recurring_pillars_nest_in_manifest_order(self):
        comps = wi.parse_architecture_manifest(
            "architecture:\n  pillars: [host-adapters, sibling-interface]\n")
        text = wi.render_root_sidebar(["architecture"], "Demo", comps)
        lines = text.splitlines()
        arch = lines.index("- [Architecture](Architecture)")
        self.assertEqual(lines[arch + 1], "  - [Host adapters](Host-Adapters)")
        self.assertEqual(lines[arch + 2], "  - [Sibling interface](Sibling-Interface)")

    def test_only_architecture_nests_other_sections_stay_flat(self):
        comps = [wi.Component("plugins", "Plugins", "s", "Plugins")]
        text = wi.render_root_sidebar(self.SECTIONS, "Demo", comps)
        # exactly one indented sub-bullet (the single component); every other
        # section is a flat top-level bullet.
        self.assertEqual([ln for ln in text.splitlines() if ln.startswith("  - ")],
                         ["  - [Plugins](Plugins)"])

    def test_components_ignored_when_architecture_not_in_sections(self):
        comps = [wi.Component("plugins", "Plugins", "s", "Plugins")]
        text = wi.render_root_sidebar(["how-to", "reference"], "Demo", comps)
        self.assertNotIn("Plugins", text)                         # no architecture → no nest
        self.assertNotIn("  - [", text)

    def test_main_writes_nested_block_to_root_sidebar(self):
        # integration: a real run with a manifest writes the nested block into the
        # on-disk root _Sidebar.md.
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            wiki.mkdir()
            (wiki / "architecture.yml").write_text(
                TestArchitectureManifest.COMPONENTS_ONLY, encoding="utf-8")
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = wi.main(["--root", str(wiki), "--no-ci", "--yes",
                              "--visibility", "public"])
            self.assertEqual(rc, 0)
            sidebar = (wiki / "_Sidebar.md").read_text(encoding="utf-8")
            self.assertIn("- [Architecture](Architecture)", sidebar)
            self.assertIn("  - [Plugins](Plugins)", sidebar)
            self.assertIn("  - [Customization model](Customization-Model)", sidebar)


class TestOperationalVisibilityGate(unittest.TestCase):
    """Operational renders only on non-public wikis (wiki-section-taxonomy 3/6 —
    render-and-gate task 2). The axis is audience, not content-sensitivity:
    `private` and `internal` render it; `public` and `unknown` suppress it."""

    def test_renders_operational_per_visibility(self):
        self.assertTrue(wi.renders_operational("private"))
        self.assertTrue(wi.renders_operational("internal"))
        self.assertFalse(wi.renders_operational("public"))
        self.assertFalse(wi.renders_operational("unknown"))       # conservative default

    def _scaffold_with_visibility(self, visibility):
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            wiki.mkdir()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = wi.main(["--root", str(wiki), "--no-ci", "--yes",
                              "--visibility", visibility])
            return rc, (wiki / "operational").exists()

    def test_main_renders_operational_when_private(self):
        rc, has_op = self._scaffold_with_visibility("private")
        self.assertEqual(rc, 0)
        self.assertTrue(has_op)

    def test_main_renders_operational_when_internal(self):
        rc, has_op = self._scaffold_with_visibility("internal")
        self.assertEqual(rc, 0)
        self.assertTrue(has_op)

    def test_main_suppresses_operational_when_public(self):
        rc, has_op = self._scaffold_with_visibility("public")
        self.assertEqual(rc, 0)
        self.assertFalse(has_op)

    def test_main_suppresses_operational_when_unknown(self):
        rc, has_op = self._scaffold_with_visibility("unknown")
        self.assertEqual(rc, 0)
        self.assertFalse(has_op)


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
        self._assert_clean(["how-to", "reference", "architecture", "designs",
                            "explanation", "operational"])

    def test_architecture_manifest_scaffold_is_gate_clean(self):
        # a manifest-driven scaffold (Architecture + nested component folders +
        # the third-level sidebar render) is gate-clean by construction: every
        # component landing is referenced by both its folder _Sidebar.md and the
        # root nested block.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "wiki"
            root.mkdir()
            comps = wi.parse_architecture_manifest(
                TestArchitectureManifest.COMPONENTS_ONLY)
            sections = wi.active_sections(wi.DEFAULT_SECTIONS, has_architecture=True)
            wi.apply_scaffold(
                root, wi.compute_scaffold_plan(set(), sections, comps),
                sections, "Demo", comps)
            hard = [i for i in cw.collect_issues(root) if i.severity == "hard"]
            self.assertEqual(
                hard, [],
                "manifest scaffold has hard check-wiki issues:\n  "
                + "\n  ".join(f"[{i.rule}] {i.path.name}:{i.line}: {i.message}" for i in hard))


class TestProvisionCI(unittest.TestCase):
    GATE = SCRIPTS / "check-wiki.py"
    TRANSFORM = SCRIPTS / "wiki_publish_transform.py"

    def test_drops_workflow_and_vendors_gate(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            wi.provision_ci(target)
            wf = target / ".github" / "workflows"
            self.assertTrue((wf / "wiki-sync.yml").is_file())           # one lint-gates-publish workflow
            gate = target / ".github" / "scripts" / "check-wiki.py"
            self.assertEqual(gate.read_bytes(), self.GATE.read_bytes())  # vendored = plugin gate
            transform = target / ".github" / "scripts" / "wiki_publish_transform.py"
            self.assertEqual(transform.read_bytes(), self.TRANSFORM.read_bytes())  # vendored = plugin transform

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
            transform = target / ".github" / "scripts" / "wiki_publish_transform.py"
            transform.write_text("STALE", encoding="utf-8")
            r = wi.provision_ci(target)                                  # both present -> skip
            self.assertIsNone(r["gate"])
            self.assertIsNone(r["transform"])
            self.assertEqual(gate.read_text(encoding="utf-8"), "STALE")  # untouched
            self.assertEqual(transform.read_text(encoding="utf-8"), "STALE")  # untouched

    def test_resync_gate_revendors_even_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            wi.provision_ci(target)
            gate = target / ".github" / "scripts" / "check-wiki.py"
            gate.write_text("STALE", encoding="utf-8")
            transform = target / ".github" / "scripts" / "wiki_publish_transform.py"
            transform.write_text("STALE", encoding="utf-8")
            wi.provision_ci(target, resync_gate=True)
            self.assertEqual(gate.read_bytes(), self.GATE.read_bytes())
            self.assertEqual(transform.read_bytes(), self.TRANSFORM.read_bytes())

    def test_plan_ci_reports_then_converges(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            p = wi.plan_ci(target)
            self.assertEqual(p["workflows"], ["wiki-sync.yml"])
            self.assertTrue(p["gate"])
            self.assertTrue(p["transform"])
            wi.provision_ci(target)
            p2 = wi.plan_ci(target)
            self.assertEqual(p2["workflows"], [])     # all present
            self.assertFalse(p2["gate"])              # gate present
            self.assertFalse(p2["transform"])         # transform present


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
        # The intent-group folders — never hidden/dot dirs. A gitignored
        # wiki/.harness/ session marker is not a wiki section, and wiki-init never
        # treats it as one (it scaffolds DEFAULT_SECTIONS / --sections, not by
        # dir-scan), so the helper must skip dotdirs to mirror real behavior.
        return sorted(d.name for d in root.iterdir()
                      if d.is_dir() and not d.name.startswith("."))

    def test_real_wiki_run_is_noop(self):
        # The no-op invariant, RESTORED in crickets-dogfood (part 4): crickets' own
        # wiki is now on the six-section frame, so the section-level scaffold plan
        # converges to nothing to do. The @expectedFailure tripwire that guarded the
        # "battery red 1→4" transition window (parts 1-3, while crickets still had
        # the old do/, why/, plugins/ folders) is gone — its job is done. The
        # stronger lock (no-op WITH the architecture.yml manifest, plus the
        # rendered-sidebar == generator-output structural check) lives in
        # TestCricketsDogfoodLock below.
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


import re as _re

_LINK_RE = _re.compile(r"\[([^\]]+)\]\(([^)#]+)\)")


def _component_refs(text, overviews):
    """Ordered (label, target) pairs from sidebar `text` whose target is one of the
    Architecture component overview basenames. The hand-built sidebar uses emoji
    section headers + flat bullets while the generator nests two-space-indented
    sub-bullets; filtering on the component overviews compares the load-bearing
    content (which components, what label, in what order) without pinning the
    cosmetic shell — exactly the "keep rich operator sidebars" allowance."""
    return [(m.group(1), m.group(2)) for m in _LINK_RE.finditer(text)
            if m.group(2) in overviews]


class TestCricketsDogfoodLock(unittest.TestCase):
    """The wiki-section-taxonomy 4/6 lock: crickets' OWN restructured wiki +
    architecture.yml is a verified generator no-op, and its hand-built root sidebar
    agrees structurally with what the generator would render from the manifest. This
    is the proof that surface 1 (generator) and surface 2 (sidebars) agree — the
    design's Risk #1/#3 mitigation, guarded going forward by the battery."""
    WIKI = REPO / "wiki"

    def _components(self):
        return wi.read_architecture_manifest(self.WIKI)

    def _active_sections(self):
        # crickets: Architecture on (manifest present), Operational off (public).
        return wi.active_sections(wi.DEFAULT_SECTIONS, has_architecture=True,
                                  non_public=False)

    def test_full_scaffold_with_manifest_is_noop(self):
        # The strong lock: the FULL planned set — section landings + per-folder
        # sidebars + every architecture/<component>/ landing + sidebar from the real
        # architecture.yml — is already on disk, so the gap-fill plan is empty.
        components = self._components()
        self.assertEqual([c.slug for c in components],
                         ["plugins", "customization-model", "build-and-distribution",
                          "host-adapters", "harness-interface"])
        existing = {p.relative_to(self.WIKI).as_posix()
                    for p in self.WIKI.rglob("*") if p.is_file()}
        plan = wi.compute_scaffold_plan(existing, self._active_sections(), components)
        self.assertEqual([it.relpath for it in plan], [],
                         "wiki-init would create files — the dogfood no-op is broken")

    def test_root_sidebar_component_refs_match_generator(self):
        # Structural (not byte) equality: the component references in the hand-built
        # root _Sidebar.md == those the generator renders from the manifest — same
        # components, same labels, same order. NOT a byte-match (that would force
        # regenerating the operator's rich emoji-header sidebar, which the plan
        # forbids); structural agreement is the real invariant.
        components = self._components()
        overviews = {c.overview for c in components}
        real = (self.WIKI / "_Sidebar.md").read_text(encoding="utf-8")
        generated = wi.render_root_sidebar(self._active_sections(), "crickets", components)
        self.assertEqual(_component_refs(real, overviews),
                         _component_refs(generated, overviews))
        # and they are exactly the five components, in manifest order:
        self.assertEqual(_component_refs(real, overviews),
                         [(c.title, c.overview) for c in components])

    def test_sidebar_drift_is_caught(self):
        # Negative test: the structural check has teeth — drop one component from the
        # rendered sidebar and the agreement breaks loudly.
        components = self._components()
        overviews = {c.overview for c in components}
        real = (self.WIKI / "_Sidebar.md").read_text(encoding="utf-8")
        generated = wi.render_root_sidebar(self._active_sections(), "crickets", components)
        drifted = real.replace("- [Host adapters](Host-Adapters)\n", "")
        self.assertNotEqual(real, drifted, "fixture line not found — test is stale")
        self.assertNotEqual(_component_refs(drifted, overviews),
                            _component_refs(generated, overviews))


if __name__ == "__main__":
    unittest.main()
