#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/project_model.py (crickets #41, task 3).

Exercises the vault->item graph over a fixture board-items source: parse + shape
validation, parent-chain resolution + child ordering, the DC-1 materialization
boundary (active vs. non-active plan), silent-source carry-through, and every
malformed-graph refusal. stdlib only — no PyYAML, no pytest.
"""
from __future__ import annotations

import importlib.util
import json
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


def _fixture() -> dict:
    """A representative graph: a version, a feature, a sub-feature, an ACTIVE
    plan (parent=feature) with two tasks, a NON-active plan (parent=sub-feature)
    with one task, plus a backlog item (silent-sourced) and an idea."""
    return {
        "items": [
            {"id": "v5", "type": "version", "track": "V5", "title": "V5 arc",
             "about": "the unbundling"},
            {"id": "f-bs", "type": "feature", "parent": "v5", "track": "V5",
             "title": "Board sync", "goal": "sync", "why_matters": "humans"},
            {"id": "sf-render", "type": "sub-feature", "parent": "f-bs",
             "track": "V5", "title": "Render path"},
            {"id": "p-bs", "type": "plan", "parent": "f-bs", "track": "V5",
             "status": "in-progress", "title": "Build it",
             "fields": {"goal": "ship", "done_when": "green"}},
            {"id": "t1", "type": "task", "parent": "p-bs", "track": "V5",
             "title": "Task 1"},
            {"id": "t2", "type": "task", "parent": "p-bs", "track": "V5",
             "title": "Task 2"},
            {"id": "p-future", "type": "plan", "parent": "sf-render",
             "track": "V5", "status": "planning", "title": "Future plan"},
            {"id": "t3", "type": "task", "parent": "p-future", "track": "V5",
             "title": "Future task"},
            {"id": "b1", "type": "backlog-item", "track": "Backlog",
             "priority": "P2", "title": "Backlog thing",
             "silent_source": "private influence"},
            {"id": "i1", "type": "idea", "track": "Ideas", "title": "Idea spark"},
        ]
    }


class TestParseAndBuild(unittest.TestCase):
    def setUp(self):
        self.graph = pm.build_graph(pm.parse_items(_fixture()))

    def test_all_items_indexed(self):
        self.assertEqual(set(self.graph),
                         {"v5", "f-bs", "sf-render", "p-bs", "t1", "t2",
                          "p-future", "t3", "b1", "i1"})

    def test_top_level_have_no_parent(self):
        for tid in ("v5", "b1", "i1"):
            self.assertIsNone(self.graph[tid].parent)
            self.assertTrue(self.graph[tid].is_top_level)

    def test_children_linked_in_input_order(self):
        # children appear in the order they were declared in the source. p-future
        # hangs off sf-render (a plan may parent to a sub-feature), so f-bs has
        # only [sf-render, p-bs].
        self.assertEqual([c.id for c in self.graph["f-bs"].children],
                         ["sf-render", "p-bs"])
        self.assertEqual([c.id for c in self.graph["sf-render"].children], ["p-future"])
        self.assertEqual([c.id for c in self.graph["p-bs"].children], ["t1", "t2"])

    def test_extra_keys_become_fields(self):
        # Inline human-sentence keys and an explicit `fields` block both land in .fields.
        self.assertEqual(self.graph["f-bs"].fields, {"goal": "sync", "why_matters": "humans"})
        self.assertEqual(self.graph["p-bs"].fields, {"goal": "ship", "done_when": "green"})
        self.assertEqual(self.graph["v5"].fields, {"about": "the unbundling"})

    def test_structural_fields_not_leaked_into_fields(self):
        self.assertNotIn("track", self.graph["f-bs"].fields)
        self.assertNotIn("title", self.graph["f-bs"].fields)
        self.assertNotIn("parent", self.graph["f-bs"].fields)

    def test_silent_source_carried(self):
        self.assertEqual(self.graph["b1"].silent_source, "private influence")
        self.assertIsNone(self.graph["f-bs"].silent_source)

    def test_parent_chain(self):
        self.assertEqual([i.id for i in pm.parent_chain(self.graph, "t1")],
                         ["p-bs", "f-bs", "v5"])
        self.assertEqual([i.id for i in pm.parent_chain(self.graph, "t3")],
                         ["p-future", "sf-render", "f-bs", "v5"])
        self.assertEqual(pm.parent_chain(self.graph, "v5"), [])

    def test_parent_chain_unknown_raises(self):
        with self.assertRaises(pm.ModelError):
            pm.parent_chain(self.graph, "nope")


class TestDC1Materialization(unittest.TestCase):
    def setUp(self):
        self.graph = pm.build_graph(pm.parse_items(_fixture()))

    def test_active_plan_materializes_its_tasks_only(self):
        ids = [i.id for i in pm.materialize(self.graph, active_plans={"p-bs"})]
        # features-and-up always; the active plan + its tasks; NOT the future plan/task.
        self.assertEqual(set(ids),
                         {"v5", "f-bs", "sf-render", "b1", "i1", "p-bs", "t1", "t2"})
        self.assertNotIn("p-future", ids)
        self.assertNotIn("t3", ids)

    def test_no_active_plan_materializes_features_and_up_only(self):
        ids = {i.id for i in pm.materialize(self.graph, active_plans=set())}
        self.assertEqual(ids, {"v5", "f-bs", "sf-render", "b1", "i1"})
        # the DC-1 invariant: no plan or task is ever pre-persisted.
        types = {i.type for i in pm.materialize(self.graph, active_plans=set())}
        self.assertEqual(types & pm.DEFERRED_MATERIALIZE, set())

    def test_both_plans_active(self):
        ids = {i.id for i in pm.materialize(self.graph, active_plans={"p-bs", "p-future"})}
        self.assertEqual(ids, {"v5", "f-bs", "sf-render", "b1", "i1",
                               "p-bs", "t1", "t2", "p-future", "t3"})

    def test_unknown_active_id_ignored(self):
        ids = {i.id for i in pm.materialize(self.graph, active_plans={"ghost"})}
        self.assertEqual(ids, {"v5", "f-bs", "sf-render", "b1", "i1"})

    def test_order_is_deterministic_input_order(self):
        ids = [i.id for i in pm.materialize(self.graph, active_plans={"p-bs"})]
        self.assertEqual(ids, ["v5", "f-bs", "sf-render", "p-bs", "t1", "t2", "b1", "i1"])

    def test_already_issued_plan_materializes_without_active_plans(self):
        # A plan that already carries a board issue (e.g. Done, no longer
        # anyone's --active-plan) must stay materialized so a diff/nesting
        # reader never mistakes its real issue for an orphan. Regression for
        # crickets #165 (a Done plan's own kickoff issue read as an orphan).
        graph = pm.build_graph(pm.parse_items(_fixture()))
        graph["p-future"].issue = 165
        ids = {i.id for i in pm.materialize(graph, active_plans=set())}
        self.assertIn("p-future", ids)
        self.assertNotIn("t3", ids)  # its task has no issue and isn't active

    def test_already_issued_task_materializes_without_active_plans(self):
        graph = pm.build_graph(pm.parse_items(_fixture()))
        graph["t3"].issue = 200
        ids = {i.id for i in pm.materialize(graph, active_plans=set())}
        self.assertIn("t3", ids)
        self.assertNotIn("p-future", ids)  # the parent plan itself has no issue


class TestValidation(unittest.TestCase):
    def _build(self, items):
        return pm.build_graph(pm.parse_items({"items": items}))

    def test_unknown_type(self):
        with self.assertRaises(pm.ModelError):
            self._build([{"id": "x", "type": "epic", "title": "t"}])

    def test_missing_required_field(self):
        with self.assertRaises(pm.ModelError):
            self._build([{"id": "x", "type": "version"}])  # no title

    def test_duplicate_id(self):
        with self.assertRaises(pm.ModelError):
            self._build([
                {"id": "v", "type": "version", "title": "a"},
                {"id": "v", "type": "version", "title": "b"},
            ])

    def test_top_level_with_parent_rejected(self):
        with self.assertRaises(pm.ModelError):
            self._build([
                {"id": "v", "type": "version", "title": "a"},
                {"id": "v2", "type": "version", "parent": "v", "title": "b"},
            ])

    def test_missing_parent_rejected(self):
        with self.assertRaises(pm.ModelError):
            self._build([{"id": "f", "type": "feature", "parent": "ghost", "title": "f"}])

    def test_orphan_non_top_level_rejected(self):
        with self.assertRaises(pm.ModelError):
            self._build([{"id": "f", "type": "feature", "title": "f"}])  # no parent

    def test_wrong_parent_type_rejected(self):
        # task's parent must be a plan, not a feature.
        with self.assertRaises(pm.ModelError):
            self._build([
                {"id": "v", "type": "version", "title": "v"},
                {"id": "f", "type": "feature", "parent": "v", "title": "f"},
                {"id": "t", "type": "task", "parent": "f", "title": "t"},
            ])

    def test_plan_accepts_feature_or_subfeature_parent(self):
        # both legal — should not raise.
        g = self._build([
            {"id": "v", "type": "version", "title": "v"},
            {"id": "f", "type": "feature", "parent": "v", "title": "f"},
            {"id": "sf", "type": "sub-feature", "parent": "f", "title": "sf"},
            {"id": "p1", "type": "plan", "parent": "f", "title": "p1"},
            {"id": "p2", "type": "plan", "parent": "sf", "title": "p2"},
        ])
        self.assertEqual(g["p1"].parent, "f")
        self.assertEqual(g["p2"].parent, "sf")

    def test_parse_requires_items_list(self):
        with self.assertRaises(pm.ModelError):
            pm.parse_items({})
        with self.assertRaises(pm.ModelError):
            pm.parse_items({"items": "nope"})


class TestCycleGuard(unittest.TestCase):
    def test_assert_acyclic_detects_cycle(self):
        # The type rules make a cycle unreachable through build_graph (the
        # hierarchy is a strict DAG by level), so the guard is exercised directly.
        a = pm.Item(id="a", type="feature", title="a", parent="b")
        b = pm.Item(id="b", type="feature", title="b", parent="a")
        with self.assertRaises(pm.ModelError):
            pm._assert_acyclic({"a": a, "b": b})


class TestLoadFromFile(unittest.TestCase):
    def test_load_round_trips_from_json(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "board-items.json"
            p.write_text(json.dumps(_fixture()), encoding="utf-8")
            graph = pm.load(p)
            self.assertIn("p-bs", graph)
            self.assertEqual([c.id for c in graph["p-bs"].children], ["t1", "t2"])


class TestDump(unittest.TestCase):
    def test_dump_load_round_trips(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "board-items.json"
            p.write_text(json.dumps(_fixture()), encoding="utf-8")
            graph = pm.load(p)
            graph["p-bs"].issue = 42
            pm.dump(graph, p)
            reloaded = pm.load(p)
            self.assertEqual(reloaded["p-bs"].issue, 42)
            self.assertEqual([c.id for c in reloaded["p-bs"].children], ["t1", "t2"])
            self.assertEqual(reloaded["p-bs"].fields, {"goal": "ship", "done_when": "green"})

    def test_dump_preserves_unrelated_top_level_keys(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "board-items.json"
            data = _fixture()
            data["_comment"] = "machine projection"
            data["_reconciled_at"] = "2026-06-19"
            p.write_text(json.dumps(data), encoding="utf-8")
            graph = pm.load(p)
            pm.dump(graph, p)
            raw = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(raw["_comment"], "machine projection")
            self.assertEqual(raw["_reconciled_at"], "2026-06-19")

    def test_dump_omits_none_structural_fields(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "board-items.json"
            pm.dump({"v": pm.Item(id="v", type="version", title="V")}, p)
            raw = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(raw["items"], [{"id": "v", "type": "version", "title": "V"}])


if __name__ == "__main__":
    unittest.main()
