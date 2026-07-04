#!/usr/bin/env python3
"""Tests for src/token-audit/scripts/handoff_pack.py (PLAN-efficiency-automation task 7).

A fixture expensive session's outputs snapshot into a handoff directory
alongside paste-ready prompts, each carrying a machine-readable tier/model
label — a structured field (`prompts.json`), not a prose annotation. The
label's key set is checked against the shared fixture schema
(`scripts/fixtures/handoff_pack_label_schema.json`) that `PLAN-efficiency-
dispatch`'s escalation tripwire is expected to conform to as well.

stdlib only — no pytest.
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
_SCRIPTS = _ROOT / "src" / "token-audit" / "scripts"
_SCHEMA_FIXTURE = _ROOT / "scripts" / "fixtures" / "handoff_pack_label_schema.json"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


hp = _load("handoff_pack")


class TestSharedFixtureSchema(unittest.TestCase):
    def test_schema_fixture_matches_module_constant(self):
        schema = json.loads(_SCHEMA_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required_keys"]), set(hp.LABEL_SCHEMA_KEYS))


class TestBuildHandoffPack(unittest.TestCase):
    SESSION_OUTPUTS = {
        "findings.md": "# Findings\n\nExpensive research output.\n",
        "plan-proposal.md": "# Plan proposal\n\nDetailed staging plan.\n",
    }

    ENTRIES = [
        hp.HandoffEntry(
            title="Verify the minors",
            prompt_text="You are a verification clerk. Read findings.md...",
            tier="T0-Mechanical", model_id="claude-haiku-4-5", effort="low",
        ),
        hp.HandoffEntry(
            title="Assemble the deliverables",
            prompt_text="You are assembling final research deliverables...",
            tier="T2-Author", model_id="claude-sonnet-5", effort="high",
        ),
    ]

    def test_snapshots_session_outputs_into_dest_dir(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "handoff"
            hp.build_handoff_pack(self.ENTRIES, self.SESSION_OUTPUTS, dest)
            for name, content in self.SESSION_OUTPUTS.items():
                self.assertEqual((dest / name).read_text(encoding="utf-8"), content)

    def test_creates_dest_dir_if_absent(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "nested" / "handoff"
            self.assertFalse(dest.exists())
            hp.build_handoff_pack(self.ENTRIES, self.SESSION_OUTPUTS, dest)
            self.assertTrue(dest.is_dir())

    def test_prompts_json_carries_structured_labels_not_prose(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "handoff"
            manifest = hp.build_handoff_pack(self.ENTRIES, self.SESSION_OUTPUTS, dest)

            on_disk = json.loads((dest / "prompts.json").read_text(encoding="utf-8"))
            self.assertEqual(on_disk, manifest)

            self.assertEqual(len(manifest["prompts"]), 2)
            for prompt in manifest["prompts"]:
                label = prompt["label"]
                self.assertIsInstance(label, dict)
                self.assertTrue(hp.label_matches_schema(label))
                for key in hp.LABEL_SCHEMA_KEYS:
                    self.assertIn(key, label)
                    self.assertIsInstance(label[key], str)

    def test_prompts_md_is_paste_ready_and_names_the_model(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "handoff"
            hp.build_handoff_pack(self.ENTRIES, self.SESSION_OUTPUTS, dest)
            text = (dest / "PROMPTS.md").read_text(encoding="utf-8")
            self.assertIn("claude-haiku-4-5", text)
            self.assertIn("You are a verification clerk.", text)

    def test_manifest_lists_snapshotted_files(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "handoff"
            manifest = hp.build_handoff_pack(self.ENTRIES, self.SESSION_OUTPUTS, dest)
            self.assertEqual(manifest["snapshotted_files"], sorted(self.SESSION_OUTPUTS))


class TestLabelMatchesSchema(unittest.TestCase):
    def test_extra_key_fails(self):
        self.assertFalse(hp.label_matches_schema(
            {"tier": "T1", "model_id": "x", "effort": "low", "extra": "nope"}
        ))

    def test_missing_key_fails(self):
        self.assertFalse(hp.label_matches_schema({"tier": "T1", "model_id": "x"}))

    def test_exact_keys_pass(self):
        self.assertTrue(hp.label_matches_schema({"tier": "T1", "model_id": "x", "effort": "low"}))


if __name__ == "__main__":
    unittest.main()
