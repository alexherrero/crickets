#!/usr/bin/env python3
"""Tests for scripts/check-plan-grounding.py (AG Phase-2, Hook 3)."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_plan_grounding", _HERE / "check-plan-grounding.py")
cpg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpg)


def _plan(fm: str, body: str = "") -> str:
    return f"---\n{fm}\n---\n\n# Plan: x\n\n{body}\n"


class TestIsGrounded(unittest.TestCase):
    def test_not_touching_architecture_passes(self):
        ok, _ = cpg.is_grounded(_plan("touches_architecture: false"))
        self.assertTrue(ok)

    def test_flag_absent_passes(self):
        ok, _ = cpg.is_grounded(_plan("parent_part_slug: x"))
        self.assertTrue(ok)

    def test_touching_with_parent_design_doc_passes(self):
        ok, _ = cpg.is_grounded(
            _plan("touches_architecture: true\nparent_design_doc: wiki/designs/x.md"))
        self.assertTrue(ok)

    def test_touching_with_locked_section_passes(self):
        ok, _ = cpg.is_grounded(
            _plan("touches_architecture: true",
                  "## Locked design calls\n- honor the seam contract\n"))
        self.assertTrue(ok)

    def test_touching_with_greenfield_assertion_passes(self):
        # asserting greenfield IS the grounding step
        ok, _ = cpg.is_grounded(
            _plan("touches_architecture: true",
                  "## Locked design calls\nGreenfield — no governing design.\n"))
        self.assertTrue(ok)

    def test_touching_but_ungrounded_fails(self):
        ok, reason = cpg.is_grounded(_plan("touches_architecture: true",
                                           "## Goal\nsomething\n"))
        self.assertFalse(ok)
        self.assertIn("touches_architecture", reason)

    def test_touching_with_empty_locked_section_fails(self):
        # heading present but no content before the next heading → not grounded
        ok, _ = cpg.is_grounded(
            _plan("touches_architecture: true",
                  "## Locked design calls\n\n## Tasks\n- do it\n"))
        self.assertFalse(ok)


class TestMain(unittest.TestCase):
    def test_usage_error(self):
        self.assertEqual(cpg.main(["check-plan-grounding.py"]), 2)

    def test_unreadable_file(self):
        self.assertEqual(
            cpg.main(["check-plan-grounding.py", "/nonexistent/PLAN.md"]), 2)

    def test_grounded_exit_zero(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "PLAN.md"
            p.write_text(_plan("touches_architecture: true\nparent_design_doc: d.md"),
                         encoding="utf-8")
            self.assertEqual(cpg.main(["check-plan-grounding.py", str(p)]), 0)

    def test_ungrounded_exit_one(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "PLAN.md"
            p.write_text(_plan("touches_architecture: true", "## Goal\nx\n"),
                         encoding="utf-8")
            self.assertEqual(cpg.main(["check-plan-grounding.py", str(p)]), 1)


if __name__ == "__main__":
    unittest.main()
