#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/plan_tracker.py
(PLAN-tracker-commands task 3): the one helper the phase commands call to name a
plan, read its status, and open, step and close its tracker.

The helper sends every tracker call through agentm_bridge.run_tracker. The stub
classes point $AGENTM_SCRIPTS_DIR at a stub tracker.py that logs its argv and
keeps each tracker's status and sections in a JSON file, so a test can assert
exactly what the helper composed and walk a tracker through its statuses
without agentm. Path.home() points at an empty directory so the conventional
clone is never found. The real-bridge class runs the real tracker.py against a
scratch task directory and is skipped when no agentm checkout is found (CI has
none).

Three fixture layouts, as agentm places them:
  the singleton       projects/probe/_harness/PLAN.md       + tracker.md
  a flat named pair   projects/probe/_harness/PLAN-foo.md   + tracker-foo.md
  a numbered task     projects/probe/tasks/042-build-the-brief/plan.md + tracker.md
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
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "plan_tracker.py"


def _load():
    spec = importlib.util.spec_from_file_location("plan_tracker", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["plan_tracker"] = m
    spec.loader.exec_module(m)
    return m


pt = _load()

# A stand-in for agentm's tracker.py. It logs argv to $STUB_TRACKER_LOG, keeps
# every tracker it opened in $STUB_TRACKER_STATE, follows the real transition
# table, and refuses a same-status rewrite the way an agentm from before the
# rewrite does when $STUB_TRACKER_OLD is set.
_STUB_TRACKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
TRANSITIONS = {"queued": ("active", "dropped"), "active": ("parked", "done", "dropped"),
               "parked": ("active", "dropped"), "done": (), "dropped": ()}
argv = sys.argv[1:]
with open(os.environ["STUB_TRACKER_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(argv) + "\n")
state_file = Path(os.environ["STUB_TRACKER_STATE"])
state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}

def opt(flag):
    return argv[argv.index(flag) + 1] if flag in argv else None

def save():
    state_file.write_text(json.dumps(state), encoding="utf-8")

if argv[0] == "new":
    out = opt("--out")
    if Path(out).exists():
        sys.stderr.write(f"tracker: {out} exists; a tracker is opened once\n")
        sys.exit(1)
    Path(out).write_text("stub tracker\n", encoding="utf-8")
    state[out] = {"status": "queued", "title": opt("--title"), "project": opt("--project"),
                  "task": opt("--task"), "design": opt("--design"), "issue": opt("--issue"),
                  "sections": {"Objective": opt("--objective"), "State": "Not started.",
                               "Next": opt("--next"), "Outcome": ""}}
    save()
    print(out)
    sys.exit(0)
if argv[0] == "show":
    if argv[1] not in state:
        sys.stderr.write(f"tracker: {argv[1]}: no such tracker\n")
        sys.exit(2)
    print(json.dumps(state[argv[1]]))
    sys.exit(0)
if argv[0] == "transition":
    t, to = state[argv[1]], opt("--to")
    if to == t["status"]:
        if to in ("done", "dropped") or os.environ.get("STUB_TRACKER_OLD"):
            sys.stderr.write(f"tracker: a `{to}` tracker cannot become `{to}`\n")
            sys.exit(1)
    elif to not in TRANSITIONS[t["status"]]:
        sys.stderr.write(f"tracker: a `{t['status']}` tracker cannot become `{to}`\n")
        sys.exit(1)
    if to in ("done", "dropped") and not (opt("--outcome") or t["sections"]["Outcome"]):
        sys.stderr.write(f"tracker: closing a tracker as `{to}` writes its Outcome\n")
        sys.exit(1)
    t["status"] = to
    for flag, section in (("--state", "State"), ("--next", "Next"), ("--outcome", "Outcome")):
        if opt(flag) is not None:
            t["sections"][section] = opt(flag)
    save()
    print(f"{argv[1]}: -> {to}")
    sys.exit(0)
sys.exit(0 if argv[0] == "check" else 2)
'''

BULLET_PLAN = """---
parent_design_doc: wiki/designs/agentm-vault.md
touches_architecture: true
---

# Plan: Build the brief

**Status:** planning
**Created:** 2026-09-14
**Brief:** The brief prints at session start.

## Goal

A session opens with where its task stands.

## Steps

### 1. The bridge
- **What:** the verbs.
- **Status:** [x]

### 2. The resolver
- **What:** the third field.
- **Status:** [ ]

### 3. The helper
- **Status:** [ ]
"""

HEADING_PLAN = """# Plan: Build the brief

**Status:** in-progress
**Brief:** The brief prints at session start.

## Tasks

### 1. The bridge — Status: [x]
### 2. Re-run the resolver — Status: [ ]
### 3. The helper — Status: [ ]
"""


class _Vault:
    """A scratch projects space holding the three layouts, a stub tracker.py
    under $AGENTM_SCRIPTS_DIR, and a repo root with no project.json."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="plan-tracker-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = self.tmp / "agentm" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "tracker.py").write_text(_STUB_TRACKER, encoding="utf-8")
        home = self.tmp / "home"
        home.mkdir()
        self.state = self.tmp / "tracker-state.json"
        self.log = self.tmp / "tracker-calls.jsonl"
        for patcher in (
            mock.patch.dict(os.environ, {
                "AGENTM_SCRIPTS_DIR": str(scripts), "STUB_TRACKER_STATE": str(self.state),
                "STUB_TRACKER_LOG": str(self.log), "STUB_TRACKER_OLD": ""}),
            mock.patch.object(Path, "home", return_value=home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

        project = self.tmp / "vault" / "projects" / "probe"
        harness = project / "_harness"
        harness.mkdir(parents=True)
        task = project / "tasks" / "042-build-the-brief"
        task.mkdir(parents=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.layouts = {
            "singleton": (harness / "PLAN.md", harness / "tracker.md"),
            "flat": (harness / "PLAN-foo.md", harness / "tracker-foo.md"),
            "task": (task / "plan.md", task / "tracker.md"),
        }
        for plan, _tracker in self.layouts.values():
            plan.write_text(BULLET_PLAN, encoding="utf-8")

    def calls(self) -> "list[list[str]]":
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def verbs(self) -> "list[str]":
        return [call[0] for call in self.calls()]

    def tracker(self, path: Path) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))[str(path)]

    def seed(self, path: Path, status: str, outcome: str = "") -> None:
        state = json.loads(self.state.read_text(encoding="utf-8")) if self.state.exists() else {}
        state[str(path)] = {"status": status, "title": "Seeded",
                            "sections": {"Objective": "o", "State": "s", "Next": "n",
                                         "Outcome": outcome}}
        self.state.write_text(json.dumps(state), encoding="utf-8")
        path.write_text("seeded tracker\n", encoding="utf-8")

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pt.main(list(argv))
        return code, out.getvalue(), err.getvalue()


class TestName(_Vault, unittest.TestCase):

    def test_each_layout(self):
        self.assertEqual(pt.plan_name(self.layouts["task"][0]), "042-build-the-brief")
        self.assertEqual(pt.plan_name(self.layouts["flat"][0]), "foo")
        self.assertEqual(pt.plan_name(self.layouts["singleton"][0]), "")

    def test_the_cli_prints_nothing_for_the_singleton(self):
        self.assertEqual(self.main("name", "--plan", str(self.layouts["singleton"][0])),
                         (0, "", ""))
        self.assertEqual(self.main("name", "--plan", str(self.layouts["task"][0])),
                         (0, "042-build-the-brief\n", ""))


class TestOpen(_Vault, unittest.TestCase):

    def open(self, layout: str, **kwargs):
        plan, tracker = self.layouts[layout]
        return pt.open_tracker(plan, str(tracker), root=self.repo, **kwargs)

    def new_call(self) -> "list[str]":
        return [call for call in self.calls() if call[0] == "new"][-1]

    def arg(self, flag: str) -> str:
        call = self.new_call()
        return call[call.index(flag) + 1]

    def test_composes_every_field_for_a_numbered_task(self):
        code, _message = self.open("task", issue=260)
        self.assertEqual(code, 0)
        _plan, tracker = self.layouts["task"]
        self.assertEqual(self.new_call(), [
            "new", "--title", "Build the brief", "--project", "probe",
            "--objective", "A session opens with where its task stands.",
            "--next", "Step 2: The resolver",
            "--task", "042-build-the-brief",
            "--design", "wiki/designs/agentm-vault.md",
            "--issue", "260",
            "--out", str(tracker)])
        self.assertEqual(self.tracker(tracker)["status"], "queued")

    def test_a_flat_pair_is_named_by_its_slug(self):
        self.assertEqual(self.open("flat")[0], 0)
        self.assertEqual((self.arg("--task"), self.arg("--project")), ("foo", "probe"))

    def test_the_singleton_names_no_task(self):
        self.assertEqual(self.open("singleton")[0], 0)
        self.assertEqual(self.arg("--project"), "probe")
        self.assertNotIn("--task", self.new_call())

    def test_the_project_comes_from_vault_project_first(self):
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness" / "project.json").write_text(
            json.dumps({"vault_project": "crickets"}), encoding="utf-8")
        self.open("task")
        self.assertEqual(self.arg("--project"), "crickets")

    def test_the_objective_falls_back_to_the_brief_then_to_the_title(self):
        plan, tracker = self.layouts["flat"]
        plan.write_text(HEADING_PLAN, encoding="utf-8")
        pt.open_tracker(plan, str(tracker), root=self.repo)
        self.assertEqual(self.arg("--objective"), "The brief prints at session start.")

        plan, tracker = self.layouts["task"]
        plan.write_text("# Plan: Build the brief\n\n**Status:** planning\n", encoding="utf-8")
        pt.open_tracker(plan, str(tracker), root=self.repo)
        self.assertEqual(self.arg("--objective"), "Build the brief")

    def test_next_reads_a_step_written_as_a_heading_suffix(self):
        plan, tracker = self.layouts["task"]
        plan.write_text(HEADING_PLAN, encoding="utf-8")
        pt.open_tracker(plan, str(tracker), root=self.repo)
        self.assertEqual(self.arg("--next"), "Step 2: Re-run the resolver")
        self.assertNotIn("--design", self.new_call())

    def test_leaves_an_open_tracker_alone(self):
        _plan, tracker = self.layouts["task"]
        self.seed(tracker, "active")
        code, message = self.open("task")
        self.assertEqual(code, 0)
        self.assertIn("already open", message)
        self.assertNotIn("new", self.verbs())

    def test_a_final_tracker_means_the_plan_runs_without_one(self):
        for status in ("done", "dropped"):
            with self.subTest(status=status):
                _plan, tracker = self.layouts["flat"]
                self.seed(tracker, status, outcome="closed")
                self.assertEqual(self.open("flat")[0], 3)
                self.assertNotIn("new", self.verbs())

    def test_an_empty_tracker_path_is_exit_3(self):
        plan, _tracker = self.layouts["task"]
        self.assertEqual(pt.open_tracker(plan, "", root=self.repo)[0], 3)
        self.assertEqual(self.calls(), [])

    def test_no_tracker_py_is_exit_3(self):
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}):
            self.assertEqual(self.open("task")[0], 3)


class TestStatus(_Vault, unittest.TestCase):

    def test_the_tracker_comes_first(self):
        plan, tracker = self.layouts["task"]
        self.seed(tracker, "active")
        self.assertEqual(pt.plan_status(plan, str(tracker)), ("active", "tracker"))

    def test_the_status_line_comes_second_in_the_five_statuses(self):
        plan, tracker = self.layouts["flat"]
        for line, expected in (("planning", "queued"), ("in-progress", "active"),
                               ("done", "done"), ("done (2026-09-13)", "done"),
                               ("Parked", "parked"), ("dropped", "dropped"),
                               ("Blocked on review", "blocked on review")):
            with self.subTest(line=line):
                plan.write_text(f"# Plan: x\n\n**Status:** {line}\n", encoding="utf-8")
                self.assertEqual(pt.plan_status(plan, str(tracker)), (expected, "status-line"))

    def test_none_when_there_is_neither(self):
        plan, tracker = self.layouts["singleton"]
        plan.write_text("# Plan: x\n\n### 1. a\n- **Status:** [ ]\n", encoding="utf-8")
        self.assertEqual(pt.plan_status(plan, str(tracker)), ("none", "none"))

    def test_an_empty_tracker_path_reads_the_status_line(self):
        plan, _tracker = self.layouts["task"]
        self.assertEqual(pt.plan_status(plan, ""), ("queued", "status-line"))

    def test_the_cli_prints_status_and_source(self):
        plan, tracker = self.layouts["task"]
        self.seed(tracker, "done", outcome="shipped")
        self.assertEqual(self.main("status", "--plan", str(plan), "--tracker", str(tracker)),
                         (0, "done\ttracker\n", ""))


class TestStep(_Vault, unittest.TestCase):

    def step(self, layout: str, state: str = "Step 2 is under way.",
             next_steps: str = "Step 2: The resolver"):
        plan, tracker = self.layouts[layout]
        return pt.step(plan, str(tracker), state=state, next_steps=next_steps, root=self.repo)

    def test_opens_then_activates_a_missing_tracker(self):
        self.assertEqual(self.step("task")[0], 0)
        _plan, tracker = self.layouts["task"]
        self.assertEqual(self.verbs(), ["new", "show", "transition"])
        t = self.tracker(tracker)
        self.assertEqual((t["status"], t["sections"]["State"]), ("active", "Step 2 is under way."))

    def test_activates_a_parked_tracker(self):
        _plan, tracker = self.layouts["flat"]
        self.seed(tracker, "parked")
        self.assertEqual(self.step("flat")[0], 0)
        self.assertEqual(self.tracker(tracker)["status"], "active")

    def test_rewrites_an_active_tracker_in_place(self):
        _plan, tracker = self.layouts["task"]
        self.seed(tracker, "active")
        self.assertEqual(self.step("task", "Step 3 is under way.", "Step 3: The helper")[0], 0)
        self.assertEqual(self.calls()[-1], ["transition", str(tracker), "--to", "active",
                                            "--state", "Step 3 is under way.",
                                            "--next", "Step 3: The helper"])
        t = self.tracker(tracker)
        self.assertEqual((t["status"], t["sections"]["Next"]), ("active", "Step 3: The helper"))

    def test_refuses_a_final_tracker_and_leaves_the_plan_alone(self):
        plan, tracker = self.layouts["task"]
        self.seed(tracker, "done", outcome="shipped")
        before = plan.read_bytes()
        self.assertEqual(self.step("task")[0], 1)
        self.assertNotIn("transition", self.verbs())
        self.assertEqual(plan.read_bytes(), before)

    def test_an_agentm_before_the_rewrite_is_exit_3_not_1(self):
        _plan, tracker = self.layouts["task"]
        self.seed(tracker, "active")
        with mock.patch.dict(os.environ, {"STUB_TRACKER_OLD": "1"}):
            code, message = self.step("task")
        self.assertEqual(code, 3)
        self.assertIn("predates", message)

    def test_the_status_line_follows_to_in_progress(self):
        plan, _tracker = self.layouts["task"]
        self.step("task")
        self.assertIn("**Status:** in-progress\n", plan.read_text(encoding="utf-8"))

    def test_with_no_tracker_support_the_line_is_still_set(self):
        plan, _tracker = self.layouts["task"]
        code, _message = pt.step(plan, "", state="s", next_steps="n", root=self.repo)
        self.assertEqual(code, 3)
        self.assertIn("**Status:** in-progress\n", plan.read_text(encoding="utf-8"))


class TestClose(_Vault, unittest.TestCase):

    def test_moves_active_to_done_with_the_outcome(self):
        plan, tracker = self.layouts["task"]
        self.seed(tracker, "active")
        self.assertEqual(pt.close(plan, str(tracker), outcome="The brief prints.",
                                  root=self.repo)[0], 0)
        t = self.tracker(tracker)
        self.assertEqual((t["status"], t["sections"]["Outcome"]), ("done", "The brief prints."))
        self.assertIn("**Status:** done\n", plan.read_text(encoding="utf-8"))

    def test_a_queued_tracker_passes_through_active(self):
        plan, tracker = self.layouts["flat"]
        self.seed(tracker, "queued")
        self.assertEqual(pt.close(plan, str(tracker), outcome="o", state="s", next_steps="n",
                                  root=self.repo)[0], 0)
        transitions = [call for call in self.calls() if call[0] == "transition"]
        self.assertEqual(transitions, [
            ["transition", str(tracker), "--to", "active"],
            ["transition", str(tracker), "--to", "done", "--outcome", "o",
             "--state", "s", "--next", "n"]])

    def test_a_done_tracker_is_left_as_it_is(self):
        plan, tracker = self.layouts["task"]
        self.seed(tracker, "done", outcome="shipped")
        self.assertEqual(pt.close(plan, str(tracker), outcome="again", root=self.repo)[0], 0)
        self.assertNotIn("transition", self.verbs())
        self.assertEqual(self.tracker(tracker)["sections"]["Outcome"], "shipped")

    def test_a_dropped_tracker_is_refused(self):
        plan, tracker = self.layouts["task"]
        self.seed(tracker, "dropped", outcome="withdrawn")
        self.assertEqual(pt.close(plan, str(tracker), outcome="o", root=self.repo)[0], 1)


class TestStatusLineMirror(_Vault, unittest.TestCase):

    def test_only_the_status_line_changes(self):
        plan, _tracker = self.layouts["task"]
        before = plan.read_bytes()
        self.assertTrue(pt.mirror_status_line(plan, "active"))
        self.assertEqual(plan.read_bytes(), before.replace(
            b"**Status:** planning\n", b"**Status:** in-progress\n", 1))

    def test_windows_line_endings_survive(self):
        plan, _tracker = self.layouts["flat"]
        plan.write_bytes(BULLET_PLAN.replace("\n", "\r\n").encode("utf-8"))
        before = plan.read_bytes()
        self.assertTrue(pt.mirror_status_line(plan, "done"))
        self.assertEqual(plan.read_bytes(), before.replace(
            b"**Status:** planning\r\n", b"**Status:** done\r\n", 1))

    def test_adds_no_line_to_a_plan_without_one(self):
        plan, _tracker = self.layouts["task"]
        plan.write_text("# Plan: x\n\n## Steps\n\n### 1. a\n- **Status:** [ ]\n", encoding="utf-8")
        before = plan.read_bytes()
        self.assertFalse(pt.mirror_status_line(plan, "active"))
        self.assertEqual(plan.read_bytes(), before)

    def test_each_tracker_status_maps_to_its_word(self):
        plan, _tracker = self.layouts["task"]
        for status, word in (("queued", "planning"), ("active", "in-progress"), ("done", "done")):
            with self.subTest(status=status):
                pt.mirror_status_line(plan, status)
                self.assertIn(f"**Status:** {word}\n", plan.read_text(encoding="utf-8"))

    def test_a_step_bullet_is_never_taken_for_the_status_line(self):
        plan, _tracker = self.layouts["task"]
        pt.mirror_status_line(plan, "done")
        self.assertEqual(plan.read_text(encoding="utf-8").count("- **Status:** [ ]"), 2)


class TestCLI(_Vault, unittest.TestCase):

    def test_no_verb_is_a_usage_error(self):
        self.assertEqual(self.main()[0], 2)

    def test_step_without_a_state_is_a_usage_error(self):
        plan, tracker = self.layouts["task"]
        self.assertEqual(self.main("step", "--plan", str(plan), "--tracker", str(tracker),
                                   "--next", "n")[0], 2)

    def test_open_then_status(self):
        plan, tracker = self.layouts["task"]
        code, out, _err = self.main("open", "--plan", str(plan), "--tracker", str(tracker),
                                    "--root", str(self.repo))
        self.assertEqual(code, 0)
        self.assertIn("opened", out)
        self.assertEqual(self.main("status", "--plan", str(plan), "--tracker", str(tracker)),
                         (0, "queued\ttracker\n", ""))

    def test_exit_3_says_why_on_stderr(self):
        plan, _tracker = self.layouts["task"]
        code, out, err = self.main("open", "--plan", str(plan), "--tracker", "",
                                   "--root", str(self.repo))
        self.assertEqual((code, out), (3, ""))
        self.assertIn("no tracker", err)

    def test_a_missing_plan_is_an_io_error(self):
        missing = self.tmp / "vault" / "projects" / "probe" / "tasks" / "ghost"
        code, _out, _err = self.main("open", "--plan", str(missing / "plan.md"),
                                     "--tracker", str(missing / "tracker.md"),
                                     "--root", str(self.repo))
        self.assertEqual(code, 2)


def _real_tracker() -> "Path | None":
    """agentm's own tracker.py in a checkout, or None: $AGENTM_SCRIPTS_DIR,
    else the conventional ~/Antigravity/agentm clone."""
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    dirs = [Path(env_dir)] if env_dir else []
    dirs.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    for d in dirs:
        if (d / "tracker.py").is_file():
            return (d / "tracker.py").resolve()
    return None


REAL_TRACKER = _real_tracker()


@unittest.skipIf(REAL_TRACKER is None, "no agentm checkout with scripts/tracker.py")
class TestRealTracker(unittest.TestCase):
    """open → step → step → close for tasks/042-build-the-brief/, through the
    bridge and the real tracker.py, in a scratch directory. The tracker that
    comes out passes tracker.py check."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="plan-tracker-real-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        task = self.tmp / "vault" / "projects" / "probe" / "tasks" / "042-build-the-brief"
        task.mkdir(parents=True)
        self.plan = task / "plan.md"
        self.plan.write_text(BULLET_PLAN, encoding="utf-8")
        self.tracker = task / "tracker.md"
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        patcher = mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(REAL_TRACKER.parent)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def show(self) -> dict:
        code, out, err = pt._bridge.run_tracker(["show", str(self.tracker)])
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def test_open_step_step_close(self):
        self.assertEqual(pt.open_tracker(self.plan, str(self.tracker), root=self.repo)[0], 0)
        opened = self.show()
        self.assertEqual((opened["status"], opened["project"], opened["task"]),
                         ("queued", "probe", "042-build-the-brief"))
        self.assertEqual(opened["design"], "wiki/designs/agentm-vault.md")
        self.assertEqual(opened["sections"]["Next"], "Step 2: The resolver")

        self.assertEqual(pt.step(self.plan, str(self.tracker), state="Step 2 is under way.",
                                 next_steps="Step 2: The resolver", root=self.repo)[0], 0)
        self.assertEqual(self.show()["status"], "active")
        self.assertEqual(pt.step(self.plan, str(self.tracker),
                                 state="The resolver prints three fields.",
                                 next_steps="Step 3: The helper", root=self.repo)[0], 0)
        stepped = self.show()
        self.assertEqual((stepped["status"], stepped["sections"]["State"]),
                         ("active", "The resolver prints three fields."))

        self.assertEqual(pt.close(self.plan, str(self.tracker), outcome="The brief prints.",
                                  root=self.repo)[0], 0)
        closed = self.show()
        self.assertEqual((closed["status"], closed["sections"]["Outcome"]),
                         ("done", "The brief prints."))
        self.assertEqual(pt._bridge.run_tracker(["check", str(self.tracker)])[0], 0)
        self.assertIn("**Status:** done\n", self.plan.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
