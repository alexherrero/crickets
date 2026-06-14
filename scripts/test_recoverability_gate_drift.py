#!/usr/bin/env python3
"""Byte-identity drift guard for the inlined recoverability-gate doctrine block.

The "Recoverability gate (autonomy doctrine)" block is the single source of
truth for developer-workflows execution autonomy. Claude Code drops
instruction-file snippets at emit time (see `emit_claude`), so the block CANNOT
be factored into a shared snippet — it is inlined verbatim into each execution
command (`release.md` / `work.md` / `bugfix.md`). That makes silent drift the
failure mode: one copy edited without the others diverges the doctrine while
every other gate stays green.

This test extracts the sentinel-anchored block (`<!-- BEGIN recoverability-gate`
… `<!-- END recoverability-gate -->`) from each command and asserts the three
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
_CMDS = _ROOT / "src" / "developer-workflows" / "commands"

# The execution commands that carry the inlined doctrine block, in canonical
# order (release.md is the byte-identity reference).
_COMMANDS = ("release.md", "work.md", "bugfix.md")

_BEGIN = "<!-- BEGIN recoverability-gate"
_END = "<!-- END recoverability-gate -->"


def _extract_block(text: str) -> str:
    """Return the sentinel-anchored block, BEGIN..END inclusive, byte-for-byte.

    No normalization: the returned substring is exactly the bytes from the start
    of the BEGIN sentinel line through the end of the END sentinel. Raises
    ValueError (via str.index) if either sentinel is absent — a missing block is
    a hard failure, not a silent skip.
    """
    start = text.index(_BEGIN)
    end = text.index(_END) + len(_END)
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
            self.assertIn(_BEGIN, text, f"{name} is missing the BEGIN sentinel")
            self.assertIn(_END, text, f"{name} is missing the END sentinel")

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
        # Guard against a vacuous pass if the sentinels collapse or the block is
        # truncated: the canonical block is multi-line and names the doctrine.
        ref = self._blocks()[_COMMANDS[0]]
        self.assertTrue(ref.startswith(_BEGIN))
        self.assertTrue(ref.endswith(_END))
        self.assertGreaterEqual(ref.count("\n"), 5)
        self.assertIn("Recoverability gate (autonomy doctrine)", ref)


if __name__ == "__main__":
    unittest.main()
