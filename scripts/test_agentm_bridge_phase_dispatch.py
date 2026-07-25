#!/usr/bin/env python3
"""Tests for the `phase-dispatch` verb of
src/development-lifecycle/scripts/agentm_bridge.py (Loose Ends follow-on —
the orphaned bridge caller plan; the sixth verb on the merged CONS-2
dispatcher, per that design's own 2026-07-10 amendment-log re-audit trigger:
a new agentm-facing lookup extends this dispatcher rather than starting a
new bridge file).

`find_harness_memory` discovery mirrors the other verbs' 3-tier cascade
($AGENTM_SCRIPTS_DIR override / co-located sibling / conventional
~/Antigravity/agentm clone). `run_phase_dispatch` proxies harness_memory.py's
own `phase-dispatch` CLI verb stdout + exit code verbatim, and — unlike the
0/1-available/unavailable verbs — always graceful-skips to exit 0 when
harness_memory.py is undiscoverable or the subprocess errors, matching
`phase_dispatch()`'s own documented non-blocking contract (it always returns
0; a phase must never be wedged by orchestration errors).

Every test is hermetic — a planted stub `harness_memory.py`, injectable env
var overrides, and a mocked Path.home() ensure no dependency on a real agentm
install (CI runs with none).
"""
from __future__ import annotations

import importlib.util
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
    spec = importlib.util.spec_from_file_location("agentm_bridge_phase_dispatch", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["agentm_bridge_phase_dispatch"] = m
    spec.loader.exec_module(m)
    return m


ab = _load()


def _make_stub_harness_memory(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


_STUB_DISPATCH_OK = """#!/usr/bin/env python3
import sys
argv = sys.argv[1:]
if argv[:2] == ["phase-dispatch", "post-work"]:
    print("post-work dispatched")
    sys.exit(0)
if argv[:2] == ["phase-dispatch", "post-release"]:
    print("post-release dispatched")
    sys.exit(0)
sys.exit(2)
"""

_STUB_DISPATCH_ECHOES_PROJECT_ROOT = """#!/usr/bin/env python3
import sys
argv = sys.argv[1:]
root = None
if "--project-root" in argv:
    root = argv[argv.index("--project-root") + 1]
print(f"root={root}")
sys.exit(0)
"""


class TestFindHarnessMemoryDiscovery(unittest.TestCase):
    """find_harness_memory() locates harness_memory.py via the 3-tier fallback."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="phase-dispatch-discovery-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_found_via_env_agentm_scripts_dir(self):
        hm = _make_stub_harness_memory(self.tmp / "env_scripts" / "harness_memory.py", _STUB_DISPATCH_OK)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(hm.parent)}):
            result = ab.find_harness_memory()
        self.assertEqual(result, hm.resolve())

    def test_found_via_conventional_clone(self):
        clone_scripts = self.tmp / "Antigravity" / "agentm" / "scripts"
        hm = _make_stub_harness_memory(clone_scripts / "harness_memory.py", _STUB_DISPATCH_OK)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            os.environ.pop("AGENTM_SCRIPTS_DIR", None)
            with mock.patch.object(ab.Path, "home", return_value=self.tmp):
                result = ab.find_harness_memory()
        self.assertEqual(result, hm.resolve())

    def test_absent_returns_none(self):
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            os.environ.pop("AGENTM_SCRIPTS_DIR", None)
            with mock.patch.object(ab.Path, "home", return_value=self.tmp):
                result = ab.find_harness_memory()
        self.assertIsNone(result)


class TestRunPhaseDispatch(unittest.TestCase):
    """run_phase_dispatch() proxies harness_memory.py's `phase-dispatch` verbatim."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="phase-dispatch-run-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_post_work_passes_through_stdout_and_exit_0(self):
        hm = _make_stub_harness_memory(self.tmp / "harness_memory.py", _STUB_DISPATCH_OK)
        out, code = ab.run_phase_dispatch("post-work", harness_memory=hm)
        self.assertEqual(code, 0)
        self.assertIn("post-work dispatched", out)

    def test_post_release_passes_through_stdout_and_exit_0(self):
        hm = _make_stub_harness_memory(self.tmp / "harness_memory.py", _STUB_DISPATCH_OK)
        out, code = ab.run_phase_dispatch("post-release", harness_memory=hm)
        self.assertEqual(code, 0)
        self.assertIn("post-release dispatched", out)

    def test_project_root_forwarded_when_given(self):
        hm = _make_stub_harness_memory(
            self.tmp / "harness_memory.py", _STUB_DISPATCH_ECHOES_PROJECT_ROOT)
        out, code = ab.run_phase_dispatch("post-work", project_root="/tmp/some-repo", harness_memory=hm)
        self.assertEqual(code, 0)
        self.assertEqual(out, "root=/tmp/some-repo")

    def test_project_root_omitted_when_not_given(self):
        hm = _make_stub_harness_memory(
            self.tmp / "harness_memory.py", _STUB_DISPATCH_ECHOES_PROJECT_ROOT)
        out, code = ab.run_phase_dispatch("post-work", harness_memory=hm)
        self.assertEqual(code, 0)
        self.assertEqual(out, "root=None")

    def test_harness_memory_none_graceful_skips_to_zero(self):
        # harness_memory=None triggers a real find_harness_memory() lookup; force absence.
        with mock.patch.object(ab, "find_harness_memory", return_value=None):
            out, code = ab.run_phase_dispatch("post-work", harness_memory=None)
        self.assertEqual((out, code), ("", 0))

    def test_missing_file_graceful_skips_to_zero(self):
        out, code = ab.run_phase_dispatch("post-work", harness_memory=self.tmp / "nope.py")
        self.assertEqual((out, code), ("", 0))


class TestMainPhaseDispatchDispatch(unittest.TestCase):
    """The `phase-dispatch` verb is wired into the top-level dispatcher."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="phase-dispatch-dispatch-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_verb_registered_in_dispatcher(self):
        self.assertIn("phase-dispatch", ab._VERBS)

    def test_no_phase_is_usage_error(self):
        self.assertEqual(ab._main_phase_dispatch([]), 2)

    def test_unknown_phase_is_usage_error(self):
        self.assertEqual(ab._main_phase_dispatch(["not-a-real-phase"]), 2)

    def test_post_work_dispatches_through_main(self):
        hm = _make_stub_harness_memory(self.tmp / "harness_memory.py", _STUB_DISPATCH_OK)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(hm.parent)}):
            code = ab.main(["agentm_bridge.py", "phase-dispatch", "post-work"])
        self.assertEqual(code, 0)

    def test_post_release_dispatches_through_main(self):
        hm = _make_stub_harness_memory(self.tmp / "harness_memory.py", _STUB_DISPATCH_OK)
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(hm.parent)}):
            code = ab.main(["agentm_bridge.py", "phase-dispatch", "post-release"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
