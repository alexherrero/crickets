#!/usr/bin/env python3
"""Tests for src/maintenance/scripts/cve_security_patch.py (crickets
wave-c-maintenance, task 2).

Exercises real git operations against a fixture repo so the "no
direct-to-main writes" guarantee is proven end-to-end, not merely assumed
(mirroring test_diagnostics_writer.py's real-bridge convention).

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "maintenance" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cve_security_patch = _load("maintenance_cve_security_patch", _SRC / "cve_security_patch.py")


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)


class CveSecurityPatchTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name) / "repo"
        self.repo_root.mkdir()
        _git(["init", "-q", "-b", "main"], self.repo_root)
        _git(["config", "user.email", "test@example.com"], self.repo_root)
        _git(["config", "user.name", "Test"], self.repo_root)
        self.manifest_relpath = "package.json"
        (self.repo_root / self.manifest_relpath).write_text(
            json.dumps({"name": "fixture-app", "dependencies": {"foo": "1.4.0"}}, indent=2) + "\n",
            encoding="utf-8",
        )
        _git(["add", "."], self.repo_root)
        _git(["commit", "-q", "-m", "initial"], self.repo_root)
        self.main_tip_before = _git(["rev-parse", "HEAD"], self.repo_root).stdout.strip()
        self.advisory = {"package": "foo", "vulnerable_version": "1.4.0", "fixed_version": "1.4.1"}

    def tearDown(self):
        self._tmp.cleanup()

    def test_advisory_produces_a_patch_to_the_correct_fixed_version(self):
        result = cve_security_patch.patch(self.repo_root, self.manifest_relpath, self.advisory)
        self.assertEqual(result["package"], "foo")
        self.assertEqual(result["new_version"], "1.4.1")
        patched = json.loads(
            _git(["show", f"{result['branch']}:{self.manifest_relpath}"], self.repo_root).stdout
        )
        self.assertEqual(patched["dependencies"]["foo"], "1.4.1")

    def test_patch_never_writes_directly_to_the_default_branch(self):
        cve_security_patch.patch(self.repo_root, self.manifest_relpath, self.advisory)
        current_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], self.repo_root).stdout.strip()
        main_tip_after = _git(["rev-parse", "main"], self.repo_root).stdout.strip()
        self.assertEqual(current_branch, "main")
        self.assertEqual(main_tip_after, self.main_tip_before)
        on_disk = json.loads((self.repo_root / self.manifest_relpath).read_text(encoding="utf-8"))
        self.assertEqual(on_disk["dependencies"]["foo"], "1.4.0")

    def test_advisory_not_matching_pinned_version_raises(self):
        stale_advisory = {"package": "foo", "vulnerable_version": "9.9.9", "fixed_version": "9.9.10"}
        with self.assertRaises(cve_security_patch.AdvisoryNotApplicable):
            cve_security_patch.patch(self.repo_root, self.manifest_relpath, stale_advisory)


if __name__ == "__main__":
    unittest.main()
