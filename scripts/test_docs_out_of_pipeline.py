#!/usr/bin/env python3
"""Docs are an opt-in pass, not a pipeline step (plan 104 step 2).

This replaces `test_documenter_routed_dispatch_drift.py`, which kept the
documenter dispatch's routed-dispatch trailer byte-identical across the five
phase commands. None of them dispatches the documenter any more: wiki pages
change through `wiki-author` on request or `wiki-watch` on a schedule. These
tests pin that the dispatch is gone and that each phase says where docs went.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CMDS = _ROOT / "src" / "development-lifecycle" / "commands"
_COMMANDS = ("work.md", "plan.md", "bugfix.md", "release.md", "setup.md")


def _read(name: str) -> str:
    return (_CMDS / name).read_text(encoding="utf-8")


class TestNoPhaseDispatchesTheDocumenter(unittest.TestCase):
    def test_no_documenter_dispatch_or_wiki_probe(self):
        for name in _COMMANDS:
            text = _read(name)
            self.assertNotIn("documenter", text, name)
            self.assertNotIn("capability wiki-maintenance", text, name)

    def test_each_phase_names_the_opt_in_path(self):
        for name in ("work.md", "plan.md", "release.md", "bugfix.md"):
            self.assertIn("`wiki-author`", _read(name), name)
        for name in ("work.md", "plan.md", "release.md"):
            self.assertIn("`wiki-watch`", _read(name), name)
        self.assertIn("`/wiki-init`", _read("setup.md"))

    def test_numbered_items_keep_their_numbers(self):
        # release.md points at "constraint 4" and work.md at "constraint 8":
        # the removed items stay as one-line stubs so those references hold.
        self.assertIn("\n4. **Docs are not part of the release gate.**", _read("release.md"))
        self.assertIn("(constraint 4)", _read("release.md"))
        self.assertIn("\n8. **Docs are an opt-in pass, later:**", _read("work.md"))
        self.assertIn("### 8. Docs\n\nNothing happens here (constraint 8).", _read("work.md"))
        self.assertIn("### 6. Docs\n\nNothing happens here (constraint 6).", _read("plan.md"))

    def test_work_edits_wiki_only_when_the_step_names_the_page(self):
        self.assertIn("Edit `wiki/` only when the step's **What** names the page.", _read("work.md"))


if __name__ == "__main__":
    unittest.main()
