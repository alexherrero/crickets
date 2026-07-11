#!/usr/bin/env python3
"""Drift-prevention test for the shared `_candidate_dirs()` cascade across the
three cross-plugin `agentm_bridge.py` copies (task 3, CONS-2 crickets-slim).

`src/diagnostics/scripts/agentm_bridge.py`, `src/maintenance/scripts/agentm_bridge.py`,
and `src/research/scripts/agentm_bridge.py` are deliberate cross-plugin
duplicates (same rationale as `pr_helpers.py` vs `wiki_watch_dispatch.py`:
plugin version dirs diverge, so cross-plugin import is structurally
unavailable at runtime). Each module's `_candidate_dirs()` implements the
identical env -> co-located -> conventional-clone path-fallback cascade —
unlike `pr_helpers.py`'s contract (which only pins a behavioral ordering
invariant and explicitly tolerates independent evolution), `_candidate_dirs()`
has no reason to differ between copies at all, so this test pins full
source-text identity, not just a weaker behavioral contract.

(The development-lifecycle plugin's own bridge family, merged into ONE
`agentm_bridge.py` under src/development-lifecycle/scripts/ by task 2, is a
disjoint, already-consolidated set and is out of scope here — see task 2's
locked design call in PLAN-cons-2-crickets-slim.md.)

What it asserts:
  - `_candidate_dirs` exists and is callable in all three modules
  - the three functions' source text (via inspect.getsource) is pairwise
    identical -- this is what "diverge from each other" means for a
    same-shape helper that is copy-pasted verbatim across plugins
  - as a behavioral cross-check, all three produce the same candidate list
    shape (same length, same suffix segments) when the module's own `here`
    is substituted for comparison and $AGENTM_SCRIPTS_DIR is unset

If any one of the three copies edits `_candidate_dirs()` without updating
the other two in lockstep, this test fails loudly -- that's the point.

Auto-discovered by check-all's `unit tests` gate
(`python3 -m unittest discover -p 'test_*.py'` run from scripts/).
"""
from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_MODULES = {
    "diagnostics": _ROOT / "src" / "diagnostics" / "scripts",
    "maintenance": _ROOT / "src" / "maintenance" / "scripts",
    "research": _ROOT / "src" / "research" / "scripts",
}


def _load(name: str, path: Path):
    src = path / "agentm_bridge.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


_diagnostics = _load("agentm_bridge_diagnostics", _MODULES["diagnostics"])
_maintenance = _load("agentm_bridge_maintenance", _MODULES["maintenance"])
_research = _load("agentm_bridge_research", _MODULES["research"])

_PLUGIN_MODULES = {
    "diagnostics": _diagnostics,
    "maintenance": _maintenance,
    "research": _research,
}


class TestCandidateDirsExists(unittest.TestCase):
    """Structural check: `_candidate_dirs` is present + callable in all three."""

    def test_all_three_have_candidate_dirs(self):
        for plugin, module in _PLUGIN_MODULES.items():
            with self.subTest(plugin=plugin):
                self.assertTrue(
                    callable(getattr(module, "_candidate_dirs", None)),
                    f"{plugin}'s agentm_bridge.py is missing a callable _candidate_dirs()",
                )


class TestCandidateDirsSourceIdentical(unittest.TestCase):
    """The load-bearing invariant: the three `_candidate_dirs()` bodies must
    stay byte-identical. There is no plugin-specific reason for this cascade
    to differ -- if it ever does, that's drift, not intentional divergence."""

    def _source(self, module) -> str:
        return inspect.getsource(module._candidate_dirs)

    def test_diagnostics_matches_maintenance(self):
        self.assertEqual(
            self._source(_diagnostics), self._source(_maintenance),
            "diagnostics/agentm_bridge.py's _candidate_dirs() has drifted from "
            "maintenance/agentm_bridge.py's -- reconcile both copies or update "
            "this test deliberately if the divergence is now intentional.",
        )

    def test_diagnostics_matches_research(self):
        self.assertEqual(
            self._source(_diagnostics), self._source(_research),
            "diagnostics/agentm_bridge.py's _candidate_dirs() has drifted from "
            "research/agentm_bridge.py's -- reconcile both copies or update "
            "this test deliberately if the divergence is now intentional.",
        )

    def test_maintenance_matches_research(self):
        self.assertEqual(
            self._source(_maintenance), self._source(_research),
            "maintenance/agentm_bridge.py's _candidate_dirs() has drifted from "
            "research/agentm_bridge.py's -- reconcile both copies or update "
            "this test deliberately if the divergence is now intentional.",
        )


class TestCandidateDirsBehaviorParity(unittest.TestCase):
    """Cross-check the source-identity assertion with an actual call: same
    env-var handling, same candidate count, same trailing path segments."""

    def setUp(self):
        self._prior_env = os.environ.pop("AGENTM_SCRIPTS_DIR", None)

    def tearDown(self):
        if self._prior_env is not None:
            os.environ["AGENTM_SCRIPTS_DIR"] = self._prior_env

    def test_same_candidate_count_with_env_unset(self):
        counts = {plugin: len(module._candidate_dirs()) for plugin, module in _PLUGIN_MODULES.items()}
        self.assertEqual(
            len(set(counts.values())), 1,
            f"candidate-dir counts diverge across plugins with $AGENTM_SCRIPTS_DIR unset: {counts}",
        )

    def test_same_conventional_clone_fallback(self):
        # The final candidate ("conventional clone") is always
        # ~/Antigravity/agentm/harness/skills/memory/scripts across all three.
        expected = Path.home() / "Antigravity" / "agentm" / "harness" / "skills" / "memory" / "scripts"
        for plugin, module in _PLUGIN_MODULES.items():
            with self.subTest(plugin=plugin):
                candidates = module._candidate_dirs()
                self.assertEqual(
                    candidates[-1], expected,
                    f"{plugin}'s _candidate_dirs() conventional-clone fallback diverged from the shared convention",
                )

    def test_env_var_honored_identically(self):
        os.environ["AGENTM_SCRIPTS_DIR"] = "/tmp/fake-agentm-scripts-dir"
        try:
            expected = Path("/tmp/fake-agentm-scripts-dir")
            for plugin, module in _PLUGIN_MODULES.items():
                with self.subTest(plugin=plugin):
                    candidates = module._candidate_dirs()
                    self.assertEqual(
                        candidates[0], expected,
                        f"{plugin}'s _candidate_dirs() didn't honor $AGENTM_SCRIPTS_DIR as the first candidate",
                    )
        finally:
            del os.environ["AGENTM_SCRIPTS_DIR"]


if __name__ == "__main__":
    unittest.main()
