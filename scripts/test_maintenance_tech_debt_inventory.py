#!/usr/bin/env python3
"""Tests for src/maintenance/scripts/tech_debt_inventory.py (crickets
wave-c-maintenance, task 3).

Integration-style (not mocked): exercises the real bridge to agentm's
save_entry(), so the standing-backlog idempotency guarantee is proven
end-to-end. See test_diagnostics_writer.py for the real-bridge sys.path/
sys.modules purge rationale this mirrors.

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


tech_debt_inventory = _load("maintenance_tech_debt_inventory", _SRC / "tech_debt_inventory.py")


_OVERSIZED_FUNCTION_SRC = "def oversized():\n" + "\n".join(f"    x{i} = {i}" for i in range(60)) + "\n    return x0\n"


class TechDebtInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pre_existing_modules = set(sys.modules)
        if tech_debt_inventory.agentm_bridge.load_save_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmp.name) / "repo"
        self.vault = Path(self._tmp.name) / "vault"
        self.repo_root.mkdir()
        self.vault.mkdir()
        (self.repo_root / "todo_module.py").write_text(
            "# TODO: replace this stub with a real implementation\ndef stub():\n    pass\n",
            encoding="utf-8",
        )
        (self.repo_root / "oversized_module.py").write_text(_OVERSIZED_FUNCTION_SRC, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_planted_debt_items_each_produce_exactly_one_classified_entry(self):
        written = tech_debt_inventory.scan_and_record(self.repo_root, self.vault)
        self.assertEqual(len(written), 2)
        entries = list((self.vault / "personal" / "debt").glob("*.md"))
        self.assertEqual(len(entries), 2)
        contents = [p.read_text(encoding="utf-8") for p in entries]
        self.assertTrue(any("tags: [documentation]" in c for c in contents))
        self.assertTrue(any("tags: [refactoring]" in c for c in contents))

    def test_rerun_against_unchanged_repo_produces_zero_duplicates(self):
        tech_debt_inventory.scan_and_record(self.repo_root, self.vault)
        second_run_written = tech_debt_inventory.scan_and_record(self.repo_root, self.vault)
        self.assertEqual(second_run_written, [])
        entries = list((self.vault / "personal" / "debt").glob("*.md"))
        self.assertEqual(len(entries), 2)


if __name__ == "__main__":
    unittest.main()
