#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/orient_render.py — the ORIENT
renderer for `/open` / `/orient` (PLAN-open-a-project-by-name tasks 3 + 5).

Every plan comes from agentm (crickets task 101): the unit tests patch the
bridge's answers, and `TestInTheScratchVault` runs the real bridge against
`no_harness_fixture`'s stub agentm — a repo-bound project and one named by slug
alone. No test builds the retired harness directory, and none reaches a real
agentm or vault.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / filename)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

orr = _load("orient_render", "orient_render.py")

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import no_harness_fixture as nhf  # noqa: E402


_PLAN_TEXT = """---
touches_architecture: false
---

# Plan: Widgets

## Tasks

### 1. First task
- **What:** does a thing.
- **Status:** [x]

### 2. Second task
- **What:** does another thing.
- **Status:** [ ]
"""


class TestTaskChecklist(unittest.TestCase):
    def test_mixed_statuses_render_checks_and_boxes(self):
        result = orr._task_checklist(_PLAN_TEXT)
        self.assertEqual(result, ["✅ First task", "⬜ Second task"])

    def test_no_tasks_returns_empty(self):
        self.assertEqual(orr._task_checklist("# Plan: Empty\n\nNo tasks here.\n"), [])

    def test_task_with_no_status_line_is_skipped(self):
        text = "### 1. Orphan task\n- **What:** no status line follows.\n"
        self.assertEqual(orr._task_checklist(text), [])


class TestProgressTail(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-progress-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_file_returns_empty(self):
        self.assertEqual(orr.progress_tail(self.tmp / "nope.md"), [])

    def test_returns_last_n_nonempty_lines(self):
        p = self.tmp / "progress.md"
        p.write_text("line1\n\nline2\nline3\nline4\n", encoding="utf-8")
        self.assertEqual(orr.progress_tail(p, n=2), ["line3", "line4"])

    def test_truncates_long_lines(self):
        p = self.tmp / "progress.md"
        p.write_text("x" * 500 + "\n", encoding="utf-8")
        tail = orr.progress_tail(p, n=1)
        self.assertEqual(len(tail[0]), orr._PROGRESS_LINE_MAXLEN)
        self.assertTrue(tail[0].endswith("…"))


class TestRenderBoardState(unittest.TestCase):
    """The ledger github-projects reads for the checkout: `items_source`, else
    `board-items.json` beside the checkout's `project.json`."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-board-"))
        self.config_dir = self.tmp / ".harness"
        self.config_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def config(self, **cfg):
        (self.config_dir / "project.json").write_text(json.dumps(cfg), encoding="utf-8")

    def test_no_checkout_or_no_config_returns_empty(self):
        self.assertEqual(orr.render_board_state(None, "widgets"), [])
        self.assertEqual(orr.render_board_state(str(self.tmp), "widgets"), [])

    def test_matches_via_the_ledger_beside_project_json(self):
        self.config()
        (self.config_dir / "board-items.json").write_text(
            '{"items": [{"id": "f-widgets", "type": "feature", "title": "Widgets thing", "status": "Todo"},'
            ' {"id": "f-other", "type": "feature", "title": "Unrelated", "status": "Done"}]}',
            encoding="utf-8",
        )
        result = orr.render_board_state(str(self.tmp), "widgets")
        self.assertEqual(len(result), 1)
        self.assertIn("Widgets thing", result[0])

    def test_items_source_takes_precedence(self):
        items_path = self.tmp / "elsewhere-board-items.json"
        items_path.write_text(
            '{"items": [{"id": "f-widgets", "type": "feature", "title": "Widgets thing", "status": "Todo"}]}',
            encoding="utf-8",
        )
        self.config(items_source=str(items_path))
        # A decoy beside project.json proves the default is not used.
        (self.config_dir / "board-items.json").write_text('{"items": []}', encoding="utf-8")
        self.assertEqual(len(orr.render_board_state(str(self.tmp), "widgets")), 1)

    def test_the_path_rule_is_the_board_plugins_own(self):
        spec = importlib.util.spec_from_file_location(
            "orient_render_project_sync", _ROOT / "src" / "github-projects" / "scripts" / "project_sync.py")
        sync = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = sync
        spec.loader.exec_module(sync)
        cfg_path = self.config_dir / "project.json"
        for cfg in ({}, {"items_source": str(self.tmp / "ledger.json")}):
            with self.subTest(cfg=cfg):
                self.config(**cfg)
                self.assertEqual(orr._board_items_path(str(self.tmp)),
                                 sync._items_path_from_cfg(cfg, str(cfg_path)))

    def test_unparsable_board_items_returns_empty(self):
        self.config()
        (self.config_dir / "board-items.json").write_text("not json", encoding="utf-8")
        self.assertEqual(orr.render_board_state(str(self.tmp), "widgets"), [])


class TestRenderOrientation(unittest.TestCase):

    def render(self, listing, project=None):
        project = project or {"slug": "widgets", "gloss": "A widget project."}
        with mock.patch.object(orr._bridge, "run_list_plans", return_value=listing):
            return orr.render_orientation(project)

    def test_no_plan_list_says_so_in_one_line(self):
        text = self.render((3, []))
        self.assertIn("# widgets", text)
        self.assertIn("A widget project.", text)
        self.assertIn(orr._NO_PLAN_LIST, text)
        self.assertNotIn("## Plans", text)

    def test_an_empty_listing_says_so_in_one_line(self):
        text = self.render((0, []))
        self.assertIn(orr._NO_PLANS, text)
        for heading in ("## Plans", "## Recent progress", "## Queued plans", "## Board state"):
            self.assertNotIn(heading, text)

    def test_a_match_with_no_checkout_is_listed_by_its_slug(self):
        with mock.patch.object(orr._bridge, "run_list_plans", return_value=(0, [])) as listed:
            orr.render_orientation({"slug": "widgets"})
        listed.assert_called_once_with(project="widgets")


# A stand-in for agentm's tracker.py: `show` prints a tracker's fields from
# $STUB_TRACKER_STATE, a JSON map of path to {"status", "importance"}.
_STUB_TRACKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
state = json.loads(Path(os.environ["STUB_TRACKER_STATE"]).read_text(encoding="utf-8"))
if argv[0] == "show" and argv[1] in state:
    print(json.dumps(state[argv[1]]))
    sys.exit(0)
sys.stderr.write("tracker: no such tracker\n")
sys.exit(2)
'''


class _AgentmProject:
    """A vault project `widgets` with a repo checkout, a stub tracker.py under
    $AGENTM_SCRIPTS_DIR, and a render that patches the bridge's brief and plan
    list to answer for it (PLAN-tracker-commands task 8)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-agentm-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = self.tmp / "agentm" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "tracker.py").write_text(_STUB_TRACKER, encoding="utf-8")
        home = self.tmp / "home"
        home.mkdir()
        self.state = self.tmp / "tracker-state.json"
        self.state.write_text("{}", encoding="utf-8")
        for patcher in (
            mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(scripts),
                                         "STUB_TRACKER_STATE": str(self.state)}),
            mock.patch.object(Path, "home", return_value=home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.project = self.tmp / "vault" / "projects" / "widgets"
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.rows = []

    def task(self, name, status, importance=None, progress=None):
        directory = self.project / "tasks" / name
        directory.mkdir(parents=True)
        (directory / "plan.md").write_text(_PLAN_TEXT, encoding="utf-8")
        tracker = directory / "tracker.md"
        tracker.write_text("tracker\n", encoding="utf-8")
        state = json.loads(self.state.read_text(encoding="utf-8"))
        state[str(tracker)] = {"status": status, "importance": importance}
        self.state.write_text(json.dumps(state), encoding="utf-8")
        log = directory / "progress.md"
        if progress:
            log.write_text(progress, encoding="utf-8")
        self.rows.append((str(directory / "plan.md"), str(log), str(tracker)))

    def flat(self, slug, status, progress=None):
        # A repo with no vault: agentm keeps its plans repo-local, each with a
        # tracker beside it (ruling 8).
        harness = self.repo / ".harness"
        harness.mkdir(parents=True, exist_ok=True)
        plan = harness / f"PLAN-{slug}.md"
        plan.write_text(_PLAN_TEXT, encoding="utf-8")
        tracker = harness / f"tracker-{slug}.md"
        tracker.write_text("tracker\n", encoding="utf-8")
        state = json.loads(self.state.read_text(encoding="utf-8"))
        state[str(tracker)] = {"status": status, "importance": None}
        self.state.write_text(json.dumps(state), encoding="utf-8")
        log = harness / f"progress-{slug}.md"
        if progress:
            log.write_text(progress, encoding="utf-8")
        self.rows.append((str(plan), str(log), str(tracker)))

    def render(self, brief=(3, ""), **overrides):
        project = {"slug": "widgets", "gloss": "A widget project.",
                   "root_path": str(self.repo), "vault_project_path": str(self.project),
                   **overrides}
        with mock.patch.object(orr._bridge, "run_project_brief", return_value=brief) as brief_call, \
                mock.patch.object(orr._bridge, "run_list_plans", return_value=(0, list(self.rows))):
            return orr.render_orientation(project), brief_call

    @staticmethod
    def section(text, heading):
        start = text.index(heading)
        end = text.find("\n## ", start + 1)
        return text[start:] if end == -1 else text[start:end]


class TestOrientationBrief(_AgentmProject, unittest.TestCase):

    def test_the_brief_leads_when_agentm_has_one(self):
        self.task("042-build-the-brief", "active", importance=5)
        text, brief_call = self.render(brief=(0, "widgets · 042-build-the-brief · active\nNext: Step 2"))
        brief_call.assert_called_once_with(str(self.repo))
        self.assertEqual(text.splitlines()[:5],
                         ["# widgets", "A widget project.", "", "## Brief",
                          "widgets · 042-build-the-brief · active"])
        self.assertLess(text.index("## Brief"), text.index("## Plans"))

    def test_no_brief_when_agentm_has_none(self):
        self.task("042-build-the-brief", "active")
        text, _brief_call = self.render(brief=(3, ""))
        self.assertNotIn("## Brief", text)
        self.assertIn("## Plans", text)

    def test_no_brief_and_no_call_without_a_root_path(self):
        text, brief_call = self.render(brief=(0, "never shown"), root_path=None)
        brief_call.assert_not_called()
        self.assertNotIn("## Brief", text)


class TestOrientationPlansThroughAgentm(_AgentmProject, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.task("041-close-the-old-thing", "done",
                  progress="2026-09-01 /work — the old thing closed\n")
        self.task("042-build-the-brief", "active", importance=3,
                  progress="2026-09-14 /work — completed step 1\n")
        self.task("043-ship-it", "parked", importance=8)
        self.task("044-next-thing", "queued")
        self.flat("alpha", "active", progress="2026-09-13 /work — alpha moved\n")
        self.flat("old", "done", progress="2026-08-01 /work — the old flat plan closed\n")

    def test_in_flight_first_by_importance_then_name_finished_as_a_count(self):
        text, _ = self.render()
        plans = self.section(text, "## Plans")
        headers = [line for line in plans.splitlines()[1:] if line and not line.startswith("  ")]
        self.assertEqual(headers, ["043-ship-it [parked]", "042-build-the-brief [active]",
                                   "PLAN-alpha.md [active]", "2 finished plans"])
        self.assertIn("  ✅ First task", plans)

    def test_no_progress_tail_for_a_finished_plan(self):
        text, _ = self.render()
        progress = self.section(text, "## Recent progress")
        self.assertIn("042-build-the-brief:", progress)
        self.assertIn("PLAN-alpha.md:", progress)
        self.assertNotIn("the old thing closed", progress)
        self.assertNotIn("the old flat plan closed", progress)

    def test_queued_plans_by_their_tracker(self):
        text, _ = self.render()
        queued = self.section(text, "## Queued plans")
        self.assertEqual(queued.splitlines()[1:], ["- 044-next-thing"])
        self.assertNotIn("044-next-thing", self.section(text, "## Plans"))

    def test_nothing_is_globbed_beyond_the_rows_agentm_lists(self):
        (self.repo / ".harness" / "PLAN-unlisted.md").write_text(_PLAN_TEXT, encoding="utf-8")
        (self.repo / ".harness" / "progress-unlisted.md").write_text("unlisted\n", encoding="utf-8")
        text, _ = self.render()
        self.assertNotIn("PLAN-unlisted.md", text)
        self.assertNotIn("progress-unlisted.md", text)


class TestInTheScratchVault(unittest.TestCase):
    """The real bridge, against the scratch vault's stub agentm: a project
    bound to a repo and a project named by slug alone each list their task
    with its tracker status, and `--note` lands in the desk."""

    def setUp(self):
        self.sp = nhf.ScratchProject()
        self.addCleanup(self.sp.cleanup)
        home = self.sp.root / "home"
        home.mkdir()
        for patcher in (
            mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(self.sp.agentm)}),
            mock.patch.object(Path, "home", return_value=home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.by_repo = {"slug": "demo", "root_path": str(self.sp.repo),
                        "vault_project_path": str(self.sp.project)}
        self.by_slug = {"slug": "demo", "vault_project_path": str(self.sp.project)}

    def test_both_kinds_of_project_list_the_task_with_its_tracker_status(self):
        for project in (self.by_repo, self.by_slug):
            with self.subTest(root=project.get("root_path")):
                text = orr.render_orientation(project)
                self.assertIn(f"{nhf.TASK} [active]", text)
        self.assertEqual(nhf.harness_dirs(self.sp.root), [])

    def test_the_base_render_writes_nothing(self):
        orr.render_orientation(self.by_repo)
        self.assertEqual(list(self.sp.desk.iterdir()), [])

    def test_the_note_lands_in_the_desk_for_both(self):
        for project in (self.by_repo, self.by_slug):
            with self.subTest(root=project.get("root_path")):
                note = orr.write_orientation_note(project, "hello orientation")
                self.assertEqual(note, self.sp.desk / "orientation-note.md")
                self.assertEqual(note.read_text(encoding="utf-8"), "hello orientation")
        self.assertEqual(nhf.harness_dirs(self.sp.root), [])

    def test_the_note_overwrites(self):
        orr.write_orientation_note(self.by_repo, "first version")
        note = orr.write_orientation_note(self.by_repo, "second version")
        self.assertEqual(note.read_text(encoding="utf-8"), "second version")

    def test_a_desk_not_yet_made_is_not_created(self):
        shutil.rmtree(self.sp.desk)
        self.assertIsNone(orr.write_orientation_note(self.by_repo, "text"))
        self.assertFalse(self.sp.desk.exists())

    def test_an_agentm_without_resolve_by_slug_still_lists_the_task(self):
        sp = nhf.ScratchProject(resolve_by_slug=False)
        self.addCleanup(sp.cleanup)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(sp.agentm)}):
            text = orr.render_orientation({"slug": "demo"})
        self.assertIn(nhf.TASK, text)


class TestNoHome(unittest.TestCase):

    def test_no_home_means_no_write(self):
        with nhf.ScratchProject(no_home=True) as sp, \
                mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(sp.agentm)}):
            self.assertIsNone(orr.write_orientation_note(
                {"slug": "demo", "root_path": str(sp.repo)}, "text"))
            self.assertEqual(list(sp.desk.iterdir()), [])

    def test_no_slug_and_no_checkout_means_no_write(self):
        self.assertIsNone(orr.write_orientation_note({}, "text"))


if __name__ == "__main__":
    unittest.main()
