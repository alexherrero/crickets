#!/usr/bin/env python3
"""Tests for the `project-brief` verb of
src/development-lifecycle/scripts/agentm_bridge.py (PLAN-tracker-commands
task 1).

agentm's project_brief.py prints where the bound project and task stand and
exits 0, or prints nothing and exits 3. The verb keeps those two answers and
turns every other outcome into 3 as well (agentm absent, a run that can't
start, any other exit), because /orient leaves the brief out rather than stop.

Every test plants a stub project_brief.py under a patched $AGENTM_SCRIPTS_DIR,
with Path.home() pointed at an empty directory, so no real agentm is reached.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
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
    spec = importlib.util.spec_from_file_location("agentm_bridge_project_brief", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["agentm_bridge_project_brief"] = m
    spec.loader.exec_module(m)
    return m


ab = _load()

# Prints a three-line brief naming the --cwd it was handed and exits 0, or exits
# with $STUB_BRIEF_EXIT. $STUB_BRIEF_SILENT makes an exit 0 print nothing.
_STUB_BRIEF = """#!/usr/bin/env python3
import os, sys
argv = sys.argv[1:]
code = int(os.environ.get("STUB_BRIEF_EXIT", "0"))
if code == 0 and not os.environ.get("STUB_BRIEF_SILENT"):
    cwd = argv[argv.index("--cwd") + 1] if "--cwd" in argv else None
    print("crickets · 042-build-the-brief · active")
    print(f"cwd={cwd}")
    print("Next: Step 2 → the resolver")
sys.exit(code)
"""

BRIEF_FOR_REPO = ["crickets · 042-build-the-brief · active", "cwd=/work/crickets",
                  "Next: Step 2 → the resolver"]


class _StubAgentm:
    """A scratch $AGENTM_SCRIPTS_DIR holding a stub project_brief.py, and a
    Path.home() with no agentm clone under it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bridge-brief-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        scripts = self.tmp / "agentm" / "scripts"
        scripts.mkdir(parents=True)
        self.stub = scripts / "project_brief.py"
        self.stub.write_text(_STUB_BRIEF, encoding="utf-8")
        home = self.tmp / "home"
        home.mkdir()
        for patcher in (
            mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(scripts)}),
            mock.patch.object(ab.Path, "home", return_value=home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def no_agentm(self):
        return mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""})

    def main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ab.main(["agentm_bridge.py", *argv])
        return code, out.getvalue(), err.getvalue()


class TestFindProjectBrief(_StubAgentm, unittest.TestCase):

    def test_found_via_agentm_scripts_dir(self):
        self.assertEqual(ab.find_project_brief(), self.stub.resolve())

    def test_none_when_agentm_is_absent(self):
        with self.no_agentm():
            self.assertIsNone(ab.find_project_brief())


class TestRunProjectBrief(_StubAgentm, unittest.TestCase):

    def test_a_brief_is_exit_0_with_its_text(self):
        code, out = ab.run_project_brief("/work/crickets")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), BRIEF_FOR_REPO)

    def test_no_cwd_passes_no_cwd_flag(self):
        code, out = ab.run_project_brief(None)
        self.assertEqual(code, 0)
        self.assertIn("cwd=None", out.splitlines())

    def test_no_brief_is_exit_3(self):
        with mock.patch.dict(os.environ, {"STUB_BRIEF_EXIT": "3"}):
            self.assertEqual(ab.run_project_brief("/work/crickets"), (3, ""))

    def test_any_other_exit_counts_as_no_brief(self):
        for other in (1, 2):
            with self.subTest(exit=other), \
                    mock.patch.dict(os.environ, {"STUB_BRIEF_EXIT": str(other)}):
                self.assertEqual(ab.run_project_brief("/work/crickets"), (3, ""))

    def test_exit_0_that_printed_nothing_counts_as_no_brief(self):
        with mock.patch.dict(os.environ, {"STUB_BRIEF_SILENT": "1"}):
            self.assertEqual(ab.run_project_brief("/work/crickets"), (3, ""))

    def test_exit_3_when_agentm_is_absent(self):
        with self.no_agentm():
            self.assertEqual(ab.run_project_brief("/work/crickets"), (3, ""))

    def test_exit_3_for_an_injected_path_that_is_gone(self):
        self.assertEqual(
            ab.run_project_brief("/work/crickets", brief=self.tmp / "gone.py"), (3, ""))


class TestProjectBriefVerb(_StubAgentm, unittest.TestCase):

    def test_registered_in_the_dispatcher(self):
        self.assertIn("project-brief", ab._VERBS)

    def test_prints_the_brief_and_exits_0(self):
        code, out, _err = self.main("project-brief", "--cwd", "/work/crickets")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), BRIEF_FOR_REPO)

    def test_cwd_defaults_to_this_process_directory(self):
        code, out, _err = self.main("project-brief")
        self.assertEqual(code, 0)
        self.assertIn(f"cwd={os.getcwd()}", out.splitlines())

    def test_no_brief_prints_nothing_and_exits_3(self):
        with mock.patch.dict(os.environ, {"STUB_BRIEF_EXIT": "3"}):
            code, out, _err = self.main("project-brief", "--cwd", "/work/crickets")
        self.assertEqual((code, out), (3, ""))

    def test_absent_agentm_exits_3(self):
        with self.no_agentm():
            code, out, _err = self.main("project-brief", "--cwd", "/work/crickets")
        self.assertEqual((code, out), (3, ""))

    def test_an_unknown_flag_is_a_usage_error(self):
        code, out, _err = self.main("project-brief", "--project", "crickets")
        self.assertEqual((code, out), (2, ""))


if __name__ == "__main__":
    unittest.main()
