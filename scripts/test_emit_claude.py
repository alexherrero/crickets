#!/usr/bin/env python3
"""Tests for scripts/emit_claude.py (crickets v3.0 #40, part 2)."""
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
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

if HAVE_YAML:
    generate = _load("generate")
    emit_claude = _load("emit_claude")


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestClaudeEmitter(unittest.TestCase):
    def setUp(self):
        self._saved = dict(generate.EMITTERS)
        generate.EMITTERS.clear()
        generate.register(emit_claude.ClaudeEmitter())
        self.tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self.tmp.name) / "dist"
        generate.build(src=_ROOT / "src", dist=self.dist)

    def tearDown(self):
        generate.EMITTERS.clear()
        generate.EMITTERS.update(self._saved)
        self.tmp.cleanup()

    def _plugin_json(self, slug):
        p = self.dist / "plugins" / slug / ".claude-plugin" / "plugin.json"
        return json.loads(p.read_text(encoding="utf-8"))

    def test_plugin_json_per_group(self):
        for slug in ("developer", "pii", "github-ci", "wiki"):
            d = self._plugin_json(slug)
            self.assertEqual(d["name"], slug)
            self.assertTrue(d.get("description"))
            self.assertEqual(d["version"], "0.1.0")

    def test_dependencies_from_requires(self):
        self.assertEqual(self._plugin_json("github-ci").get("dependencies"), ["developer"])
        self.assertEqual(self._plugin_json("wiki").get("dependencies"), ["developer"])
        self.assertNotIn("dependencies", self._plugin_json("pii"))
        self.assertNotIn("dependencies", self._plugin_json("developer"))

    def test_components_copied(self):
        d = self.dist / "plugins"
        self.assertTrue((d / "pii" / "skills" / "pii-scrubber" / "SKILL.md").exists())
        self.assertTrue((d / "github-ci" / "skills" / "dependabot-fixer" / "SKILL.md").exists())
        self.assertTrue((d / "developer" / "agents" / "evaluator.md").exists())
        self.assertTrue((d / "wiki" / "agents" / "diataxis-evaluator.md").exists())

    def test_marketplace_lists_all_with_resolving_sources(self):
        mk = json.loads((self.dist / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual({p["name"] for p in mk["plugins"]}, {"developer", "pii", "github-ci", "wiki"})
        for p in mk["plugins"]:
            self.assertEqual(p["source"], f"./plugins/{p['name']}")
            self.assertTrue((self.dist / "plugins" / p["name"]).is_dir())

    def test_deterministic_rebuild(self):
        tmp2 = tempfile.TemporaryDirectory()
        try:
            dist2 = Path(tmp2.name) / "dist"
            generate.build(src=_ROOT / "src", dist=dist2)
            f1 = sorted(p.relative_to(self.dist) for p in self.dist.rglob("*") if p.is_file())
            f2 = sorted(p.relative_to(dist2) for p in dist2.rglob("*") if p.is_file())
            self.assertEqual(f1, f2)
            for rel in f1:
                self.assertEqual((self.dist / rel).read_bytes(), (dist2 / rel).read_bytes(), rel)
        finally:
            tmp2.cleanup()


if __name__ == "__main__":
    unittest.main()
