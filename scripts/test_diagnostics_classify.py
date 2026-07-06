#!/usr/bin/env python3
"""Tests for src/diagnostics/scripts/classify.py (crickets wave-c-diagnostics, task 2a).

Deterministic namespace classification from exit code / tool / structured
output -- no inference, no LLM judgment.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "diagnostics" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


classify_mod = _load("diagnostics_classify", _SRC / "classify.py")


class ClassifyTests(unittest.TestCase):
    def test_structured_rule_id_is_lint(self):
        ns = classify_mod.classify(exit_code=1, structured_output={"rule_id": "no-unused-vars"})
        self.assertEqual(ns, "lint")

    def test_structured_failing_test_id_is_test(self):
        ns = classify_mod.classify(exit_code=1, structured_output={"failing_test_id": "test_foo"})
        self.assertEqual(ns, "test")

    def test_tool_pytest_is_test(self):
        ns = classify_mod.classify(exit_code=1, tool="pytest")
        self.assertEqual(ns, "test")

    def test_tool_mypy_is_type(self):
        ns = classify_mod.classify(exit_code=1, tool="mypy")
        self.assertEqual(ns, "type")

    def test_tool_ruff_is_lint(self):
        ns = classify_mod.classify(exit_code=1, tool="ruff")
        self.assertEqual(ns, "lint")

    def test_tool_make_is_build(self):
        ns = classify_mod.classify(exit_code=2, tool="make")
        self.assertEqual(ns, "build")

    def test_unknown_tool_falls_back_to_runtime(self):
        ns = classify_mod.classify(exit_code=1, tool="some-custom-script")
        self.assertEqual(ns, "runtime")

    def test_tool_is_case_insensitive(self):
        ns = classify_mod.classify(exit_code=1, tool="PyTest")
        self.assertEqual(ns, "test")

    def test_structured_output_wins_over_tool(self):
        ns = classify_mod.classify(
            exit_code=1, tool="make", structured_output={"failing_test_id": "test_foo"}
        )
        self.assertEqual(ns, "test")


if __name__ == "__main__":
    unittest.main()
