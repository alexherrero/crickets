#!/usr/bin/env python3
"""Tests for scripts/emit_antigravity.py (crickets v3.0 #40, part 3)."""
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
    emit_antigravity = _load("emit_antigravity")


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestAntigravityEmitter(unittest.TestCase):
    def setUp(self):
        self._saved = dict(generate.EMITTERS)
        generate.EMITTERS.clear()
        generate.register(emit_antigravity.AntigravityEmitter())
        self.tmp = tempfile.TemporaryDirectory()
        self.dist = Path(self.tmp.name) / "dist"
        generate.build(src=_ROOT / "src", dist=self.dist)
        self.agdist = self.dist / "antigravity"

    def tearDown(self):
        generate.EMITTERS.clear()
        generate.EMITTERS.update(self._saved)
        self.tmp.cleanup()

    def _plugin_json(self, slug):
        return json.loads((self.agdist / "plugins" / slug / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    def test_plugin_json_no_native_dependencies(self):
        # AG composition is thin — plugin.json never carries dependencies.
        for slug in ("developer", "pii", "github-ci", "wiki"):
            d = self._plugin_json(slug)
            self.assertEqual(d["name"], slug)
            self.assertNotIn("dependencies", d)
            self.assertIn("author", d)

    def test_components_copied_for_ag_supporting_only(self):
        d = self.agdist / "plugins"
        self.assertTrue((d / "pii" / "skills" / "pii-scrubber" / "SKILL.md").exists())
        self.assertTrue((d / "github-ci" / "skills" / "dependabot-fixer" / "SKILL.md").exists())
        self.assertTrue((d / "developer" / "agents" / "evaluator.md").exists())
        self.assertTrue((d / "wiki" / "agents" / "diataxis-evaluator.md").exists())

    def test_thin_composition_no_inlined_base(self):
        # github-ci requires developer but carries ONLY its own primitive — no
        # developer components inlined.
        gci = self.agdist / "plugins" / "github-ci"
        self.assertFalse((gci / "agents" / "evaluator.md").exists())
        self.assertEqual([p.name for p in (gci / "skills").iterdir()], ["dependabot-fixer"])

    def test_marketplace_ag_shape(self):
        mk = json.loads((self.agdist / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(mk["interface"]["displayName"], "Crickets")
        by = {p["name"]: p for p in mk["plugins"]}
        self.assertEqual(set(by), {"developer", "pii", "github-ci", "wiki"})
        for p in mk["plugins"]:
            self.assertEqual(p["source"], {"source": "local", "path": f"./plugins/{p['name']}"})
            self.assertEqual(p["policy"]["installation"], "AVAILABLE")
            self.assertEqual(p["category"], "Coding")
        # requires documented (thin) on dependents, absent on standalone
        self.assertEqual(by["github-ci"]["requires"], ["developer"])
        self.assertEqual(by["wiki"]["requires"], ["developer"])
        self.assertNotIn("requires", by["pii"])
        self.assertNotIn("requires", by["developer"])

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
