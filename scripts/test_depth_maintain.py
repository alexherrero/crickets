#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/depth_maintain.py (AG Wave D, task 2).

The Planner (TPM) persona's depth-floor maintainer: given a graph and a
harness dir of active PLAN-<slug>.md files, detect a Feature/Sub-feature with
zero materialized Plan children while a real, un-nested plan file exists for
it, and either materialize the missing Plan (idempotently, in-memory only —
this module never calls `gh`) or flag it for operator judgment when neither
matching signal (slug-equals-feature-id, or an explicit fields.plan_slug)
resolves. stdlib only — no pytest, no live `gh` calls, no network.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "github-projects" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pm = _load("project_model", _SRC / "project_model.py")
dm = _load("depth_maintain", _SRC / "depth_maintain.py")


def _graph(items):
    return pm.build_graph(pm.parse_items({"items": items}))


class TestListPlanSlugs(unittest.TestCase):
    def test_lists_named_plans_only(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN.md").write_text("# Singleton\n", encoding="utf-8")
            (d / "PLAN-foo.md").write_text("# Foo Plan\n", encoding="utf-8")
            (d / "PLAN-bar.md").write_text("# Bar Plan\n", encoding="utf-8")
            (d / "PLAN.archive.20260101-foo.md").write_text("# old\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            self.assertEqual(set(slugs), {"foo", "bar"})
            self.assertEqual(slugs["foo"], d / "PLAN-foo.md")

    def test_skips_conflicted_copies(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-foo.md").write_text("# Foo\n", encoding="utf-8")
            (d / "PLAN-foo (conflicted copy 2026-07-06).md").write_text("x", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            self.assertEqual(set(slugs), {"foo"})

    def test_missing_dir_returns_empty(self):
        self.assertEqual(dm.list_plan_slugs(Path("/does/not/exist")), {})


class TestFindDepthGaps(unittest.TestCase):
    def _fixture_no_plan(self):
        """A Feature with zero Plan children — the collapsed-depth case."""
        return _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ])

    def test_slug_equals_feature_id_is_auto_materializable(self):
        graph = self._fixture_no_plan()
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-some-feature.md").write_text("# Ship Some Feature\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            gaps = dm.find_depth_gaps(graph, slugs)
        self.assertEqual(len(gaps), 1)
        gap = gaps[0]
        self.assertEqual(gap.feature_id, "some-feature")
        self.assertEqual(gap.matched_slug, "some-feature")
        self.assertEqual(gap.reason, "")

    def test_explicit_plan_slug_field_wins_and_resolves(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w",
             "fields": {"plan_slug": "renamed-plan"}},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-renamed-plan.md").write_text("# Renamed\n", encoding="utf-8")
            # Also drop a same-id plan file to prove the explicit field wins,
            # not the id-equality fallback.
            (d / "PLAN-some-feature.md").write_text("# Should Not Be Used\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            gaps = dm.find_depth_gaps(graph, slugs)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].matched_slug, "renamed-plan")

    def test_explicit_plan_slug_field_with_no_matching_file_is_flagged(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w",
             "fields": {"plan_slug": "ghost-plan"}},
        ])
        gaps = dm.find_depth_gaps(graph, {})
        self.assertEqual(len(gaps), 1)
        self.assertIsNone(gaps[0].matched_slug)
        self.assertIn("ghost-plan", gaps[0].reason)

    def test_no_signal_at_all_is_not_flagged(self):
        # DC-1's expected steady state: a Feature with no active plan yet is
        # NOT a gap — silently no-op, not every under-populated Feature is drift.
        graph = self._fixture_no_plan()
        gaps = dm.find_depth_gaps(graph, {})
        self.assertEqual(gaps, [])

    def test_feature_with_existing_plan_child_is_never_a_gap(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-f-bs.md").write_text("# Should be ignored\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            gaps = dm.find_depth_gaps(graph, slugs)
        self.assertEqual(gaps, [])

    def test_sub_feature_checked_independently(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "sf-render", "type": "sub-feature", "parent": "f-bs",
             "title": "Render path"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-sf-render.md").write_text("# Render Path Plan\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            gaps = dm.find_depth_gaps(graph, slugs)
        # f-bs itself has no direct plan child (only a sub-feature child) but
        # also no matching plan file of its own id -> not flagged; sf-render
        # resolves via id-equality.
        self.assertEqual([g.feature_id for g in gaps], ["sf-render"])


class TestMaterializeGap(unittest.TestCase):
    def test_materializes_minimal_plan_item(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-some-feature.md").write_text("# Ship Some Feature\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            gaps = dm.find_depth_gaps(graph, slugs)
            item = dm.materialize_gap(gaps[0], graph)
        self.assertIsNotNone(item)
        self.assertEqual(item.id, "plan-some-feature")
        self.assertEqual(item.type, "plan")
        self.assertEqual(item.parent, "some-feature")
        self.assertEqual(item.title, "Ship Some Feature")
        self.assertIn(item, graph["some-feature"].children)
        self.assertIs(graph["plan-some-feature"], item)

    def test_falls_back_to_slug_when_no_h1(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-some-feature.md").write_text("no heading here\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            gaps = dm.find_depth_gaps(graph, slugs)
            item = dm.materialize_gap(gaps[0], graph)
        self.assertEqual(item.title, "PLAN-some-feature")

    def test_idempotent_second_call_is_noop(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-some-feature.md").write_text("# Ship\n", encoding="utf-8")
            slugs = dm.list_plan_slugs(d)
            gaps = dm.find_depth_gaps(graph, slugs)
            first = dm.materialize_gap(gaps[0], graph)
            self.assertEqual(len(graph["some-feature"].children), 1)
            second = dm.materialize_gap(gaps[0], graph)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(graph["some-feature"].children), 1)  # no duplicate

    def test_flagged_gap_is_never_materialized(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w",
             "fields": {"plan_slug": "ghost"}},
        ])
        gaps = dm.find_depth_gaps(graph, {})
        result = dm.materialize_gap(gaps[0], graph)
        self.assertIsNone(result)
        self.assertEqual(graph["some-feature"].children, [])


class TestRun(unittest.TestCase):
    def test_full_depth_no_op_zero_writes(self):
        """A fixture already at full depth -> no-op, zero writes (plan's own
        verification criterion for task 2)."""
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
            {"id": "t1", "type": "task", "parent": "p-bs", "title": "Task 1"},
        ])
        before = {iid: list(it.children) for iid, it in graph.items()}
        with tempfile.TemporaryDirectory() as t:
            result = dm.run(graph, Path(t))
        self.assertEqual(result, {"materialized": [], "flagged": []})
        after = {iid: list(it.children) for iid, it in graph.items()}
        self.assertEqual(before, after)

    def test_materializes_the_missing_plan_end_to_end(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-some-feature.md").write_text("# Ship Some Feature\n", encoding="utf-8")
            result = dm.run(graph, d)
        self.assertEqual(len(result["materialized"]), 1)
        self.assertEqual(result["flagged"], [])
        self.assertIn("plan-some-feature", graph)
        self.assertEqual(graph["plan-some-feature"].type, "plan")
        self.assertEqual(graph["some-feature"].type, "feature")  # untouched

    def test_dry_run_previews_without_mutating_graph(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-some-feature.md").write_text("# Ship\n", encoding="utf-8")
            result = dm.run(graph, d, materialize=False)
        self.assertEqual(result["materialized"], [])
        self.assertNotIn("some-feature", [c.id for c in graph["some-feature"].children])
        self.assertEqual(graph["some-feature"].children, [])


if __name__ == "__main__":
    unittest.main()
