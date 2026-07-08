#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/add_select_options.py
(PLAN-board-tracking-model task 2). All tests use a mocked `runner` --
never a real `gh` call, and definitely never a real GraphQL mutation
against a live board."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "github-projects" / "scripts"


def _load(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


aso = _load("add_select_options", _SRC / "add_select_options.py")

_EXISTING = [
    {"id": "opt-v5", "name": "V5", "color": "GREEN", "description": "V5 desc"},
    {"id": "opt-v6", "name": "V6", "color": "YELLOW", "description": "V6 desc"},
]


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_runner(stdout_obj=None, returncode=0, stderr=""):
    calls = []

    def runner(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        stdout = json.dumps(stdout_obj) if stdout_obj is not None else ""
        return _FakeCompletedProcess(returncode, stdout, stderr)

    runner.calls = calls
    return runner


class BuildMutationOptionsTests(unittest.TestCase):
    def test_preserves_existing_options_verbatim(self):
        result = aso.build_mutation_options(_EXISTING, [])
        self.assertEqual(result, [
            {"id": "opt-v5", "name": "V5", "color": "GREEN", "description": "V5 desc"},
            {"id": "opt-v6", "name": "V6", "color": "YELLOW", "description": "V6 desc"},
        ])

    def test_new_options_appended_without_id(self):
        new = [aso.NewOption(name="T0-Mechanical", color="GRAY", description="mechanical work")]
        result = aso.build_mutation_options(_EXISTING, new)
        self.assertEqual(len(result), 3)
        added = result[2]
        self.assertNotIn("id", added)
        self.assertEqual(added["name"], "T0-Mechanical")
        self.assertEqual(added["color"], "GRAY")

    def test_existing_options_never_lose_their_id(self):
        new = [aso.NewOption(name="T0-Mechanical", color="GRAY")]
        result = aso.build_mutation_options(_EXISTING, new)
        for opt in result[:2]:
            self.assertIn("id", opt)
            self.assertTrue(opt["id"])

    def test_duplicate_name_raises_rather_than_silently_overwriting(self):
        new = [aso.NewOption(name="V5", color="GRAY")]
        with self.assertRaises(ValueError):
            aso.build_mutation_options(_EXISTING, new)

    def test_missing_description_defaults_to_empty_string(self):
        existing = [{"id": "x", "name": "X", "color": "GRAY", "description": None}]
        result = aso.build_mutation_options(existing, [])
        self.assertEqual(result[0]["description"], "")

    def test_empty_existing_options_still_appends_new(self):
        new = [aso.NewOption(name="T0-Mechanical", color="GRAY")]
        result = aso.build_mutation_options([], new)
        self.assertEqual(len(result), 1)
        self.assertNotIn("id", result[0])


class FetchExistingOptionsTests(unittest.TestCase):
    def test_parses_options_from_response(self):
        response = {"data": {"node": {"id": "field-1", "name": "Track", "options": _EXISTING}}}
        runner = _fake_runner(stdout_obj=response)
        options = aso.fetch_existing_options("field-1", runner=runner)
        self.assertEqual(options, _EXISTING)

    def test_nonzero_exit_raises(self):
        runner = _fake_runner(returncode=1, stderr="boom")
        with self.assertRaises(RuntimeError):
            aso.fetch_existing_options("field-1", runner=runner)

    def test_graphql_errors_key_raises(self):
        response = {"data": None, "errors": [{"message": "field not found"}]}
        runner = _fake_runner(stdout_obj=response)
        with self.assertRaises(RuntimeError):
            aso.fetch_existing_options("field-1", runner=runner)

    def test_malformed_response_raises(self):
        response = {"data": {"node": None}}
        runner = _fake_runner(stdout_obj=response)
        with self.assertRaises(RuntimeError):
            aso.fetch_existing_options("field-1", runner=runner)

    def test_request_uses_stdin_input_not_shell_flags(self):
        response = {"data": {"node": {"id": "field-1", "options": []}}}
        runner = _fake_runner(stdout_obj=response)
        aso.fetch_existing_options("field-1", runner=runner)
        cmd = runner.calls[0]["cmd"]
        self.assertEqual(cmd, ["gh", "api", "graphql", "--input", "-"])
        sent = json.loads(runner.calls[0]["kwargs"]["input"])
        self.assertEqual(sent["variables"]["fieldId"], "field-1")


class AddOptionsTests(unittest.TestCase):
    def test_dry_run_never_calls_the_mutation(self):
        fetch_response = {"data": {"node": {"id": "field-1", "options": _EXISTING}}}
        runner = _fake_runner(stdout_obj=fetch_response)
        result = aso.add_options("field-1", [aso.NewOption(name="T0-Mechanical", color="GRAY")], dry_run=True, runner=runner)
        self.assertFalse(result["executed"])
        self.assertEqual(len(runner.calls), 1)  # only the fetch, never the mutation

    def test_dry_run_returns_the_full_options_payload(self):
        fetch_response = {"data": {"node": {"id": "field-1", "options": _EXISTING}}}
        runner = _fake_runner(stdout_obj=fetch_response)
        result = aso.add_options("field-1", [aso.NewOption(name="T0-Mechanical", color="GRAY")], dry_run=True, runner=runner)
        self.assertEqual(len(result["options"]), 3)

    def test_non_dry_run_calls_fetch_then_mutation(self):
        fetch_response = {"data": {"node": {"id": "field-1", "options": _EXISTING}}}
        mutation_response = {"data": {"updateProjectV2Field": {"projectV2Field": {"id": "field-1"}}}}
        calls_seen = {"n": 0}

        def runner(cmd, **kwargs):
            calls_seen["n"] += 1
            resp = fetch_response if calls_seen["n"] == 1 else mutation_response
            return _FakeCompletedProcess(0, json.dumps(resp), "")

        result = aso.add_options("field-1", [aso.NewOption(name="T0-Mechanical", color="GRAY")], dry_run=False, runner=runner)
        self.assertTrue(result["executed"])
        self.assertEqual(calls_seen["n"], 2)

    def test_new_option_name_collision_raises_before_any_mutation_call(self):
        fetch_response = {"data": {"node": {"id": "field-1", "options": _EXISTING}}}
        runner = _fake_runner(stdout_obj=fetch_response)
        with self.assertRaises(ValueError):
            aso.add_options("field-1", [aso.NewOption(name="V5", color="GRAY")], dry_run=False, runner=runner)
        self.assertEqual(len(runner.calls), 1)  # never reached the mutation


if __name__ == "__main__":
    unittest.main()
