#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/preflight_reconcile.py (LC-6).

The cheap pre-flight reconcile that `/plan --activate` and `/spawn-worker` consult:
a staged/active plan that declares `expected_artifacts` is "already shipped" iff
EVERY listed path exists under the project root. Every test is hermetic — a
throwaway tmp dir stands in for the repo root; the plan is a string with (or
without) frontmatter. No git, no agentm clone.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pr = _load("preflight_reconcile")


class TestExpectedArtifacts(unittest.TestCase):
    """The frontmatter list parse — inline + block forms, dormant defaults."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pr-arts-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _plan(self, body: str) -> Path:
        p = self.tmp / "PLAN-foo.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_inline_list_form(self):
        p = self._plan("---\nexpected_artifacts: [a/x.py, b/y.md]\n---\n# Plan\n")
        self.assertEqual(pr.expected_artifacts(p), ["a/x.py", "b/y.md"])

    def test_block_list_form(self):
        p = self._plan(
            "---\n"
            "parent_part_slug: foo\n"
            "expected_artifacts:\n"
            "  - a/x.py\n"
            "  - b/y.md\n"
            "---\n# Plan\n"
        )
        self.assertEqual(pr.expected_artifacts(p), ["a/x.py", "b/y.md"])

    def test_block_list_ends_at_next_top_level_key(self):
        # A non-blank line back at column 0 ends the block — the trailing key's
        # value must NOT be swallowed into the artifact list.
        p = self._plan(
            "---\n"
            "expected_artifacts:\n"
            "  - a/x.py\n"
            "status: final\n"
            "---\n# Plan\n"
        )
        self.assertEqual(pr.expected_artifacts(p), ["a/x.py"])

    def test_absent_key_is_dormant(self):
        p = self._plan("---\nparent_part_slug: foo\n---\n# Plan\n")
        self.assertEqual(pr.expected_artifacts(p), [])

    def test_empty_inline_list_is_dormant(self):
        p = self._plan("---\nexpected_artifacts: []\n---\n# Plan\n")
        self.assertEqual(pr.expected_artifacts(p), [])

    def test_no_frontmatter_is_dormant(self):
        p = self._plan("# Plan: foo\n\n**Status:** planning\n")
        self.assertEqual(pr.expected_artifacts(p), [])

    def test_unreadable_plan_is_dormant_not_a_raise(self):
        # A reconcile must never crash the activation it guards.
        missing = self.tmp / "does-not-exist.md"
        self.assertEqual(pr.expected_artifacts(missing), [])


class TestAlreadyShipped(unittest.TestCase):
    """The reconcile: shipped iff EVERY declared artifact exists under root."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pr-shipped-"))
        self.plan = self.tmp / "PLAN-foo.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _declare(self, *arts: str):
        inline = ", ".join(arts)
        self.plan.write_text(
            f"---\nexpected_artifacts: [{inline}]\n---\n# Plan\n", encoding="utf-8")

    def _touch(self, rel: str):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("shipped\n", encoding="utf-8")

    def test_all_present_is_shipped(self):
        self._declare("src/new_a.py", "wiki/decisions/0099-x.md")
        self._touch("src/new_a.py")
        self._touch("wiki/decisions/0099-x.md")
        shipped, present = pr.already_shipped(self.plan, self.tmp)
        self.assertTrue(shipped)
        self.assertEqual(set(present), {"src/new_a.py", "wiki/decisions/0099-x.md"})

    def test_partial_present_is_not_shipped(self):
        # One artifact exists, one missing → the lane still has work → proceed.
        self._declare("src/new_a.py", "src/new_b.py")
        self._touch("src/new_a.py")
        shipped, present = pr.already_shipped(self.plan, self.tmp)
        self.assertFalse(shipped)
        self.assertEqual(present, ["src/new_a.py"])

    def test_none_present_is_not_shipped(self):
        self._declare("src/new_a.py", "src/new_b.py")
        shipped, present = pr.already_shipped(self.plan, self.tmp)
        self.assertFalse(shipped)
        self.assertEqual(present, [])

    def test_no_declaration_is_dormant(self):
        # No expected_artifacts key → never shipped (the back-compat default),
        # even if unrelated files exist in the repo.
        self.plan.write_text("---\nparent_part_slug: foo\n---\n# Plan\n",
                             encoding="utf-8")
        self._touch("src/whatever.py")
        shipped, present = pr.already_shipped(self.plan, self.tmp)
        self.assertFalse(shipped)
        self.assertEqual(present, [])

    def test_a_directory_artifact_counts_as_present(self):
        # `.exists()` is true for a dir too — a plan that ships a new directory
        # (e.g. a new wiki subtree) reconciles on the dir's presence.
        self._declare("wiki/new-section")
        (self.tmp / "wiki" / "new-section").mkdir(parents=True)
        shipped, _ = pr.already_shipped(self.plan, self.tmp)
        self.assertTrue(shipped)


class TestShippedMessage(unittest.TestCase):
    """The shared refusal text both callers emit verbatim."""

    def test_message_carries_the_canonical_phrase_and_the_slug(self):
        msg = pr.shipped_message("foo", ["src/a.py", "src/b.py"])
        self.assertIn("already shipped — nothing to do", msg)
        self.assertIn("foo", msg)
        self.assertIn("src/a.py", msg)
        self.assertIn("src/b.py", msg)
        self.assertTrue(msg.endswith("\n"))

    def test_message_is_stable_for_empty_present(self):
        # Defensive: shipped_message is only called when shipped, but it must not
        # blow up on an empty list (it never is in practice, but the join is guarded).
        msg = pr.shipped_message("foo", [])
        self.assertIn("already shipped — nothing to do", msg)


if __name__ == "__main__":
    unittest.main()
