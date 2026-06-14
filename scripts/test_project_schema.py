#!/usr/bin/env python3
"""Tests for src/github-projects/scripts/project_schema.json (crickets #41, task 8).

The project.json schema is the vault↔board binding contract. The real config
lives in the gitignored vault (and may carry local paths), so these tests run a
small stdlib JSON-Schema *subset* validator (required / additionalProperties /
type / enum — all this schema uses) against **placeholder** fixtures only:

  - a well-formed config conforms;
  - each documented malformation is rejected (missing required, unknown key,
    bad project_surface enum, wrong-typed items_source / github.number);
  - the schema stays in lockstep with project_sync.load_config (a config that
    conforms also loads, and the load_config refusals are schema violations).

This locks the contract so a future schema edit can't silently widen or break
it. stdlib only — no jsonschema (the shipped helpers are stdlib-only too).
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
_SRC = _ROOT / "src" / "github-projects" / "scripts"
_SCHEMA = json.loads((_SRC / "project_schema.json").read_text(encoding="utf-8"))

_JSON_TYPE = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool,
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ps = _load("project_sync", _SRC / "project_sync.py")


def conforms(obj, schema, path="$") -> list:
    """Minimal JSON-Schema subset check covering exactly what project_schema.json
    uses: type, required, properties, additionalProperties (false / a subschema),
    and enum. Returns a list of human-readable violations ([] == conforms)."""
    errs = []
    t = schema.get("type")
    if t and not isinstance(obj, _JSON_TYPE[t]):
        # bool is an int in Python — reject it where an integer is expected.
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


def _ok_cfg() -> dict:
    return {
        "vault_project": "crickets",
        "github": {"owner": "<owner>", "number": 5,
                   "url": "https://github.com/users/<owner>/projects/5",
                   "repo": "<owner>/<repo>"},
        "project_surface": "github-board",
        "items_source": "board-items.json",
        "fields": {"track": "Track", "type": "Type", "priority": "Priority",
                   "start": "Start", "target": "Target", "status": "Status"},
    }


class TestSchemaShape(unittest.TestCase):
    def test_schema_declares_the_locked_contract(self):
        self.assertEqual(_SCHEMA["required"], ["vault_project", "github"])
        self.assertIs(_SCHEMA["additionalProperties"], False)
        self.assertIn("items_source", _SCHEMA["properties"])
        self.assertEqual(_SCHEMA["properties"]["items_source"]["type"], "string")
        self.assertEqual(
            _SCHEMA["properties"]["project_surface"]["enum"],
            ["github-board", "local-index", "none"])


class TestConformance(unittest.TestCase):
    def test_well_formed_conforms(self):
        self.assertEqual(conforms(_ok_cfg(), _SCHEMA), [])

    def test_minimal_required_only_conforms(self):
        self.assertEqual(
            conforms({"vault_project": "x", "github": {"owner": "o", "number": 1}},
                     _SCHEMA), [])

    def test_missing_required_top_key_rejected(self):
        bad = _ok_cfg(); del bad["github"]
        self.assertTrue(any("github" in e for e in conforms(bad, _SCHEMA)))

    def test_unknown_top_level_key_rejected(self):
        bad = _ok_cfg(); bad["surprise"] = 1
        self.assertTrue(any("surprise" in e for e in conforms(bad, _SCHEMA)))

    def test_bad_project_surface_enum_rejected(self):
        bad = _ok_cfg(); bad["project_surface"] = "trello"
        self.assertTrue(any("enum" in e for e in conforms(bad, _SCHEMA)))

    def test_items_source_must_be_string(self):
        bad = _ok_cfg(); bad["items_source"] = 42
        self.assertTrue(any("items_source" in e for e in conforms(bad, _SCHEMA)))

    def test_github_number_must_be_integer(self):
        bad = _ok_cfg(); bad["github"]["number"] = "five"
        self.assertTrue(any("number" in e for e in conforms(bad, _SCHEMA)))

    def test_unknown_github_key_rejected(self):
        bad = _ok_cfg(); bad["github"]["token"] = "secret"
        self.assertTrue(any("token" in e for e in conforms(bad, _SCHEMA)))


class TestSchemaTracksLoadConfig(unittest.TestCase):
    """A config that conforms also loads; the load_config refusals are exactly
    schema violations — the two enforcement layers stay in lockstep."""

    def _load_config(self, cfg):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "project.json"
            p.write_text(json.dumps(cfg), encoding="utf-8")
            return ps.load_config(p)

    def test_conforming_config_loads(self):
        cfg = _ok_cfg()
        self.assertEqual(conforms(cfg, _SCHEMA), [])
        self.assertEqual(self._load_config(cfg)["github"]["number"], 5)

    def test_load_config_refusal_is_a_schema_violation(self):
        for bad in ({"vault_project": "x"},                       # no github
                    {"vault_project": "x", "github": {"owner": "o"}}):  # no number
            self.assertTrue(conforms(bad, _SCHEMA), f"{bad} should violate schema")
            with self.assertRaises(ps.SyncError):
                self._load_config(bad)


if __name__ == "__main__":
    unittest.main()
