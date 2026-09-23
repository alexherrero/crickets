#!/usr/bin/env python3
"""Tests for check-no-harness-paths.py — the gate that keeps `_harness` out of the plugins."""
from __future__ import annotations

import importlib.util
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_no_harness_paths",
                                               HERE / "check-no-harness-paths.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


class Scratch(unittest.TestCase):
    """A scratch tree off git, so the gate walks it."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def put(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def hits(self, exempt=None):
        return gate.scan(self.root, exempt={} if exempt is None else exempt)


class WhatCounts(Scratch):
    def test_a_path_literal_is_a_hit(self):
        self.put("src/demo/scripts/w.py", 'd = vault / "_harness" / "x"\n')
        hits = self.hits()
        self.assertEqual([(h["rel"], h["line"], h["allowed"]) for h in hits],
                         [("src/demo/scripts/w.py", 1, None)])

    def test_a_comment_is_a_hit(self):
        self.put("src/demo/commands/c.md", "State lives in the vault `_harness/`.\n")
        self.assertEqual(len(self.hits()), 1)

    def test_identifiers_and_the_repo_local_dir_are_not_hits(self):
        self.put("src/demo/scripts/w.py",
                 "resolve_harness_root()\nfind_harness_memory()\n"
                 "_harness_memory_module = None\np = root / '.harness' / 'project.json'\n")
        self.assertEqual(self.hits(), [])

    def test_tests_are_scanned(self):
        self.put("scripts/test_demo.py", '(vault / "_harness").mkdir()\n')
        self.assertEqual(len(self.hits()), 1)

    def test_out_of_scope_paths_are_not_scanned(self):
        for rel in ("wiki/Page.md", "CHANGELOG.md", "dist/claude-code/x.py", "README.md"):
            self.put(rel, "the vault `_harness/`\n")
        self.assertEqual(self.hits(), [])


class WhatIsAllowed(Scratch):
    def test_the_line_marker(self):
        self.put("src/demo/scripts/w.py",
                 'OLD = "_harness"  # harness-deprecation: the retired name\n')
        self.assertEqual([h["allowed"] for h in self.hits()], ["marker"])

    def test_the_file_marker(self):
        self.put("src/demo/scripts/m.py",
                 '"""A finished migration. harness-deprecation: file"""\nX = "_harness"\n')
        self.assertEqual([h["allowed"] for h in self.hits()], ["marker (file)"])

    def test_an_exempt_file(self):
        self.put("src/demo/scripts/w.py", 'd = "_harness"\n')
        hits = self.hits({"src/demo/scripts/w.py": "task 999"})
        self.assertEqual([h["allowed"] for h in hits], ["exempt: task 999"])

    def test_an_exempt_file_with_no_hits_is_stale(self):
        self.put("src/demo/scripts/w.py", "clean = True\n")
        exempt = {"src/demo/scripts/w.py": "task 999"}
        self.assertEqual(gate.stale_exemptions(self.hits(exempt), exempt),
                         ["src/demo/scripts/w.py"])


class TheRepo(unittest.TestCase):
    """The gate on this repo: every hit is exempt, marked, or gone."""

    def test_the_repo_is_clean(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = gate.main([])
        self.assertEqual(rc, 0, err.getvalue())

    def test_every_exemption_names_a_landing(self):
        for rel, owner in gate.EXEMPT.items():
            self.assertTrue(owner.startswith(("100-", "101-")), rel)

    def test_inventory_exits_0(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = gate.main(["--inventory"])
        self.assertEqual(rc, 0)
        self.assertIn("check-no-harness-paths: inventory", out.getvalue())


if __name__ == "__main__":
    unittest.main()
