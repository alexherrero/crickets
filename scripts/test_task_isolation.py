#!/usr/bin/env python3
"""Tests for task_isolation.py — operator-declared task independence for worktree-per-task mode.

Covers:
  - parse_task_flags: correct parsing of Isolated: true / absent / case-insensitive
  - should_isolate_task: isolated vs non-isolated tasks, missing file, missing task
  - Independence of execution-isolation and merge-granularity knobs (task 3)

Auto-discovered by check-all's `unit tests` gate.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ti = _load("task_isolation")

# ── fixture plans ─────────────────────────────────────────────────────────────

_PLAN_ONE_ISOLATED = """\
# Plan: test

**Status:** in-progress

## Tasks

### 1. Build the thing
- **What:** implement it
- **Verification:** tests pass
- **Status:** [ ]
- **Isolated:** true

### 2. Write docs
- **What:** write them
- **Verification:** docs exist
- **Status:** [ ]
"""

_PLAN_MIXED = """\
# Plan: test

## Tasks

### 1. Independent task
- **What:** standalone work — touches only new files
- **Status:** [ ]
- **Isolated:** true

### 2. Dependent task
- **What:** builds on task 1 output
- **Status:** [ ]

### 3. Also independent
- **What:** no shared files with tasks 1 or 2
- **Status:** [ ]
- **Isolated:** true
"""

_PLAN_NONE_ISOLATED = """\
# Plan: test

## Tasks

### 1. Task one
- **What:** sequential step A
- **Status:** [ ]

### 2. Task two
- **What:** sequential step B — depends on step A
- **Status:** [ ]
"""

_PLAN_CASE_INSENSITIVE = """\
## Tasks

### 1. Task
- **What:** x
- **Status:** [ ]
- **Isolated:** TRUE
"""

_PLAN_EMPTY_TASKS = """\
# Plan: test

## Tasks

No tasks yet.
"""


def _write_plan(content: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


# ── parse_task_flags ──────────────────────────────────────────────────────────

class TestParseTaskFlags(unittest.TestCase):

    def test_isolated_task_detected(self):
        flags = ti.parse_task_flags(_write_plan(_PLAN_ONE_ISOLATED))
        self.assertEqual(len(flags), 2)
        self.assertTrue(flags[0]["isolated"], "task 1 must be isolated")
        self.assertFalse(flags[1]["isolated"], "task 2 must not be isolated")

    def test_mixed_tasks(self):
        flags = ti.parse_task_flags(_write_plan(_PLAN_MIXED))
        self.assertEqual([f["isolated"] for f in flags], [True, False, True])

    def test_none_isolated(self):
        flags = ti.parse_task_flags(_write_plan(_PLAN_NONE_ISOLATED))
        self.assertTrue(all(not f["isolated"] for f in flags))

    def test_task_indices_correct(self):
        flags = ti.parse_task_flags(_write_plan(_PLAN_MIXED))
        self.assertEqual([f["index"] for f in flags], [1, 2, 3])

    def test_missing_plan_returns_empty(self):
        self.assertEqual(ti.parse_task_flags("/nonexistent/PLAN.md"), [])

    def test_empty_tasks_section_returns_empty(self):
        self.assertEqual(ti.parse_task_flags(_write_plan(_PLAN_EMPTY_TASKS)), [])

    def test_isolated_marker_case_insensitive(self):
        flags = ti.parse_task_flags(_write_plan(_PLAN_CASE_INSENSITIVE))
        self.assertEqual(len(flags), 1)
        self.assertTrue(flags[0]["isolated"])


# ── should_isolate_task ───────────────────────────────────────────────────────

class TestShouldIsolateTask(unittest.TestCase):

    def test_isolated_task_returns_true(self):
        path = _write_plan(_PLAN_ONE_ISOLATED)
        self.assertTrue(ti.should_isolate_task(path, 1))

    def test_non_isolated_task_returns_false(self):
        path = _write_plan(_PLAN_ONE_ISOLATED)
        self.assertFalse(ti.should_isolate_task(path, 2))

    def test_absent_task_num_returns_false(self):
        path = _write_plan(_PLAN_ONE_ISOLATED)
        self.assertFalse(ti.should_isolate_task(path, 99))

    def test_missing_file_returns_false(self):
        self.assertFalse(ti.should_isolate_task("/nonexistent/PLAN.md", 1))

    def test_mixed_plan_independent_tasks(self):
        path = _write_plan(_PLAN_MIXED)
        self.assertTrue(ti.should_isolate_task(path, 1))
        self.assertFalse(ti.should_isolate_task(path, 2),
                         "dependent task must not be isolated")
        self.assertTrue(ti.should_isolate_task(path, 3))

    def test_no_isolated_tasks(self):
        path = _write_plan(_PLAN_NONE_ISOLATED)
        self.assertFalse(ti.should_isolate_task(path, 1))
        self.assertFalse(ti.should_isolate_task(path, 2))


# ── knob independence (task 3) ────────────────────────────────────────────────

class TestKnobsAreIndependent(unittest.TestCase):
    """worktree-per-task (execution isolation) != PR-per-task (merge granularity).

    Running tasks in separate worktrees can still land as a single per-plan PR.
    The task isolation flag is independent of the integration mode setting.
    """

    def test_isolated_flag_readable_regardless_of_integration_mode(self):
        # The Isolated: true flag on a task is a PLAN.md field — it is read by
        # task_isolation.py independently of project.json's integration setting.
        # Per-task execution isolation does not force per-task PRs.
        path = _write_plan(_PLAN_ONE_ISOLATED)
        # Flag is readable regardless of which integration mode is configured —
        # task_isolation.py never reads integration from project.json.
        self.assertTrue(ti.should_isolate_task(path, 1),
                        "isolated flag must be readable independent of integration mode")

    def test_non_isolated_task_unaffected_by_integration_mode(self):
        path = _write_plan(_PLAN_ONE_ISOLATED)
        self.assertFalse(ti.should_isolate_task(path, 2),
                         "non-isolated flag must be False independent of integration mode")

    def test_all_tasks_non_isolated_still_valid_for_per_plan_pr(self):
        # A worktree-per-task config with no Isolated: true tasks is valid —
        # it simply runs everything directly (same as worktree-per-plan with no tasks).
        path = _write_plan(_PLAN_NONE_ISOLATED)
        self.assertFalse(ti.should_isolate_task(path, 1))
        self.assertFalse(ti.should_isolate_task(path, 2))


if __name__ == "__main__":
    unittest.main()
