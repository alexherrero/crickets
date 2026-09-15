#!/usr/bin/env python3
"""Tests for the `tracker` verb of
src/development-lifecycle/scripts/agentm_bridge.py (PLAN-tracker-commands
task 1).

crickets reaches agentm's tracker.py only through this verb and never renders
or parses tracker text itself, so the verb's whole job is to hand argv over
untouched and give back the exit code, stdout and stderr as they came, plus
exit 3 when there is no tracker.py to run.

The stub classes plant a fake tracker.py under a patched $AGENTM_SCRIPTS_DIR,
with Path.home() pointed at an empty directory so the conventional clone is
never found. The real-bridge class runs the real tracker.py against a scratch
file and is skipped when no agentm checkout is found (CI has none).
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
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "agentm_bridge.py"


def _load():
    spec = importlib.util.spec_from_file_location("agentm_bridge_tracker", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["agentm_bridge_tracker"] = m
    spec.loader.exec_module(m)
    return m


ab = _load()

# Prints its argv as JSON, writes one line to stderr, and exits with
# $STUB_TRACKER_EXIT (default 0).
_STUB_TRACKER = """#!/usr/bin/env python3
import json, os, sys
print(json.dumps(sys.argv[1:], ensure_ascii=False))
sys.stderr.write("stub stderr\\n")
sys.exit(int(os.environ.get("STUB_TRACKER_EXIT", "0")))
"""


class _StubAgentm:
    """A scratch $AGENTM_SCRIPTS_DIR holding a stub tracker.py, and a
    Path.home() with no agentm clone under it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bridge-tracker-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.scripts = self.tmp / "agentm" / "scripts"
        self.scripts.mkdir(parents=True)
        self.stub = self.scripts / "tracker.py"
        self.stub.write_text(_STUB_TRACKER, encoding="utf-8")
        self.home = self.tmp / "home"
        self.home.mkdir()
        for patcher in (
            mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(self.scripts)}),
            mock.patch.object(ab.Path, "home", return_value=self.home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def no_agentm(self):
        """Take the stub away: no $AGENTM_SCRIPTS_DIR, and no clone under home."""
        return mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""})

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ab.main(["agentm_bridge.py", *argv])
        return code, out.getvalue(), err.getvalue()


class TestFindTracker(_StubAgentm, unittest.TestCase):

    def test_found_via_agentm_scripts_dir(self):
        self.assertEqual(ab.find_tracker(), self.stub.resolve())

    def test_found_via_the_conventional_clone(self):
        clone = self.home / "Antigravity" / "agentm" / "scripts" / "tracker.py"
        clone.parent.mkdir(parents=True)
        clone.write_text(_STUB_TRACKER, encoding="utf-8")
        with self.no_agentm():
            self.assertEqual(ab.find_tracker(), clone.resolve())

    def test_none_when_agentm_is_absent(self):
        with self.no_agentm():
            self.assertIsNone(ab.find_tracker())


class TestRunTracker(_StubAgentm, unittest.TestCase):

    def test_argv_passes_through_for_each_subcommand(self):
        calls = {
            "new": ["new", "--title", "Build the brief", "--project", "probe",
                    "--task", "042-build-the-brief", "--objective", "It prints.",
                    "--next", "Step 1: the bridge", "--out", "/v/tracker.md"],
            "show": ["show", "/v/tracker.md"],
            "transition": ["transition", "/v/tracker.md", "--to", "active",
                           "--state", "Step 1 is under way.",
                           "--next", "Step 1: the bridge"],
            "check": ["check", "/v/a/tracker.md", "/v/b/tracker.md"],
        }
        for sub, args in calls.items():
            with self.subTest(subcommand=sub):
                code, out, err = ab.run_tracker(args)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out), args)
                self.assertEqual(err, "stub stderr\n")

    def test_exit_codes_pass_through_with_stderr(self):
        for expected in (0, 1, 2):
            with self.subTest(exit=expected), \
                    mock.patch.dict(os.environ, {"STUB_TRACKER_EXIT": str(expected)}):
                code, out, err = ab.run_tracker(["show", "/v/tracker.md"])
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(out), ["show", "/v/tracker.md"])
                self.assertEqual(err, "stub stderr\n")

    def test_text_outside_ascii_survives_both_ways(self):
        args = ["transition", "/v/tracker.md", "--to", "active",
                "--state", "Step 2 → the resolver — green"]
        code, out, _err = ab.run_tracker(args)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), args)

    def test_an_injected_path_is_the_one_run(self):
        other = self.tmp / "elsewhere" / "tracker.py"
        other.parent.mkdir()
        other.write_text("import sys\nprint('elsewhere')\nsys.exit(0)\n", encoding="utf-8")
        code, out, _err = ab.run_tracker(["show", "/v/tracker.md"], tracker=other)
        self.assertEqual((code, out), (0, "elsewhere\n"))

    def test_exit_3_when_tracker_is_absent(self):
        with self.no_agentm():
            code, out, err = ab.run_tracker(["show", "/v/tracker.md"])
        self.assertEqual((code, out), (3, ""))
        self.assertIn("tracker.py was not found", err)

    def test_exit_3_for_an_injected_path_that_is_gone(self):
        code, out, _err = ab.run_tracker(["show", "/v/tracker.md"],
                                         tracker=self.tmp / "gone" / "tracker.py")
        self.assertEqual((code, out), (3, ""))


class TestTrackerVerb(_StubAgentm, unittest.TestCase):

    def test_registered_in_the_dispatcher(self):
        self.assertIn("tracker", ab._VERBS)

    def test_no_subcommand_is_a_usage_error(self):
        code, out, err = self.main("tracker")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("usage", err)

    def test_an_unknown_subcommand_is_a_usage_error(self):
        code, out, _err = self.main("tracker", "update", "/v/tracker.md")
        self.assertEqual((code, out), (2, ""))

    def test_proxies_stdout_stderr_and_exit_code(self):
        with mock.patch.dict(os.environ, {"STUB_TRACKER_EXIT": "1"}):
            code, out, err = self.main("tracker", "transition", "/v/tracker.md",
                                       "--to", "done")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out), ["transition", "/v/tracker.md", "--to", "done"])
        self.assertEqual(err, "stub stderr\n")

    def test_exit_3_with_a_note_when_agentm_is_absent(self):
        with self.no_agentm():
            code, out, err = self.main("tracker", "show", "/v/tracker.md")
        self.assertEqual((code, out), (3, ""))
        self.assertIn("not found", err)


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
    """A tracker's whole life through the bridge, against the real tracker.py:
    open, show, activate, rewrite under `active`, close. tracker.py is standard
    library only and writes nothing but the file it is handed, a scratch one
    here."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bridge-tracker-real-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = self.tmp / "probe" / "tasks" / "042-build-the-brief" / "tracker.md"
        self.path.parent.mkdir(parents=True)

    def run_ok(self, *args) -> str:
        code, out, err = ab.run_tracker([str(a) for a in args], tracker=REAL_TRACKER)
        self.assertEqual(code, 0, err)
        return out

    def show(self) -> dict:
        return json.loads(self.run_ok("show", self.path))

    def open_tracker(self):
        self.run_ok("new", "--title", "Build the brief", "--project", "probe",
                    "--task", "042-build-the-brief", "--objective", "The brief prints.",
                    "--next", "Step 1: the bridge", "--out", self.path)

    def test_new_show_activate_rewrite_close(self):
        self.open_tracker()
        opened = self.show()
        self.assertEqual((opened["status"], opened["task"]), ("queued", "042-build-the-brief"))
        self.assertEqual(opened["sections"]["Next"], "Step 1: the bridge")

        self.run_ok("transition", self.path, "--to", "active")
        self.assertEqual(self.show()["status"], "active")

        self.run_ok("transition", self.path, "--to", "active",
                    "--state", "The bridge verbs are in.", "--next", "Step 2: the resolver")
        rewritten = self.show()
        self.assertEqual(rewritten["status"], "active")
        self.assertEqual(rewritten["sections"]["State"], "The bridge verbs are in.")
        self.assertEqual(rewritten["sections"]["Next"], "Step 2: the resolver")

        self.run_ok("transition", self.path, "--to", "done", "--outcome", "The brief prints.")
        closed = self.show()
        self.assertEqual(closed["status"], "done")
        self.assertEqual(closed["sections"]["Outcome"], "The brief prints.")
        self.assertIsNotNone(closed["closed"])
        self.assertEqual(ab.run_tracker(["check", str(self.path)], tracker=REAL_TRACKER)[0], 0)

    def test_a_refused_transition_is_exit_1_with_the_reason_on_stderr(self):
        self.open_tracker()
        code, _out, err = ab.run_tracker(
            ["transition", str(self.path), "--to", "done", "--outcome", "early"],
            tracker=REAL_TRACKER)
        self.assertEqual(code, 1)
        self.assertIn("cannot become", err)

    def test_opening_twice_is_refused(self):
        self.open_tracker()
        code, _out, err = ab.run_tracker(
            ["new", "--title", "Again", "--project", "probe", "--objective", "o",
             "--next", "n", "--out", str(self.path)], tracker=REAL_TRACKER)
        self.assertEqual(code, 1)
        self.assertIn("opened once", err)


if __name__ == "__main__":
    unittest.main()
