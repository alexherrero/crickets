#!/usr/bin/env python3
"""Tests for src/diagnostics/scripts/{fingerprint_index,recall_ladder}.py
(crickets wave-c-diagnostics, task 2).

The zero-inference guarantee this suite exists to prove: a Layer-1 exact
fingerprint+project hit must short-circuit before the Layer-2 semantic engine
is ever invoked. Asserted via a spy on agentm_bridge.query_semantic
(mock.patch.object + assert_not_called/assert_called_once), mirroring the
established idiom in agentm/scripts/test_vault_lock.py.

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


fpi = _load("diagnostics_fingerprint_index", _SRC / "fingerprint_index.py")
ladder = _load("diagnostics_recall_ladder", _SRC / "recall_ladder.py")
# recall_ladder.py loads its own agentm_bridge by file path (private sys.modules
# key) and exposes it as `ladder.agentm_bridge` -- patch that exact object, not
# a separately-loaded instance, or the mock would miss the calls ladder makes.
bridge = ladder.agentm_bridge


class FingerprintIndexTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_lookup_on_empty_index_is_none(self):
        self.assertIsNone(fpi.lookup(self.vault, "fp-a", "crickets"))

    def test_record_then_lookup_round_trips(self):
        fpi.record(self.vault, "fp-a", "crickets", "projects/crickets/failure-incident/x.md")
        self.assertEqual(
            fpi.lookup(self.vault, "fp-a", "crickets"),
            "projects/crickets/failure-incident/x.md",
        )

    def test_lookup_is_project_scoped(self):
        fpi.record(self.vault, "fp-a", "crickets", "projects/crickets/failure-incident/x.md")
        self.assertIsNone(fpi.lookup(self.vault, "fp-a", "agentm"))

    def test_index_persists_across_loads(self):
        fpi.record(self.vault, "fp-a", "crickets", "projects/crickets/failure-incident/x.md")
        reloaded = fpi.load_index(self.vault)
        self.assertIn("crickets::fp-a", reloaded)


class RecallLadderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_layer1_hit_short_circuits_layer2(self):
        fpi.record(self.vault, "fp-known", "crickets", "projects/crickets/failure-incident/known.md")
        with mock.patch.object(bridge, "query_semantic") as spy:
            result = ladder.recall(
                vault=self.vault,
                fingerprint="fp-known",
                project="crickets",
                query_text="ValueError in classify",
                namespace="runtime",
            )
        spy.assert_not_called()
        self.assertEqual(result["layer"], 1)
        self.assertEqual(result["path"], "projects/crickets/failure-incident/known.md")

    def test_layer1_miss_falls_back_to_layer2(self):
        canned = [{"path": "projects/crickets/failure-incident/other.md", "score": 0.81}]
        with mock.patch.object(bridge, "query_semantic", return_value=canned) as spy:
            result = ladder.recall(
                vault=self.vault,
                fingerprint="fp-unseen",
                project="crickets",
                query_text="ValueError in classify",
                namespace="runtime",
            )
        spy.assert_called_once()
        self.assertEqual(result["layer"], 2)
        self.assertEqual(result["candidates"], canned)

    def test_layer2_call_is_scoped_by_project_kind_and_status(self):
        with mock.patch.object(bridge, "query_semantic", return_value=[]) as spy:
            ladder.recall(
                vault=self.vault,
                fingerprint="fp-unseen",
                project="crickets",
                query_text="ValueError in classify",
                namespace="runtime",
            )
        _, kwargs = spy.call_args
        self.assertIn("kind=failure-incident", kwargs["filter_expr"])
        self.assertIn("project=crickets", kwargs["filter_expr"])
        self.assertIn("status=active", kwargs["filter_expr"])


if __name__ == "__main__":
    unittest.main()
