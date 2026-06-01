#!/usr/bin/env python3
"""Tests for scripts/src_model.py (crickets v3.0 #40, part 2)."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m  # dataclasses resolve field types via sys.modules[__module__]
    spec.loader.exec_module(m)
    return m


try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

src_model = _load("src_model") if HAVE_YAML else None


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestSrcModel(unittest.TestCase):
    def test_real_tree_shape(self):
        groups = src_model.load_groups(_ROOT / "src")
        by = {g.slug: g for g in groups}
        self.assertEqual(set(by), {"developer", "github-ci", "pii", "wiki"})
        # composition
        self.assertEqual(by["github-ci"].requires, ["developer"])
        self.assertEqual(by["wiki"].requires, ["developer"])
        self.assertEqual(by["pii"].requires, [])
        self.assertTrue(by["pii"].standalone)
        self.assertFalse(by["github-ci"].standalone)
        # primitive counts: developer = 3 hooks + evaluator agent
        self.assertEqual(len(by["developer"].primitives), 4)
        self.assertEqual(len(by["pii"].primitives), 1)
        self.assertEqual(sum(len(g.primitives) for g in groups), 7)
        # a primitive's shape
        prims = {p.name: p for p in by["developer"].primitives}
        self.assertEqual(prims["commit-on-stop"].kind, "hook")
        self.assertIn("claude-code", prims["commit-on-stop"].supported_hosts)

    def test_supports_host(self):
        by = {g.slug: g for g in src_model.load_groups(_ROOT / "src")}
        self.assertTrue(by["developer"].supports("claude-code"))

    def test_deterministic_order(self):
        a = [g.slug for g in src_model.load_groups(_ROOT / "src")]
        b = [g.slug for g in src_model.load_groups(_ROOT / "src")]
        self.assertEqual(a, b)
        self.assertEqual(a, sorted(a))

    def test_missing_src_returns_empty(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(src_model.load_groups(Path(t) / "nope"), [])


if __name__ == "__main__":
    unittest.main()
