#!/usr/bin/env python3
"""Lock for the design re-home (AG Wave A rename 2 task 4) and what became of it.

The design commands and helpers moved out of development-lifecycle into the design
plugin in AG Wave A rename 2, and development-lifecycle must not carry them again.
That part of the lock stands. The rest of the design plugin's old content (the
template walk, the draft -> review -> final gate, translate and sequence, the three
templates and the scripts only they used) retired with the old design standard in
plan 103 step 12; test_design_retired.py pins that. What this file asserts about
the design plugin now is its surviving layout.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


class TestWaveARename2Design(unittest.TestCase):
    def test_moved_files_gone_from_development_lifecycle(self):
        dl_commands = _REPO_ROOT / "src" / "development-lifecycle" / "commands"
        # spec.md is not listed: /spec came back to development-lifecycle in
        # plan 103 as the loop's anchor writer, a different command from the
        # six-section PRD that moved out in this rename. /interview-me is gone
        # everywhere (test_spec_wiring.py pins that).
        for name in ("interview-me.md", "document-decision.md", "design.md"):
            self.assertFalse((dl_commands / name).exists(), f"{name} still under development-lifecycle/commands/")
        dl_scripts = _REPO_ROOT / "src" / "development-lifecycle" / "scripts"
        for name in ("design_doc.py", "design_sequence.py"):
            self.assertFalse((dl_scripts / name).exists(), f"{name} still under development-lifecycle/scripts/")
        self.assertFalse(
            (_REPO_ROOT / "src" / "development-lifecycle" / "templates" / "design-doc.md").exists()
        )

    def test_the_design_plugin_keeps_design_and_its_prose_pass(self):
        # Plan 105 step 3 retired /document-decision and the adr skill (0 uses);
        # test_dead_weight_retired.py pins them gone.
        design_dir = _REPO_ROOT / "src" / "design"
        for rel in (
            "commands/design.md",
            "scripts/prose_pass.py", "scripts/project_homes.py",
            "skills/prose-pass/SKILL.md",
        ):
            self.assertTrue((design_dir / rel).is_file(), f"{rel} missing under src/design/")


if __name__ == "__main__":
    unittest.main()
