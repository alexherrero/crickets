#!/usr/bin/env python3
"""No plugin writer can create the retired harness directory (agentm-vault part 15).

Each case runs one writer against a `ScratchProject` — a vault project in the
task layout with a stub agentm — and then asserts `harness_dirs()` is empty.
The cases grow with task 100's steps: every writer a step moves onto a home
agentm names gains a case here.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import no_harness_fixture as nhf  # noqa: E402


class TheFixture(unittest.TestCase):
    """The fixture itself is the task layout, and builds no harness directory."""

    def test_builds_the_task_layout(self):
        with nhf.ScratchProject() as sp:
            self.assertTrue((sp.task / "plan.md").is_file())
            self.assertTrue((sp.task / "tracker.md").is_file())
            self.assertTrue(sp.designs.is_dir())
            self.assertTrue(sp.desk.is_dir())
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def test_harness_dirs_finds_a_planted_one(self):
        with nhf.ScratchProject() as sp:
            planted = sp.project / nhf.HARNESS_DIRNAME
            planted.mkdir()
            self.assertEqual(nhf.harness_dirs(sp.root), [planted])

    def test_stub_names_the_homes(self):
        with nhf.ScratchProject() as sp:
            for kind, want in (("tasks", sp.project / "tasks"), ("designs", sp.designs),
                               ("desk", sp.desk)):
                r = subprocess.run([sys.executable, str(sp.agentm / "process_seam.py"),
                                    "project-path", kind, "--cwd", str(sp.repo)],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(Path(r.stdout.strip()), want)

    def test_stub_lists_the_task(self):
        with nhf.ScratchProject() as sp:
            r = subprocess.run([sys.executable, str(sp.agentm / "harness_memory.py"),
                                "list-plans", "--project-root", str(sp.repo)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual([Path(line) for line in r.stdout.split()], [sp.plan])

    def test_stub_without_a_home_exits_1(self):
        with nhf.ScratchProject(no_home=True) as sp:
            r = subprocess.run([sys.executable, str(sp.agentm / "process_seam.py"),
                                "project-path", "desk"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()
