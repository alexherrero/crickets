#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/queue_status.py (queue-status-lite bridge).

The bridge runs agentm's `queue_status_lite.py` from the cwd and passes its
output through; crickets enumerates no plans itself (agentm-vault part 15, task
101 retired the standalone `.harness/` fallback). Every test is hermetic: the
reader is a planted stub, found through `$AGENTM_SCRIPTS_DIR` with `HOME`
isolated, so nothing here depends on a real agentm clone (CI runs with none).
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
_SRC = _ROOT / "src" / "development-lifecycle" / "scripts" / "queue_status.py"


def _load():
    spec = importlib.util.spec_from_file_location("queue_status", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["queue_status"] = m
    spec.loader.exec_module(m)
    return m


qs = _load()

# What agentm's reader prints for a project that keeps tasks.
_TASK_DASHBOARD = (
    "Active plans in /v/projects/demo:\n\n"
    "  042-build-the-brief  [active]\n"
    "                       last: 2026-09-22 /work — completed step 1\n"
)


class _Env(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="qs-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "home").mkdir()

    def use(self, scripts_dir):
        patcher = mock.patch.dict(os.environ, {
            "HOME": str(self.tmp / "home"), "AGENTM_SCRIPTS_DIR": str(scripts_dir or "")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def stub(self, body: str) -> Path:
        d = self.tmp / "agentm"
        d.mkdir(exist_ok=True)
        (d / "queue_status_lite.py").write_text(body, encoding="utf-8")
        return d


class TestDelegation(_Env):
    def test_passthrough_verbatim(self):
        reader = self.stub(f"import sys\nsys.stdout.write({_TASK_DASHBOARD!r})\n") / "queue_status_lite.py"
        self.assertEqual(qs.run(reader=reader), (0, _TASK_DASHBOARD, ""))

    def test_the_reader_gets_no_directory_argument(self):
        # agentm resolves the project from the cwd; crickets names no directory.
        reader = self.stub("import sys\nprint(repr(sys.argv[1:]))\n") / "queue_status_lite.py"
        rc, out, _ = qs.run(reader=reader)
        self.assertEqual((rc, out.strip()), (0, "[]"))

    def test_nonzero_exit_propagates(self):
        reader = self.stub("import sys\nsys.stderr.write('boom')\nsys.exit(3)\n") / "queue_status_lite.py"
        self.assertEqual(qs.run(reader=reader), (3, "", "boom"))

    def test_no_reader_is_one_line_and_exit_0(self):
        self.assertEqual(qs.run(reader=None), (0, qs.NO_AGENTM, ""))


class TestLocateReader(_Env):
    def test_found_through_agentm_scripts_dir(self):
        d = self.stub("print('x')\n")
        self.use(d)
        self.assertEqual(qs.locate_reader(), (d / "queue_status_lite.py").resolve())

    def test_none_without_agentm(self):
        self.use(None)
        self.assertIsNone(qs.locate_reader())


class TestMainCLI(_Env):
    def test_main_passes_the_dashboard_through(self):
        self.use(self.stub(f"import sys\nsys.stdout.write({_TASK_DASHBOARD!r})\n"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = qs.main(["queue_status.py"])
        self.assertEqual((rc, buf.getvalue()), (0, _TASK_DASHBOARD))

    def test_main_without_agentm_says_so(self):
        self.use(None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = qs.main(["queue_status.py"])
        self.assertEqual((rc, buf.getvalue()), (0, qs.NO_AGENTM))

    def test_harness_dir_is_gone(self):
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            qs.main(["queue_status.py", "--harness-dir", "/x"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
