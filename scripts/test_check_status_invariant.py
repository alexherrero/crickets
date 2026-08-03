#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/check_status_invariant.py.

The status-vs-issue-state gate — the axis `check_project_sync` structurally
cannot see, because `status` appears in no body template and that gate diffs
bodies. Exercises the pure `compute_violations` in both drift directions, the
statuses that assert nothing, the read-only `fetch_issue_states` parse through a
fake runner, and `main()`'s graceful-skip + injected-fetch paths — all
network-free.

The regression this pins: a vault row left `Todo` while its issue closed months
ago produced **zero** drift from the body gate, which is how two boards
accumulated ~35 stale open issues under fully green checks.

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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pm = _load("project_model", _SRC / "project_model.py")
ps = _load("project_sync", _SRC / "project_sync.py")
csi = _load("check_status_invariant", _SRC / "check_status_invariant.py")

_CFG = {
    "vault_project": "crickets",
    "github": {"owner": "o", "number": 5, "repo": "o/r",
               "url": "https://github.com/users/o/projects/5"},
}


def _graph(version_status="Done", feature_status="Todo"):
    """A version + a feature under it, each board-persisted with an issue.
    Plan/task omitted — DC-1 keeps them vault-only unless active."""
    return pm.build_graph(pm.parse_items({"items": [
        {"id": "v5", "type": "version", "track": "V5", "title": "V5 arc",
         "about": "the unbundling", "issue": 7, "status": version_status},
        {"id": "f", "type": "feature", "parent": "v5", "track": "V5",
         "title": "Board sync", "goal": "sync", "why_matters": "humans",
         "issue": 8, "status": feature_status},
    ]}))


def _violations(graph, states):
    return csi.compute_violations(graph, states, pm=pm)


class TestComputeViolations(unittest.TestCase):
    def test_clean_when_status_and_issue_state_agree(self):
        g = _graph(version_status="Done", feature_status="Todo")
        self.assertEqual(_violations(g, {7: "CLOSED", 8: "OPEN"}), [])

    def test_stale_open_when_a_live_row_has_a_closed_issue(self):
        # THE regression: the row still reads Todo, the work closed long ago.
        # This is the shape the body-diff gate reports as zero drift.
        g = _graph(feature_status="Todo")
        v = _violations(g, {7: "CLOSED", 8: "CLOSED"})
        self.assertEqual([(x.kind, x.item_id, x.issue) for x in v],
                         [("stale-open", "f", 8)])
        self.assertIn("the vault lags", v[0].render())

    def test_stale_done_when_a_finished_row_has_an_open_issue(self):
        # The other direction: the row says shipped, the close never landed.
        g = _graph(version_status="Done", feature_status="Todo")
        v = _violations(g, {7: "OPEN", 8: "OPEN"})
        self.assertEqual([(x.kind, x.item_id, x.issue) for x in v],
                         [("stale-done", "v5", 7)])
        self.assertIn("the close never landed", v[0].render())

    def test_both_directions_are_caught_in_one_pass(self):
        g = _graph(version_status="Done", feature_status="Todo")
        v = _violations(g, {7: "OPEN", 8: "CLOSED"})
        self.assertEqual(sorted(x.kind for x in v), ["stale-done", "stale-open"])

    def test_parked_expects_a_closed_issue(self):
        # Parked is deliberate deferral, closed as not-planned — so an open
        # issue under a Parked row is drift exactly like a Done one.
        g = _graph(version_status="Parked", feature_status="Todo")
        self.assertEqual([x.kind for x in _violations(g, {7: "OPEN", 8: "OPEN"})],
                         ["stale-done"])
        self.assertEqual(_violations(g, {7: "CLOSED", 8: "OPEN"}), [])

    def test_in_progress_expects_an_open_issue(self):
        g = _graph(version_status="In Progress", feature_status="Todo")
        self.assertEqual(_violations(g, {7: "OPEN", 8: "OPEN"}), [])
        self.assertEqual([x.kind for x in _violations(g, {7: "CLOSED", 8: "OPEN"})],
                         ["stale-open"])

    def test_null_status_asserts_nothing_in_either_direction(self):
        g = _graph(version_status=None, feature_status=None)
        self.assertEqual(_violations(g, {7: "OPEN", 8: "CLOSED"}), [])

    def test_null_status_rows_are_still_reported_not_dropped(self):
        g = _graph(version_status=None, feature_status="Todo")
        lines = csi.compute_unasserted(g, pm=pm)
        self.assertEqual(len(lines), 1)
        self.assertIn("version:v5", lines[0])

    def test_issue_absent_from_the_snapshot_is_the_other_gates_axis(self):
        # Board membership belongs to check_project_sync; reporting it here too
        # would just make both gates noisier about the same fact.
        g = _graph(feature_status="Todo")
        self.assertEqual(_violations(g, {7: "CLOSED"}), [])

    def test_row_with_no_issue_is_skipped(self):
        g = pm.build_graph(pm.parse_items({"items": [
            {"id": "v5", "type": "version", "track": "V5", "title": "V5",
             "about": "x", "status": "Done"},
        ]}))
        self.assertEqual(_violations(g, {}), [])

    def test_output_is_deterministically_ordered(self):
        g = _graph(version_status="Done", feature_status="Todo")
        states = {7: "OPEN", 8: "CLOSED"}
        self.assertEqual([x.item_id for x in _violations(g, states)],
                         [x.item_id for x in _violations(g, states)])


class TestFetchIssueStates(unittest.TestCase):
    def test_parses_one_state_all_call_into_a_number_state_map(self):
        calls = []

        def runner(argv):
            calls.append(argv)
            return json.dumps([{"number": 7, "state": "CLOSED"},
                               {"number": 8, "state": "OPEN"}])

        self.assertEqual(csi.fetch_issue_states(_CFG, runner=runner),
                         {7: "CLOSED", 8: "OPEN"})
        # One call, --state all: two passes could tear if an issue closes between
        # them, and the Projects GraphQL API is not touched at all.
        self.assertEqual(len(calls), 1)
        self.assertIn("--state", calls[0])
        self.assertIn("all", calls[0])
        self.assertNotIn("api", calls[0])

    def test_state_is_normalized_to_upper_case(self):
        def runner(argv):
            return json.dumps([{"number": 7, "state": "closed"}])
        self.assertEqual(csi.fetch_issue_states(_CFG, runner=runner), {7: "CLOSED"})

    def test_missing_repo_is_a_check_error(self):
        with self.assertRaises(csi.CheckError):
            csi.fetch_issue_states({"github": {}}, runner=lambda a: "[]")


class TestMain(unittest.TestCase):
    def _cfg_dir(self, items):
        t = tempfile.TemporaryDirectory()
        d = Path(t.name)
        (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
        (d / "board-items.json").write_text(json.dumps({"items": items}),
                                            encoding="utf-8")
        return t, d / "project.json"

    _ITEMS = [{"id": "v5", "type": "version", "track": "V5", "title": "V5",
               "about": "x", "issue": 7, "status": "Todo"}]

    def test_skips_cleanly_when_there_is_no_project_json(self):
        # The CI posture: .harness/ is gitignored, so this is the path CI takes.
        self.assertEqual(csi.main(["--config", "/nonexistent/project.json"]), 0)

    def test_passes_when_the_invariant_holds(self):
        t, cfg = self._cfg_dir(self._ITEMS)
        with t:
            self.assertEqual(csi.main(["--config", str(cfg)],
                                      fetch=lambda c: {7: "OPEN"}), 0)

    def test_fails_on_a_violation(self):
        t, cfg = self._cfg_dir(self._ITEMS)
        with t:
            self.assertEqual(csi.main(["--config", str(cfg)],
                                      fetch=lambda c: {7: "CLOSED"}), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
