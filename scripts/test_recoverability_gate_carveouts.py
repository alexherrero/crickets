#!/usr/bin/env python3
"""Carve-out conformance guard for the recoverability-gate autonomy doctrine.

The autonomy doctrine (PLAN-developer-workflows-autonomy-autonomy-doctrine)
relaxes the *confirmation* gate on recoverable actions, but it explicitly leaves
three carve-outs untouched. A future edit that quietly relaxes one of them — say,
dropping the mandatory `pii-scrubber` from the block, or stripping the
no-`Co-Authored-By` rule from work.md's commit step — could still pass the
byte-identity drift test (the three block copies might remain identical to each
other) while silently widening autonomy past the locked design. This test is the
complementary guard: it asserts the carve-outs are present in the shipped
sources, not merely mutually consistent.

  1. Worker-tree initiation stays operator-initiated — `/spawn-worker` +
     `/integrate-worker` keep their "Operator-initiated only" + never-autonomous
     language, and the doctrine block names them as unchanged.
  2. The PII pre-push hook + `pii-scrubber` invocation stay mandatory — named in
     the block's carve-out clause in every execution command.
  3. The no-`Co-Authored-By` commit rule is intact — in the block's carve-out
     clause AND in work.md's standing commit-step instruction (the real
     enforcement point, outside the block, which the drift test does not cover).

It also asserts (a) each execution command carries the doctrine block. Together
with the byte-identity drift test, this proves the doctrine relaxed only what it
meant to.

Auto-discovered by check-all's `unit tests` gate (`unittest discover -p
'test_*.py'`) — no new top-level gate; the 8/8 count is unchanged.

Task 3 of PLAN-developer-workflows-autonomy-autonomy-doctrine.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CMDS = _ROOT / "src" / "developer-workflows" / "commands"

# The execution commands that carry the inlined doctrine block.
_EXECUTION = ("release.md", "work.md", "bugfix.md")

_BEGIN = "<!-- BEGIN recoverability-gate"
_END = "<!-- END recoverability-gate -->"

# Load-bearing carve-out fragments that MUST appear (verbatim) in the doctrine
# block of every execution command. Removing any is a relaxation, not a reword.
_CARVEOUT_FRAGMENTS = (
    "Worker-tree initiation stays operator-initiated "
    "(`/spawn-worker` + `/integrate-worker`)",
    "the PII pre-push hook + `pii-scrubber` invocation stay mandatory",
    "the no-`Co-Authored-By` commit rule is untouched",
)


def _read(name: str) -> str:
    return (_CMDS / name).read_text(encoding="utf-8")


class TestRecoverabilityGateCarveouts(unittest.TestCase):
    def test_each_execution_command_carries_the_block(self):
        for name in _EXECUTION:
            text = _read(name)
            self.assertIn(_BEGIN, text, f"{name} is missing the doctrine block (BEGIN sentinel)")
            self.assertIn(_END, text, f"{name} is missing the doctrine block (END sentinel)")

    def test_block_names_all_three_carveouts(self):
        for name in _EXECUTION:
            text = _read(name)
            for fragment in _CARVEOUT_FRAGMENTS:
                self.assertIn(
                    fragment,
                    text,
                    f"{name} no longer states the carve-out: {fragment!r} — "
                    f"the doctrine must not relax it.",
                )

    def test_no_coauthored_by_rule_intact_in_work_commit_step(self):
        # The block names it, but the load-bearing enforcement is work.md's
        # commit step — outside the block, so the drift test does not cover it.
        text = _read("work.md")
        self.assertIn(
            "Do not add a `Co-Authored-By:` trailer",
            text,
            "work.md's commit step no longer forbids the Co-Authored-By trailer.",
        )

    def test_worktree_commands_stay_operator_initiated(self):
        for name in ("spawn-worker.md", "integrate-worker.md"):
            text = _read(name)
            self.assertIn(
                "Operator-initiated only.",
                text,
                f"{name} lost its 'Operator-initiated only.' constraint.",
            )
            self.assertIn(
                "autonomous",
                text,
                f"{name} lost its never-autonomous language.",
            )


if __name__ == "__main__":
    unittest.main()
