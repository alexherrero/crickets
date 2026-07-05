#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/harness_root_drift.py (R2.5 task 12).

Fixture-only by design (see the module's own docstring): a real crickets
checkout can carry legitimate pre-vault-cutover archives under its repo-side
`.harness/` that were never meant to move, so this never scans real disk state
— every scenario here is a deliberately-constructed fixture.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "developer-workflows" / "scripts" / "harness_root_drift.py"


def _load():
    spec = importlib.util.spec_from_file_location("harness_root_drift", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["harness_root_drift"] = m
    spec.loader.exec_module(m)
    return m


hrd = _load()


class TestFindHarnessRootDrift(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hrd-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_drift_when_repo_side_is_the_resolved_root(self):
        # The correct standalone case: resolver's active root IS repo-side
        # .harness/ — even with queue/archive files present, nothing to flag.
        repo_side = self.tmp / ".harness"
        (repo_side / "queued-plans").mkdir(parents=True)
        (repo_side / "queued-plans" / "PLAN-foo.md").write_text("x", encoding="utf-8")
        drifted = hrd.find_harness_root_drift(self.tmp, repo_side)
        self.assertEqual(drifted, [])

    def test_no_drift_when_repo_side_absent(self):
        # Resolved elsewhere, and repo-side .harness/ doesn't even exist.
        vault_root = self.tmp / "vault" / "_harness"
        drifted = hrd.find_harness_root_drift(self.tmp, vault_root)
        self.assertEqual(drifted, [])

    def test_no_drift_when_repo_side_exists_but_empty(self):
        # Resolved elsewhere, repo-side .harness/ exists but has no queue/archive files.
        (self.tmp / ".harness").mkdir()
        vault_root = self.tmp / "vault" / "_harness"
        drifted = hrd.find_harness_root_drift(self.tmp, vault_root)
        self.assertEqual(drifted, [])

    def test_drift_detected_queued_plan_on_wrong_root(self):
        # The deliberately-mismatched fixture: resolver says vault-side, but a
        # queued plan physically sits under repo-side .harness/.
        stranded = self.tmp / ".harness" / "queued-plans" / "PLAN-foo.md"
        stranded.parent.mkdir(parents=True)
        stranded.write_text("STRANDED\n", encoding="utf-8")
        vault_root = self.tmp / "vault" / "_harness"
        drifted = hrd.find_harness_root_drift(self.tmp, vault_root)
        self.assertEqual(drifted, [stranded.resolve()])

    def test_drift_detected_archive_on_wrong_root(self):
        stranded = self.tmp / ".harness" / "PLAN.archive.20260705-foo.md"
        stranded.parent.mkdir(parents=True)
        stranded.write_text("STRANDED\n", encoding="utf-8")
        vault_root = self.tmp / "vault" / "_harness"
        drifted = hrd.find_harness_root_drift(self.tmp, vault_root)
        self.assertEqual(drifted, [stranded.resolve()])

    def test_drift_clears_once_file_moved_to_resolved_root(self):
        # "passes once the file is on the resolved root" — plan's own wording.
        stranded = self.tmp / ".harness" / "queued-plans" / "PLAN-foo.md"
        stranded.parent.mkdir(parents=True)
        stranded.write_text("STRANDED\n", encoding="utf-8")
        vault_root = self.tmp / "vault" / "_harness"
        self.assertNotEqual(hrd.find_harness_root_drift(self.tmp, vault_root), [])

        # Fix: move the file to the resolved (vault-side) root.
        fixed = vault_root / "queued-plans" / "PLAN-foo.md"
        fixed.parent.mkdir(parents=True)
        fixed.write_text(stranded.read_text(encoding="utf-8"), encoding="utf-8")
        stranded.unlink()

        self.assertEqual(hrd.find_harness_root_drift(self.tmp, vault_root), [])

    def test_multiple_stranded_files_all_reported_sorted(self):
        harness = self.tmp / ".harness"
        (harness / "queued-plans").mkdir(parents=True)
        (harness / "queued-plans" / "PLAN-b.md").write_text("x", encoding="utf-8")
        (harness / "queued-plans" / "PLAN-a.md").write_text("x", encoding="utf-8")
        (harness / "PLAN.archive.20260601-old.md").write_text("x", encoding="utf-8")
        vault_root = self.tmp / "vault" / "_harness"
        drifted = hrd.find_harness_root_drift(self.tmp, vault_root)
        self.assertEqual(len(drifted), 3)
        self.assertEqual(drifted, sorted(drifted))


class TestMainCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hrd-cli-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_drift_exits_zero(self):
        vault_root = self.tmp / "vault" / "_harness"
        rc = hrd.main(["harness_root_drift.py", str(self.tmp), str(vault_root)])
        self.assertEqual(rc, 0)

    def test_drift_exits_one(self):
        stranded = self.tmp / ".harness" / "queued-plans" / "PLAN-foo.md"
        stranded.parent.mkdir(parents=True)
        stranded.write_text("x", encoding="utf-8")
        vault_root = self.tmp / "vault" / "_harness"
        rc = hrd.main(["harness_root_drift.py", str(self.tmp), str(vault_root)])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
