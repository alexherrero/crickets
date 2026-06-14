#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/check_project_sync.py (crickets #41, task 6).

The vault==board drift gate (D-④). Exercises the pure ``compute_drift`` over an
injected board snapshot (the four drift kinds: create / missing / update /
orphan, plus the clean in-sync case), the read-only ``fetch_board_bodies`` parse
through a fake runner, and ``main()``'s graceful-skip + injected-fetch happy/drift
paths — all network-free. The live ``gh`` orchestration is exercised in task 9's
gated backfill, not here.

stdlib only — no pytest.
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

_CFG = {
    "vault_project": "crickets",
    "github": {"owner": "o", "number": 5, "repo": "o/r",
               "url": "https://github.com/users/o/projects/5"},
}


def _graph(issue_for_v5=7):
    """A version (board-persisted, top-level) with a bound issue, plus a feature
    under it (also board-persisted). Plan/task omitted — DC-1 keeps them vault-only
    unless active, which keeps the fixture's materialized set small + stable."""
    return pm.build_graph(pm.parse_items({"items": [
        {"id": "v5", "type": "version", "track": "V5", "title": "V5 arc",
         "about": "the unbundling", "issue": issue_for_v5},
        {"id": "f", "type": "feature", "parent": "v5", "track": "V5",
         "title": "Board sync", "goal": "sync", "why_matters": "humans",
         "issue": 8},
    ]}))


def _rendered(item, graph):
    return ps.render_item(item, ps.project_repo_url(_CFG), _TEMPLATES,
                          graph=graph, public=True)


def _in_sync_board(graph):
    """A board snapshot whose bodies exactly match the rendered source."""
    return {it.issue: _rendered(it, graph)
            for it in pm.materialize(graph, active_plans=set())}


class TestComputeDrift(unittest.TestCase):
    def _drift(self, graph, board):
        return cps.compute_drift(graph, _CFG, _TEMPLATES, board, pm=pm, ps=ps)

    def test_in_sync_is_empty(self):
        g = _graph()
        self.assertEqual(self._drift(g, _in_sync_board(g)), [])

    def test_changed_body_is_update(self):
        g = _graph()
        board = _in_sync_board(g)
        board[7] = "totally different body"
        drift = self._drift(g, board)
        self.assertEqual(len(drift), 1)
        self.assertIn("update", drift[0])
        self.assertIn("version:v5", drift[0])
        self.assertIn("#7", drift[0])

    def test_unmaterialized_issue_is_create(self):
        g = _graph(issue_for_v5=None)  # v5 has no issue yet
        board = {8: _rendered(g["f"], g)}  # only the feature is on the board
        drift = self._drift(g, board)
        self.assertEqual(len(drift), 1)
        self.assertIn("create", drift[0])
        self.assertIn("version:v5", drift[0])

    def test_issue_missing_from_board(self):
        g = _graph()
        board = {8: _rendered(g["f"], g)}  # v5's issue #7 not on the board
        drift = self._drift(g, board)
        self.assertEqual(len(drift), 1)
        self.assertIn("missing", drift[0])
        self.assertIn("#7", drift[0])

    def test_orphan_board_issue(self):
        g = _graph()
        board = _in_sync_board(g)
        board[999] = "an issue with no vault item"
        drift = self._drift(g, board)
        self.assertEqual(len(drift), 1)
        self.assertIn("orphan", drift[0])
        self.assertIn("#999", drift[0])

    def test_multiple_drift_kinds_all_reported(self):
        g = _graph()
        board = _in_sync_board(g)
        board[7] = "changed"        # update
        board[999] = "stray"        # orphan
        drift = self._drift(g, board)
        self.assertEqual(len(drift), 2)
        kinds = " ".join(drift)
        self.assertIn("update", kinds)
        self.assertIn("orphan", kinds)


class TestFetchBoardBodies(unittest.TestCase):
    def test_parses_and_builds_request(self):
        seen = {}

        def runner(argv):
            seen["argv"] = argv
            return json.dumps([{"number": 7, "body": "b7"},
                               {"number": 8, "body": "b8"}])

        bodies = cps.fetch_board_bodies(_CFG, runner=runner)
        self.assertEqual(bodies, {7: "b7", 8: "b8"})
        self.assertEqual(seen["argv"],
                         ["gh", "issue", "list", "--repo", "o/r", "--state",
                          "open", "--json", "number,body", "--limit", "1000"])

    def test_requires_repo(self):
        with self.assertRaises(cps.CheckError):
            cps.fetch_board_bodies({"github": {"owner": "o", "number": 5}})

    def test_gh_failure_raises(self):
        def runner(argv):
            raise cps.CheckError("boom")
        with self.assertRaises(cps.CheckError):
            cps.fetch_board_bodies(_CFG, runner=runner)


class TestMain(unittest.TestCase):
    def _write_cfg_dir(self, graph_items):
        t = tempfile.TemporaryDirectory()
        d = Path(t.name)
        (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
        (d / "board-items.json").write_text(
            json.dumps({"items": graph_items}), encoding="utf-8")
        return t, d / "project.json"

    def test_no_config_skips_green(self):
        # The check-all-in-a-non-board-repo path: missing project.json → exit 0.
        rc = cps.main(["--config", "/nonexistent/project.json"])
        self.assertEqual(rc, 0)

    def test_injected_fetch_in_sync_passes(self):
        items = [{"id": "v5", "type": "version", "track": "V5", "title": "V5 arc",
                  "about": "the unbundling", "issue": 7}]
        t, cfg_p = self._write_cfg_dir(items)
        try:
            g = _graph()  # same shape, but main builds its own graph from file
            # Build the in-sync body for the version straight from the file graph.
            file_graph = pm.load(cfg_p.parent / "board-items.json")
            body = _rendered(file_graph["v5"], file_graph)
            rc = cps.main(["--config", str(cfg_p)], fetch=lambda cfg: {7: body})
        finally:
            t.cleanup()
        self.assertEqual(rc, 0)

    def test_injected_fetch_drift_fails(self):
        items = [{"id": "v5", "type": "version", "track": "V5", "title": "V5 arc",
                  "about": "the unbundling", "issue": 7}]
        t, cfg_p = self._write_cfg_dir(items)
        try:
            rc = cps.main(["--config", str(cfg_p)],
                          fetch=lambda cfg: {7: "stale body"})
        finally:
            t.cleanup()
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
