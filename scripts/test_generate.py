#!/usr/bin/env python3
"""Tests for scripts/generate.py core (crickets v3.0 #40, part 2)."""
from __future__ import annotations

import importlib.util
import json
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

generate = _load("generate") if HAVE_YAML else None


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestDumpJson(unittest.TestCase):
    def test_deterministic_sorted(self):
        a = generate.dump_json({"b": 1, "a": 2})
        b = generate.dump_json({"a": 2, "b": 1})
        self.assertEqual(a, b)
        self.assertTrue(a.endswith("\n"))
        self.assertEqual(json.loads(a), {"a": 2, "b": 1})


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestBuildClean(unittest.TestCase):
    def setUp(self):
        self._saved = dict(generate.EMITTERS)
        generate.EMITTERS.clear()

    def tearDown(self):
        generate.EMITTERS.clear()
        generate.EMITTERS.update(self._saved)

    def test_build_no_emitters_is_noop(self):
        with tempfile.TemporaryDirectory() as t:
            dist = Path(t) / "dist"
            rc = generate.build(src=_ROOT / "src", dist=dist)
            self.assertEqual(rc, 0)
            self.assertFalse(dist.exists())  # no emitters → nothing written

    def test_build_runs_emitter_per_supporting_group(self):
        seen = []

        class Fake(generate.HostEmitter):
            host = "claude-code"  # every group supports it

            def emit_group(self, group, dist_root):
                seen.append(group.slug)
                d = dist_root / "plugins" / group.slug
                d.mkdir(parents=True, exist_ok=True)
                (d / "marker").write_text("x", encoding="utf-8")
                return {"name": group.slug, "source": f"./plugins/{group.slug}"}

            def write_marketplace(self, entries, dist_root):
                (dist_root / "marketplace.json").write_text(
                    generate.dump_json({"plugins": entries}), encoding="utf-8")

        generate.register(Fake())
        with tempfile.TemporaryDirectory() as t:
            dist = Path(t) / "dist"
            rc = generate.build(src=_ROOT / "src", dist=dist)
            self.assertEqual(rc, 0)
            self.assertEqual(sorted(seen), ["developer", "github-ci", "pii", "wiki"])
            mk = json.loads((dist / "marketplace.json").read_text())
            self.assertEqual({e["name"] for e in mk["plugins"]},
                             {"developer", "github-ci", "pii", "wiki"})

    def test_clean_removes_dist(self):
        with tempfile.TemporaryDirectory() as t:
            dist = Path(t) / "dist"
            (dist / "plugins").mkdir(parents=True)
            (dist / "x").write_text("y", encoding="utf-8")
            rc = generate.clean(dist=dist)
            self.assertEqual(rc, 0)
            self.assertFalse(dist.exists())


if __name__ == "__main__":
    unittest.main()
