#!/usr/bin/env python3
"""The handoff-pack renderer emits agentm's handoff marker under every prompt
(paired change for agentm's miner-provenance ruling 1): a section a person
copies out of PROMPTS.md carries the marker, so agentm's reflect miner never
mines the paste as the operator's own words."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "src" / "tokens" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import handoff_pack as hp  # noqa: E402


class TheMarker(unittest.TestCase):
    def test_every_prompt_section_carries_the_marker(self):
        with tempfile.TemporaryDirectory() as td:
            entries = [hp.HandoffEntry(title=f"Part {i}", prompt_text=f"Do part {i}.", tier="T1-Execute",
                                       model_id="claude-sonnet-5", effort="medium") for i in (1, 2)]
            hp.build_handoff_pack(entries, {}, Path(td))
            text = (Path(td) / "PROMPTS.md").read_text(encoding="utf-8")
        sections = text.split("\n## ")[1:]
        self.assertEqual(len(sections), 2)
        for s in sections:
            self.assertIn(hp.HANDOFF_MARKER, s)
            self.assertIn("> " + hp.HANDOFF_MARKER, s, "the quoted paste block itself carries it")

    def test_the_marker_matches_agentms_recogniser(self):
        self.assertTrue(hp.HANDOFF_MARKER.startswith("<!-- agentm:handoff"))
        self.assertTrue(hp.HANDOFF_MARKER.endswith("-->"))


if __name__ == "__main__":
    unittest.main()
