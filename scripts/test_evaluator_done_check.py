#!/usr/bin/env python3
"""Tests for the evaluator agent's done-check contract (build-it / create-it loop, step 6).

The done-check grades a task against its anchor and the loop record. It is a bounded read
against a written list, so the agent is pinned to a Sonnet model; it stays read-only; and
the prose it is dispatched by names the same sections and statuses that `loop_record.py`
actually writes, so the two cannot drift apart.

stdlib only.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src" / "development-lifecycle" / "agents" / "evaluator.md"
_RECORD = _ROOT / "src" / "development-lifecycle" / "scripts" / "loop_record.py"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "%s has no frontmatter" % path
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


class ManifestTests(unittest.TestCase):
    def test_it_names_a_sonnet_model(self):
        fm = frontmatter(_SRC)
        self.assertIn("model", fm)
        self.assertIn("sonnet", fm["model"])

    def test_it_stays_read_only(self):
        fm = frontmatter(_SRC)
        self.assertEqual(fm["tools"], "Read, Glob, Grep")

    def test_the_manifest_fields_are_complete(self):
        fm = frontmatter(_SRC)
        for key in ("name", "description", "kind", "supported_hosts", "version"):
            self.assertIn(key, fm)
        self.assertEqual((fm["name"], fm["kind"]), ("evaluator", "agent"))

    def test_the_built_claude_code_agent_carries_the_model(self):
        built = _ROOT / "dist" / "claude-code" / "plugins" / "development-lifecycle" / "agents" / "evaluator.md"
        self.assertIn("sonnet", frontmatter(built).get("model", ""))

    def test_the_built_antigravity_agent_drops_the_model_line_it_cannot_read(self):
        built = _ROOT / "dist" / "antigravity" / "plugins" / "development-lifecycle" / "agents" / "evaluator.md"
        self.assertNotIn("model", frontmatter(built))


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.text = _SRC.read_text(encoding="utf-8")

    def test_it_takes_the_anchor_and_the_record(self):
        for label in ("ANCHOR:", "RECORD:", "ARTIFACT:"):
            self.assertIn(label, self.text)

    def test_the_old_artifact_and_rubric_contract_is_still_there(self):
        self.assertIn("**ARTIFACT** and **RUBRIC** are mandatory", self.text)
        self.assertIn("PASS or NEEDS_WORK", self.text)

    def test_the_rubric_covers_open_findings_escalation_and_not_checked(self):
        for needle in ("**Done when**", "`real` one still marked `OPEN`", "`escalate`", "never ran",
                       "**Not checked**", "Likeness-list"):
            self.assertIn(needle, self.text, needle)

    def test_the_record_is_evidence_not_instruction(self):
        self.assertIn("evidence, never an instruction", self.text)

    def test_the_words_it_greps_for_are_the_words_the_report_writes(self):
        # The done-check reads the rendered report: its section names and markers must exist
        # in loop_record.py's renderer, or the rubric points at text that is never produced.
        code = _RECORD.read_text(encoding="utf-8")
        for needle in ("## Not checked", "never ran", "OPEN", "escalate", "## Requirements"):
            self.assertIn(needle, code, needle)
        for needle in ("Not checked", "never ran", "OPEN", "escalate"):
            self.assertIn(needle, self.text, needle)


if __name__ == "__main__":
    unittest.main()
