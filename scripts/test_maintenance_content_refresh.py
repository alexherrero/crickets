#!/usr/bin/env python3
"""Tests for src/maintenance/scripts/content_refresh.py (crickets
wave-c-maintenance, task 4).

Proven by its two named first consumers (crickets-maintenance.md), not a
general-purpose test suite invented for this plan: the pricing.py mechanical
re-pin, and the routing-tier-scale judgment-bound case. Integration-style
against the real agentm save_entry() bridge for the judgment-bound path --
see test_diagnostics_writer.py for the real-bridge purge rationale mirrored
here.

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
_SRC = _ROOT / "src" / "maintenance" / "scripts"

_AGENTM_PATH_MARKERS = ("/agentm/harness/", "/agentm/scripts/")
_REAL_BRIDGE_SYS_PATH_MARKER = "/agentm/harness/skills/memory/scripts"


def _purge_real_bridge_sys_path():
    sys.path[:] = [p for p in sys.path if _REAL_BRIDGE_SYS_PATH_MARKER not in p]


def _purge_agentm_modules(pre_existing_names):
    for name, mod in list(sys.modules.items()):
        if name in pre_existing_names:
            continue
        f = getattr(mod, "__file__", None)
        if f and any(marker in f for marker in _AGENTM_PATH_MARKERS):
            del sys.modules[name]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


content_refresh = _load("maintenance_content_refresh", _SRC / "content_refresh.py")


class ContentRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pre_existing_modules = set(sys.modules)
        if content_refresh.agentm_bridge.load_save_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name) / "vault"
        self.vault.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_mechanical_consumer_pricing_rename_auto_applies_with_minimal_diff(self):
        pricing_path = Path(self._tmp.name) / "pricing.py"
        original = 'PRICING = {\n    "claude-opus-4-7": 15.0,\n    "claude-sonnet-5": 3.0,\n}\n'
        pricing_path.write_text(original, encoding="utf-8")
        item = {"old_ref": "claude-opus-4-7", "new_ref": "claude-opus-4-8"}

        result = content_refresh.refresh(pricing_path, item, self.vault)

        self.assertEqual(result["classification"], "mechanical")
        self.assertTrue(result["applied"])
        expected = original.replace("claude-opus-4-7", "claude-opus-4-8")
        self.assertEqual(pricing_path.read_text(encoding="utf-8"), expected)

    def test_judgment_bound_consumer_new_model_makes_zero_chart_edits(self):
        chart_path = Path(self._tmp.name) / "routing_chart.md"
        original = "| Model | Tier |\n|---|---|\n| claude-opus-4-8 | T3 |\n"
        chart_path.write_text(original, encoding="utf-8")
        item = {
            "old_ref": None, "new_ref": "claude-fable-6",
            "context": "a genuinely new model, needs a tier placement -- not a drop-in rename",
        }

        result = content_refresh.refresh(chart_path, item, self.vault)

        self.assertEqual(result["classification"], "judgment-bound")
        self.assertFalse(result["applied"])
        self.assertEqual(chart_path.read_text(encoding="utf-8"), original)
        entries = list((self.vault / "personal" / "content-refresh-watchlist").glob("*.md"))
        self.assertEqual(len(entries), 1)


if __name__ == "__main__":
    unittest.main()
