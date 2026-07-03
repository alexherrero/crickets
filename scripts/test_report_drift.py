#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/report_drift.py (board-write-path task 6).

The scheduled, report-only drift cycle: runs check_project_sync's drift
detector UNMODIFIED (no edits to check_project_sync.py in this plan) and posts
a single summary comment on the Version issue, idempotent by a hidden marker
keyed to the exact drift content. Exercises the pure marker/report builders,
the Version-issue resolution + no-Version-issue log fallback, the
list-and-match dedupe against a prior identical report, and the hard
constraint that this cycle never issues an item-edit / issue-edit / item-add —
detection and reporting only. stdlib only — no pytest, no live `gh` calls.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
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
cps = _load("check_project_sync", _SRC / "check_project_sync.py")
rd = _load("report_drift", _SRC / "report_drift.py")

_CFG = {
    "vault_project": "crickets",
    "github": {"owner": "o", "number": 5, "repo": "o/r",
               "url": "https://github.com/users/o/projects/5"},
}

_DRIFT = ["update  feature:f — issue #8 body differs from the rendered source",
         "orphan  issue #99 — on the board, not in the vault source"]


def _graph_with_version(issue=7):
    return pm.build_graph(pm.parse_items({"items": [
        {"id": "v5", "type": "version", "title": "V5 arc", "issue": issue,
         "about": "the arc"},
    ]}))


class TestDriftReportMarker(unittest.TestCase):
    def test_marker_stable_for_same_drift(self):
        self.assertEqual(rd.drift_report_marker(_DRIFT), rd.drift_report_marker(_DRIFT))

    def test_marker_differs_for_different_drift(self):
        self.assertNotEqual(rd.drift_report_marker(_DRIFT), rd.drift_report_marker([]))

    def test_render_includes_both_drift_lines_and_marker(self):
        body = rd.render_drift_report(_DRIFT)
        self.assertIn(_DRIFT[0], body)
        self.assertIn(_DRIFT[1], body)
        self.assertIn(rd.drift_report_marker(_DRIFT), body)


class TestRun(unittest.TestCase):
    def _runner(self, comments=(), calls=None):
        calls = calls if calls is not None else []

        def runner(argv):
            calls.append(argv)
            if argv[:3] == ["gh", "issue", "view"]:
                return json.dumps({"comments": [{"body": c} for c in comments]})
            return ""
        return runner, calls

    def test_clean_state_is_pass_no_calls(self):
        graph = _graph_with_version()
        runner, calls = self._runner()
        buf = io.StringIO()
        rc = rd.run(graph, _CFG, [], ps=ps, runner=runner, dry_run=False, out=buf)
        self.assertEqual(rc, 0)
        self.assertIn("PASS", buf.getvalue())
        self.assertEqual(calls, [])

    def test_drift_posts_one_comment_on_version_issue(self):
        graph = _graph_with_version(issue=7)
        runner, calls = self._runner(comments=[])
        rc = rd.run(graph, _CFG, _DRIFT, ps=ps, runner=runner, dry_run=False)
        self.assertEqual(rc, 1)
        comment_calls = [c for c in calls if c[:3] == ["gh", "issue", "comment"]]
        self.assertEqual(len(comment_calls), 1)
        self.assertEqual(comment_calls[0][:4], ["gh", "issue", "comment", "7"])
        self.assertIn(rd.drift_report_marker(_DRIFT), comment_calls[0][-1])

    def test_repost_of_unchanged_drift_is_noop(self):
        graph = _graph_with_version(issue=7)
        marker = rd.drift_report_marker(_DRIFT)
        runner, calls = self._runner(comments=[marker])
        rc = rd.run(graph, _CFG, _DRIFT, ps=ps, runner=runner, dry_run=False)
        self.assertEqual(rc, 1)
        comment_calls = [c for c in calls if c[:3] == ["gh", "issue", "comment"]]
        self.assertEqual(comment_calls, [])

    def test_no_version_issue_logs_instead_of_posting(self):
        graph = pm.build_graph(pm.parse_items({"items": [
            {"id": "v5", "type": "version", "title": "V5 arc"},  # no issue yet
        ]}))
        runner, calls = self._runner()
        buf = io.StringIO()
        rc = rd.run(graph, _CFG, _DRIFT, ps=ps, runner=runner, dry_run=False, out=buf)
        self.assertEqual(rc, 1)
        self.assertIn(_DRIFT[0], buf.getvalue())
        self.assertEqual(calls, [])

    def test_dry_run_never_calls_runner_for_the_post(self):
        graph = _graph_with_version(issue=7)
        runner, calls = self._runner(comments=[])
        buf = io.StringIO()
        rd.run(graph, _CFG, _DRIFT, ps=ps, runner=runner, dry_run=True, out=buf)
        self.assertIn("gh issue comment 7 --repo o/r --body", buf.getvalue())
        self.assertEqual([c for c in calls if c[:3] == ["gh", "issue", "comment"]], [])

    def test_never_issues_a_mutating_board_write(self):
        # The hard constraint: report-only, no item-edit / issue-edit / item-add,
        # in any of the scenarios above.
        graph = _graph_with_version(issue=7)
        runner, calls = self._runner(comments=[])
        rd.run(graph, _CFG, _DRIFT, ps=ps, runner=runner, dry_run=False)
        forbidden = {("gh", "project", "item-edit"), ("gh", "issue", "edit"),
                    ("gh", "project", "item-add")}
        self.assertFalse(any(tuple(c[:3]) in forbidden for c in calls))


class TestMainIntegration(unittest.TestCase):
    """The CLI entrypoint, wired to check_project_sync's compute_drift UNMODIFIED
    (an injected `fetch` stands in for the live `gh issue list` board read)."""

    def _cfg_dir(self, items):
        import json as _json
        import tempfile
        t = tempfile.TemporaryDirectory()
        d = Path(t.name)
        (d / "project.json").write_text(_json.dumps(_CFG), encoding="utf-8")
        (d / "board-items.json").write_text(_json.dumps({"items": items}),
                                            encoding="utf-8")
        return t, d / "project.json"

    def test_main_dry_runs_end_to_end_with_drift(self):
        items = [{"id": "v5", "type": "version", "title": "V5 arc", "issue": 7,
                  "about": "the arc"}]
        t, cfg_p = self._cfg_dir(items)
        try:
            # Empty board snapshot -> the version item is "missing" drift.
            calls = []

            def runner(argv):
                calls.append(argv)
                return json.dumps({"comments": []})

            buf = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buf):
                rc = rd.main(["--config", str(cfg_p), "--dry-run"],
                            runner=runner, fetch=lambda cfg: {})
            out = buf.getvalue()
        finally:
            t.cleanup()
        self.assertEqual(rc, 1)
        self.assertIn("gh issue comment 7 --repo o/r --body", out)
        self.assertIn("missing", out)


if __name__ == "__main__":
    unittest.main()
