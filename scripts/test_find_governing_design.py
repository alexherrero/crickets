#!/usr/bin/env python3
"""Tests for the `governing-design` verb of
src/development-lifecycle/scripts/agentm_bridge.py (formerly the standalone
find_governing_design.py, merged into the shared bridge — CONS-2 task 2).

Discovery (find_governing_design_resolver): $AGENTM_SCRIPTS_DIR, co-located
sibling, conventional ~/Antigravity/ clone, and graceful-skip (None) when absent.

Delegation (run_governing_design_resolve): propagates resolver stdout + exit
code (governed / greenfield / usage); forwards --root / --include-proposed /
--json; exits 1 cleanly when the resolver is absent (no hang).

Every test is hermetic — injectable resolver paths + env overrides ensure no
dependency on a real agentm install (CI runs with none). Mirrors the
process-seam verb's own test shape.
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
    spec = importlib.util.spec_from_file_location("find_governing_design", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["find_governing_design"] = m
    spec.loader.exec_module(m)
    return m


fgd = _load()


def _make_fake_resolver(path: Path, body: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body or "# stub resolver\n", encoding="utf-8")
    return path


class TestFindResolverDiscovery(unittest.TestCase):
    """find_governing_design_resolver() locates governs_resolver.py via fallback order; None when absent."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fgd-discovery-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_found_via_env_agentm_scripts_dir(self):
        r = _make_fake_resolver(self.tmp / "env_scripts" / "governs_resolver.py")
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(r.parent)}):
            result = fgd.find_governing_design_resolver()
        self.assertEqual(result, r.resolve())

    def test_env_takes_priority_over_colocated(self):
        env_r = _make_fake_resolver(self.tmp / "env_dir" / "governs_resolver.py")
        colocated = _make_fake_resolver(_SRC.parent / "governs_resolver.py")
        try:
            with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": str(env_r.parent)}):
                result = fgd.find_governing_design_resolver()
            self.assertEqual(result, env_r.resolve())
        finally:
            colocated.unlink(missing_ok=True)

    def test_found_via_colocated_sibling(self):
        colocated = _make_fake_resolver(_SRC.parent / "governs_resolver.py")
        try:
            env_without = {k: v for k, v in os.environ.items()
                           if k != "AGENTM_SCRIPTS_DIR"}
            with mock.patch.dict(os.environ, env_without, clear=True):
                result = fgd.find_governing_design_resolver()
            self.assertIsNotNone(result)
            self.assertTrue(result.is_file())
        finally:
            colocated.unlink(missing_ok=True)

    def test_found_via_conventional_antigravity_clone(self):
        home = self.tmp / "fake_home"
        r = _make_fake_resolver(
            home / "Antigravity" / "agentm" / "scripts" / "governs_resolver.py")
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = fgd.find_governing_design_resolver()
        self.assertEqual(result, r.resolve())

    def test_returns_none_when_all_absent(self):
        home = self.tmp / "empty_home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = fgd.find_governing_design_resolver()
        self.assertIsNone(result)


class TestRunResolve(unittest.TestCase):
    """run_governing_design_resolve() propagates resolver stdout + exit code; exits 1 when absent."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fgd-run-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_resolver(self, body: str) -> Path:
        p = self.tmp / "fake_resolver.py"
        p.write_text(body, encoding="utf-8")
        return p

    def test_governed_path_propagated_exit_zero(self):
        # Echo a design path on stdout, exit 0 (governed).
        r = self._make_resolver(
            "import sys\nsys.stdout.write('wiki/designs/crickets-hld.md\\n')\nsys.exit(0)\n")
        out, rc = fgd.run_governing_design_resolve("src/x.py", root="/repo", resolver=r)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "wiki/designs/crickets-hld.md")

    def test_greenfield_exit_one_empty_stdout(self):
        r = self._make_resolver(
            "import sys\nsys.stderr.write('no design\\n')\nsys.exit(1)\n")
        out, rc = fgd.run_governing_design_resolve("src/x.py", root="/repo", resolver=r)
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")

    def test_usage_exit_two_propagated(self):
        r = self._make_resolver("import sys\nsys.exit(2)\n")
        out, rc = fgd.run_governing_design_resolve("", root="/repo", resolver=r)
        self.assertEqual(rc, 2)

    def test_root_and_flags_forwarded(self):
        # Echo argv so we can assert --root / --include-proposed / --json forwarded.
        r = self._make_resolver(
            "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n")
        out, rc = fgd.run_governing_design_resolve(
            "memory", root="/repo", include_proposed=True, as_json=True, resolver=r)
        self.assertEqual(rc, 0)
        self.assertIn("--root", out)
        self.assertIn("/repo", out)
        self.assertIn("--include-proposed", out)
        self.assertIn("--json", out)
        self.assertIn("memory", out)

    def test_resolver_absent_exits_one_no_hang(self):
        with mock.patch.object(fgd, "find_governing_design_resolver", return_value=None):
            out, rc = fgd.run_governing_design_resolve("src/x.py", root="/repo")
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")

    def test_resolver_error_graceful_skip(self):
        # A resolver path that doesn't exist → OSError on exec → graceful ("", 1).
        out, rc = fgd.run_governing_design_resolve(
            "src/x.py", root="/repo", resolver=self.tmp / "does-not-exist.py")
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")


class TestMainCLI(unittest.TestCase):
    """main() exits 2 on bad usage; defaults --root to cwd; proxies the resolver."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fgd-main-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_target_exits_two(self):
        rc = fgd.main(["agentm_bridge.py", "governing-design"])
        self.assertEqual(rc, 2)

    def test_governed_target_proxied(self):
        r = self.tmp / "resolver.py"
        r.write_text("import sys\nsys.stdout.write('wiki/designs/x.md\\n')\nsys.exit(0)\n",
                     encoding="utf-8")
        with mock.patch.object(fgd, "find_governing_design_resolver", return_value=r):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = fgd.main(["agentm_bridge.py", "governing-design", "src/x.py"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), "wiki/designs/x.md")

    def test_default_root_is_cwd(self):
        # The resolver echoes argv; assert main injected --root <cwd> by default.
        r = self.tmp / "resolver.py"
        r.write_text("import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\nsys.exit(0)\n",
                     encoding="utf-8")
        with mock.patch.object(fgd, "find_governing_design_resolver", return_value=r):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = fgd.main(["agentm_bridge.py", "governing-design", "src/x.py"])
        self.assertEqual(rc, 0)
        self.assertIn("--root", out.getvalue())
        self.assertIn(os.getcwd(), out.getvalue())

    def test_resolver_absent_exits_one_no_output(self):
        with mock.patch.object(fgd, "find_governing_design_resolver", return_value=None):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = fgd.main(["agentm_bridge.py", "governing-design", "src/x.py"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
