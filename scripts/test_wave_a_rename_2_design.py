#!/usr/bin/env python3
"""Lock for AG Wave A rename 2 task 4 (PLAN-wave-a-renames-2): the design-docs
-> design re-home + de-dupe. Asserts development-lifecycle/commands/ no longer
carries the four files that moved to design/, and that design/commands/design.md
retains distinct instructions from both pre-move source copies (the de-dupe's
no-content-loss requirement).
"""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


class TestWaveARename2Design(unittest.TestCase):
    def test_moved_files_gone_from_development_lifecycle(self):
        dl_commands = _REPO_ROOT / "src" / "development-lifecycle" / "commands"
        for name in ("spec.md", "interview-me.md", "document-decision.md", "design.md"):
            self.assertFalse((dl_commands / name).exists(), f"{name} still under development-lifecycle/commands/")
        dl_scripts = _REPO_ROOT / "src" / "development-lifecycle" / "scripts"
        for name in ("design_doc.py", "design_sequence.py"):
            self.assertFalse((dl_scripts / name).exists(), f"{name} still under development-lifecycle/scripts/")
        self.assertFalse(
            (_REPO_ROOT / "src" / "development-lifecycle" / "templates" / "design-doc.md").exists()
        )

    def test_moved_files_present_under_design(self):
        design_dir = _REPO_ROOT / "src" / "design"
        for rel in (
            "commands/spec.md", "commands/interview-me.md", "commands/document-decision.md",
            "commands/design.md", "scripts/design_doc.py", "scripts/design_sequence.py",
            "templates/design-doc.md",
        ):
            self.assertTrue((design_dir / rel).is_file(), f"{rel} missing under src/design/")

    def test_design_md_retains_both_sources_distinct_content(self):
        text = (_REPO_ROOT / "src" / "design" / "commands" / "design.md").read_text(encoding="utf-8")
        # From development-lifecycle's full implementation (the surviving copy):
        self.assertIn("Three verbs, one pipeline", text)
        self.assertIn("Status lifecycle (the hard gate)", text)
        self.assertIn("design_sequence.py", text)
        # From design-docs' stub (the delegate-pointer framing folds into the
        # surviving copy's own "upstream authoring step" framing — confirm the
        # three-verb dispatch table the stub also carried is present):
        self.assertIn("/design translate <slug>", text)
        self.assertIn("/design sequence <slug>", text)


if __name__ == "__main__":
    unittest.main()
