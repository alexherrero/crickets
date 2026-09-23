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

    def test_the_lifecycle_desk_answer(self):
        """development-lifecycle (task 101 step 5): the desk features.json lives in."""
        script = HERE.parent / "src" / "development-lifecycle" / "scripts" / "project_homes.py"
        with nhf.ScratchProject() as sp:
            r = self.run_py(sp, script, ["home", "desk", "--cwd", str(sp.repo)])
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(r.stdout.strip()), sp.desk)
            self.assertEqual(list(sp.desk.iterdir()), [])
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def test_design_paths(self):
        """design (step 5): the designs home, a confidential design, a parts dir."""
        script = HERE.parent / "src" / "design" / "scripts" / "design_doc.py"
        with nhf.ScratchProject() as sp:
            root = ["--project-root", str(sp.repo)]
            for argv, want in ((["designs-home", *root], sp.designs),
                               (["design-path", "arc", *root], sp.designs / "arc.md"),
                               (["parts-dir", "arc", *root], sp.designs / "arc" / "parts")):
                r = self.run_py(sp, script, argv)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(Path(r.stdout.strip()), want)
            self.assertEqual(sorted(p.name for p in sp.designs.iterdir()), [])
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def test_design_sequence_placement(self):
        """design (step 6): a part placed as a queued task where agentm says."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ds_no_harness", HERE.parent / "src" / "design" / "scripts" / "design_sequence.py")
        ds = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ds)
        with nhf.ScratchProject() as sp:
            task = sp.project / "tasks" / "043-arc-one"

            def run(rel, args):
                if rel.endswith("resolve_plan.py"):
                    return (0, f"{task / 'plan.md'}\t{task / 'progress.md'}\t{task / 'tracker.md'}\n", "")
                return (0, "", "")

            rc, out = ds.place("arc-one", "# Plan: one\n", str(sp.repo), design="arc",
                               part="one", today="2026-09-22", run=run)
            self.assertEqual(rc, 0, out)
            self.assertTrue((task / "plan.md").is_file())
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def _wiki_watch(self):
        import importlib.util
        wiki = HERE.parent / "src" / "wiki" / "scripts"
        sys.path.insert(0, str(wiki))
        self.addCleanup(sys.path.remove, str(wiki))
        spec = importlib.util.spec_from_file_location("ww_cycle_no_harness",
                                                      wiki / "wiki_watch_cycle.py")
        cyc = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cyc  # its dataclasses resolve their module by name
        spec.loader.exec_module(cyc)
        return cyc

    def _cycle(self, cyc, sp):
        return cyc.run_cycle(sp.repo, enabled=True,
                             run_config=cyc.cfg.RunConfig(watch_sources=["."], dispatch_mode="pr"),
                             wiki_target=str(sp.repo / "wiki"), token="abc123",
                             changed_paths=["src/w.py"], gh_available=False, now=1.0)

    def test_a_wiki_watch_cycle(self):
        """wiki (step 7): a cycle keeps its cursors and audit in the project's desk/."""
        import os
        from unittest import mock
        cyc = self._wiki_watch()
        with nhf.ScratchProject() as sp, mock.patch.dict(os.environ, sp.env()):
            report = self._cycle(cyc, sp)
            self.assertFalse(report.skipped, report.reason)
            self.assertEqual(Path(report.state_dir), sp.desk / "wiki-watch")
            self.assertTrue((sp.desk / "wiki-watch" / "audit.log").is_file())
            self.assertFalse((sp.repo / ".harness" / "wiki-watch").exists())
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def test_a_wiki_watch_cycle_without_agentm_skips(self):
        import os
        from unittest import mock
        cyc = self._wiki_watch()
        with nhf.ScratchProject() as sp, mock.patch.dict(
                os.environ, {"AGENTM_SCRIPTS_DIR": "", "HOME": str(sp.root / "home")}):
            report = self._cycle(cyc, sp)
            self.assertTrue(report.skipped)
            self.assertIn("no desk", report.reason)
            self.assertFalse((sp.repo / ".harness" / "wiki-watch").exists())
            self.assertFalse((sp.desk / "wiki-watch").exists())
            self.assertEqual(nhf.harness_dirs(sp.root), [])

    def test_a_handoff_pack_in_the_default(self):
        """tokens (step 8): a pack built into its default lands in the desk."""
        import importlib.util
        import os
        from unittest import mock
        spec = importlib.util.spec_from_file_location(
            "hp_no_harness", HERE.parent / "src" / "tokens" / "scripts" / "handoff_pack.py")
        hp = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = hp  # its dataclasses resolve their module by name
        spec.loader.exec_module(hp)
        with nhf.ScratchProject() as sp, mock.patch.dict(os.environ, sp.env()):
            dest = hp.default_destination("n1-handoff", sp.repo)
            hp.build_handoff_pack([hp.HandoffEntry("t", "p", "T0", "m", "low")], {"a.md": "x"}, dest)
            self.assertTrue((sp.desk / "n1-handoff" / "PROMPTS.md").is_file())
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
