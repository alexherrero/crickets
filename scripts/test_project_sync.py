#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/project_sync.py (crickets #41, task 4).

The deterministic render path (rule 6 / DC-4). Exercises:

  - the link + date builders (commit/issue/release URLs and markdown links, the
    trailing-slash normalization, fmt_date's accept/reject);
  - ``fill()`` — substitution, the missing-required-value refusal, the
    None-drops-the-whole-clause optionality, and single-space ``·`` preservation
    inside a clause;
  - golden per-type renders (Task, Plan, Feature, Version, Backlog-item, Idea)
    asserting the EXACT locked v4-41 template shape with correctly-built links,
    ``YYYY-MM-DD`` dates, and ``\\n\\n``-joined lifecycle stages;
  - the silent-source split: ``public=False`` appends the private attribution,
    ``public=True`` omits it;
  - ``bug`` (no locked template this cycle) raises RenderError;
  - completeness: no rendered body leaves an unfilled ``{{placeholder}}``.

stdlib only — no pytest. project_sync is duck-typed over project_model.Item, so
fixtures build real Item objects (and set ``.issue`` where a link must resolve).
"""
from __future__ import annotations

import contextlib
import datetime
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
_REPO = "https://github.com/o/r"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pm = _load("project_model", _SRC / "project_model.py")
ps = _load("project_sync", _SRC / "project_sync.py")


def _render(item, graph=None, public=True):
    return ps.render_item(item, _REPO, _TEMPLATES, graph=graph, public=public)


class TestLinkBuilders(unittest.TestCase):
    def test_commit_url(self):
        self.assertEqual(ps.commit_url(_REPO, "abc1234"),
                         "https://github.com/o/r/commit/abc1234")

    def test_issue_url(self):
        self.assertEqual(ps.issue_url(_REPO, 42), "https://github.com/o/r/issues/42")

    def test_release_url(self):
        self.assertEqual(ps.release_url(_REPO, "v1.2.3"),
                         "https://github.com/o/r/releases/tag/v1.2.3")

    def test_trailing_slash_normalized(self):
        # A repo_url with a trailing slash must not produce a double slash.
        self.assertEqual(ps.commit_url("https://github.com/o/r/", "abc"),
                         "https://github.com/o/r/commit/abc")
        self.assertEqual(ps.issue_url("https://github.com/o/r/", 7),
                         "https://github.com/o/r/issues/7")
        self.assertEqual(ps.release_url("https://github.com/o/r/", "v1"),
                         "https://github.com/o/r/releases/tag/v1")

    def test_commit_link(self):
        self.assertEqual(ps.commit_link(_REPO, "abc1234"),
                         "[`abc1234`](https://github.com/o/r/commit/abc1234)")

    def test_issue_link(self):
        self.assertEqual(ps.issue_link(_REPO, 42, "Board sync"),
                         "[Board sync](https://github.com/o/r/issues/42)")

    def test_release_link(self):
        self.assertEqual(ps.release_link(_REPO, "v1.2.3"),
                         "[v1.2.3](https://github.com/o/r/releases/tag/v1.2.3)")


class TestFmtDate(unittest.TestCase):
    def test_valid_iso_string(self):
        self.assertEqual(ps.fmt_date("2026-06-14"), "2026-06-14")

    def test_date_object(self):
        self.assertEqual(ps.fmt_date(datetime.date(2026, 6, 14)), "2026-06-14")

    def test_datetime_object(self):
        self.assertEqual(ps.fmt_date(datetime.datetime(2026, 6, 14, 9, 30)),
                         "2026-06-14")

    def test_non_iso_string_rejected(self):
        for bad in ("06/14/2026", "2026-6-14", "June 14", "2026-06-14T00:00"):
            with self.subTest(value=bad), self.assertRaises(ps.RenderError):
                ps.fmt_date(bad)

    def test_non_date_value_rejected(self):
        with self.assertRaises(ps.RenderError):
            ps.fmt_date(20260614)

    def test_impossible_calendar_date_rejected(self):
        # DEFECT 3 regression: a structurally-valid (YYYY-MM-DD-shaped) but
        # calendrically-impossible date must be rejected, not passed through
        # verbatim — board-items.json is agent-authored, so a typo'd month/day
        # should fail loudly rather than reach the board.
        for bad in ("2026-13-99", "2026-02-30", "2026-00-10"):
            with self.subTest(value=bad), self.assertRaises(ps.RenderError):
                ps.fmt_date(bad)


class TestFill(unittest.TestCase):
    def test_basic_substitution(self):
        out = ps.fill("**A:** {{x}}  ·  **B:** {{y}}", {"x": "1", "y": "2"})
        self.assertEqual(out, "**A:** 1  ·  **B:** 2")

    def test_missing_required_key_raises(self):
        with self.assertRaises(ps.RenderError):
            ps.fill("**A:** {{x}}", {})

    def test_none_drops_whole_clause(self):
        out = ps.fill("{{keep}}  ·  {{drop}}", {"keep": "here", "drop": None})
        self.assertEqual(out, "here")

    def test_none_in_multi_placeholder_clause_drops_clause(self):
        # The feature-closeout 'Deferred:' clause has two placeholders; if either
        # is absent the whole clause must drop (not render a half-empty clause).
        out = ps.fill("**Done:** {{a}}  ·  **Deferred:** {{b}} → {{c}}",
                      {"a": "yes", "b": None, "c": None})
        self.assertEqual(out, "**Done:** yes")

    def test_preserves_single_space_middot_within_clause(self):
        # ' · ' (single-space) is intra-clause and must survive; only '  ·  '
        # (double-space) is a clause separator.
        out = ps.fill("**L:** {{a}} · {{b}}", {"a": "link", "b": "2026-06-14"})
        self.assertEqual(out, "**L:** link · 2026-06-14")


class TestLoadTemplate(unittest.TestCase):
    def test_missing_template_raises(self):
        with self.assertRaises(ps.RenderError):
            ps.load_template(_TEMPLATES, "no-such-template")

    def test_known_template_loads(self):
        self.assertIn("{{about}}", ps.load_template(_TEMPLATES, "version"))


class TestGoldenRenders(unittest.TestCase):
    def test_task(self):
        item = pm.Item(id="t1", type="task", title="T", fields={
            "kickoff": {"goal": "Build the thing", "done_when": "tests green"},
            "progress": [{"date": "2026-06-14", "sha": "abc1234",
                          "progress": "scaffolded"}],
            "closeout": {"outcome": "shipped", "sha": "def5678",
                         "date": "2026-06-15"},
        })
        self.assertEqual(_render(item), "\n\n".join([
            "**① Goal:** Build the thing  ·  **Done when:** tests green",
            "**② 2026-06-14** ([`abc1234`](https://github.com/o/r/commit/abc1234)): scaffolded",
            "**③ Outcome:** shipped  ·  **Landed:** [`def5678`](https://github.com/o/r/commit/def5678) · 2026-06-15",
        ]))

    def test_plan_with_resolved_task_link(self):
        linked = pm.Item(id="lt", type="task", title="Wire it", issue=12)
        plan = pm.Item(id="p1", type="plan", title="P", fields={
            "kickoff": {"goal": "Ship board sync", "done_when": "green"},
            "progress": [{"date": "2026-06-14", "task": "lt",
                          "progress": "task 1 done"}],
            "closeout": {"outcome": "shipped", "release": "v0.1.0",
                         "date": "2026-06-15"},
        })
        graph = {"lt": linked, "p1": plan}
        self.assertEqual(_render(plan, graph=graph), "\n\n".join([
            "**① Goal:** Ship board sync  ·  **Done when:** green",
            "**② 2026-06-14** (→ [Wire it](https://github.com/o/r/issues/12)): task 1 done",
            "**③ Outcome:** shipped  ·  **Shipped:** [v0.1.0](https://github.com/o/r/releases/tag/v0.1.0) · 2026-06-15",
        ]))

    def test_plan_progress_task_link_falls_back_to_literal(self):
        # No 'task' id on the progress entry -> the literal word "task", never a
        # dropped clause (the whole progress line is one clause).
        plan = pm.Item(id="p2", type="plan", title="P", fields={
            "kickoff": {"goal": "g", "done_when": "d"},
            "progress": [{"date": "2026-06-14", "progress": "moved"}],
        })
        body = _render(plan, graph={"p2": plan})
        self.assertIn("**② 2026-06-14** (→ task): moved", body)

    def test_feature_no_deferred_drops_clause(self):
        feat = pm.Item(id="f1", type="feature", title="F", fields={
            "kickoff": {"goal": "sync to board",
                        "why_matters": "humans see status"},
            "progress": [{"date": "2026-06-14", "plan_goal": "Build it",
                          "version": "v0.1.0"}],
            "closeout": {"outcome": "done", "releases": ["v0.1.0", "v0.1.1"]},
        })
        self.assertEqual(_render(feat), "\n\n".join([
            "**① Goal:** sync to board  ·  **Why it matters:** humans see status",
            "**② 2026-06-14**: Build it shipped (v0.1.0)",
            "**③ Outcome:** done  ·  **Shipped:** [v0.1.0](https://github.com/o/r/releases/tag/v0.1.0) · [v0.1.1](https://github.com/o/r/releases/tag/v0.1.1)",
        ]))

    def test_feature_with_deferred_link(self):
        target = pm.Item(id="d1", type="feature", title="Spanish pass", issue=99)
        feat = pm.Item(id="f2", type="feature", title="F2", fields={
            "kickoff": {"goal": "g", "why_matters": "w"},
            "closeout": {"outcome": "done", "release": "v0.1.0",
                         "deferred": "the translate pass", "deferred_target": "d1"},
        })
        graph = {"d1": target, "f2": feat}
        body = _render(feat, graph=graph)
        self.assertIn(
            "**③ Outcome:** done  ·  **Shipped:** [v0.1.0](https://github.com/o/r/releases/tag/v0.1.0)  ·  "
            "**Deferred:** the translate pass → [Spanish pass](https://github.com/o/r/issues/99)",
            body)

    def test_feature_deferred_survives_without_target(self):
        # DEFECT 1 regression: deferred prose present, NO deferred_target. The
        # human-authored deferral must render even when nothing is linked — it
        # must not vanish along with the (absent) link. Before the fix, fill()
        # dropped the whole `**Deferred:** {{deferred}} → {{deferred_link}}`
        # clause because deferred_link resolved to None.
        feat = pm.Item(id="f3", type="feature", title="F3", fields={
            "kickoff": {"goal": "g", "why_matters": "w"},
            "closeout": {"outcome": "done", "release": "v0.1.0",
                         "deferred": "the auth rework"},
        })
        body = _render(feat)
        self.assertIn(
            "**③ Outcome:** done  ·  **Shipped:** [v0.1.0](https://github.com/o/r/releases/tag/v0.1.0)  ·  "
            "**Deferred:** the auth rework",
            body)
        self.assertNotIn("None", body)
        self.assertNotIn("→", body)  # no orphaned arrow when there's nothing to link

    def test_feature_deferred_survives_unmaterialized_target(self):
        # DEFECT 1 regression: deferred_target given, but its issue isn't
        # materialized yet (the normal DC-1 state for a future target) — the
        # prose must still render; only the `→ link` is omitted.
        target = pm.Item(id="d2", type="feature", title="Later", issue=None)
        feat = pm.Item(id="f4", type="feature", title="F4", fields={
            "kickoff": {"goal": "g", "why_matters": "w"},
            "closeout": {"outcome": "done", "release": "v0.1.0",
                         "deferred": "the translate pass", "deferred_target": "d2"},
        })
        body = _render(feat, graph={"d2": target, "f4": feat})
        self.assertIn("**Deferred:** the translate pass", body)
        self.assertNotIn("None", body)
        self.assertNotIn("→", body)

    def test_version(self):
        v = pm.Item(id="v5", type="version", title="V5",
                    fields={"about": "the unbundling arc"})
        self.assertEqual(_render(v), "**About:** the unbundling arc")

    def test_backlog_item(self):
        b = pm.Item(id="b1", type="backlog-item", title="B", priority="P2",
                    fields={"what": "add X", "why_matters": "users want it",
                            "priority_reason": "low effort"})
        self.assertEqual(
            _render(b),
            "**What:** add X  ·  **Why it matters:** users want it  ·  "
            "**Priority:** P2 — low effort")

    def test_backlog_item_with_promotion(self):
        target = pm.Item(id="pt", type="feature", title="Real feature", issue=50)
        b = pm.Item(id="b2", type="backlog-item", title="B", priority="P1",
                    fields={"what": "x", "why_matters": "y",
                            "priority_reason": "z",
                            "promotion": {"target": "pt", "date": "2026-06-14"}})
        graph = {"pt": target, "b2": b}
        body = _render(b, graph=graph)
        self.assertTrue(body.endswith(
            "\n\n**Promoted → [Real feature](https://github.com/o/r/issues/50)** · 2026-06-14"))

    def test_idea_without_promote_target_drops_clause(self):
        i = pm.Item(id="i1", type="idea", title="I",
                    fields={"spark": "what if we cached"})
        self.assertEqual(_render(i), "what if we cached")

    def test_idea_with_promote_target(self):
        i = pm.Item(id="i2", type="idea", title="I",
                    fields={"spark": "cache it", "promote_target": "a feature"})
        self.assertEqual(_render(i), "cache it  ·  **Could promote → a feature**")


class TestSilentSource(unittest.TestCase):
    def _backlog(self):
        return pm.Item(id="b1", type="backlog-item", title="B", priority="P2",
                       silent_source="private influence",
                       fields={"what": "x", "why_matters": "y",
                               "priority_reason": "z"})

    def test_public_omits_silent_source(self):
        body = _render(self._backlog(), public=True)
        self.assertNotIn("Source (private)", body)
        self.assertNotIn("private influence", body)

    def test_private_appends_silent_source(self):
        body = _render(self._backlog(), public=False)
        self.assertTrue(body.endswith(
            "\n\n**Source (private):** private influence"))

    def test_no_silent_source_no_attribution_even_private(self):
        item = pm.Item(id="b2", type="backlog-item", title="B", priority="P2",
                       fields={"what": "x", "why_matters": "y",
                               "priority_reason": "z"})
        self.assertNotIn("Source (private)", _render(item, public=False))


class TestRefusalsAndCompleteness(unittest.TestCase):
    def test_bug_has_no_template(self):
        bug = pm.Item(id="bug1", type="bug", title="crash")
        with self.assertRaises(ps.RenderError):
            _render(bug)

    def test_no_rendered_body_leaves_unfilled_placeholder(self):
        target = pm.Item(id="pt", type="feature", title="Real", issue=50)
        items = [
            pm.Item(id="t", type="task", title="T", fields={
                "kickoff": {"goal": "g", "done_when": "d"},
                "progress": [{"date": "2026-06-14", "sha": "abc",
                              "progress": "p"}],
                "closeout": {"outcome": "o", "sha": "def", "date": "2026-06-15"}}),
            pm.Item(id="v", type="version", title="V", fields={"about": "a"}),
            pm.Item(id="i", type="idea", title="I", fields={"spark": "s"}),
            pm.Item(id="b", type="backlog-item", title="B", priority="P2", fields={
                "what": "w", "why_matters": "y", "priority_reason": "r",
                "promotion": {"target": "pt", "date": "2026-06-14"}}),
        ]
        graph = {"pt": target}
        for item in items:
            with self.subTest(type=item.type):
                body = _render(item, graph=graph)
                self.assertNotIn("{{", body)
                self.assertNotIn("}}", body)


_CFG = {
    "vault_project": "crickets",
    "github": {"owner": "o", "number": 5, "repo": "o/r",
               "url": "https://github.com/users/o/projects/5"},
}


class TestConfig(unittest.TestCase):
    def test_load_config_ok(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "project.json"
            p.write_text(json.dumps(_CFG), encoding="utf-8")
            cfg = ps.load_config(p)
            self.assertEqual(cfg["github"]["number"], 5)

    def test_load_config_rejects_missing_top_keys(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "project.json"
            p.write_text(json.dumps({"vault_project": "x"}), encoding="utf-8")
            with self.assertRaises(ps.SyncError):
                ps.load_config(p)

    def test_load_config_rejects_missing_github_number(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "project.json"
            p.write_text(json.dumps({"vault_project": "x",
                                     "github": {"owner": "o"}}), encoding="utf-8")
            with self.assertRaises(ps.SyncError):
                ps.load_config(p)

    def test_project_repo_url(self):
        self.assertEqual(ps.project_repo_url(_CFG), "https://github.com/o/r")

    def test_project_repo_url_requires_repo(self):
        with self.assertRaises(ps.SyncError):
            ps.project_repo_url({"github": {"owner": "o", "number": 5}})

    def test_project_url_from_cfg(self):
        self.assertEqual(ps.project_url(_CFG),
                         "https://github.com/users/o/projects/5")

    def test_project_url_derived_when_absent(self):
        cfg = {"github": {"owner": "o", "number": 9}}
        self.assertEqual(ps.project_url(cfg),
                         "https://github.com/users/o/projects/9")


class TestArgvBuilders(unittest.TestCase):
    def test_issue_create(self):
        self.assertEqual(
            ps.issue_create_argv("o/r", "Title", "Body"),
            ["gh", "issue", "create", "--repo", "o/r",
             "--title", "Title", "--body", "Body"])

    def test_issue_edit(self):
        self.assertEqual(
            ps.issue_edit_argv("o/r", 7, "Body"),
            ["gh", "issue", "edit", "7", "--repo", "o/r", "--body", "Body"])

    def test_project_item_add(self):
        self.assertEqual(
            ps.project_item_add_argv("o", 5, "https://github.com/o/r/issues/9"),
            ["gh", "project", "item-add", "5", "--owner", "o",
             "--url", "https://github.com/o/r/issues/9"])

    def test_project_create(self):
        self.assertEqual(
            ps.project_create_argv("o", "r"),
            ["gh", "project", "create", "--owner", "o", "--title", "r"])

    def test_item_edit_text_date_select(self):
        self.assertEqual(
            ps.project_item_edit_text_argv("P", "I", "F", "V"),
            ["gh", "project", "item-edit", "--id", "I", "--project-id", "P",
             "--field-id", "F", "--text", "V"])
        self.assertEqual(
            ps.project_item_edit_date_argv("P", "I", "F", "2026-06-14"),
            ["gh", "project", "item-edit", "--id", "I", "--project-id", "P",
             "--field-id", "F", "--date", "2026-06-14"])
        self.assertEqual(
            ps.project_item_edit_select_argv("P", "I", "F", "OPT"),
            ["gh", "project", "item-edit", "--id", "I", "--project-id", "P",
             "--field-id", "F", "--single-select-option-id", "OPT"])


class TestPlanItemAction(unittest.TestCase):
    def test_no_issue_is_create(self):
        item = pm.Item(id="v", type="version", title="V")
        self.assertEqual(ps.plan_item_action(item, "body").kind, "create")

    def test_unchanged_body_is_noop(self):
        item = pm.Item(id="v", type="version", title="V", issue=7)
        a = ps.plan_item_action(item, "body", current_body="body")
        self.assertEqual(a.kind, "noop")

    def test_unchanged_modulo_whitespace_is_noop(self):
        item = pm.Item(id="v", type="version", title="V", issue=7)
        self.assertEqual(
            ps.plan_item_action(item, "body\n", current_body="  body  ").kind,
            "noop")

    def test_changed_body_is_update(self):
        item = pm.Item(id="v", type="version", title="V", issue=7)
        self.assertEqual(
            ps.plan_item_action(item, "new", current_body="old").kind, "update")

    def test_existing_issue_unknown_state_forces_update(self):
        # current_body=None on a materialized issue must NOT be assumed no-op.
        item = pm.Item(id="v", type="version", title="V", issue=7)
        self.assertEqual(ps.plan_item_action(item, "body").kind, "update")


class TestBuildCommands(unittest.TestCase):
    def test_noop_yields_no_commands(self):
        a = ps.Action("noop", "v", "V", "body", 7)
        self.assertEqual(ps.build_commands(a, _CFG), [])

    def test_create_yields_issue_create(self):
        a = ps.Action("create", "v", "V", "body", None)
        cmds = ps.build_commands(a, _CFG)
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0].argv, ps.issue_create_argv("o/r", "V", "body"))

    def test_create_with_url_appends_item_add(self):
        a = ps.Action("create", "v", "V", "body", None)
        cmds = ps.build_commands(a, _CFG,
                                 issue_url="https://github.com/o/r/issues/9")
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[1].argv,
                         ps.project_item_add_argv("o", 5,
                                                  "https://github.com/o/r/issues/9"))

    def test_update_yields_issue_edit(self):
        a = ps.Action("update", "v", "V", "body", 7)
        cmds = ps.build_commands(a, _CFG)
        self.assertEqual(cmds[0].argv, ps.issue_edit_argv("o/r", 7, "body"))


class TestSyncItemIdempotency(unittest.TestCase):
    def _version(self, issue=None):
        return pm.Item(id="v5", type="version", title="V5", issue=issue,
                       fields={"about": "the arc"})

    def test_unchanged_state_is_noop_no_commands(self):
        item = self._version(issue=7)
        body = ps.render_item(item, "https://github.com/o/r", _TEMPLATES)
        action, cmds = ps.sync_item(item, _CFG, _TEMPLATES, current_body=body)
        self.assertEqual(action.kind, "noop")
        self.assertEqual(cmds, [])

    def test_stale_state_is_update(self):
        item = self._version(issue=7)
        action, cmds = ps.sync_item(item, _CFG, _TEMPLATES, current_body="stale")
        self.assertEqual(action.kind, "update")
        self.assertEqual(cmds[0].argv,
                         ps.issue_edit_argv("o/r", 7, "**About:** the arc"))

    def test_unmaterialized_is_create(self):
        item = self._version(issue=None)
        action, cmds = ps.sync_item(item, _CFG, _TEMPLATES)
        self.assertEqual(action.kind, "create")
        self.assertEqual(cmds[0].argv[:3], ["gh", "issue", "create"])


class TestExecute(unittest.TestCase):
    def _cmds(self):
        return [ps.GhCommand(ps.issue_edit_argv("o/r", 7, "body"))]

    def test_dry_run_prints_and_returns_without_running(self):
        calls = []
        buf = io.StringIO()
        ran = ps.execute(self._cmds(), dry_run=True,
                         runner=lambda argv: calls.append(argv), out=buf)
        self.assertEqual(calls, [])  # nothing executed
        self.assertIn("gh issue edit 7 --repo o/r --body body", buf.getvalue())
        self.assertEqual(ran, [("gh issue edit 7 --repo o/r --body body", None)])

    def test_live_runs_via_injected_runner(self):
        calls = []
        ran = ps.execute(self._cmds(), dry_run=False,
                         runner=lambda argv: calls.append(argv) or "ok")
        self.assertEqual(calls, [["gh", "issue", "edit", "7", "--repo", "o/r",
                                  "--body", "body"]])
        self.assertEqual(ran, [("gh issue edit 7 --repo o/r --body body", "ok")])


class TestApplyUpdate(unittest.TestCase):
    def test_task_progress_appends_entry(self):
        item = pm.Item(id="t", type="task", title="T", fields={})
        ps.apply_update(item, "task-progress", date="2026-06-14",
                        commit="abc", summary="did x")
        self.assertEqual(item.fields["progress"],
                         [{"date": "2026-06-14", "sha": "abc", "progress": "did x"}])

    def test_task_progress_appends_to_existing(self):
        item = pm.Item(id="t", type="task", title="T",
                       fields={"progress": [{"date": "2026-06-13", "sha": "old",
                                             "progress": "p0"}]})
        ps.apply_update(item, "task-progress", date="2026-06-14",
                        commit="new", summary="p1")
        self.assertEqual(len(item.fields["progress"]), 2)

    def test_task_progress_same_sha_is_noop(self):
        # SHA-keyed dedupe: re-posting the same commit must not duplicate the
        # progress entry (a re-run on unchanged state writes nothing).
        item = pm.Item(id="t", type="task", title="T", fields={})
        ps.apply_update(item, "task-progress", date="2026-06-14",
                        commit="abc", summary="did x")
        ps.apply_update(item, "task-progress", date="2026-06-15",
                        commit="abc", summary="did x again")
        self.assertEqual(item.fields["progress"],
                         [{"date": "2026-06-14", "sha": "abc", "progress": "did x"}])

    def test_task_progress_requires_commit_and_summary(self):
        item = pm.Item(id="t", type="task", title="T", fields={})
        with self.assertRaises(ps.RenderError):
            ps.apply_update(item, "task-progress", date="2026-06-14", summary="x")
        with self.assertRaises(ps.RenderError):
            ps.apply_update(item, "task-progress", date="2026-06-14", commit="x")

    def test_plan_progress_summary_only(self):
        item = pm.Item(id="p", type="plan", title="P", fields={})
        ps.apply_update(item, "plan-progress", date="2026-06-14", summary="task done")
        self.assertEqual(item.fields["progress"],
                         [{"date": "2026-06-14", "progress": "task done"}])

    def test_task_closeout_sets_closeout(self):
        item = pm.Item(id="t", type="task", title="T", fields={})
        ps.apply_update(item, "task-closeout", date="2026-06-15",
                        commit="def", summary="shipped")
        self.assertEqual(item.fields["closeout"],
                         {"outcome": "shipped", "sha": "def", "date": "2026-06-15"})

    def test_feature_progress_unsupported(self):
        item = pm.Item(id="f", type="feature", title="F", fields={})
        with self.assertRaises(ps.RenderError):
            ps.apply_update(item, "feature-progress", date="2026-06-14",
                            summary="x")

    def test_plan_closeout_unsupported(self):
        item = pm.Item(id="p", type="plan", title="P", fields={})
        with self.assertRaises(ps.RenderError):
            ps.apply_update(item, "plan-closeout", date="2026-06-14",
                            commit="x", summary="y")

    def test_kickoff_unsupported(self):
        item = pm.Item(id="t", type="task", title="T", fields={})
        with self.assertRaises(ps.RenderError):
            ps.apply_update(item, "task-kickoff", date="2026-06-14", summary="x")

    def test_bad_update_type(self):
        item = pm.Item(id="t", type="task", title="T", fields={})
        with self.assertRaises(ps.RenderError):
            ps.apply_update(item, "garbage", date="2026-06-14")

    def test_unknown_stage(self):
        item = pm.Item(id="t", type="task", title="T", fields={})
        with self.assertRaises(ps.RenderError):
            ps.apply_update(item, "task-foo", date="2026-06-14")


class TestPostComment(unittest.TestCase):
    def _task(self, issue=9):
        return pm.Item(id="t1", type="task", title="T", issue=issue)

    def _runner(self, comments=(), calls=None):
        calls = calls if calls is not None else []

        def runner(argv):
            calls.append(argv)
            if argv[:3] == ["gh", "issue", "view"]:
                return json.dumps({"comments": [{"body": c} for c in comments]})
            return ""
        return runner, calls

    def test_first_post_issues_comment(self):
        runner, calls = self._runner(comments=[])
        out = ps.post_comment(self._task(), "task-progress", _CFG, date="2026-07-03",
                              commit="abc1234", summary="did x",
                              runner=runner, dry_run=False)
        self.assertEqual(out, "")
        comment_calls = [c for c in calls if c[:3] == ["gh", "issue", "comment"]]
        self.assertEqual(len(comment_calls), 1)
        self.assertEqual(comment_calls[0][:4], ["gh", "issue", "comment", "9"])
        self.assertIn("<!-- board:sha:abc1234 -->", comment_calls[0][-1])

    def test_repost_same_sha_is_noop(self):
        # list-and-match dedupe: the marker is already on an existing comment.
        runner, calls = self._runner(comments=["<!-- board:sha:abc1234 -->"])
        ps.post_comment(self._task(), "task-progress", _CFG, date="2026-07-03",
                        commit="abc1234", summary="did x again",
                        runner=runner, dry_run=False)
        comment_calls = [c for c in calls if c[:3] == ["gh", "issue", "comment"]]
        self.assertEqual(comment_calls, [])

    def test_taskclose_marker_variant(self):
        runner, calls = self._runner(comments=[])
        ps.post_comment(self._task(), "task-closeout", _CFG, date="2026-07-03",
                        commit="def5678", summary="shipped",
                        runner=runner, dry_run=False)
        comment_calls = [c for c in calls if c[:3] == ["gh", "issue", "comment"]]
        self.assertEqual(len(comment_calls), 1)
        self.assertIn("<!-- board:taskclose:t1 -->", comment_calls[0][-1])

    def test_no_issue_is_noop(self):
        runner, calls = self._runner(comments=[])
        ps.post_comment(self._task(issue=None), "task-progress", _CFG,
                        date="2026-07-03", commit="abc", summary="x",
                        runner=runner, dry_run=False)
        self.assertEqual(calls, [])

    def test_non_task_update_type_is_noop(self):
        runner, calls = self._runner(comments=[])
        ps.post_comment(self._task(), "plan-progress", _CFG, date="2026-07-03",
                        summary="x", runner=runner, dry_run=False)
        self.assertEqual(calls, [])

    def test_unreadable_comment_state_is_noop(self):
        # A gh failure on the read must never risk a duplicate post.
        def runner(argv):
            raise ps.SyncError("boom")
        calls = []
        ps.post_comment(self._task(), "task-progress", _CFG, date="2026-07-03",
                        commit="abc", summary="x",
                        runner=lambda a: (calls.append(a), runner(a))[1],
                        dry_run=False)
        self.assertEqual(len(calls), 1)  # only the (failed) view call, no comment post

    def test_dry_run_previews_without_posting(self):
        runner, calls = self._runner(comments=[])
        buf = io.StringIO()
        ps.post_comment(self._task(), "task-progress", _CFG, date="2026-07-03",
                        commit="abc1234", summary="did x",
                        runner=runner, dry_run=True, out=buf)
        self.assertIn("gh issue comment 9 --repo o/r --body", buf.getvalue())
        self.assertEqual([c for c in calls if c[:3] == ["gh", "issue", "comment"]], [])


class TestFindItem(unittest.TestCase):
    def _graph(self):
        return {
            "a": pm.Item(id="a", type="version", title="A", issue=7),
            "b": pm.Item(id="b", type="version", title="B"),
        }

    def test_by_id(self):
        self.assertEqual(ps.find_item(self._graph(), item_id="b").id, "b")

    def test_by_issue(self):
        self.assertEqual(ps.find_item(self._graph(), issue=7).id, "a")

    def test_unknown_id_raises(self):
        with self.assertRaises(ps.SyncError):
            ps.find_item(self._graph(), item_id="z")

    def test_unbound_issue_raises(self):
        with self.assertRaises(ps.SyncError):
            ps.find_item(self._graph(), issue=99)

    def test_no_selector_raises(self):
        with self.assertRaises(ps.SyncError):
            ps.find_item(self._graph())


class TestResolveFieldIds(unittest.TestCase):
    def test_parses_fields_and_options(self):
        canned = json.dumps({"fields": [
            {"id": "F1", "name": "Track",
             "options": [{"id": "O1", "name": "V5"},
                         {"id": "O2", "name": "Backlog"}]},
            {"id": "F2", "name": "Start"},
        ]})
        seen = {}

        def runner(argv):
            seen["argv"] = argv
            return canned

        ids = ps.resolve_field_ids(_CFG, runner=runner)
        self.assertEqual(ids["Track"]["id"], "F1")
        self.assertEqual(ids["Track"]["options"]["V5"], "O1")
        self.assertEqual(ids["Start"]["options"], {})
        self.assertEqual(seen["argv"],
                         ["gh", "project", "field-list", "5",
                          "--owner", "o", "--format", "json"])


class TestSyncFields(unittest.TestCase):
    """DC-2 field writes (task 4): idempotent, Status flips only at a named
    lifecycle transition, never an option-creating mutation."""

    _FIELD_LIST = json.dumps({"fields": [
        {"id": "F_TRACK", "name": "Track",
         "options": [{"id": "O_V5", "name": "V5"}]},
        {"id": "F_STATUS", "name": "Status",
         "options": [{"id": "O_TODO", "name": "Todo"},
                     {"id": "O_PROG", "name": "In Progress"},
                     {"id": "O_DONE", "name": "Done"}]},
    ]})

    def _runner(self, item_status, calls=None):
        calls = calls if calls is not None else []

        def runner(argv):
            calls.append(argv)
            if argv[:3] == ["gh", "project", "view"]:
                return json.dumps({"id": "PROJECT_ID"})
            if argv[:3] == ["gh", "project", "item-list"]:
                return json.dumps({"items": [
                    {"id": "ITEM_ID", "content": {"number": 9},
                     "Track": "V5", "Status": item_status},
                ]})
            if argv[:3] == ["gh", "project", "field-list"]:
                return self._FIELD_LIST
            return ""
        return runner, calls

    def _task(self):
        return pm.Item(id="t1", type="task", title="T", issue=9, track="V5")

    def test_progress_flips_status_todo_to_in_progress(self):
        runner, calls = self._runner(item_status="Todo")
        expected_argv = ps.project_item_edit_select_argv(
            "PROJECT_ID", "ITEM_ID", "F_STATUS", "O_PROG")
        rendered = ps.sync_fields(self._task(), _CFG, "progress",
                                  runner=runner, dry_run=False)
        self.assertEqual(rendered, [ps.GhCommand(expected_argv).render()])
        item_edit_calls = [c for c in calls if c[:3] == ["gh", "project", "item-edit"]]
        self.assertEqual(item_edit_calls, [expected_argv])

    def test_closeout_flips_status_and_closes_issue(self):
        runner, calls = self._runner(item_status="In Progress")
        ps.sync_fields(self._task(), _CFG, "closeout", runner=runner, dry_run=False)
        item_edit_calls = [c for c in calls if c[:3] == ["gh", "project", "item-edit"]]
        self.assertEqual(item_edit_calls,
                         [ps.project_item_edit_select_argv(
                             "PROJECT_ID", "ITEM_ID", "F_STATUS", "O_DONE")])
        close_calls = [c for c in calls if c[:3] == ["gh", "issue", "close"]]
        self.assertEqual(close_calls, [["gh", "issue", "close", "9", "--repo", "o/r"]])

    def test_matching_field_is_idempotent_skip(self):
        # Track already "V5" on the board AND item.track == "V5" -> no item-edit
        # for Track; stage=None means Status is never touched either.
        runner, calls = self._runner(item_status="Todo")
        ps.sync_fields(self._task(), _CFG, None, runner=runner, dry_run=False)
        item_edit_calls = [c for c in calls if c[:3] == ["gh", "project", "item-edit"]]
        self.assertEqual(item_edit_calls, [])

    def test_progress_repost_is_idempotent_once_in_progress(self):
        # Already "In Progress" on the board -> the progress-stage Status write
        # is skipped (idempotent-skip IS the Todo->In-Progress-once mechanism).
        runner, calls = self._runner(item_status="In Progress")
        ps.sync_fields(self._task(), _CFG, "progress", runner=runner, dry_run=False)
        item_edit_calls = [c for c in calls if c[:3] == ["gh", "project", "item-edit"]]
        self.assertEqual(item_edit_calls, [])

    def test_no_issue_is_noop(self):
        runner, calls = self._runner(item_status="Todo")
        ps.sync_fields(pm.Item(id="t2", type="task", title="T"), _CFG, "progress",
                       runner=runner, dry_run=False)
        self.assertEqual(calls, [])

    def test_never_creates_a_field_option(self):
        # Static grep-lock: this write path must never call updateProjectV2Field
        # or any option-creating mutation — only `item-edit` on options
        # `field-list` already resolves.
        src = (_SRC / "project_sync.py").read_text(encoding="utf-8")
        self.assertNotIn("updateProjectV2Field", src)
        self.assertNotIn("field create", src)
        self.assertNotIn("option create", src)


class TestSyncNesting(unittest.TestCase):
    """Depth materialization (task 5): native sub-issue nesting via the
    addSubIssue GraphQL mutation, list-and-match dedupe against a parent's
    existing sub-issues."""

    def _graph(self):
        return {
            "f1": pm.Item(id="f1", type="feature", title="F", issue=8),
            "p1": pm.Item(id="p1", type="plan", parent="f1", title="P", issue=9),
            "t1": pm.Item(id="t1", type="task", parent="p1", title="T", issue=10),
        }

    def _runner(self, existing_sub_numbers=(), calls=None):
        calls = calls if calls is not None else []

        def runner(argv):
            calls.append(argv)
            if argv[:3] == ["gh", "api", "graphql"] and "query=query(" in argv[4]:
                number = int(argv[-1].split("=", 1)[1])
                if number == 8:  # the parent (feature f1, issue 8)
                    nodes = [{"number": n} for n in existing_sub_numbers]
                    return json.dumps({"data": {"repository": {"issue": {
                        "id": "NODE_F1", "number": 8,
                        "subIssues": {"nodes": nodes}}}}})
                return json.dumps({"data": {"repository": {"issue": {
                    "id": f"NODE_ISSUE_{number}", "number": number,
                    "subIssues": {"nodes": []}}}}})
            return ""
        return runner, calls

    def test_nests_task_under_its_parent(self):
        graph = self._graph()
        item = graph["p1"]  # plan p1 (issue 9), parent feature f1 (issue 8)
        runner, calls = self._runner(existing_sub_numbers=[])
        ps.sync_nesting(item, _CFG, graph, runner=runner, dry_run=False)
        mutation_calls = [c for c in calls
                          if "addSubIssue" in (c[4] if len(c) > 4 else "")]
        self.assertEqual(len(mutation_calls), 1)
        self.assertEqual(mutation_calls[0],
                         ps.add_sub_issue_argv("NODE_F1", "NODE_ISSUE_9"))

    def test_already_nested_is_noop(self):
        graph = self._graph()
        item = graph["p1"]
        runner, calls = self._runner(existing_sub_numbers=[9])  # already linked
        ps.sync_nesting(item, _CFG, graph, runner=runner, dry_run=False)
        mutation_calls = [c for c in calls
                          if "addSubIssue" in (c[4] if len(c) > 4 else "")]
        self.assertEqual(mutation_calls, [])

    def test_unmaterialized_parent_is_noop(self):
        graph = self._graph()
        graph["f1"].issue = None  # parent not yet on the board
        runner, calls = self._runner()
        ps.sync_nesting(graph["p1"], _CFG, graph, runner=runner, dry_run=False)
        self.assertEqual(calls, [])

    def test_non_plan_task_type_is_noop(self):
        graph = self._graph()
        runner, calls = self._runner()
        ps.sync_nesting(graph["f1"], _CFG, graph, runner=runner, dry_run=False)
        self.assertEqual(calls, [])

    def test_sync_all_nesting_covers_materialized_items(self):
        graph = self._graph()
        runner, calls = self._runner(existing_sub_numbers=[])
        ps.sync_all_nesting(graph, _CFG, ["p1"], runner=runner, dry_run=False)
        mutation_calls = [c for c in calls
                          if "addSubIssue" in (c[4] if len(c) > 4 else "")]
        # Task t1 (parent p1, active) and Plan p1 (parent f1) both nest.
        self.assertEqual(len(mutation_calls), 2)


class TestCLIDryRun(unittest.TestCase):
    """End-to-end ``main(['post', ...])`` regression tests. The unit tests above
    drive sync_item/apply_update directly and so bypass main()'s three failure
    surfaces: the importlib load of project_model (must register in sys.modules
    before exec or the @dataclass under `from __future__` resolution fails), the
    default templates dir (a SIBLING of scripts/, not a child), and selector
    resolution. Each was a real bug a direct-call test could not catch."""

    def _cfg_dir(self, items):
        """Write project.json + sibling board-items.json into a temp dir; return
        the temp dir handle and the config path. Caller owns the handle."""
        t = tempfile.TemporaryDirectory()
        d = Path(t.name)
        (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
        (d / "board-items.json").write_text(json.dumps({"items": items}),
                                            encoding="utf-8")
        return t, d / "project.json"

    def test_post_renders_and_dry_runs(self):
        # A version with a bound issue → an update (current body unknown ⇒ forced),
        # rendered through the DEFAULT (sibling) templates dir, printed by --dry-run.
        items = [{"id": "v5", "type": "version", "track": "V5", "title": "V5 arc",
                  "about": "the unbundling", "issue": 7}]
        t, cfg_p = self._cfg_dir(items)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ps.main(["post", "--config", str(cfg_p),
                              "--issue", "7", "--dry-run"])
            out = buf.getvalue()
        finally:
            t.cleanup()
        self.assertEqual(rc, 0)
        self.assertIn("gh issue edit 7 --repo o/r", out)
        self.assertIn("**About:** the unbundling", out)

    def test_post_missing_selector_raises(self):
        t, cfg_p = self._cfg_dir(
            [{"id": "v5", "type": "version", "title": "V5 arc", "about": "x"}])
        try:
            with self.assertRaises(ps.SyncError):
                ps.main(["post", "--config", str(cfg_p), "--dry-run"])
        finally:
            t.cleanup()

    def test_post_fold_progress_appears_in_body(self):
        # --type plan-progress --summary folds a ② line into the plan's body, then
        # re-renders it through main() end-to-end.
        items = [
            {"id": "v5", "type": "version", "title": "V5 arc", "issue": 7},
            {"id": "f", "type": "feature", "parent": "v5", "title": "F", "issue": 8},
            {"id": "p1", "type": "plan", "parent": "f", "title": "P", "issue": 9},
        ]
        t, cfg_p = self._cfg_dir(items)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ps.main(["post", "--config", str(cfg_p), "--issue", "9",
                              "--type", "plan-progress", "--summary", "did it",
                              "--dry-run"])
            out = buf.getvalue()
        finally:
            t.cleanup()
        self.assertEqual(rc, 0)
        self.assertIn("gh issue edit 9 --repo o/r", out)
        self.assertIn("(→ task): did it", out)

    def test_sync_nesting_cli_dry_runs(self):
        items = [
            {"id": "v5", "type": "version", "title": "V5 arc", "issue": 7},
            {"id": "f", "type": "feature", "parent": "v5", "title": "F", "issue": 8},
            {"id": "p1", "type": "plan", "parent": "f", "title": "P", "issue": 9},
        ]
        t, cfg_p = self._cfg_dir(items)
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ps.main(["sync-nesting", "--config", str(cfg_p),
                              "--active-plan", "p1", "--dry-run"])
        finally:
            t.cleanup()
        self.assertEqual(rc, 0)


class TestMainPersistence(unittest.TestCase):
    """cricketsPluginsA#5 regression: main() must persist state back to
    board-items.json, not just fold it into an in-memory Item that vanishes
    when the process exits. Injected-runner, no live `gh` calls."""

    def _cfg_dir(self, items):
        t = tempfile.TemporaryDirectory()
        d = Path(t.name)
        (d / "project.json").write_text(json.dumps(_CFG), encoding="utf-8")
        (d / "board-items.json").write_text(json.dumps({"items": items}),
                                            encoding="utf-8")
        return t, d / "project.json", d / "board-items.json"

    def test_task_progress_persists_and_reruns_are_noop(self):
        items = [
            {"id": "v1", "type": "version", "title": "V"},
            {"id": "f1", "type": "feature", "parent": "v1", "title": "F"},
            {"id": "p1", "type": "plan", "parent": "f1", "title": "P"},
            {"id": "t1", "type": "task", "parent": "p1", "title": "T", "issue": 9},
        ]
        t, cfg_p, items_p = self._cfg_dir(items)
        try:
            before = items_p.read_text(encoding="utf-8")

            def runner(argv):
                if argv[:3] == ["gh", "issue", "view"]:
                    raise ps.SyncError("not found")  # forces current_body=None
                return ""

            rc1 = ps.main(["post", "--config", str(cfg_p), "--issue", "9",
                          "--type", "task-progress", "--commit", "abc",
                          "--summary", "did x"], runner=runner)
            self.assertEqual(rc1, 0)
            after_run1 = items_p.read_text(encoding="utf-8")
            self.assertNotEqual(before, after_run1)  # (a) file changed on disk

            rc2 = ps.main(["post", "--config", str(cfg_p), "--issue", "9",
                          "--type", "task-progress", "--commit", "abc",
                          "--summary", "did x again"], runner=runner)
            self.assertEqual(rc2, 0)
            after_run2 = items_p.read_text(encoding="utf-8")

            reloaded = pm.load(items_p)
            self.assertEqual(reloaded["t1"].fields["progress"],
                             [{"date": reloaded["t1"].fields["progress"][0]["date"],
                               "sha": "abc", "progress": "did x"}])
            # (b) same-SHA re-run appends nothing new to item.fields["progress"]
            self.assertEqual(len(reloaded["t1"].fields["progress"]), 1)
        finally:
            t.cleanup()

    def test_create_action_persists_returned_issue_number(self):
        items = [
            {"id": "v2", "type": "version", "title": "V"},
            {"id": "f2", "type": "feature", "parent": "v2", "title": "F"},
            {"id": "p2", "type": "plan", "parent": "f2", "title": "P"},
            {"id": "t2", "type": "task", "parent": "p2", "title": "New task"},
        ]
        t, cfg_p, items_p = self._cfg_dir(items)
        try:
            def runner(argv):
                if argv[:3] == ["gh", "issue", "create"]:
                    return "https://github.com/o/r/issues/999"
                return ""

            rc = ps.main(["post", "--config", str(cfg_p), "--id", "t2"],
                        runner=runner)
            self.assertEqual(rc, 0)

            # (c) the create action's returned issue number lands in item.issue
            reloaded = pm.load(items_p)
            self.assertEqual(reloaded["t2"].issue, 999)
        finally:
            t.cleanup()


if __name__ == "__main__":
    unittest.main()
