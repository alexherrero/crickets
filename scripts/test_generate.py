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
if HAVE_YAML:
    emit_claude = _load("emit_claude")
    emit_antigravity = _load("emit_antigravity")


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
            self.assertEqual(sorted(seen),
                             ["code-review", "developer-safety",
                              "developer-workflows", "github-ci", "pii", "wiki-maintenance"])
            mk = json.loads((dist / "claude-code" / "marketplace.json").read_text())
            self.assertEqual({e["name"] for e in mk["plugins"]},
                             {"code-review", "developer-safety",
                              "developer-workflows", "github-ci", "pii", "wiki-maintenance"})

    def test_clean_removes_dist(self):
        with tempfile.TemporaryDirectory() as t:
            dist = Path(t) / "dist"
            (dist / "plugins").mkdir(parents=True)
            (dist / "x").write_text("y", encoding="utf-8")
            rc = generate.clean(dist=dist)
            self.assertEqual(rc, 0)
            self.assertFalse(dist.exists())


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestCheck(unittest.TestCase):
    def setUp(self):
        self._saved = dict(generate.EMITTERS)
        generate.EMITTERS.clear()
        generate.register(emit_claude.ClaudeEmitter())
        generate.register(emit_antigravity.AntigravityEmitter())
        self.tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self.tmp.name) / "dist"
        # temp repo-root so the real repo's root pointers aren't touched by tests
        self.root = Path(self.tmp.name) / "root"
        generate.build(src=_ROOT / "src", dist=self.dist, root=self.root)

    def tearDown(self):
        generate.EMITTERS.clear()
        generate.EMITTERS.update(self._saved)
        self.tmp.cleanup()

    def test_in_sync_passes(self):
        self.assertEqual(generate.check(src=_ROOT / "src", dist=self.dist, root=self.root), 0)

    def test_default_set_emitted(self):
        ds = json.loads((self.dist / "default-set.json").read_text(encoding="utf-8"))
        self.assertEqual(ds["plugins"],
                         ["code-review", "developer-safety",
                          "developer-workflows", "github-ci", "pii", "wiki-maintenance"])

    def test_changed_file_fails(self):
        f = next(self.dist.rglob("plugin.json"))
        f.write_text(f.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(generate.check(src=_ROOT / "src", dist=self.dist, root=self.root), 1)

    def test_missing_file_fails(self):
        next(self.dist.rglob("plugin.json")).unlink()
        self.assertEqual(generate.check(src=_ROOT / "src", dist=self.dist, root=self.root), 1)

    def test_extra_file_fails(self):
        (self.dist / "claude-code" / "STRAY.txt").write_text("x", encoding="utf-8")
        self.assertEqual(generate.check(src=_ROOT / "src", dist=self.dist, root=self.root), 1)

    # ── repo-root marketplace pointer (one-word GitHub install) ──────────────
    def test_root_pointers_emitted_with_dist_sources(self):
        cl = json.loads((self.root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(cl["name"], "crickets")
        srcs = {p["name"]: p["source"] for p in cl["plugins"]}
        self.assertEqual(srcs["developer-workflows"], "./dist/claude-code/plugins/developer-workflows")
        ag = json.loads((self.root / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        ag_srcs = {p["name"]: p["source"]["path"] for p in ag["plugins"]}
        self.assertEqual(ag_srcs["developer-workflows"], "./dist/antigravity/plugins/developer-workflows")

    def test_root_pointer_drift_fails(self):
        rp = self.root / ".claude-plugin" / "marketplace.json"
        rp.write_text(rp.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(generate.check(src=_ROOT / "src", dist=self.dist, root=self.root), 1)

    def test_root_pointer_missing_fails(self):
        (self.root / ".agents" / "plugins" / "marketplace.json").unlink()
        self.assertEqual(generate.check(src=_ROOT / "src", dist=self.dist, root=self.root), 1)


if __name__ == "__main__":
    unittest.main()
