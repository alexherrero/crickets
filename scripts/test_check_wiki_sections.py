#!/usr/bin/env python3
"""Tests for check-wiki.py rules (m) + (n) — component-overview section structure.

A component-overview landing (architecture/<slug>/<Base>.md, mode index) carries
its manifest's required sections — intro · how-it-works · component-composition ·
see-also — in relative order (rule m). Every H2 is either a required section or a
declared heading-variant of an optional section that applies to component-overview
(rule n, e.g. safety → Safety / Host gaps / Limitations); any other H2 is unknown.
Both read the bundled section library (DC-5). Soft on live pages during the
taxonomy-migration interim (DC-6); the committed proof-slice fixtures are the hard
acceptance tests.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
FIXTURES = SCRIPTS / "fixtures" / "component-overview"


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


cw = _load("check_wiki_sections_under_test", "../src/wiki-maintenance/scripts/check-wiki.py")

OPTIONAL = {"Safety", "Host gaps", "Limitations"}


def _heads(text: str):
    return cw.parse_headings(text.splitlines())


def _model(optional=OPTIONAL):
    return cw.ComponentOverviewModel(["How it works", "How it fits", "See also"], set(optional))


# A conforming component-overview body: intro (no H2) + the three required H2s.
CONFORMING = """<!-- mode: index -->
# Some Component

**Crickets** is a toolkit. This component does a thing.

## How it works

It works like so.

## How it fits

- **[Sibling](Sibling)** — what crosses the seam.

## See also

- [Reference](Reference) — the field-level detail.
"""


class ComponentOverviewModelTest(unittest.TestCase):
    """The model is derived from the bundled manifest + section library."""

    def test_required_h2s_match_manifest_order(self):
        model = cw._component_overview_model()
        self.assertIsNotNone(model, "section library should be reachable in-repo")
        self.assertEqual(model.required_h2s, ["How it works", "How it fits", "See also"])

    def test_optional_headings_from_library(self):
        # rule (n)'s allowance: the safety section's declared heading-variants,
        # scanned from the library (optional: true + applies-to component-overview).
        model = cw._component_overview_model()
        self.assertEqual(model.optional_headings, {"Safety", "Host gaps", "Limitations"})


class DetectionTest(unittest.TestCase):
    """_is_component_overview encodes DC-3: nested-one-level mode-index pages
    under architecture/, excluding Architecture.md + the plugins/** subtree."""

    def _wiki(self) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def _write(self, root: Path, rel: str, text: str = "# X\n") -> Path:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def test_nested_index_page_is_component_overview(self):
        root = self._wiki()
        p = self._write(root, "architecture/sample-component/Sample-Component.md")
        self.assertTrue(cw._is_component_overview(p, root))

    def test_top_level_architecture_md_excluded(self):
        root = self._wiki()
        p = self._write(root, "architecture/Architecture.md")
        self.assertFalse(cw._is_component_overview(p, root))

    def test_plugins_subtree_excluded(self):
        root = self._wiki()
        p = self._write(root, "architecture/plugins/Plugins.md")
        self.assertFalse(cw._is_component_overview(p, root))

    def test_deeper_nesting_excluded(self):
        root = self._wiki()
        p = self._write(root, "architecture/comp/sub/Deep.md")
        self.assertFalse(cw._is_component_overview(p, root))

    def test_non_index_mode_excluded(self):
        # A mode hint overrides the architecture folder default; a how-to-moded
        # page in the slot is not a component overview.
        root = self._wiki()
        p = self._write(root, "architecture/odd/Odd.md", "<!-- mode: how-to -->\n# Odd\n")
        self.assertFalse(cw._is_component_overview(p, root))

    def test_outside_architecture_excluded(self):
        root = self._wiki()
        p = self._write(root, "how-to/Something.md")
        self.assertFalse(cw._is_component_overview(p, root))

    def test_path_outside_wiki_root_excluded(self):
        root = self._wiki()
        outside = Path(tempfile.mkdtemp()) / "architecture" / "x" / "X.md"
        self.addCleanup(shutil.rmtree, outside.parent.parent, ignore_errors=True)
        self.assertFalse(cw._is_component_overview(outside, root))


class RuleMSectionOrderTest(unittest.TestCase):
    """rule (m) owns required-section presence + relative order ONLY; membership
    of extra H2s is rule (n)'s job."""

    def setUp(self):
        self.model = _model()
        self.p = Path("architecture/x/X.md")

    def _run(self, text: str):
        issues: list = []
        cw.rule_m_section_order(self.p, _heads(text), self.model, issues)
        return [i for i in issues if i.rule == "m"]

    def test_conforming_page_clean(self):
        self.assertEqual(self._run(CONFORMING), [])

    def test_swapped_order_fires(self):
        text = CONFORMING.replace(
            "## How it works\n\nIt works like so.\n\n## How it fits\n\n"
            "- **[Sibling](Sibling)** — what crosses the seam.\n",
            "## How it fits\n\n- **[Sibling](Sibling)** — what crosses the seam.\n\n"
            "## How it works\n\nIt works like so.\n")
        found = self._run(text)
        self.assertTrue(any("missing or out of order" in i.message for i in found))

    def test_missing_required_section_fires(self):
        text = CONFORMING.replace(
            "## How it fits\n\n- **[Sibling](Sibling)** — what crosses the seam.\n\n", "")
        found = self._run(text)
        self.assertTrue(any("missing or out of order" in i.message for i in found))

    def test_unknown_section_does_not_fire_m(self):
        # An extra H2 with the required order intact is rule (n)'s concern, not (m)'s.
        text = CONFORMING + "\n## Wibble\n\nNot a known section.\n"
        self.assertEqual(self._run(text), [])

    def test_findings_are_soft(self):
        text = CONFORMING.replace(
            "## How it works\n\nIt works like so.\n\n## How it fits\n\n"
            "- **[Sibling](Sibling)** — what crosses the seam.\n",
            "## How it fits\n\n- **[Sibling](Sibling)** — what crosses the seam.\n\n"
            "## How it works\n\nIt works like so.\n")
        found = self._run(text)
        self.assertTrue(found)
        self.assertTrue(all(i.severity == "soft" for i in found))

    def test_none_model_is_noop(self):
        issues: list = []
        cw.rule_m_section_order(self.p, _heads(CONFORMING), None, issues)
        self.assertEqual(issues, [])


class RuleNHeadingVariantTest(unittest.TestCase):
    """rule (n): every H2 is a required section or a declared optional
    heading-variant; anything else is an unknown section."""

    def setUp(self):
        self.model = _model()
        self.p = Path("architecture/x/X.md")

    def _run(self, text: str, model=None):
        issues: list = []
        cw.rule_n_heading_variant(self.p, _heads(text), model or self.model, issues)
        return [i for i in issues if i.rule == "n"]

    def test_conforming_page_clean(self):
        self.assertEqual(self._run(CONFORMING), [])

    def test_unknown_section_fires(self):
        text = CONFORMING + "\n## Wibble\n\nNot a known section.\n"
        found = self._run(text)
        self.assertTrue(any("unknown section" in i.message and "Wibble" in i.message
                            for i in found))

    def test_optional_host_gaps_allowed(self):
        text = CONFORMING.replace(
            "## See also",
            "## Host gaps\n\n- It has a host gap.\n\n## See also")
        self.assertEqual(self._run(text), [])

    def test_optional_limitations_allowed(self):
        text = CONFORMING.replace(
            "## See also",
            "## Limitations\n\n- It has a limitation.\n\n## See also")
        self.assertEqual(self._run(text), [])

    def test_off_list_heading_fires(self):
        text = CONFORMING.replace(
            "## See also",
            "## Caveats\n\n- An off-list heading.\n\n## See also")
        found = self._run(text)
        self.assertTrue(any("unknown section" in i.message and "Caveats" in i.message
                            for i in found))

    def test_host_gaps_unknown_when_optional_set_empty(self):
        # Documents the model-population dependency: without the library scan
        # (empty optional set) an optional heading reads as unknown.
        text = CONFORMING.replace(
            "## See also",
            "## Host gaps\n\n- It has a host gap.\n\n## See also")
        found = self._run(text, model=_model(optional=set()))
        self.assertTrue(any("Host gaps" in i.message for i in found))

    def test_findings_are_soft(self):
        text = CONFORMING + "\n## Wibble\n\nUnknown.\n"
        found = self._run(text)
        self.assertTrue(found)
        self.assertTrue(all(i.severity == "soft" for i in found))

    def test_none_model_is_noop(self):
        issues: list = []
        cw.rule_n_heading_variant(self.p, _heads(CONFORMING), None, issues)
        self.assertEqual(issues, [])


class FixtureAcceptanceTest(unittest.TestCase):
    """The committed proof-slice fixtures are the hard test: a full collect_issues
    scan over each must surface zero rule (m)/(n) findings (DC-6)."""

    def _wiki(self) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def _place(self, root: Path, slug: str, fixture: str) -> None:
        dest = root / "architecture" / slug / fixture
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text((FIXTURES / fixture).read_text(encoding="utf-8"), encoding="utf-8")

    def _mn(self, root: Path):
        return [i for i in cw.collect_issues(root) if i.rule in ("m", "n")]

    def test_required_only_fixture_clean(self):
        root = self._wiki()
        self._place(root, "sample-component", "Sample-Component.md")
        self.assertEqual(self._mn(root), [], "required-only fixture should be clean")

    def test_guarded_fixture_with_optional_section_clean(self):
        # A Host-Adapters-shaped page (optional `## Host gaps` between How it fits
        # and See also) passes clean once rule (n) reads the optional set.
        root = self._wiki()
        self._place(root, "sample-guarded", "Sample-Guarded-Component.md")
        self.assertEqual(self._mn(root), [], "guarded fixture should be clean")

    def test_broken_order_fires_rule_m(self):
        root = self._wiki()
        broken = root / "architecture" / "broken" / "Broken.md"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_text(
            "<!-- mode: index -->\n# Broken\n\n**Crickets** is a toolkit.\n\n"
            "## How it fits\n\n- **[Sib](Sib)** — seam.\n\n"
            "## How it works\n\nIt works.\n\n## See also\n\n- [Ref](Ref) — detail.\n",
            encoding="utf-8")
        m_issues = [i for i in cw.collect_issues(root) if i.rule == "m"]
        self.assertTrue(m_issues, "out-of-order component-overview should fire rule m")
        self.assertTrue(all(i.severity == "soft" for i in m_issues))

    def test_off_list_heading_fires_rule_n(self):
        root = self._wiki()
        bad = root / "architecture" / "offlist" / "Offlist.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text(
            "<!-- mode: index -->\n# Offlist\n\n**Crickets** is a toolkit.\n\n"
            "## How it works\n\nIt works.\n\n## How it fits\n\n- **[Sib](Sib)** — seam.\n\n"
            "## Caveats\n\n- Off-list heading.\n\n## See also\n\n- [Ref](Ref) — detail.\n",
            encoding="utf-8")
        n_issues = [i for i in cw.collect_issues(root) if i.rule == "n"]
        self.assertTrue(any("Caveats" in i.message for i in n_issues),
                        "off-list heading should fire rule n")
        self.assertTrue(all(i.severity == "soft" for i in n_issues))


if __name__ == "__main__":
    unittest.main()
