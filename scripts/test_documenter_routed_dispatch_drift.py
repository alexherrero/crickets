#!/usr/bin/env python3
"""Byte-identity drift guard for the documenter's routed-dispatch trailer (R2.5 task 10).

ADR 0026 phase-aware model routing wired a "Routed dispatch (separate
graceful-skip)" + "Mandatory fan-out announcement (unconditional)" trailer
onto the documenter-dispatch mentions in `work.md` and `plan.md`, but
`bugfix.md`, `release.md`, and `setup.md`'s own documenter-dispatch mentions
were deferred and never got it — three phase commands silently dispatching
the documenter without the same model routing every other phase command's
dispatch carries.

Like the recoverability-gate block (`test_recoverability_gate_drift.py`),
this trailer can't be factored into a shared snippet (Claude Code drops
instruction-file snippets at emit time) — it is inlined verbatim into every
command that dispatches the documenter. That makes silent drift the failure
mode this test guards: one copy edited without the others (or a future
command's documenter-dispatch mention omitting it entirely) diverges the
routing convention while every other gate stays green.

`generate.py check` (run by check-all.sh) separately proves `dist/` mirrors
these sources, so asserting byte-identity across the five `src/` copies is
sufficient.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CMDS = _ROOT / "src" / "development-lifecycle" / "commands"

# Every command whose spec dispatches the documenter, in canonical order
# (work.md is the byte-identity reference — the original P12 copy).
_COMMANDS = ("work.md", "plan.md", "bugfix.md", "release.md", "setup.md")

_START = "**Routed dispatch (separate graceful-skip):**"
_END = "never proceed silently."


def _extract_trailer(text: str) -> str:
    """Return the trailer, START..END inclusive, byte-for-byte.

    No normalization. Raises ValueError (via str.index) if the start marker
    is absent — a missing trailer is a hard failure, not a silent skip.
    """
    start = text.index(_START)
    end = text.index(_END, start) + len(_END)
    return text[start:end]


class TestDocumenterRoutedDispatchByteIdentity(unittest.TestCase):
    def _trailers(self) -> dict:
        return {
            name: _extract_trailer((_CMDS / name).read_text(encoding="utf-8"))
            for name in _COMMANDS
        }

    def test_each_documenter_dispatching_command_carries_the_trailer(self):
        for name in _COMMANDS:
            text = (_CMDS / name).read_text(encoding="utf-8")
            self.assertIn(_START, text, f"{name} is missing the routed-dispatch trailer")

    def test_trailers_are_byte_identical(self):
        trailers = self._trailers()
        reference_name = _COMMANDS[0]
        reference = trailers[reference_name]
        for name in _COMMANDS[1:]:
            self.assertEqual(
                trailers[name],
                reference,
                f"routed-dispatch trailer in {name} diverges from {reference_name} "
                f"(byte-identity required — no whitespace normalization). "
                f"Re-inline the canonical trailer verbatim.",
            )

    def test_trailer_is_well_formed(self):
        # Guard against a vacuous pass if the markers collapse or the text is
        # truncated: the canonical trailer names both the routing seam and
        # the mandatory announcement.
        ref = self._trailers()[_COMMANDS[0]]
        self.assertTrue(ref.startswith(_START))
        self.assertTrue(ref.endswith(_END))
        self.assertIn("token-audit", ref)
        self.assertIn("classify_work_type", ref)
        self.assertIn("fanout_announcement.py", ref)
        self.assertIn("needs_inheritance_pause", ref)


if __name__ == "__main__":
    unittest.main()
