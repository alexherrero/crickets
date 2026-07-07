#!/usr/bin/env python3
"""Tests for src/design/scripts/architecture_rung.py (crickets
wave-c-design-and-conventions, task 1).

Design call (documented in the task's own progress log, not silently
decided): the composition-analysis artifact is the parsed `children:`/
`governs:` frontmatter, not a search for specific prose section headings --
the two real AG HLD precedents use doc-specific prose ("How agentm and
crickets work together") that shares no generic heading string a template
could require verbatim. The architecture-review pass is a mechanical
existence check: every declared child resolves to a real file.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "design" / "scripts"


def _locate_agentm_designs() -> "Path | None":
    """The agentm repo's wiki/designs/ dir, or None if unreachable.

    Order: an explicit AGENTM_REPO override, then the conventional clone
    location -- NOT a naive "sibling of this repo's root" assumption, which
    breaks the moment this file runs from inside a nested worktree
    (.claude/worktrees/<slug>/ is not a sibling of ~/Antigravity/crickets at
    all). Mirrors agentm_bridge.py's own _candidate_dirs() convention."""
    override = os.environ.get("AGENTM_REPO", "").strip()
    if override:
        p = Path(os.path.expanduser(override)) / "wiki" / "designs"
        if p.is_dir():
            return p
    conventional = Path.home() / "Antigravity" / "agentm" / "wiki" / "designs"
    return conventional if conventional.is_dir() else None


_AGENTM_DESIGNS = _locate_agentm_designs()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


architecture_rung = _load("design_architecture_rung", _SRC / "architecture_rung.py")


class CompositionAnalysisFixtureTests(unittest.TestCase):
    """A multi-system design fixture (two or more systems + a cross-system
    composition claim) produces a composition-analysis artifact and an
    architecture-review pass."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.designs_dir = Path(self._tmp.name)
        (self.designs_dir / "child-a.md").write_text("# Child A\n", encoding="utf-8")
        (self.designs_dir / "child-b.md").write_text("# Child B\n", encoding="utf-8")
        self.parent = self.designs_dir / "parent-hld.md"
        self.parent.write_text(
            "---\n"
            "title: Fixture parent HLD\n"
            "status: launched\n"
            "kind: design\n"
            "scope: arc\n"
            "area: fixture/architecture\n"
            "governs:\n"
            "  - fixture/**\n"
            "children:\n"
            "  - child-a.md\n"
            "  - child-b.md\n"
            "---\n\n"
            "# Fixture parent HLD\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_multi_system_fixture_produces_the_composition_analysis_artifact(self):
        analysis = architecture_rung.composition_analysis(self.parent)
        self.assertEqual(analysis["children"], ["child-a.md", "child-b.md"])
        self.assertEqual(analysis["governs"], ["fixture/**"])
        self.assertTrue(analysis["is_multi_system"])

    def test_multi_system_fixture_produces_an_architecture_review_pass(self):
        review = architecture_rung.architecture_review(self.parent)
        self.assertEqual(review["missing"], [])
        self.assertTrue(review["passed"])

    def test_a_dangling_child_is_caught_as_a_broken_composition_claim(self):
        self.parent.write_text(
            self.parent.read_text(encoding="utf-8").replace("child-b.md", "child-does-not-exist.md"),
            encoding="utf-8",
        )
        review = architecture_rung.architecture_review(self.parent)
        self.assertEqual(review["missing"], ["child-does-not-exist.md"])
        self.assertFalse(review["passed"])

    def test_a_single_child_is_not_multi_system(self):
        self.parent.write_text(
            self.parent.read_text(encoding="utf-8").replace(
                "children:\n  - child-a.md\n  - child-b.md\n", "children:\n  - child-a.md\n",
            ),
            encoding="utf-8",
        )
        analysis = architecture_rung.composition_analysis(self.parent)
        self.assertFalse(analysis["is_multi_system"])


@unittest.skipUnless(_AGENTM_DESIGNS is not None, "agentm sibling checkout unavailable -- real-HLD test skipped")
class RealAgHldSetTests(unittest.TestCase):
    """Re-running against the actual AG HLD set (already-real designs)
    produces no contradictions with what was manually done there."""

    def test_agentm_hld_composition_claim_has_zero_dangling_children(self):
        # agentm-hld.md is the real, already-existing multi-system parent
        # (12 children, per its own frontmatter) -- confirms the mechanical
        # review agrees with what was manually verified when each child
        # design was added, with no retrofitting of either file.
        review = architecture_rung.architecture_review(_AGENTM_DESIGNS / "agentm-hld.md")
        self.assertEqual(review["missing"], [])
        self.assertTrue(review["passed"])
        self.assertGreaterEqual(len(review["resolved"]), 2)

    def test_agentm_foundations_hld_has_no_children_frontmatter(self):
        # Documented scope boundary: agentm-foundations-hld.md discusses two
        # systems (agentm + crickets) in prose but carries no `children:`
        # frontmatter -- composition_analysis's signal is frontmatter-based,
        # not prose-inferred, so this correctly reports not-multi-system
        # rather than a false contradiction.
        analysis = architecture_rung.composition_analysis(_AGENTM_DESIGNS / "agentm-foundations-hld.md")
        self.assertEqual(analysis["children"], [])
        self.assertFalse(analysis["is_multi_system"])


if __name__ == "__main__":
    unittest.main()
