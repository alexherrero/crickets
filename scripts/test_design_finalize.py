#!/usr/bin/env python3
"""Tests for src/design/scripts/design_finalize.py -- `/design finalize`
tooling (crickets wave-c-design-and-conventions, task 3).

The tool (a) flags a stale [PENDING-IMPL] placeholder as a finding rather
than silently collapsing over it, and (b) collapses the amendment log
correctly when there's no such flag.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "design" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


design_finalize = _load("design_finalize_module", _SRC / "design_finalize.py")


class StalePlaceholderTests(unittest.TestCase):
    def test_a_stale_placeholder_is_flagged_not_silently_collapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "fixture-shipped").mkdir()
            (repo_root / "fixture-shipped" / "primitive.py").write_text("x", encoding="utf-8")
            doc = repo_root / "fixture-design.md"
            doc.write_text(
                "---\ntitle: Fixture\nstatus: launched\nkind: design\n"
                "governs:\n  - fixture-shipped/**\n---\n\n"
                "# Fixture\n\n"
                "**[PENDING-IMPL]** — build the primitive (documenter); it does not exist today.\n\n"
                "## Amendment log\n\n"
                "**2026-07-01** — seeded.\n",
                encoding="utf-8",
            )
            result = design_finalize.finalize(doc, repo_root)
            self.assertTrue(result["stale"]["stale"])
            self.assertIsNone(result["collapsed_text"])

    def test_a_genuinely_unbuilt_placeholder_is_not_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            doc = repo_root / "fixture-design.md"
            doc.write_text(
                "---\ntitle: Fixture\nstatus: launched\nkind: design\n"
                "governs:\n  - fixture-never-built/**\n---\n\n"
                "# Fixture\n\n"
                "**[PENDING-IMPL]** — build the primitive (documenter); it does not exist today.\n\n"
                "## Amendment log\n\n"
                "**2026-07-01** — seeded.\n",
                encoding="utf-8",
            )
            result = design_finalize.finalize(doc, repo_root)
            self.assertFalse(result["stale"]["stale"])
            self.assertIsNotNone(result["collapsed_text"])


class AmendmentLogCollapseTests(unittest.TestCase):
    def test_clean_fixture_amendment_log_collapses_same_day_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            doc = repo_root / "clean-design.md"
            doc.write_text(
                "---\ntitle: Fixture\nstatus: launched\nkind: design\n---\n\n"
                "# Fixture\n\nSome body text, not touched.\n\n"
                "## Amendment log\n\n"
                "**2026-07-06** — first change today.\n"
                "**2026-07-06** — second change today.\n"
                "**2026-07-01** — an earlier day, stays separate.\n",
                encoding="utf-8",
            )
            result = design_finalize.finalize(doc, repo_root)
            self.assertFalse(result["stale"]["stale"])
            collapsed = result["collapsed_text"]
            self.assertIn("# Fixture\n\nSome body text, not touched.", collapsed)
            self.assertEqual(
                collapsed.count("**2026-07-06**"), 1,
                "same-day entries should collapse into exactly one bullet",
            )
            self.assertIn("first change today. second change today.", collapsed)
            self.assertIn("**2026-07-01** — an earlier day, stays separate.", collapsed)


class DesignCommandOffersFinalizeTests(unittest.TestCase):
    def test_design_command_documents_the_finalize_verb(self):
        text = (_ROOT / "src" / "design" / "commands" / "design.md").read_text(encoding="utf-8")
        self.assertIn("design finalize", text)
        self.assertIn("design_finalize.py", text)


if __name__ == "__main__":
    unittest.main()
