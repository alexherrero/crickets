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

import datetime
import importlib.util
import sys
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


if __name__ == "__main__":
    unittest.main()
