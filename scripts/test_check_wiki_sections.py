#!/usr/bin/env python3
"""Tests for check-wiki.py rule (m) — component-overview section structure.

A component-overview landing (architecture/<slug>/<Base>.md, mode index) carries
its manifest's required sections — intro · how-it-works · component-composition ·
see-also — in relative order. rule (m) reads the bundled section library (DC-5),
derives the required H2 order, and flags missing/out-of-order/unknown sections.
Soft on live pages during the taxonomy-migration interim (DC-6); the committed
proof-slice fixture is the hard acceptance test.
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


def _heads(text: str):
    return cw.parse_headings(text.splitlines())


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

    def test_optional_headings_empty_in_task1(self):
        # rule (n) / Task 2 populates this; in Task 1 it is intentionally empty.
        model = cw._component_overview_model()
        self.assertEqual(model.optional_headings, set())


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
    """Pure-logic checks against a synthetic model (isolated from the library)."""

    def setUp(self):
        self.model = cw.ComponentOverviewModel(
            ["How it works", "How it fits", "See also"], set())
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

    def test_unknown_section_fires(self):
        text = CONFORMING + "\n## Wibble\n\nNot a known section.\n"
        found = self._run(text)
        self.assertTrue(any("unknown section" in i.message and "Wibble" in i.message
                            for i in found))

    def test_host_gaps_unknown_in_task1(self):
        # Until rule (n) / Task 2 declares the optional heading-variants, an
        # optional section like `## Host gaps` reads as unknown. Documents the gap.
        text = CONFORMING.replace(
            "## See also",
            "## Host gaps\n\n- It has a host gap.\n\n## See also")
        found = self._run(text)
        self.assertTrue(any("unknown section" in i.message and "Host gaps" in i.message
                            for i in found))

    def test_findings_are_soft(self):
        text = CONFORMING + "\n## Wibble\n\nUnknown.\n"
        found = self._run(text)
        self.assertTrue(found)
        self.assertTrue(all(i.severity == "soft" for i in found))

    def test_none_model_is_noop(self):
        issues: list = []
        cw.rule_m_section_order(self.p, _heads(CONFORMING), None, issues)
        self.assertEqual(issues, [])


class FixtureAcceptanceTest(unittest.TestCase):
    """The committed proof-slice fixture is the hard test: a full collect_issues
    scan over it must surface zero rule-(m) findings (DC-6)."""

    def _wiki(self) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def test_committed_fixture_has_no_rule_m_findings(self):
        root = self._wiki()
        dest = root / "architecture" / "sample-component" / "Sample-Component.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text((FIXTURES / "Sample-Component.md").read_text(encoding="utf-8"),
                        encoding="utf-8")
        m_issues = [i for i in cw.collect_issues(root) if i.rule == "m"]
        self.assertEqual(m_issues, [], f"fixture should be clean, got: {m_issues}")

    def test_broken_page_fires_rule_m(self):
        root = self._wiki()
        broken = root / "architecture" / "broken" / "Broken.md"
        broken.parent.mkdir(parents=True, exist_ok=True)
        # H2s out of manifest order — How it fits before How it works.
        broken.write_text(
            "<!-- mode: index -->\n# Broken\n\n**Crickets** is a toolkit.\n\n"
            "## How it fits\n\n- **[Sib](Sib)** — seam.\n\n"
            "## How it works\n\nIt works.\n\n## See also\n\n- [Ref](Ref) — detail.\n",
            encoding="utf-8")
        m_issues = [i for i in cw.collect_issues(root) if i.rule == "m"]
        self.assertTrue(m_issues, "broken component-overview should fire rule m")
        self.assertTrue(all(i.severity == "soft" for i in m_issues))


if __name__ == "__main__":
    unittest.main()
