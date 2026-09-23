#!/usr/bin/env python3
"""The evidence tracker gates a task's `plan.md` (agentm-vault part 15, task 100 step 3).

Since the projects migration a plan lives at `tasks/<name>/plan.md` in the
vault. The hook gates a flip there when agentm lists that file among the
project's plans, asks agentm only when an op would flip a checkbox, and fails
closed when agentm is installed but gives no answer. A repo-local
`.harness/PLAN(-slug).md` stays gated by its shape, with or without agentm.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import no_harness_fixture as nhf  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "evidence_tracker_tasks_under_test",
    ROOT / "src" / "code-review" / "hooks" / "evidence-tracker" / "evidence_tracker.py")
et = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = et  # its dataclasses resolve their module by name
_spec.loader.exec_module(et)

UNCHECKED = "- **Status:** [ ]"
CHECKED = "- **Status:** [x]"


def flip(path: Path) -> str:
    return json.dumps({"tool_name": "Edit", "tool_input": {
        "file_path": str(path), "old_string": UNCHECKED, "new_string": CHECKED}})


def read(path: Path) -> str:
    return json.dumps({"tool_name": "Read", "tool_input": {"file_path": str(path)}})


class _Case(unittest.TestCase):
    def setUp(self):
        self.sp = nhf.ScratchProject()
        self.addCleanup(self.sp.cleanup)
        self.home = Path(tempfile.mkdtemp())
        self.agentm(self.sp.agentm)

    def tearDown(self):
        self.assertEqual(nhf.harness_dirs(self.sp.root), [])

    def agentm(self, scripts_dir):
        patcher = mock.patch.dict(os.environ, {
            "HOME": str(self.home), "AGENTM_SCRIPTS_DIR": str(scripts_dir or "")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, event: str) -> "tuple[int, str]":
        err = io.StringIO()
        with redirect_stderr(err):
            rc = et.cli_check(event, self.sp.repo)
        return rc, err.getvalue()

    def plan_like(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.sp.plan.read_text(encoding="utf-8"), encoding="utf-8")
        return path


class ATasksPlan(_Case):
    def test_a_flip_without_evidence_is_blocked(self):
        rc, err = self.check(flip(self.sp.plan))
        self.assertEqual(rc, 2)
        self.assertIn("default-FAIL", err)

    def test_a_flip_after_an_evidence_read_passes(self):
        evidence = self.sp.repo / "tests" / "test_brief.py"
        evidence.parent.mkdir()
        evidence.write_text("assert True\n", encoding="utf-8")
        self.assertEqual(self.check(read(evidence))[0], 0)
        self.assertEqual(self.check(flip(self.sp.plan)), (0, ""))

    def test_the_evidence_none_opt_out(self):
        text = self.sp.plan.read_text(encoding="utf-8").replace(
            "- **Verification:** it exists.",
            "- **Verification:** it exists.\n- **Evidence:** none — a docs-only step")
        self.sp.plan.write_text(text, encoding="utf-8")
        self.assertEqual(self.check(flip(self.sp.plan)), (0, ""))


class NotAPlan(_Case):
    def test_a_plan_md_agentm_does_not_list(self):
        docs = self.plan_like(self.sp.repo / "docs" / "plan.md")
        self.assertEqual(self.check(flip(docs)), (0, ""))

    def test_a_plan_named_file_outside_harness_is_not_gated_by_its_name(self):
        loose = self.plan_like(self.sp.project / "PLAN.md")
        self.assertEqual(self.check(flip(loose)), (0, ""))

    def test_an_ordinary_write_never_asks_agentm(self):
        src = self.sp.repo / "src" / "w.py"
        src.parent.mkdir()
        src.write_text("x = 1\n", encoding="utf-8")
        event = json.dumps({"tool_name": "Write",
                            "tool_input": {"file_path": str(src), "content": "x = 2\n"}})
        with mock.patch("subprocess.run", side_effect=AssertionError("agentm was asked")):
            self.assertEqual(self.check(event), (0, ""))

    def test_a_plan_edit_that_flips_nothing_never_asks_agentm(self):
        event = json.dumps({"tool_name": "Edit", "tool_input": {
            "file_path": str(self.sp.plan), "old_string": "A brief exists.",
            "new_string": "A brief exists, and is short."}})
        with mock.patch("subprocess.run", side_effect=AssertionError("agentm was asked")):
            self.assertEqual(self.check(event), (0, ""))


class RepoPlans(_Case):
    def test_a_repo_plan_is_gated_without_agentm(self):
        self.agentm(None)
        named = self.plan_like(self.sp.repo / ".harness" / "PLAN-foo.md")
        rc, err = self.check(flip(named))
        self.assertEqual(rc, 2)
        self.assertIn("default-FAIL", err)

    def test_a_tasks_plan_is_not_gated_without_agentm(self):
        self.agentm(None)
        self.assertEqual(self.check(flip(self.sp.plan)), (0, ""))


class NoAnswer(_Case):
    def test_a_hanging_agentm_blocks_the_flip(self):
        stub = self.home / "hanging"
        stub.mkdir()
        (stub / "harness_memory.py").write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
        self.agentm(stub)
        with mock.patch.object(et, "_AGENTM_TIMEOUT", 0.5):
            rc, err = self.check(flip(self.sp.plan))
        self.assertEqual(rc, 2)
        self.assertIn("could not confirm", err)

    def test_an_erroring_agentm_blocks_the_flip(self):
        stub = self.home / "erroring"
        stub.mkdir()
        (stub / "harness_memory.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        self.agentm(stub)
        self.assertEqual(self.check(flip(self.sp.plan))[0], 2)


class TheHookScript(_Case):
    """The shipped hook, run as the host runs it: PreToolUse JSON on stdin."""

    def test_the_cli_blocks_a_tasks_flip(self):
        r = subprocess.run(
            [sys.executable, str(ROOT / "src" / "code-review" / "hooks" / "evidence-tracker"
                                 / "evidence_tracker.py"),
             "--mode", "check", "--project-root", str(self.sp.repo)],
            input=flip(self.sp.plan), capture_output=True, text=True, env=dict(os.environ))
        self.assertEqual(r.returncode, 2, r.stderr)


if __name__ == "__main__":
    unittest.main()
