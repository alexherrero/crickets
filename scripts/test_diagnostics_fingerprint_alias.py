#!/usr/bin/env python3
"""Tests for the fingerprint alias mechanism (crickets wave-c-diagnostics, task 3).

Self-reinforcing convergence: a confident Layer-2 semantic match on a drifted
fingerprint attaches that new fingerprint as an alias of the existing incident,
so a *second* recall on the same drifted fingerprint resolves via Layer-1 --
not Layer-2 again. A weak (below-threshold) Layer-2 match must NOT auto-alias.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "diagnostics" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


fpi = _load("diagnostics_fingerprint_index_alias", _SRC / "fingerprint_index.py")
ladder = _load("diagnostics_recall_ladder_alias", _SRC / "recall_ladder.py")
bridge = ladder.agentm_bridge

_CANONICAL_PATH = "projects/crickets/failure-incident/known.md"


class FingerprintAliasMechanismTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        fpi.record(self.vault, "fp-A", "crickets", _CANONICAL_PATH)

    def tearDown(self):
        self._tmp.cleanup()

    def test_confident_layer2_match_attaches_alias_and_converges_to_layer1(self):
        confident_hit = [{"path": _CANONICAL_PATH, "score": 0.9}]
        with mock.patch.object(bridge, "query_semantic", return_value=confident_hit) as spy:
            first = ladder.recall(
                vault=self.vault,
                fingerprint="fp-B-drifted",
                project="crickets",
                query_text="ValueError in classify (drifted)",
                namespace="runtime",
            )
        spy.assert_called_once()
        self.assertEqual(first["layer"], 2)

        # The alias must already be resolvable via a direct Layer-1 lookup.
        self.assertEqual(fpi.lookup(self.vault, "fp-B-drifted", "crickets"), _CANONICAL_PATH)

        # A second recall on the drifted fingerprint alone must now be a
        # Layer-1 hit -- semantic search must NOT run again.
        with mock.patch.object(bridge, "query_semantic") as spy2:
            second = ladder.recall(
                vault=self.vault,
                fingerprint="fp-B-drifted",
                project="crickets",
                query_text="ValueError in classify (drifted)",
                namespace="runtime",
            )
        spy2.assert_not_called()
        self.assertEqual(second["layer"], 1)
        self.assertEqual(second["path"], _CANONICAL_PATH)

    def test_weak_layer2_match_does_not_auto_alias(self):
        weak_hit = [{"path": _CANONICAL_PATH, "score": 0.3}]
        with mock.patch.object(bridge, "query_semantic", return_value=weak_hit):
            ladder.recall(
                vault=self.vault,
                fingerprint="fp-C-unrelated",
                project="crickets",
                query_text="totally different failure",
                namespace="runtime",
            )
        self.assertIsNone(fpi.lookup(self.vault, "fp-C-unrelated", "crickets"))

    def test_confident_match_on_unindexed_path_does_not_crash(self):
        # A confident Layer-2 hit whose path has no canonical sidecar entry
        # (e.g. an incident that predates the sidecar index) must be a no-op,
        # not an error.
        stray_hit = [{"path": "projects/crickets/failure-incident/unindexed.md", "score": 0.95}]
        with mock.patch.object(bridge, "query_semantic", return_value=stray_hit):
            result = ladder.recall(
                vault=self.vault,
                fingerprint="fp-D",
                project="crickets",
                query_text="some failure",
                namespace="runtime",
            )
        self.assertEqual(result["layer"], 2)
        self.assertIsNone(fpi.lookup(self.vault, "fp-D", "crickets"))


if __name__ == "__main__":
    unittest.main()
