#!/usr/bin/env python3
"""Byte-identity drift guard for `/open` and `/orient` (PLAN-open-a-project-by-name
task 4).

Claude Code command markdown has no include mechanism — a command file is
loaded verbatim as a prompt, the same reason the recoverability-gate doctrine
block is inlined byte-identical across `work.md`/`bugfix.md`/`release.md`
(see `test_recoverability_gate_drift.py`). `/open` and `/orient` are one
implementation, two entry points, so `open.md` and `orient.md` carry the same
process body — this test proves it, rather than trusting it by inspection.

The two files are allowed to differ in exactly two places: the frontmatter
`name:` line, and the one intro-paragraph line naming which command is
"running" vs. "also invocable as." Every other byte must match — a change to
the LOCATE/CONFIRM/ORIENT process in one file that isn't mirrored in the other
fails this test loudly.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CMDS = _ROOT / "src" / "development-lifecycle" / "commands"

_NAME_LINE_RE = re.compile(r"^name: \w+$", re.MULTILINE)
_INTRO_LINE_RE = re.compile(
    r"^You are running \*\*`/\w+`\*\* \(also invocable as `/\w+`.*$", re.MULTILINE
)


def _normalize(text: str) -> str:
    """Strip the two permitted-to-differ lines to placeholders."""
    text = _NAME_LINE_RE.sub("name: <cmd>", text, count=1)
    text = _INTRO_LINE_RE.sub("<intro line>", text, count=1)
    return text


class TestOpenOrientByteIdentity(unittest.TestCase):
    def _read(self, filename: str) -> str:
        path = _CMDS / filename
        self.assertTrue(path.is_file(), f"{path} missing")
        return path.read_text(encoding="utf-8")

    def test_process_bodies_are_identical_modulo_name_and_intro(self):
        open_text = self._read("open.md")
        orient_text = self._read("orient.md")
        self.assertEqual(_normalize(open_text), _normalize(orient_text))

    def test_frontmatter_name_fields_actually_differ(self):
        """Sanity check the normalizer isn't hiding an accidental copy-paste
        (both files literally named `open`, e.g.)."""
        open_text = self._read("open.md")
        orient_text = self._read("orient.md")
        self.assertIn("name: open", open_text)
        self.assertIn("name: orient", orient_text)
        self.assertNotIn("name: orient", open_text)
        self.assertNotIn("name: open", orient_text)

    def test_intro_lines_actually_differ(self):
        open_text = self._read("open.md")
        orient_text = self._read("orient.md")
        self.assertIn("You are running **`/open`**", open_text)
        self.assertIn("You are running **`/orient`**", orient_text)


if __name__ == "__main__":
    unittest.main()
