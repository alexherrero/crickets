#!/usr/bin/env python3
"""dependabot-fixer's diagnosis step, recast onto the shared /diagnose engine
(PLAN-wave-d-cross-wiring task 1).

Replicates test_diagnostics_diagnose_e2e.py's calling-convention pattern
(importlib sibling-load of diagnose.py, call diagnose() directly) but exercises
it through the confidence-gate proxy dependabot-fixer's SKILL.md now documents:

  - Cold start (`outcome == "written"`, no similar-incident hypothesis) -> ABORT.
  - Recurrence (`outcome == "layer1_hit"`, or a Layer-2 candidate with a real
    prior fix) -> PROCEED, using the recalled prior as the proposed-fix seed.

This is the locked proxy mapping from the plan's "Locked design calls" section --
/diagnose has no confidence score, so this mapping is the semantic bridge that
replaces dependabot-fixer's old inline category+confidence gate.

Also asserts (statically, on SKILL.md's own text) that the old inline
category+confidence reasoning is gone and the file documents a call to
diagnose() instead -- task 3's portfolio-consistency check re-asserts this
repo-wide; this local check is the red-test-first proof for task 1 itself.

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
_DIAGNOSE_SRC = _ROOT / "src" / "diagnostics" / "scripts"
_SKILL_MD = _ROOT / "src" / "maintenance" / "skills" / "dependabot-fixer" / "SKILL.md"

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


diagnose_mod = _load("cross_wiring_diagnose", _DIAGNOSE_SRC / "diagnose.py")


def _confidence_gate_decision(result: dict) -> str:
    """The locked proxy mapping (PLAN-wave-d-cross-wiring, Locked design calls):

    abort  <- outcome == "written" with no similar-incident hypothesis (cold
              start / Layer-2 miss -- nothing to go on)
    proceed <- outcome == "layer1_hit", or a Layer-2 candidate carries a real
               prior fix (a "Similar to existing incident..." hypothesis)
    """
    if result["outcome"] == "layer1_hit":
        return "proceed"
    hypotheses = result.get("hypotheses", [])
    has_prior_fix = any(h.startswith("Similar to existing incident") for h in hypotheses)
    return "proceed" if has_prior_fix else "abort"


class DependabotFixerDiagnoseWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pre_existing_modules = set(sys.modules)
        if diagnose_mod.writer.agentm_bridge.load_save_module() is None:
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

    def test_cold_start_aborts_recurrence_proceeds_with_prior_fix(self):
        traceback_text = (
            "Traceback (most recent call last):\n"
            '  File "/Users/alexherrero/proj/ci.py", line 42, in build\n'
            "    raise RuntimeError(\"incompatible peer dependency: libbar>=2.0\")\n"
            "RuntimeError: incompatible peer dependency: libbar>=2.0\n"
        )

        first = diagnose_mod.diagnose(
            vault=self.vault,
            project="crickets",
            traceback_text=traceback_text,
            tool="ci",
        )
        self.assertEqual(first["outcome"], "written")
        self.assertEqual(_confidence_gate_decision(first), "abort")

        second = diagnose_mod.diagnose(
            vault=self.vault,
            project="crickets",
            traceback_text=traceback_text,
            tool="ci",
        )
        self.assertEqual(second["outcome"], "layer1_hit")
        self.assertEqual(second["path"], first["path"])
        self.assertEqual(_confidence_gate_decision(second), "proceed")

    def test_skill_md_documents_diagnose_call_not_inline_reasoning(self):
        text = _SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("diagnose.py", text)
        self.assertNotIn("failure category, confidence (high/medium/low)", text)
        self.assertIn("layer1_hit", text)
        self.assertIn("written", text)


if __name__ == "__main__":
    unittest.main()
