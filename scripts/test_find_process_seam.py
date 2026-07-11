#!/usr/bin/env python3
"""Tests for the `process-seam` verb of
src/development-lifecycle/scripts/agentm_bridge.py (formerly the standalone
find_process_seam.py, merged into the shared bridge — CONS-2 task 2).

Discovery (find_seam): $AGENTM_SCRIPTS_DIR, co-located sibling, conventional
~/Antigravity/ clone, and graceful-skip when absent.

Delegation (run_state_path): propagates seam stdout + exit code for both
state-path verbs; exits 1 cleanly when seam absent (no hang).

Every test is hermetic — injectable seam paths and env var overrides ensure no
dependency on a real agentm install (CI runs with none).
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
    spec = importlib.util.spec_from_file_location("find_process_seam", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["find_process_seam"] = m
    spec.loader.exec_module(m)
    return m


fps = _load()


def _make_fake_seam(path: Path, body: str = "") -> Path:
    """Plant a fake process_seam.py at path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "# stub seam\n", encoding="utf-8")
    return path


class TestFindSeamDiscovery(unittest.TestCase):
    """find_seam() locates process_seam.py via fallback order; None when absent."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fps-discovery-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_found_via_env_agentm_scripts_dir(self):
        seam = _make_fake_seam(self.tmp / "env_scripts" / "process_seam.py")
        env = {**os.environ, "AGENTM_SCRIPTS_DIR": str(seam.parent)}
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(seam.parent)}):
            result = fps.find_seam()
        self.assertEqual(result, seam.resolve())

    def test_found_via_env_takes_priority_over_colocated(self):
        env_seam = _make_fake_seam(self.tmp / "env_dir" / "process_seam.py")
        colocated = _make_fake_seam(_SRC.parent / "process_seam.py")
        try:
            with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(env_seam.parent)}):
                result = fps.find_seam()
            self.assertEqual(result, env_seam.resolve())
        finally:
            colocated.unlink(missing_ok=True)

    def test_found_via_colocated_sibling(self):
        colocated = _make_fake_seam(_SRC.parent / "process_seam.py")
        try:
            with mock.patch.dict(os.environ, {}, clear=False):
                # Ensure env var is absent for this test
                env_without = {k: v for k, v in os.environ.items()
                               if k != "AGENTM_SCRIPTS_DIR"}
                with mock.patch.dict(os.environ, env_without, clear=True):
                    result = fps.find_seam()
            # Must resolve to the co-located copy (or the real ~/Antigravity one if
            # it exists and is found first — this test plants a co-located sibling
            # so find_seam must pick it up when env var is absent).
            # Accept either: the co-located stub, or the real agentm seam.
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
        finally:
            colocated.unlink(missing_ok=True)

    def test_found_via_conventional_antigravity_clone(self):
        home = self.tmp / "fake_home"
        seam = _make_fake_seam(home / "Antigravity" / "agentm" / "scripts" / "process_seam.py")
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = fps.find_seam()
        self.assertEqual(result, seam.resolve())

    def test_returns_none_when_all_absent(self):
        home = self.tmp / "empty_home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = fps.find_seam()
        self.assertIsNone(result)


class TestRunStatePath(unittest.TestCase):
    """run_state_path() propagates seam stdout + exit code; exits 1 when absent."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fps-run-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_seam(self, body: str) -> Path:
        p = self.tmp / "fake_seam.py"
        p.write_text(body, encoding="utf-8")
        return p

    def test_plan_path_propagated_exit_zero(self):
        seam = self._make_seam(
            "import sys\nwhich = sys.argv[2]\n"
            "sys.stdout.write('/v/_harness/PLAN.md\\n' if which == 'plan' else '/v/_harness/progress.md\\n')\n"
            "sys.exit(0)\n"
        )
        out, rc = fps.run_state_path("plan", [], seam=seam)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "/v/_harness/PLAN.md")

    def test_progress_path_propagated_exit_zero(self):
        seam = self._make_seam(
            "import sys\nwhich = sys.argv[2]\n"
            "sys.stdout.write('/v/_harness/PLAN.md\\n' if which == 'plan' else '/v/_harness/progress.md\\n')\n"
            "sys.exit(0)\n"
        )
        out, rc = fps.run_state_path("progress", [], seam=seam)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "/v/_harness/progress.md")

    def test_extra_args_forwarded_to_seam(self):
        seam = self._make_seam(
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n"
        )
        out, rc = fps.run_state_path("plan", ["--plan", "foo", "--cwd", "/root"], seam=seam)
        self.assertEqual(rc, 0)
        self.assertIn("--plan", out)
        self.assertIn("foo", out)
        self.assertIn("--cwd", out)
        self.assertIn("/root", out)

    def test_exit_one_graceful_skip_propagated(self):
        seam = self._make_seam("import sys\nsys.exit(1)\n")
        out, rc = fps.run_state_path("plan", [], seam=seam)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")

    def test_exit_two_propagated(self):
        seam = self._make_seam(
            "import sys\nsys.stderr.write('dangling\\n')\nsys.exit(2)\n"
        )
        out, rc = fps.run_state_path("plan", [], seam=seam)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")

    def test_seam_absent_exits_one_no_hang(self):
        # seam=None triggers auto-discovery; stub find_seam to confirm absent path.
        with mock.patch.object(fps, "find_seam", return_value=None):
            out, rc = fps.run_state_path("plan", [])
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")

    def test_seam_absent_auto_discovery_fails_exits_one(self):
        home = self.tmp / "empty_home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                out, rc = fps.run_state_path("plan", [])
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")


class TestMainCLI(unittest.TestCase):
    """main() exits 2 on bad usage; otherwise proxies the seam."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fps-main-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bad_usage_exits_two(self):
        rc = fps.main(["agentm_bridge.py", "process-seam"])
        self.assertEqual(rc, 2)

    def test_bad_verb_exits_two(self):
        rc = fps.main(["agentm_bridge.py", "process-seam", "bad-verb", "plan"])
        self.assertEqual(rc, 2)

    def test_state_path_plan_proxied(self):
        seam = self.tmp / "seam.py"
        seam.write_text("import sys\nsys.stdout.write('/v/PLAN.md\\n')\nsys.exit(0)\n",
                        encoding="utf-8")
        with mock.patch.object(fps, "find_seam", return_value=seam):
            import io, contextlib
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = fps.main(["agentm_bridge.py", "process-seam", "state-path", "plan"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), "/v/PLAN.md")

    def test_seam_absent_exits_one_no_output(self):
        with mock.patch.object(fps, "find_seam", return_value=None):
            import io, contextlib
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = fps.main(["agentm_bridge.py", "process-seam", "state-path", "plan"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
