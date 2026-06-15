#!/usr/bin/env python3
"""Tests for the isolation block in project_schema.json (worktree-per-plan, task 1).

Validates the new `isolation` property using the same stdlib subset-validator
pattern as test_project_schema.py (no jsonschema dependency). Asserts:

  - a well-formed isolation block (all enum values including the reserved
    worktree-per-task) conforms;
  - an undeclared key inside isolation is rejected (additionalProperties: false);
  - enum values outside the declared set are rejected;
  - the isolation block is optional (a config without it still conforms).

Auto-discovered by check-all's `unit tests` gate.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCHEMA_PATH = _ROOT / "src" / "github-projects" / "scripts" / "project_schema.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

_JSON_TYPE = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool,
}


def conforms(obj, schema, path="$") -> list:
    """Minimal JSON-Schema subset: type, required, properties, additionalProperties, enum."""
    errs = []
    t = schema.get("type")
    if t and not isinstance(obj, _JSON_TYPE[t]):
        if not (t in ("integer", "number") and isinstance(obj, bool) is False
                and isinstance(obj, _JSON_TYPE[t])):
            errs.append(f"{path}: expected {t}, got {type(obj).__name__}")
            return errs
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in enum {schema['enum']}")
    if t == "object" and isinstance(obj, dict):
        for r in schema.get("required", []):
            if r not in obj:
                errs.append(f"{path}: missing required {r!r}")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, v in obj.items():
            if k in props:
                errs += conforms(v, props[k], f"{path}.{k}")
            elif addl is False:
                errs.append(f"{path}: unknown key {k!r}")
            elif isinstance(addl, dict):
                errs += conforms(v, addl, f"{path}.{k}")
    return errs


def _base_cfg() -> dict:
    return {"vault_project": "crickets", "github": {"owner": "o", "number": 1}}


class TestIsolationSchemaShape(unittest.TestCase):
    def test_schema_declares_isolation_property(self):
        props = _SCHEMA["properties"]
        self.assertIn("isolation", props)
        iso = props["isolation"]
        self.assertEqual(iso["type"], "object")
        self.assertIs(iso["additionalProperties"], False)

    def test_mode_enum_has_three_values(self):
        mode_enum = _SCHEMA["properties"]["isolation"]["properties"]["mode"]["enum"]
        self.assertIn("worktree-per-plan", mode_enum)
        self.assertIn("direct", mode_enum)
        self.assertIn("worktree-per-task", mode_enum, "reserved enum value must be present")

    def test_integration_enum_has_two_values(self):
        int_enum = _SCHEMA["properties"]["isolation"]["properties"]["integration"]["enum"]
        self.assertIn("pull-request", int_enum)
        self.assertIn("direct-push", int_enum)


class TestIsolationConformance(unittest.TestCase):
    def test_config_without_isolation_conforms(self):
        self.assertEqual(conforms(_base_cfg(), _SCHEMA), [])

    def test_full_isolation_block_conforms(self):
        cfg = {**_base_cfg(), "isolation": {"mode": "worktree-per-plan", "integration": "pull-request"}}
        self.assertEqual(conforms(cfg, _SCHEMA), [])

    def test_direct_mode_conforms(self):
        cfg = {**_base_cfg(), "isolation": {"mode": "direct", "integration": "direct-push"}}
        self.assertEqual(conforms(cfg, _SCHEMA), [])

    def test_reserved_worktree_per_task_conforms(self):
        cfg = {**_base_cfg(), "isolation": {"mode": "worktree-per-task"}}
        self.assertEqual(conforms(cfg, _SCHEMA), [])

    def test_empty_isolation_block_conforms(self):
        cfg = {**_base_cfg(), "isolation": {}}
        self.assertEqual(conforms(cfg, _SCHEMA), [])

    def test_unknown_isolation_key_rejected(self):
        cfg = {**_base_cfg(), "isolation": {"mode": "worktree-per-plan", "surprise": True}}
        errs = conforms(cfg, _SCHEMA)
        self.assertTrue(any("surprise" in e for e in errs), errs)

    def test_unknown_mode_value_rejected(self):
        cfg = {**_base_cfg(), "isolation": {"mode": "auto"}}
        errs = conforms(cfg, _SCHEMA)
        self.assertTrue(any("enum" in e for e in errs), errs)

    def test_unknown_integration_value_rejected(self):
        cfg = {**_base_cfg(), "isolation": {"integration": "squash"}}
        errs = conforms(cfg, _SCHEMA)
        self.assertTrue(any("enum" in e for e in errs), errs)

    def test_wrong_type_mode_rejected(self):
        cfg = {**_base_cfg(), "isolation": {"mode": 42}}
        errs = conforms(cfg, _SCHEMA)
        self.assertTrue(any("mode" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
