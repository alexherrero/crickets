#!/usr/bin/env python3
"""/bugfix's Analyze phase, wired to the shared /diagnose engine as additive
context (PLAN-wave-d-cross-wiring task 2).

Replicates test_diagnostics_diagnose_e2e.py's calling-convention pattern
(importlib sibling-load of diagnose.py, call diagnose() directly), applied to
the two cases bugfix.md's Analyze step documents:

  - A prior matching failure-incident exists (Layer-1 hit) -> the mechanized
    step surfaces the prior path/hypotheses as a starting hypothesis set,
    BEFORE the manual explorer dispatch / "ask why three times" pass runs.
  - No prior incident (cold start) -> the mechanized step still writes a new
    incident (graceful no-op for the Analyze write-up: an empty hypothesis
    seed, never an error), and the manual flow proceeds unblocked.

/diagnose ranks hypotheses; it does not conclude root cause -- this is
additive context for the existing "ask why three times" pass, never a
replacement for it (locked design call). This test only exercises the
mechanized seed step; it does not simulate the manual reasoning pass itself.

Also asserts (statically, on bugfix.md's own text) that the Analyze phase
documents the diagnose() call ahead of the explorer dispatch, and that the
manual "ask why three times" root-cause pass is still present and unchanged
in framing.

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
_BUGFIX_MD = _ROOT / "src" / "development-lifecycle" / "commands" / "bugfix.md"

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


diagnose_mod = _load("bugfix_cross_wiring_diagnose", _DIAGNOSE_SRC / "diagnose.py")


def _analysis_hypothesis_seed(result: dict) -> list:
    """The mechanized Analyze-phase seed step (PLAN-wave-d-cross-wiring task 2):
    fold diagnose()'s namespace/hypotheses/prior-incident path into a starting
    hypothesis set for ## Analysis -- additive, never a conclusion."""
    if result["outcome"] == "layer1_hit":
        return [f"Prior incident on file: {result['path']} (namespace: {result['namespace']})"]
    return list(result.get("hypotheses", []))


class BugfixAnalyzeDiagnoseWiringTests(unittest.TestCase):
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

    def test_layer1_hit_seeds_analysis_before_explorer_dispatch(self):
        traceback_text = (
            "Traceback (most recent call last):\n"
            '  File "/Users/alexherrero/proj/app.py", line 88, in handle\n'
            "    raise ValueError(\"malformed payload: missing 'id' field\")\n"
            "ValueError: malformed payload: missing 'id' field\n"
        )
        first = diagnose_mod.diagnose(
            vault=self.vault, project="crickets", traceback_text=traceback_text,
        )
        self.assertEqual(first["outcome"], "written")

        # Simulated reproduction of the *same* bug in a later /bugfix run.
        second = diagnose_mod.diagnose(
            vault=self.vault, project="crickets", traceback_text=traceback_text,
        )
        self.assertEqual(second["outcome"], "layer1_hit")

        seed = _analysis_hypothesis_seed(second)
        self.assertEqual(len(seed), 1)
        self.assertIn(second["path"], seed[0])

    def test_cold_start_yields_empty_seed_not_an_error(self):
        traceback_text = (
            'proj/module.py:99: error: Argument 1 to "bar" has incompatible '
            'type "str"; expected "int"\nFound 1 error in 1 file\n'
        )
        result = diagnose_mod.diagnose(
            vault=self.vault, project="crickets", traceback_text=traceback_text, tool="mypy",
        )
        self.assertEqual(result["outcome"], "written")
        seed = _analysis_hypothesis_seed(result)
        # Cold start: no prior incident, but diagnose() still ranks a generic
        # fallback hypothesis -- never an empty list, never an error/exception.
        self.assertGreaterEqual(len(seed), 1)
        self.assertLessEqual(len(seed), 3)

    def test_bugfix_md_documents_diagnose_seed_ahead_of_explorer_dispatch(self):
        text = _BUGFIX_MD.read_text(encoding="utf-8")
        analyze_start = text.index("### 2. Analyze")
        fix_start = text.index("### 3. Fix")
        analyze_section = text[analyze_start:fix_start]

        self.assertIn("diagnose.py", analyze_section)
        diagnose_idx = analyze_section.index("diagnose.py")
        explorer_idx = analyze_section.index("dispatch the `explorer` sub-agent")
        self.assertLess(
            diagnose_idx, explorer_idx,
            "diagnose() call must be documented before the explorer dispatch",
        )
        # Additive, not a replacement -- the "ask why three times" pass must survive.
        self.assertIn('Ask "why" three times', analyze_section)


if __name__ == "__main__":
    unittest.main()
