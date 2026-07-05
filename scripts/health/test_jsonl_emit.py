#!/usr/bin/env python3
"""Tests for scripts/health/jsonl_emit.py (R2.1)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import jsonl_emit as je


class TestResolveJsonlOut(unittest.TestCase):
    def test_space_separated_flag(self):
        self.assertEqual(je.resolve_jsonl_out(["prog", "--jsonl-out", "/tmp/x.jsonl"]), "/tmp/x.jsonl")

    def test_equals_separated_flag(self):
        self.assertEqual(je.resolve_jsonl_out(["prog", "--jsonl-out=/tmp/x.jsonl"]), "/tmp/x.jsonl")

    def test_env_fallback(self):
        with mock.patch.dict(os.environ, {"HEALTH_JSONL_OUT": "/tmp/env.jsonl"}, clear=False):
            self.assertEqual(je.resolve_jsonl_out(["prog"]), "/tmp/env.jsonl")

    def test_none_when_neither_present(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(je.resolve_jsonl_out(["prog"]))


class TestStripJsonlOutFlag(unittest.TestCase):
    def test_strips_space_separated(self):
        self.assertEqual(je.strip_jsonl_out_flag(["prog", "--jsonl-out", "x", "-v"]), ["prog", "-v"])

    def test_strips_equals_separated(self):
        self.assertEqual(je.strip_jsonl_out_flag(["prog", "--jsonl-out=x", "-v"]), ["prog", "-v"])

    def test_leaves_other_args_untouched(self):
        self.assertEqual(je.strip_jsonl_out_flag(["prog", "-v", "TestCase"]), ["prog", "-v", "TestCase"])


class TestEmitJsonlCheck(unittest.TestCase):
    def test_noop_when_no_path(self):
        je.emit_jsonl_check(None, suite="s", check="c", passed=True)  # must not raise

    def test_writes_pass_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "out.jsonl")
            je.emit_jsonl_check(path, suite="s", check="c", passed=True, weight=2.0)
            record = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record, {"suite": "s", "axis": "capability function", "check": "c", "weight": 2.0, "pass": True})

    def test_writes_dark_record_for_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "out.jsonl")
            je.emit_jsonl_check(path, suite="s", check="c", passed=None)
            record = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertIsNone(record["pass"])
            self.assertTrue(record["dark"])

    def test_appends_across_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "out.jsonl")
            je.emit_jsonl_check(path, suite="s", check="c1", passed=True)
            je.emit_jsonl_check(path, suite="s", check="c2", passed=False)
            lines = Path(path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)


class _AllPassModule:
    class TestX(unittest.TestCase):
        def test_ok(self):
            self.assertTrue(True)


class _OneFailModule:
    class TestX(unittest.TestCase):
        def test_ok(self):
            self.assertTrue(True)

        def test_fails(self):
            self.assertTrue(False)


class TestRunModuleAsHealthCheck(unittest.TestCase):
    def test_all_pass_writes_pass_true_and_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "out.jsonl")
            rc = je.run_module_as_health_check(
                _AllPassModule, ["prog", "--jsonl-out", path], suite="s", check="c")
            self.assertEqual(rc, 0)
            record = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertTrue(record["pass"])

    def test_one_failure_writes_pass_false_and_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "out.jsonl")
            rc = je.run_module_as_health_check(
                _OneFailModule, ["prog", "--jsonl-out", path], suite="s", check="c")
            self.assertEqual(rc, 1)
            record = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertFalse(record["pass"])

    def test_without_jsonl_out_still_returns_correct_exit_code_and_writes_nothing(self):
        rc = je.run_module_as_health_check(_OneFailModule, ["prog"], suite="s", check="c")
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
