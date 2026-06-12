#!/usr/bin/env python3
"""Structural specs for the developer-workflows phase commands (multi-plan writers).

These are grep-style assertions over the *source* spec prose in
`src/developer-workflows/commands/*.md` — not unit tests of Python. They lock the
load-bearing facts the V5-10 "writers" plan introduced so a later edit can't
silently regress them:

  * `/work` (and, from T4, `/plan` + `/review`) resolve their on-disk pair by
    invoking `resolve_plan.py` — they never re-derive plan paths inline.
  * Every plan read and progress append routes through the **resolved** pair, so
    a named plan writes `progress-<name>.md`, never the shared singleton.
  * The `task N` selector still works, and a bare invocation stays the
    byte-identical singleton (back-compat is the invariant).

`generate.py check` (run by check-all.sh) separately proves `dist/` mirrors these
sources, so asserting the source spec is sufficient.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CMDS = _ROOT / "src" / "developer-workflows" / "commands"


def _read(name: str) -> str:
    return (_CMDS / name).read_text(encoding="utf-8")


class TestWorkSpec(unittest.TestCase):
    """`/work` is named-plan-aware by *consuming* resolve_plan.py (T3)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read("work.md")

    def test_i_invokes_resolve_plan_bridge(self):
        # (i) It calls the bridge — and via python3, not `bash` (a .py file needs
        # an interpreter; `bash <pyfile>` is the same bug the probe line carried).
        self.assertIn("resolve_plan.py", self.text)
        self.assertIn(
            'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"', self.text
        )
        self.assertNotIn(
            'bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"', self.text
        )

    def test_i_consumes_does_not_reimplement(self):
        # The user invariant: consume the agentm reader, never re-derive paths here.
        self.assertIn("never re-deriving", self.text)

    def test_ii_routes_reads_and_writes_through_resolved_pair(self):
        # (ii) Both the PLAN read and the progress append name the *resolved* pair —
        # the scoped progress-<name>.md is called out so the append can't target
        # the shared singleton.
        self.assertIn("resolved `PLAN.md`", self.text)
        self.assertIn("resolved `progress.md`", self.text)
        self.assertIn("progress-<name>.md", self.text)

    def test_iii_preserves_task_selector(self):
        # (iii) `task N` still selects a specific task.
        self.assertIn("task N", self.text)
        self.assertIn("task selector", self.text)

    def test_iv_bare_is_byte_identical_singleton(self):
        # (iv) Back-compat invariant stated in-spec.
        self.assertIn("byte-identical", self.text)
        self.assertIn("singleton", self.text)

    def test_risk7_nonzero_exit_is_hard_stop(self):
        # Risk #7: a dangling binding hard-stops; it never silently falls back to
        # the singleton (which would bind the worker to the wrong plan).
        low = self.text.lower()
        self.assertIn("hard stop", low)
        self.assertIn("never fall back to the singleton", low)


if __name__ == "__main__":
    unittest.main()
