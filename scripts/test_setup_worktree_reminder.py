#!/usr/bin/env python3
"""Content-conformance guard: `/setup`'s scaffold output carries the soft
worktree close-out doctrine reminder (worktree-native-flow task 7).

The human-facing complement to task 5's shepherd sidecar — the shepherd
reclaims what's provably safe on its own schedule, but a soft reminder in
`/setup`'s own output is the non-blocking nudge for everything else. This
test exists so a future edit to `setup.md` can't silently drop the line
(the plan's own verification: "no existing /setup test asserts the old
(absent) text in a way that would silently pass either way" — there was no
prior test at all, so this positively pins the new line instead).

Auto-discovered by check-all's `unit tests` gate.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SETUP_MD = _ROOT / "src" / "development-lifecycle" / "commands" / "setup.md"

_REMINDER_FRAGMENT = (
    "A worktree you're done with should be closed out (kept intentionally, "
    "or removed) rather than left dangling"
)


class TestSetupWorktreeReminder(unittest.TestCase):
    def test_scaffold_output_carries_the_reminder(self):
        text = _SETUP_MD.read_text(encoding="utf-8")
        self.assertIn(
            _REMINDER_FRAGMENT,
            text,
            "setup.md no longer carries the worktree close-out doctrine "
            "reminder — the human-facing complement to the shepherd sidecar.",
        )

    def test_reminder_is_explicitly_non_blocking(self):
        # It must read as advisory, not a gate — "not a hook, not a gate" is
        # the load-bearing framing that keeps this from becoming a stop point.
        text = _SETUP_MD.read_text(encoding="utf-8")
        self.assertIn("not a hook, not a gate", text)


if __name__ == "__main__":
    unittest.main()
