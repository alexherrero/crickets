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
_SCRIPTS = _ROOT / "src" / "tokens" / "scripts"
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


class TestDefaultDestination(unittest.TestCase):
    """agentm-vault part 15: with no destination named, a pack goes to the
    project's own desk/ as agentm names it; with no desk there is no default."""

    def setUp(self):
        import os
        from unittest import mock
        sys.path.insert(0, str(_ROOT / "scripts"))
        import no_harness_fixture as nhf
        self.nhf = nhf
        self.sp = nhf.ScratchProject()
        self.addCleanup(self.sp.cleanup)
        self.env = lambda values: self._patch(os, mock, values)

    def _patch(self, os, mock, values):
        patcher = mock.patch.dict(os.environ, {"HOME": str(self.sp.root / "home"), **values})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.assertEqual(self.nhf.harness_dirs(self.sp.root), [])

    def test_the_default_is_the_projects_desk(self):
        self.env({"AGENTM_SCRIPTS_DIR": str(self.sp.agentm)})
        dest = hp.default_destination("n1-handoff", self.sp.repo)
        self.assertEqual(dest, self.sp.desk / "n1-handoff")
        self.assertFalse(dest.exists())

    def test_a_pack_lands_in_the_default(self):
        self.env({"AGENTM_SCRIPTS_DIR": str(self.sp.agentm)})
        dest = hp.default_destination("n1-handoff", self.sp.repo)
        hp.build_handoff_pack(TestBuildHandoffPack.ENTRIES,
                              TestBuildHandoffPack.SESSION_OUTPUTS, dest)
        self.assertTrue((self.sp.desk / "n1-handoff" / "PROMPTS.md").is_file())
        self.assertTrue((self.sp.desk / "n1-handoff" / "prompts.json").is_file())

    def test_no_agentm_is_no_default(self):
        self.env({"AGENTM_SCRIPTS_DIR": ""})
        self.assertIsNone(hp.default_destination("n1-handoff", self.sp.repo))

    def test_a_named_destination_still_wins(self):
        # The default is only the default: a pack built into a named directory
        # lands there, and nothing is written to the desk.
        named = self.sp.root / "elsewhere"
        hp.build_handoff_pack(TestBuildHandoffPack.ENTRIES,
                              TestBuildHandoffPack.SESSION_OUTPUTS, named)
        self.assertTrue((named / "PROMPTS.md").is_file())
        self.assertEqual(list(self.sp.desk.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
