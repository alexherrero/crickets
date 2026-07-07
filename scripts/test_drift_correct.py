#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/drift_correct.py (AG Wave D, task 3).

The Planner (TPM) persona's drift-corrector: extends beyond report_drift.py's
report-only posture — an `update`-drift item gets project_sync.py's existing
idempotent `post` body-sync; an `orphan` is surfaced for operator judgment,
never auto-closed or edited. Exercises `classify()` (a pure re-derivation of
update/orphan drift, independent of check_project_sync.compute_drift's string
output) and `correct()`/`run()` against a fake `gh` runner — no live `gh`
calls, no network, no mutation of check_project_sync.py's own behavior.
"""
from __future__ import annotations

import importlib.util
import io
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
dc = _load("drift_correct", _SRC / "drift_correct.py")

_CFG = {
    "vault_project": "crickets",
    "github": {"owner": "o", "number": 5, "repo": "o/r",
              "url": "https://github.com/users/o/projects/5"},
}


def _graph(issue_for_v5=7):
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
    return {it.issue: _rendered(it, graph)
            for it in pm.materialize(graph, active_plans=set())}


class TestClassify(unittest.TestCase):
    def _findings(self, graph, board):
        return dc.classify(graph, _CFG, _TEMPLATES, board, pm=pm, ps=ps)

    def test_in_sync_yields_no_findings(self):
        g = _graph()
        self.assertEqual(self._findings(g, _in_sync_board(g)), [])

    def test_changed_body_is_update_finding(self):
        g = _graph()
        board = _in_sync_board(g)
        board[7] = "totally different body"
        findings = self._findings(g, board)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "update")
        self.assertEqual(findings[0].item_id, "v5")
        self.assertEqual(findings[0].issue, 7)

    def test_orphan_issue_is_orphan_finding(self):
        g = _graph()
        board = _in_sync_board(g)
        board[999] = "an issue with no vault item"
        findings = self._findings(g, board)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "orphan")
        self.assertIsNone(findings[0].item_id)
        self.assertEqual(findings[0].issue, 999)

    def test_create_and_missing_are_not_classified(self):
        # v5 has no issue at all (create), and f's issue is absent from the
        # board (missing) -- neither is this corrector's scope.
        g = _graph(issue_for_v5=None)
        board = {}  # f's issue #8 also absent -> missing, not classified
        findings = self._findings(g, board)
        self.assertEqual(findings, [])

    def test_multiple_findings_all_classified(self):
        g = _graph()
        board = _in_sync_board(g)
        board[7] = "changed"
        board[999] = "stray"
        findings = self._findings(g, board)
        kinds = sorted(f.kind for f in findings)
        self.assertEqual(kinds, ["orphan", "update"])


class TestCorrect(unittest.TestCase):
    def _cfg_dir(self, items):
        t = tempfile.TemporaryDirectory()
        d = Path(t.name)
        (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
        (d / "board-items.json").write_text(json.dumps({"items": items}), encoding="utf-8")
        return t, d / "project.json"

    def test_update_finding_calls_post_for_that_item(self):
        items = [{"id": "v5", "type": "version", "title": "V5 arc",
                 "about": "the unbundling", "issue": 7}]
        t, cfg_p = self._cfg_dir(items)
        try:
            calls = []

            def runner(argv):
                calls.append(argv)
                if argv[:3] == ["gh", "project", "view"]:
                    return json.dumps({"id": "PROJ1"})
                if argv[:3] == ["gh", "project", "item-list"]:
                    return json.dumps({"items": []})
                if argv[:3] == ["gh", "issue", "view"]:
                    return json.dumps({"body": "stale body"})
                return ""

            findings = [dc.Finding("update", "v5", 7, "version")]
            buf = io.StringIO()
            result = dc.correct(findings, _CFG, cfg_p, ps=ps, runner=runner,
                                dry_run=False, out=buf)
        finally:
            t.cleanup()
        self.assertEqual(result["corrected"], ["v5"])
        self.assertEqual(result["flagged"], [])
        # project_sync.py's own post path issued the edit -- reused, not duplicated.
        edit_calls = [c for c in calls if c[:3] == ["gh", "issue", "edit"]]
        self.assertEqual(len(edit_calls), 1)

    def test_orphan_finding_never_touches_the_board(self):
        t, cfg_p = self._cfg_dir([])
        try:
            calls = []
            runner = lambda argv: calls.append(argv) or ""
            findings = [dc.Finding("orphan", None, 999)]
            buf = io.StringIO()
            result = dc.correct(findings, _CFG, cfg_p, ps=ps, runner=runner,
                                dry_run=False, out=buf)
        finally:
            t.cleanup()
        self.assertEqual(result["corrected"], [])
        self.assertEqual(result["flagged"], [999])
        self.assertEqual(calls, [])  # no gh call of ANY kind for an orphan
        self.assertIn("FLAGGED", buf.getvalue())
        self.assertIn("#999", buf.getvalue())
        self.assertIn("never auto-closed", buf.getvalue())

    def test_orphan_never_issues_close_or_edit_even_alongside_an_update(self):
        items = [{"id": "v5", "type": "version", "title": "V5 arc",
                 "about": "the unbundling", "issue": 7}]
        t, cfg_p = self._cfg_dir(items)
        try:
            calls = []

            def runner(argv):
                calls.append(argv)
                if argv[:3] == ["gh", "project", "view"]:
                    return json.dumps({"id": "PROJ1"})
                if argv[:3] == ["gh", "project", "item-list"]:
                    return json.dumps({"items": []})
                if argv[:3] == ["gh", "issue", "view"]:
                    return json.dumps({"body": "stale"})
                return ""

            findings = [dc.Finding("update", "v5", 7, "version"),
                       dc.Finding("orphan", None, 999)]
            result = dc.correct(findings, _CFG, cfg_p, ps=ps, runner=runner, dry_run=False)
        finally:
            t.cleanup()
        forbidden = {("gh", "issue", "close"), ("gh", "project", "item-edit")}
        orphan_related = [c for c in calls if "999" in c]
        self.assertEqual(orphan_related, [])
        self.assertFalse(any(tuple(c[:3]) in forbidden for c in calls
                            if "999" in " ".join(str(x) for x in c)))
        self.assertEqual(result["flagged"], [999])

    def test_dry_run_never_issues_a_write_call(self):
        # dry_run mirrors project_sync.py's own established --dry-run contract
        # (unchanged, per the plan's constraint): read calls (project view,
        # issue view, item-list) still happen live to preview against real
        # state, but no WRITE call (issue edit/close, item-edit, item-add,
        # comment) is ever issued.
        items = [{"id": "v5", "type": "version", "title": "V5 arc",
                 "about": "the unbundling", "issue": 7}]
        t, cfg_p = self._cfg_dir(items)
        try:
            calls = []

            def runner(argv):
                calls.append(argv)
                if argv[:3] == ["gh", "project", "view"]:
                    return json.dumps({"id": "PROJ1"})
                if argv[:3] == ["gh", "project", "item-list"]:
                    return json.dumps({"items": []})
                if argv[:3] == ["gh", "issue", "view"]:
                    return json.dumps({"body": "stale body"})
                return ""

            findings = [dc.Finding("update", "v5", 7, "version")]
            buf = io.StringIO()
            result = dc.correct(findings, _CFG, cfg_p, ps=ps, runner=runner,
                                dry_run=True, out=buf)
        finally:
            t.cleanup()
        writes = {("gh", "issue", "edit"), ("gh", "issue", "close"),
                 ("gh", "project", "item-edit"), ("gh", "project", "item-add"),
                 ("gh", "issue", "comment")}
        self.assertFalse(any(tuple(c[:3]) in writes for c in calls))
        self.assertEqual(result["corrected"], ["v5"])  # dry-run still "would fix"


class TestRunEndToEnd(unittest.TestCase):
    def test_clean_state_corrects_and_flags_nothing(self):
        g = _graph()
        board = _in_sync_board(g)
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
            cfg_p = d / "project.json"
            result = dc.run(g, _CFG, cfg_p, _TEMPLATES, board, pm=pm, ps=ps,
                            runner=lambda a: "", dry_run=True)
        self.assertEqual(result, {"corrected": [], "flagged": []})

    def test_re_run_after_correction_confirms_clean(self):
        # A fixture with injected update drift -> corrector runs -> re-running
        # check_project_sync's own compute_drift confirms clean (plan's own
        # verification criterion for task 3).
        items = [{"id": "v5", "type": "version", "title": "V5 arc",
                 "about": "the unbundling", "issue": 7}]
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
            (d / "board-items.json").write_text(json.dumps({"items": items}),
                                                encoding="utf-8")
            cfg_p = d / "project.json"

            board_state = {}

            def runner(argv):
                if argv[:3] == ["gh", "project", "view"]:
                    return json.dumps({"id": "PROJ1"})
                if argv[:3] == ["gh", "project", "item-list"]:
                    return json.dumps({"items": []})
                if argv[:3] == ["gh", "issue", "view"]:
                    return json.dumps({"body": board_state.get(7, "stale body")})
                if argv[:3] == ["gh", "issue", "edit"]:
                    board_state[7] = argv[-1]  # capture the new body
                    return ""
                return ""

            graph = pm.load(d / "board-items.json")
            correct_body = _rendered(graph["v5"], graph)
            findings = [dc.Finding("update", "v5", 7, "version")]
            dc.correct(findings, _CFG, cfg_p, ps=ps, runner=runner, dry_run=False)

            # Re-run check_project_sync's own compute_drift against the
            # corrected board state -- confirms clean, unmodified oracle.
            fresh_graph = pm.load(d / "board-items.json")
            drift = cps.compute_drift(fresh_graph, _CFG, _TEMPLATES,
                                      {7: board_state[7]}, pm=pm, ps=ps)
        self.assertEqual(board_state[7].strip(), correct_body.strip())
        self.assertEqual(drift, [])


if __name__ == "__main__":
    unittest.main()
