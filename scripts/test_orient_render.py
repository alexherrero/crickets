#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/orient_render.py — the ORIENT
renderer for `/open` / `/orient` (PLAN-open-a-project-by-name tasks 3 + 5).

Composes queue_status.py's existing plan-file discovery + Status: extraction
(imported, not re-derived) and stage_plan.py's `_QUEUED_DIR` constant. Every
test builds a throwaway fixture `_harness/` tree — no dependency on a real
agentm install or a real vault.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

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


_PLAN_TEXT = """---
touches_architecture: false
---

# Plan: Widgets

**Status:** in-progress

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


class TestRenderPlanStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-plan-status-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_plans_returns_empty(self):
        self.assertEqual(orr.render_plan_status(self.tmp), [])

    def test_singleton_plan_renders_status_and_checklist(self):
        (self.tmp / "PLAN.md").write_text(_PLAN_TEXT, encoding="utf-8")
        blocks = orr.render_plan_status(self.tmp)
        self.assertEqual(len(blocks), 1)
        self.assertIn("PLAN.md [in-progress]", blocks[0])
        self.assertIn("✅ First task", blocks[0])
        self.assertIn("⬜ Second task", blocks[0])


class TestRenderQueuedPlans(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-queued-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_queued_dir_returns_empty(self):
        self.assertEqual(orr.render_queued_plans(self.tmp), [])

    def test_lists_queued_plan_files(self):
        qd = self.tmp / "queued-plans"
        qd.mkdir()
        (qd / "PLAN-b.md").write_text("b", encoding="utf-8")
        (qd / "PLAN-a.md").write_text("a", encoding="utf-8")
        self.assertEqual(orr.render_queued_plans(self.tmp), ["PLAN-a.md", "PLAN-b.md"])


class TestRenderBoardState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-board-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_project_json_or_board_items_returns_empty(self):
        self.assertEqual(orr.render_board_state(self.tmp, "widgets"), [])

    def test_matches_via_harness_local_board_items_fallback(self):
        (self.tmp / "board-items.json").write_text(
            '{"items": [{"id": "f-widgets", "type": "feature", "title": "Widgets thing", "status": "Todo"},'
            ' {"id": "f-other", "type": "feature", "title": "Unrelated", "status": "Done"}]}',
            encoding="utf-8",
        )
        result = orr.render_board_state(self.tmp, "widgets")
        self.assertEqual(len(result), 1)
        self.assertIn("Widgets thing", result[0])

    def test_project_json_items_source_takes_precedence(self):
        items_path = self.tmp / "elsewhere-board-items.json"
        items_path.write_text(
            '{"items": [{"id": "f-widgets", "type": "feature", "title": "Widgets thing", "status": "Todo"}]}',
            encoding="utf-8",
        )
        (self.tmp / "project.json").write_text(
            json.dumps({"items_source": str(items_path)}), encoding="utf-8",
        )
        # Plant a decoy at the harness-local fallback path to prove it's not used.
        (self.tmp / "board-items.json").write_text('{"items": []}', encoding="utf-8")
        result = orr.render_board_state(self.tmp, "widgets")
        self.assertEqual(len(result), 1)

    def test_unparsable_board_items_returns_empty(self):
        (self.tmp / "board-items.json").write_text("not json", encoding="utf-8")
        self.assertEqual(orr.render_board_state(self.tmp, "widgets"), [])


class TestResolveHarnessDir(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-resolve-harness-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_neither_present_returns_none(self):
        self.assertIsNone(orr.resolve_harness_dir({"slug": "widgets"}))

    def test_prefers_vault_project_path_over_root_path(self):
        vault_harness = self.tmp / "vault-proj" / "_harness"
        vault_harness.mkdir(parents=True)
        local_harness = self.tmp / "local-proj" / ".harness"
        local_harness.mkdir(parents=True)
        project = {
            "vault_project_path": str(self.tmp / "vault-proj"),
            "root_path": str(self.tmp / "local-proj"),
        }
        self.assertEqual(orr.resolve_harness_dir(project), vault_harness)

    def test_falls_back_to_local_root_path(self):
        local_harness = self.tmp / "local-proj" / ".harness"
        local_harness.mkdir(parents=True)
        project = {"root_path": str(self.tmp / "local-proj")}
        self.assertEqual(orr.resolve_harness_dir(project), local_harness)


class TestRenderOrientation(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-full-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_harness_dir_still_renders_gracefully(self):
        text = orr.render_orientation({"slug": "widgets", "gloss": "A widget project."})
        self.assertIn("# widgets", text)
        self.assertIn("A widget project.", text)
        self.assertIn("no _harness/ found", text)

    def test_full_render_includes_every_present_section(self):
        harness = self.tmp / "proj" / "_harness"
        harness.mkdir(parents=True)
        (harness / "PLAN.md").write_text(_PLAN_TEXT, encoding="utf-8")
        (harness / "progress.md").write_text("2026-01-01 did a thing\n", encoding="utf-8")
        qd = harness / "queued-plans"
        qd.mkdir()
        (qd / "PLAN-next.md").write_text("next", encoding="utf-8")
        (harness / "board-items.json").write_text(
            '{"items": [{"id": "f-widgets", "type": "feature", "title": "Widgets", "status": "Todo"}]}',
            encoding="utf-8",
        )
        project = {"slug": "widgets", "gloss": "A widget project.", "vault_project_path": str(self.tmp / "proj")}
        text = orr.render_orientation(project)
        self.assertIn("## Plans", text)
        self.assertIn("## Recent progress", text)
        self.assertIn("## Queued plans", text)
        self.assertIn("## Board state", text)

    def test_missing_sections_are_omitted_not_stubbed(self):
        harness = self.tmp / "proj" / "_harness"
        harness.mkdir(parents=True)
        # No PLAN.md, no progress.md, no queued-plans/, no board-items.json.
        project = {"slug": "widgets", "vault_project_path": str(self.tmp / "proj")}
        text = orr.render_orientation(project)
        self.assertNotIn("## Plans", text)
        self.assertNotIn("## Recent progress", text)
        self.assertNotIn("## Queued plans", text)
        self.assertNotIn("## Board state", text)


class TestWriteOrientationNote(unittest.TestCase):
    """Task 5 (goal-6 pointer-note flag) verification."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orient-note-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_base_render_never_writes_to_disk(self):
        harness = self.tmp / "proj" / "_harness"
        harness.mkdir(parents=True)
        project = {"slug": "widgets", "vault_project_path": str(self.tmp / "proj")}
        orr.render_orientation(project)
        self.assertFalse((harness / orr._ORIENTATION_NOTE_NAME).exists())

    def test_writes_note_file(self):
        harness = self.tmp / "_harness"
        harness.mkdir()
        note_path = orr.write_orientation_note(harness, "hello orientation")
        self.assertEqual(note_path, harness / "orientation-note.md")
        self.assertEqual(note_path.read_text(encoding="utf-8"), "hello orientation")

    def test_idempotent_overwrite_not_append(self):
        harness = self.tmp / "_harness"
        harness.mkdir()
        orr.write_orientation_note(harness, "first version")
        note_path = orr.write_orientation_note(harness, "second version")
        content = note_path.read_text(encoding="utf-8")
        self.assertEqual(content, "second version")
        self.assertNotIn("first version", content)

    def test_creates_harness_dir_if_absent(self):
        harness = self.tmp / "not-yet-created" / "_harness"
        self.assertFalse(harness.exists())
        note_path = orr.write_orientation_note(harness, "text")
        self.assertTrue(note_path.is_file())


if __name__ == "__main__":
    unittest.main()
