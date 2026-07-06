#!/usr/bin/env python3
"""Tests for ci_diff_classifier.py — the job-level docs-only diet inside
ci-all's aggregate job (PLAN-per-plan-ci task 1).

Auto-discovered by check-all's `unit tests` gate.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name: str):
    src = _HERE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cdc = _load("ci_diff_classifier")


class TestIsDocsOnly(unittest.TestCase):
    def test_wiki_only_diff_is_docs_only(self):
        self.assertTrue(cdc.is_docs_only(["wiki/foo.md", "wiki/reference/Bar.md"]))

    def test_top_level_md_is_docs_only(self):
        self.assertTrue(cdc.is_docs_only(["README.md", "CHANGELOG.md"]))

    def test_mixed_wiki_and_md_is_docs_only(self):
        self.assertTrue(cdc.is_docs_only(["wiki/foo.md", "README.md"]))

    def test_one_code_file_among_many_docs_is_not_docs_only(self):
        self.assertFalse(cdc.is_docs_only(["wiki/foo.md", "scripts/bar.py"]))

    def test_pure_code_diff_is_not_docs_only(self):
        self.assertFalse(cdc.is_docs_only(["scripts/bar.py", "src/x/y.py"]))

    def test_non_md_file_inside_wiki_dir_is_still_docs_only(self):
        # wiki/** is a directory-prefix match, not conditioned on extension.
        self.assertTrue(cdc.is_docs_only(["wiki/assets/diagram.svg"]))

    def test_md_file_outside_repo_root_but_not_wiki_is_docs_only(self):
        # *.md matches anywhere by suffix, not just top-level.
        self.assertTrue(cdc.is_docs_only(["src/development-lifecycle/README.md"]))

    def test_empty_file_list_is_not_docs_only(self):
        # Conservative: an empty diff is never treated as a skip signal.
        self.assertFalse(cdc.is_docs_only([]))


class TestMainCLI(unittest.TestCase):
    def test_docs_only_exits_zero(self):
        self.assertEqual(cdc.main(["prog", "wiki/foo.md", "README.md"]), 0)

    def test_code_touching_exits_one(self):
        self.assertEqual(cdc.main(["prog", "wiki/foo.md", "scripts/bar.py"]), 1)

    def test_no_args_exits_two(self):
        self.assertEqual(cdc.main(["prog"]), 2)


if __name__ == "__main__":
    unittest.main()
