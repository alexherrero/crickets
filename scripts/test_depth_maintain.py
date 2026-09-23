#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/depth_maintain.py (AG Wave D, task 2).

The Planner (TPM) persona's depth-floor maintainer: given a graph and the
plans agentm lists (a flat PLAN-<slug>.md, or a task's tasks/NNN-<slug>/plan.md;
the tests stand agentm's list in with `_in(d)`), detect a Feature/Sub-feature with
zero materialized Plan children while a real, un-nested plan file exists for
it, and either materialize the missing Plan (idempotently, in-memory only —
this module never calls `gh`) or flag it for operator judgment when neither
matching signal (slug-equals-feature-id, or an explicit fields.plan_slug)
resolves. stdlib only — no pytest, no live `gh` calls, no network.
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

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


def _in(d):
    """Stands in for agentm's plan list: the plan files in a scratch dir."""
    return sorted(Path(d).glob("*.md"))


class TestListPlanSlugs(unittest.TestCase):
    def test_lists_named_plans_only(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN.md").write_text("# Singleton\n", encoding="utf-8")
            (d / "PLAN-foo.md").write_text("# Foo Plan\n", encoding="utf-8")
            (d / "PLAN-bar.md").write_text("# Bar Plan\n", encoding="utf-8")
            (d / "PLAN.archive.20260101-foo.md").write_text("# old\n", encoding="utf-8")
            slugs = dm.index_plans(_in(d))
            self.assertEqual(set(slugs), {"foo", "bar"})
            self.assertEqual(slugs["foo"], d / "PLAN-foo.md")

    def test_skips_conflicted_copies(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-foo.md").write_text("# Foo\n", encoding="utf-8")
            (d / "PLAN-foo (conflicted copy 2026-07-06).md").write_text("x", encoding="utf-8")
            slugs = dm.index_plans(_in(d))
            self.assertEqual(set(slugs), {"foo"})

    def test_missing_dir_returns_empty(self):
        self.assertEqual(dm.list_plan_slugs(Path("/does/not/exist"), lister=lambda root: None), {})


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
            slugs = dm.index_plans(_in(d))
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
            slugs = dm.index_plans(_in(d))
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
            slugs = dm.index_plans(_in(d))
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
            slugs = dm.index_plans(_in(d))
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
            slugs = dm.index_plans(_in(d))
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
            slugs = dm.index_plans(_in(d))
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
            slugs = dm.index_plans(_in(d))
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


_PLAN_BODY = """# Ship It

## Tasks

### 1. First task
- What: do the first thing.

### 2. Second task
- What: do the second thing.
"""


class TestFindTaskGaps(unittest.TestCase):
    def _plan_with_zero_tasks(self):
        return _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
        ])

    def test_plan_with_checklist_and_no_tasks_is_a_gap(self):
        graph = self._plan_with_zero_tasks()
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-p-bs.md").write_text(_PLAN_BODY, encoding="utf-8")
            slugs = dm.index_plans(_in(d))
            gaps = dm.find_task_gaps(graph, slugs)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].plan_id, "p-bs")
        self.assertEqual(gaps[0].missing,
                         [("1", "First task"), ("2", "Second task")])

    def test_plan_with_task_children_already_is_never_a_gap(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
            {"id": "t1", "type": "task", "parent": "p-bs", "title": "Task 1"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-p-bs.md").write_text(_PLAN_BODY, encoding="utf-8")
            slugs = dm.index_plans(_in(d))
            gaps = dm.find_task_gaps(graph, slugs)
        self.assertEqual(gaps, [])

    def test_no_bound_plan_file_is_skipped_not_flagged(self):
        # An already-completed/archived plan with no live PLAN-<slug>.md —
        # its empty Task list is history, not a gap.
        graph = self._plan_with_zero_tasks()
        gaps = dm.find_task_gaps(graph, {})
        self.assertEqual(gaps, [])

    def test_plan_file_with_no_task_headings_is_not_a_gap(self):
        graph = self._plan_with_zero_tasks()
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-p-bs.md").write_text("# Ship It\n\nNo tasks yet.\n",
                                            encoding="utf-8")
            slugs = dm.index_plans(_in(d))
            gaps = dm.find_task_gaps(graph, slugs)
        self.assertEqual(gaps, [])


class TestMaterializeTaskGap(unittest.TestCase):
    def test_materializes_one_task_per_heading(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-p-bs.md").write_text(_PLAN_BODY, encoding="utf-8")
            slugs = dm.index_plans(_in(d))
            gaps = dm.find_task_gaps(graph, slugs)
            added = dm.materialize_task_gap(gaps[0], graph)
        self.assertEqual(len(added), 2)
        self.assertEqual([i.title for i in added], ["First task", "Second task"])
        self.assertEqual([c.id for c in graph["p-bs"].children],
                         ["p-bs-t1", "p-bs-t2"])
        self.assertEqual(graph["p-bs-t1"].parent, "p-bs")
        self.assertEqual(graph["p-bs-t1"].type, "task")

    def test_idempotent_second_call_adds_nothing(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-p-bs.md").write_text(_PLAN_BODY, encoding="utf-8")
            slugs = dm.index_plans(_in(d))
            gaps = dm.find_task_gaps(graph, slugs)
            first = dm.materialize_task_gap(gaps[0], graph)
            gaps2 = dm.find_task_gaps(graph, slugs)  # now has task children -> no gap
            second = dm.materialize_task_gap(gaps[0], graph) if gaps2 else []
        self.assertEqual(len(first), 2)
        self.assertEqual(gaps2, [])  # re-scan sees the plan as already full-depth
        self.assertEqual(len(graph["p-bs"].children), 2)  # no duplicates


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
            result = dm.run(graph, Path(t), lister=_in)
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
            result = dm.run(graph, d, lister=_in)
        self.assertEqual(len(result["materialized"]), 1)
        self.assertEqual(result["flagged"], [])
        self.assertIn("plan-some-feature", graph)
        self.assertEqual(graph["plan-some-feature"].type, "plan")
        self.assertEqual(graph["some-feature"].type, "feature")  # untouched

    def test_materializes_plan_then_its_own_tasks_in_one_cascade(self):
        # An already-materialized Plan with no Task children -> both levels
        # resolve in a single run() call: the Plan gap is Feature->Plan (n/a
        # here, it's already materialized), so this exercises Plan->Task alone
        # while a sibling Feature gap also resolves in the same pass.
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-p-bs.md").write_text(_PLAN_BODY, encoding="utf-8")
            result = dm.run(graph, d, lister=_in)
        self.assertEqual(len(result["materialized"]), 2)
        self.assertEqual(result["flagged"], [])
        self.assertEqual(set(graph["p-bs"].children[i].id for i in range(2)),
                         {"p-bs-t1", "p-bs-t2"})

    def test_dry_run_never_materializes_tasks_either(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "title": "Board sync",
             "goal": "g", "why_matters": "w"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-p-bs.md").write_text(_PLAN_BODY, encoding="utf-8")
            result = dm.run(graph, d, lister=_in, materialize=False)
        self.assertEqual(result["materialized"], [])
        self.assertEqual(graph["p-bs"].children, [])

    def test_dry_run_previews_without_mutating_graph(self):
        graph = _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ])
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "PLAN-some-feature.md").write_text("# Ship\n", encoding="utf-8")
            result = dm.run(graph, d, lister=_in, materialize=False)
        self.assertEqual(result["materialized"], [])
        self.assertNotIn("some-feature", [c.id for c in graph["some-feature"].children])
        self.assertEqual(graph["some-feature"].children, [])


class TestTheTaskLayout(unittest.TestCase):
    """agentm-vault part 15: plans come from agentm's list, and a task's
    `tasks/NNN-<verb-slug>/plan.md` matches a board item by either name."""

    def setUp(self):
        sys.path.insert(0, str(_HERE))
        import no_harness_fixture as nhf
        self.nhf = nhf
        self.sp = nhf.ScratchProject()
        self.addCleanup(self.sp.cleanup)
        patcher = mock.patch.dict(os.environ, {
            "AGENTM_SCRIPTS_DIR": str(self.sp.agentm), "HOME": str(self.sp.root / "home")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.assertEqual(self.nhf.harness_dirs(self.sp.root), [])

    def test_a_task_is_indexed_by_its_name_and_its_verb_slug(self):
        idx = dm.index_plans([self.sp.plan])
        self.assertEqual(idx, {"042-build-the-brief": self.sp.plan,
                               "build-the-brief": self.sp.plan})

    def test_a_shared_verb_slug_is_left_out(self):
        other = self.sp.project / "tasks" / "043-build-the-brief" / "plan.md"
        other.parent.mkdir()
        other.write_text("# Plan: again\n", encoding="utf-8")
        err = io.StringIO()
        with redirect_stderr(err):
            idx = dm.index_plans([self.sp.plan, other])
        self.assertEqual(set(idx), {"042-build-the-brief", "043-build-the-brief"})
        self.assertIn("more than one task", err.getvalue())

    def test_the_plans_come_from_agentm(self):
        self.assertEqual(dm.list_plan_slugs(self.sp.repo),
                         {"042-build-the-brief": self.sp.plan, "build-the-brief": self.sp.plan})

    def test_no_agentm_is_an_empty_index(self):
        os.environ["AGENTM_SCRIPTS_DIR"] = ""
        self.assertEqual(dm.list_plan_slugs(self.sp.repo), {})

    def _feature(self, fid):
        return _graph([
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x"},
            {"id": fid, "type": "feature", "parent": "v5",
             "title": "Brief", "goal": "g", "why_matters": "w"},
        ])

    def test_a_feature_keyed_by_the_verb_slug_materializes_the_task(self):
        graph = self._feature("build-the-brief")
        result = dm.run(graph, self.sp.repo)
        self.assertEqual([(i.type, i.title) for i in result["materialized"]][0],
                         ("plan", "Plan: Build the brief"))
        self.assertEqual(result["flagged"], [])

    def test_a_feature_keyed_by_the_full_name_materializes_the_task(self):
        graph = self._feature("042-build-the-brief")
        result = dm.run(graph, self.sp.repo, materialize=False)
        self.assertEqual(result["flagged"], [])

    def test_harness_dir_is_gone_from_both_clis(self):
        for prog in (dm._build_parser(),):
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                prog.parse_args(["--config", "p.json", "--harness-dir", "x"])


if __name__ == "__main__":
    unittest.main()
