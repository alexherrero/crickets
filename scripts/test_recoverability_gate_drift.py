#!/usr/bin/env python3
"""Byte-identity drift guard for the inlined recoverability-gate doctrine block.

The "Recoverability gate" block is the short summary of the autonomy doctrine
each execution command carries; the full doctrine lives in developer-safety's
`recoverability` skill (crickets plan 105 step 1). Claude Code drops
instruction-file snippets at emit time (see `emit_claude`), so the block CANNOT
be factored into a shared snippet — it is inlined verbatim into each execution
command (`release.md` / `work.md` / `bugfix.md`). That makes silent drift the
failure mode: one copy edited without the others diverges the doctrine while
every other gate stays green.

This test extracts the block (the `## Recoverability gate` heading and its
summary paragraph) from each command and asserts the three
copies are **byte-identical** — no whitespace normalization, no trimming. A
single-byte divergence in any copy fails the build. The block is short and
inlined verbatim; any intentional wording change is an all-copies-together
amendment (kernel-defect class under the self-amending loop), never a one-file
edit.

`generate.py check` (run by check-all.sh) separately proves `dist/` mirrors
these sources, so asserting byte-identity across the three `src/` copies is
sufficient. Auto-discovered by check-all's `unit tests` gate
(`unittest discover -p 'test_*.py'`) — no new top-level gate; the 8/8 count is
unchanged.

Task 2 of PLAN-developer-workflows-autonomy-autonomy-doctrine.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CMDS = _ROOT / "src" / "development-lifecycle" / "commands"

# The execution commands that carry the inlined doctrine block, in canonical
# order (release.md is the byte-identity reference).
_COMMANDS = ("release.md", "work.md", "bugfix.md")

# Plan 105 step 1: the block is the `## Recoverability gate` heading and its one
# summary paragraph, up to the next blank line (the old HTML sentinels are gone).
_BEGIN = "## Recoverability gate\n\n"


def _extract_block(text: str) -> str:
    """Return the block, heading through the end of its summary paragraph, byte-for-byte.

    No normalization. Raises ValueError (via str.index) if the heading is absent
    — a missing block is a hard failure, not a silent skip.
    """
    start = text.index(_BEGIN)
    end = text.index("\n\n", start + len(_BEGIN) + 1)
    return text[start:end]


class TestRecoverabilityGateByteIdentity(unittest.TestCase):
    def _blocks(self) -> dict:
        return {
            name: _extract_block((_CMDS / name).read_text(encoding="utf-8"))
            for name in _COMMANDS
        }

    def test_each_command_carries_the_block(self):
        for name in _COMMANDS:
            text = (_CMDS / name).read_text(encoding="utf-8")
            self.assertIn(_BEGIN, text, f"{name} is missing the Recoverability gate summary")
            self.assertNotIn("BEGIN recoverability-gate", text,
                             f"{name} still carries the old sentinel-anchored doctrine copy")

    def test_blocks_are_byte_identical(self):
        blocks = self._blocks()
        reference_name = _COMMANDS[0]
        reference = blocks[reference_name]
        for name in _COMMANDS[1:]:
            self.assertEqual(
                blocks[name],
                reference,
                f"recoverability-gate block in {name} diverges from "
                f"{reference_name} (byte-identity required — no whitespace "
                f"normalization). Re-inline the canonical block verbatim.",
            )

    def test_block_is_nonempty_and_well_formed(self):
        # Guard against a vacuous pass if the block is truncated: heading, blank
        # line, and a summary that names the doctrine and points at its home.
        ref = self._blocks()[_COMMANDS[0]]
        self.assertTrue(ref.startswith(_BEGIN))
        body = ref[len(_BEGIN):]
        self.assertIn("recoverability, not destructiveness or blast-radius", body)
        # Plan 105 step 1: the block is a summary that points at the doctrine's
        # one home, and stays a summary (at most 80 words, at least 40).
        self.assertIn("the `recoverability` skill", body)
        self.assertLessEqual(len(body.split()), 80)
        self.assertGreaterEqual(len(body.split()), 40)


if __name__ == "__main__":
    unittest.main()
