#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/planner_maintain.py (AG Wave D, task 4).

The Planner (TPM) persona's one composed entrypoint: depth-maintenance (task
2) then drift-correction (task 3), over the same in-memory graph, so a
depth-materialized item is visible to the drift pass in the same cycle.
Exercises `run()` end to end against a fixture (no live `gh` calls).
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
_TEMPLATES = _ROOT / "src" / "github-projects" / "templates"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pm = _load("project_model", _SRC / "project_model.py")
ps = _load("project_sync", _SRC / "project_sync.py")
cps = _load("check_project_sync", _SRC / "check_project_sync.py")
dm = _load("depth_maintain", _SRC / "depth_maintain.py")
dc = _load("drift_correct", _SRC / "drift_correct.py")
plm = _load("planner_maintain", _SRC / "planner_maintain.py")

_CFG = {
    "vault_project": "crickets",
    "github": {"owner": "o", "number": 5, "repo": "o/r",
              "url": "https://github.com/users/o/projects/5"},
}


class TestRunEndToEnd(unittest.TestCase):
    def test_explicit_invocation_runs_both_depth_and_drift_logic(self):
        """Explicit invocation of the Planner runs both task-2 and task-3
        logic end to end against a fixture (the plan's own task-4
        verification criterion)."""
        graph = pm.build_graph(pm.parse_items({"items": [
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x",
             "issue": 7},
            {"id": "some-feature", "type": "feature", "parent": "v5",
             "title": "Some Feature", "goal": "g", "why_matters": "w"},
        ]}))
        # Drift: v5's board body is stale relative to the rendered source.
        board = {7: "a stale body that will never match the render"}

        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
            items_path = d / "board-items.json"
            pm.dump(graph, items_path)
            (d / "PLAN-some-feature.md").write_text(
                "# Ship Some Feature\n", encoding="utf-8")
            cfg_p = d / "project.json"

            calls = []

            def runner(argv):
                calls.append(argv)
                if argv[:3] == ["gh", "project", "view"]:
                    return json.dumps({"id": "PROJ1"})
                if argv[:3] == ["gh", "project", "item-list"]:
                    return json.dumps({"items": []})
                if argv[:3] == ["gh", "issue", "view"]:
                    return json.dumps({"body": board.get(7, "")})
                return ""

            result = plm.run(graph, _CFG, cfg_p, d, _TEMPLATES, board, items_path,
                             pm=pm, ps=ps, dm=dm, dc=dc, runner=runner,
                             dry_run=False)

            # The depth pass's materialization was persisted to disk BEFORE
            # the drift pass ran (otherwise project_sync.py post's own disk
            # re-read would never have seen the newly-added Plan for its own
            # field sync) — checked inside the tempdir's own lifetime.
            persisted = json.loads(items_path.read_text(encoding="utf-8"))
            self.assertIn("plan-some-feature", [i["id"] for i in persisted["items"]])

        # Task 2's logic ran: the Feature's missing Plan materialized.
        self.assertEqual(len(result["depth_materialized"]), 1)
        self.assertIn("plan-some-feature", graph)
        # Task 3's logic ran: v5's stale body triggered a correction.
        self.assertIn("v5", result["drift_corrected"])
        edit_calls = [c for c in calls if c[:3] == ["gh", "issue", "edit"]]
        self.assertEqual(len(edit_calls), 1)

    def test_clean_full_depth_fixture_is_a_full_no_op(self):
        graph = pm.build_graph(pm.parse_items({"items": [
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x",
             "issue": 7},
        ]}))
        board = {7: ps.render_item(graph["v5"], ps.project_repo_url(_CFG),
                                   _TEMPLATES, graph=graph, public=True)}
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
            cfg_p = d / "project.json"
            items_path = d / "board-items.json"
            result = plm.run(graph, _CFG, cfg_p, d, _TEMPLATES, board, items_path,
                             pm=pm, ps=ps, dm=dm, dc=dc,
                             runner=lambda a: "", dry_run=True)
        self.assertEqual(result["depth_materialized"], [])
        self.assertEqual(result["depth_flagged"], [])
        self.assertEqual(result["drift_corrected"], [])
        self.assertEqual(result["drift_flagged"], [])

    def test_orphan_drift_flagged_never_touches_the_board(self):
        graph = pm.build_graph(pm.parse_items({"items": [
            {"id": "v5", "type": "version", "title": "V5 arc", "about": "x",
             "issue": 7},
        ]}))
        correct_body = ps.render_item(graph["v5"], ps.project_repo_url(_CFG),
                                      _TEMPLATES, graph=graph, public=True)
        board = {7: correct_body, 999: "an orphan issue"}
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
            cfg_p = d / "project.json"
            items_path = d / "board-items.json"
            calls = []
            runner = lambda argv: calls.append(argv) or ""
            result = plm.run(graph, _CFG, cfg_p, d, _TEMPLATES, board, items_path,
                             pm=pm, ps=ps, dm=dm, dc=dc, runner=runner,
                             dry_run=False)
        self.assertEqual(result["drift_flagged"], [999])
        self.assertEqual(calls, [])  # in-sync v5 -> no post call; orphan -> no call


class TestMainCLI(unittest.TestCase):
    def test_main_dry_run_end_to_end(self):
        import io
        import contextlib

        items = [{"id": "v5", "type": "version", "title": "V5 arc",
                 "about": "x", "issue": 7}]
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
            (d / "board-items.json").write_text(json.dumps({"items": items}),
                                                encoding="utf-8")
            cfg_p = d / "project.json"

            def runner(argv):
                if argv[:3] == ["gh", "project", "view"]:
                    return json.dumps({"id": "PROJ1"})
                if argv[:3] == ["gh", "project", "item-list"]:
                    return json.dumps({"items": []})
                if argv[:3] == ["gh", "issue", "view"]:
                    return json.dumps({"body": "stale"})
                return ""

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = plm.main(["--config", str(cfg_p), "--dry-run"],
                             runner=runner, fetch=lambda cfg: {7: "stale"})
        self.assertEqual(rc, 0)  # correction, not a flag -> clean exit
        self.assertIn("corrected v5", buf.getvalue())

    def test_no_config_skips_green(self):
        rc = plm.main(["--config", "/nonexistent/project.json"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
