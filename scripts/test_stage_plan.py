"""Tests for src/development-lifecycle/scripts/stage_plan.py (V5-10 sibling #1;
task-only since crickets task 101).

Staging is a queued task: `path` prints the task's own `plan.md`, and `activate`
moves its `queued` tracker to `active`. Where the task lives is agentm's answer,
through `resolve_plan`; a planted stub stands in for agentm's process seam
(`resolver=<stub path>`), answering `state-path plan`, `progress` and `tracker`
one path per call, and a stub tracker.py under $AGENTM_SCRIPTS_DIR answers the
tracker reads and moves. The layouts: a numbered task (`tasks/042-build-the-brief/`),
and the repo-local flat pair agentm still serves a repo with no vault, which
staging refuses because it needs the task layout. No fixture creates a vault
harness directory. No test reaches a real seam except the real-bridge class,
which runs against a scratch vault and skips when no agentm checkout is found.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
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
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


sp = _load("stage_plan")


def _write_stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _seam_stub(path: Path, plan, progress, tracker, *, exit_code: int = 0) -> Path:
    """A stub process_seam.py that answers `state-path {plan|progress|tracker}`
    one path per call, the way agentm's seam does. `tracker=None` makes the
    tracker call an invalid choice, as it is for a seam from before the tracker;
    a non-zero `exit_code` makes every call exit with it."""
    answers = {"plan": str(plan), "progress": str(progress)}
    if tracker is not None:
        answers["tracker"] = str(tracker)
    return _write_stub(path, (
        "import sys\n"
        f"answers = {answers!r}\n"
        f"if {exit_code}:\n"
        "    sys.stderr.write('[process_seam] refused\\n')\n"
        f"    sys.exit({exit_code})\n"
        "which = sys.argv[2]\n"
        "if which not in answers:\n"
        "    sys.stderr.write('invalid choice: ' + which + '\\n')\n"
        "    sys.exit(2)\n"
        "print(answers[which])\n"
        "sys.exit(0)\n"
    ))


# A stand-in for agentm's tracker.py: `show` prints a tracker's status from
# $STUB_TRACKER_STATE (a JSON map of path to status), and `transition` follows
# the real table, or refuses when $STUB_TRACKER_REFUSE is set.
_STUB_TRACKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
state_file = Path(os.environ["STUB_TRACKER_STATE"])
state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
if argv[0] == "show":
    if argv[1] not in state:
        sys.stderr.write("tracker: no such tracker\n")
        sys.exit(2)
    print(json.dumps({"status": state[argv[1]]}))
    sys.exit(0)
if argv[0] == "transition":
    current, to = state[argv[1]], argv[argv.index("--to") + 1]
    moves = {"queued": ("active", "dropped"), "active": ("parked", "done", "dropped"),
             "parked": ("active", "dropped")}
    if os.environ.get("STUB_TRACKER_REFUSE") or to not in moves.get(current, ()):
        sys.stderr.write(f"tracker: a `{current}` tracker cannot become `{to}`\n")
        sys.exit(1)
    state[argv[1]] = to
    state_file.write_text(json.dumps(state), encoding="utf-8")
    print(f"{argv[1]}: {current} -> {to}")
    sys.exit(0)
sys.exit(2)
'''


class _Layouts:
    """A scratch vault project holding the numbered task `042-build-the-brief`,
    a repo with its repo-local `.harness/`, a stub tracker.py under
    $AGENTM_SCRIPTS_DIR, and a Path.home() with no agentm clone under it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-layouts-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = self.tmp / "agentm" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "tracker.py").write_text(_STUB_TRACKER, encoding="utf-8")
        home = self.tmp / "home"
        home.mkdir()
        self.state = self.tmp / "tracker-state.json"
        for patcher in (
            mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(scripts),
                                         "STUB_TRACKER_STATE": str(self.state),
                                         "STUB_TRACKER_REFUSE": ""}),
            mock.patch.object(Path, "home", return_value=home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        project = self.tmp / "vault" / "projects" / "probe"
        self.task = project / "tasks" / "042-build-the-brief"
        self.task.mkdir(parents=True)
        (self.task / "plan.md").write_text("# Plan: Build the brief\n", encoding="utf-8")
        self.root = self.tmp / "repo"
        self.local = self.root / ".harness"
        self.local.mkdir(parents=True)

    def flat_seam(self) -> Path:
        """agentm's answer for a repo with no vault: its repo-local flat pair."""
        return _seam_stub(self.tmp / "seam-flat.py", self.local / "PLAN-foo.md",
                          self.local / "progress-foo.md", self.local / "tracker-foo.md")

    def task_seam(self, *, exit_code: int = 0) -> Path:
        return _seam_stub(self.tmp / "seam-task.py", self.task / "plan.md",
                          self.task / "progress.md", self.task / "tracker.md",
                          exit_code=exit_code)

    def set_tracker(self, path: Path, status: str) -> None:
        state = json.loads(self.state.read_text(encoding="utf-8")) if self.state.exists() else {}
        state[str(path)] = status
        self.state.write_text(json.dumps(state), encoding="utf-8")
        path.write_text("tracker\n", encoding="utf-8")

    def status_of(self, path: Path) -> str:
        return json.loads(self.state.read_text(encoding="utf-8"))[str(path)]

    def ship(self, rel: str) -> None:
        shipped = self.root / rel
        shipped.parent.mkdir(parents=True, exist_ok=True)
        shipped.write_text("shipped\n", encoding="utf-8")


class TestPath(_Layouts, unittest.TestCase):

    def test_a_task_stages_as_its_own_plan(self):
        rc, out, err = sp.staging_path("042-build-the-brief", str(self.root),
                                       resolver=self.task_seam())
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(Path(out.strip()), self.task / "plan.md")

    def test_the_singleton_is_refused_by_both_verbs(self):
        for verb in (sp.staging_path, sp.activate):
            with self.subTest(verb=verb.__name__):
                rc, out, err = verb("PLAN.md", str(self.root), resolver=self.flat_seam())
                self.assertEqual((rc, out), (2, ""))
                self.assertIn("named plan", err)

    def test_a_flat_answer_is_refused_by_both_verbs_and_nothing_is_written(self):
        (self.local / "PLAN-foo.md").write_text("# Plan: foo\n", encoding="utf-8")
        before = sorted(p.name for p in self.local.iterdir())
        for verb in (sp.staging_path, sp.activate):
            with self.subTest(verb=verb.__name__):
                rc, out, err = verb("foo", str(self.root), resolver=self.flat_seam())
                self.assertEqual((rc, out), (2, ""))
                self.assertIn("staging needs the task layout", err)
        self.assertEqual(sorted(p.name for p in self.local.iterdir()), before)
        self.assertFalse((self.local / "queued-plans").exists())

    def test_exit_4_passes_through_both_verbs(self):
        seam = self.task_seam(exit_code=4)
        for verb in (sp.staging_path, sp.activate):
            with self.subTest(verb=verb.__name__):
                rc, out, _err = verb("build-the-brief", str(self.root), resolver=seam)
                self.assertEqual((rc, out), (4, ""))

    def test_no_agentm_is_exit_1_through_both_verbs(self):
        for verb in (sp.staging_path, sp.activate):
            with self.subTest(verb=verb.__name__):
                rc, out, err = verb("foo", str(self.root), resolver=None)
                self.assertEqual((rc, out), (1, ""))
                self.assertIn("through agentm", err)


class TestActivateTask(_Layouts, unittest.TestCase):

    def activate(self):
        return sp.activate("042-build-the-brief", str(self.root), resolver=self.task_seam())

    def test_a_queued_task_activates_by_its_transition(self):
        tracker = self.task / "tracker.md"
        self.set_tracker(tracker, "queued")
        before = (self.task / "plan.md").read_bytes()
        rc, out, err = self.activate()
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), self.task / "plan.md")
        self.assertEqual(self.status_of(tracker), "active")
        self.assertEqual((self.task / "plan.md").read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.task.iterdir()), ["plan.md", "tracker.md"])

    def test_a_task_with_no_tracker_is_refused(self):
        rc, out, err = self.activate()
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("no tracker", err)

    def test_a_task_already_active_is_refused(self):
        tracker = self.task / "tracker.md"
        self.set_tracker(tracker, "active")
        rc, out, err = self.activate()
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("is active", err)
        self.assertEqual(self.status_of(tracker), "active")

    def test_lc6_is_exit_3_and_leaves_the_tracker_queued(self):
        (self.task / "plan.md").write_text(
            "---\nexpected_artifacts: [src/done.py]\n---\n# Plan: Build the brief\n",
            encoding="utf-8")
        self.ship("src/done.py")
        tracker = self.task / "tracker.md"
        self.set_tracker(tracker, "queued")
        rc, out, _err = self.activate()
        self.assertEqual((rc, out), (3, ""))
        self.assertEqual(self.status_of(tracker), "queued")


class TestMainCLI(_Layouts, unittest.TestCase):
    """End-to-end main() over a stub seam found through the bridge's discovery."""

    def setUp(self):
        super().setUp()
        saved = sp.resolve_plan._bridge.find_seam
        self.addCleanup(setattr, sp.resolve_plan._bridge, "find_seam", saved)
        seam = self.task_seam()
        sp.resolve_plan._bridge.find_seam = lambda: seam

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = sp.main(["stage_plan.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_path(self):
        rc, out, err = self._run("path", "042-build-the-brief", "--project-root", str(self.root))
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), str(self.task / "plan.md"))

    def test_main_path_singleton_nonzero(self):
        rc, out, err = self._run("path", "PLAN", "--project-root", str(self.root))
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("named plan", err)

    def test_main_activate(self):
        tracker = self.task / "tracker.md"
        self.set_tracker(tracker, "queued")
        rc, out, err = self._run("activate", "042-build-the-brief", "--project-root", str(self.root))
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), str(self.task / "plan.md"))
        self.assertEqual(self.status_of(tracker), "active")


def _real_agentm_scripts() -> "Path | None":
    """An agentm checkout's scripts dir holding both process_seam.py and
    tracker.py: $AGENTM_SCRIPTS_DIR, else the conventional clone; else None."""
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    dirs = [Path(env_dir)] if env_dir else []
    dirs.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    for d in dirs:
        if (d / "process_seam.py").is_file() and (d / "tracker.py").is_file():
            return d.resolve()
    return None


REAL_AGENTM = _real_agentm_scripts()


@unittest.skipIf(REAL_AGENTM is None, "no agentm checkout with process_seam.py and tracker.py")
class TestRealBridge(unittest.TestCase):
    """Activation through agentm's real seam and tracker.py, in a scratch vault:
    a queued `tasks/042-build-the-brief/`. Nothing points at the live vault or
    the operator's home."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sp-real-bridge-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        vault = self.tmp / "vault"
        self.task = vault / "projects" / "probe" / "tasks" / "042-build-the-brief"
        self.task.mkdir(parents=True)
        self.repo = self.tmp / "repo"
        (self.repo / ".harness").mkdir(parents=True)
        (self.repo / ".harness" / "project.json").write_text(
            json.dumps({"vault_project": "probe"}), encoding="utf-8")
        home = self.tmp / "home"
        (home / ".claude").mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {
            "HOME": str(home),
            "AGENTM_INSTALL_PREFIX": str(home / ".claude"),
            "MEMORY_ROOT": str(vault),
            "AGENTM_SCRIPTS_DIR": str(REAL_AGENTM),
            "OBSIDIAN_VAULT_SCRIPTS": str(_ROOT / "src" / "obsidian-vault" / "scripts"),
            "XDG_CACHE_HOME": str(self.tmp / "cache"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MEMORY_VAULT_PATH", None)
        self.seam = REAL_AGENTM / "process_seam.py"

    def run_tracker(self, *args: str) -> str:
        code, out, err = sp.resolve_plan._bridge.run_tracker(list(args))
        self.assertEqual(code, 0, err)
        return out

    def open_queued(self, path: Path, task: str) -> None:
        self.run_tracker("new", "--title", "Probe", "--project", "probe", "--task", task,
                         "--objective", "It activates.", "--next", "Step 1: activate",
                         "--out", str(path))

    def status_of(self, path: Path) -> str:
        return json.loads(self.run_tracker("show", str(path)))["status"]

    def test_a_queued_numbered_task(self):
        (self.task / "plan.md").write_text("# Plan: Build the brief\n\n**Status:** planning\n",
                                           encoding="utf-8")
        tracker = self.task / "tracker.md"
        self.open_queued(tracker, "042-build-the-brief")
        rc, out, err = sp.activate("042-build-the-brief", str(self.repo), resolver=self.seam)
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(out.strip()), self.task / "plan.md")
        self.assertEqual(self.status_of(tracker), "active")


if __name__ == "__main__":
    unittest.main()
