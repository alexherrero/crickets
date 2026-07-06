#!/usr/bin/env python3
"""Tests for src/maintenance/scripts/deps_currency.py (crickets
wave-c-maintenance, task 1).

deps-currency is a passive report, not a repairer -- these tests prove both
the drift-surfacing behavior and that the manifest is never touched.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import json
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


deps_currency = _load("maintenance_deps_currency", _SRC / "deps_currency.py")


class DepsCurrencyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.manifest_path = Path(self._tmp.name) / "package.json"
        self.manifest_path.write_text(
            json.dumps({
                "name": "fixture-app",
                "dependencies": {
                    "foo": "^1.0.0",  # drifted -- CI still green on 1.0.0, 1.2.0 exists
                    "bar": "^2.0.0",  # not drifted -- pinned already matches latest
                },
            }, indent=2),
            encoding="utf-8",
        )
        self._latest_versions = {"foo": "1.2.0", "bar": "2.0.0"}

    def tearDown(self):
        self._tmp.cleanup()

    def test_drifted_package_produces_exactly_one_finding(self):
        findings = deps_currency.scan(self.manifest_path, self._latest_versions)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["package"], "foo")
        self.assertEqual(findings[0]["pinned"], "^1.0.0")
        self.assertEqual(findings[0]["latest"], "1.2.0")

    def test_manifest_is_byte_identical_before_and_after_the_scan(self):
        before = self.manifest_path.read_bytes()
        deps_currency.scan(self.manifest_path, self._latest_versions)
        after = self.manifest_path.read_bytes()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
