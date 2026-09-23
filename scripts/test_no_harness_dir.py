#!/usr/bin/env python3
"""No plugin writer can create the retired harness directory (agentm-vault part 15).

Each case runs one writer against a `ScratchProject` — a vault project in the
task layout with a stub agentm — and then asserts `harness_dirs()` is empty.
The cases grow with task 100's steps: every writer a step moves onto a home
agentm names gains a case here.
"""
from __future__ import annotations

import json
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


class Writers(unittest.TestCase):
    """One case per writer a step moved onto a home agentm names."""

    def run_py(self, sp, script: Path, args, stdin: str = "") -> subprocess.CompletedProcess:
        env = sp.env()
        env["HOME"] = str(sp.root / "home")
        return subprocess.run([sys.executable, str(script), *args], input=stdin,
                              capture_output=True, text=True, env=env)

    def test_the_evidence_tracker(self):
        """code-review (step 3): a Read, a blocked flip in a task's plan.md, a reset."""
        hook = HERE.parent / "src" / "code-review" / "hooks" / "evidence-tracker" / "evidence_tracker.py"
        with nhf.ScratchProject() as sp:
            root = ["--project-root", str(sp.repo)]
            read = json.dumps({"tool_name": "Read", "tool_input": {"file_path": str(sp.plan)}})
            flip = json.dumps({"tool_name": "Edit", "tool_input": {
                "file_path": str(sp.plan), "old_string": "- **Status:** [ ]",
                "new_string": "- **Status:** [x]"}})
            self.assertEqual(self.run_py(sp, hook, ["--mode", "check", *root], read).returncode, 0)
            self.assertEqual(self.run_py(sp, hook, ["--mode", "check", *root], flip).returncode, 2)
            self.assertEqual(self.run_py(sp, hook, ["--mode", "reset", *root]).returncode, 0)
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def test_depth_maintenance(self):
        """github-projects (step 4): a dry-run cycle over agentm's plan list."""
        script = next((HERE.parent / "src").glob("*-projects/scripts/depth_maintain.py"))
        with nhf.ScratchProject() as sp:
            items = sp.desk / "board-items.json"
            items.write_text(json.dumps({"items": [
                {"id": "v5", "type": "version", "title": "V5", "about": "x"},
                {"id": "build-the-brief", "type": "feature", "parent": "v5",
                 "title": "Brief", "goal": "g", "why_matters": "w"}]}), encoding="utf-8")
            cfg = sp.repo / ".harness" / "project.json"
            cfg.write_text(json.dumps({
                "vault_project": "demo", "items_source": str(items),
                "github": {"owner": "o", "number": 1, "repo": "o/r", "url": "u"}}),
                encoding="utf-8")
            r = self.run_py(sp, script, ["--config", str(cfg), "--project-root", str(sp.repo),
                                         "--dry-run"])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(nhf.harness_dirs(sp.root), [])


if __name__ == "__main__":
    unittest.main()
