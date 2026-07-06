#!/usr/bin/env python3
"""Tests for src/diagnostics/scripts/writer.py -- the scrubbed failure-incident
writer (crickets wave-c-diagnostics, task 4).

Integration-style (not mocked): exercises the real bridge to agentm's
save_entry(), so the mandatory privacy scrub is proven end-to-end rather than
merely assumed. A third test proves the written entry round-trips through
task 2's Layer-1 recall path via its own fingerprint.

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
_SRC = _ROOT / "src" / "diagnostics" / "scripts"

# Snapshot BEFORE any real-bridge activity: agentm's save.py/recall.py insert
# their own scripts dir onto sys.path (and bare-import siblings like
# permeable_boundary/vault_lock into sys.modules) as a side effect of being
# loaded -- a real, process-global mutation that otherwise leaks into whatever
# test file runs next alphabetically (observed: test_diataxis_capture.py's own
# permeable_boundary-unavailable expectation broke once this file's real bridge
# calls had run first in the same process). Restored in tearDownClass.
#
# sys.modules cleanup is filtered by file path (agentm's tree only), not a
# blanket new-keys diff -- a blanket diff also deletes unrelated modules some
# OTHER test file happens to bare-import for the first time during this
# window (observed: test_finalize_unit.py's own `import finalize_unit`,
# which broke a same-object monkeypatch once purged and re-imported fresh).
_SYS_PATH_SNAPSHOT = list(sys.path)
_AGENTM_PATH_MARKERS = ("/agentm/harness/", "/agentm/scripts/")


def _purge_agentm_modules():
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if f and any(marker in f for marker in _AGENTM_PATH_MARKERS):
            del sys.modules[name]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


writer = _load("diagnostics_writer", _SRC / "writer.py")
ladder = _load("diagnostics_recall_ladder_for_writer_test", _SRC / "recall_ladder.py")


class FailureIncidentWriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Integration-style: needs the real agentm sibling checkout (a local
        # dev-machine convention, not present in CI, which has no sibling
        # repo). Skip gracefully rather than error -- matches the codebase's
        # own convention for an absent optional dependency (e.g. agentm's own
        # tests skip when sqlite-vec is unavailable).
        if writer.agentm_bridge.load_save_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        sys.path[:] = _SYS_PATH_SNAPSHOT
        _purge_agentm_modules()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name) / "vault"
        self.vault.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_injected_secret_is_scrubbed_from_written_entry(self):
        target = writer.write_failure_incident(
            self.vault,
            project="crickets",
            fingerprint="fp-secret-test",
            namespace="runtime",
            symptom="ValueError raised; log line: key=sk-" + "a" * 40,
            hypotheses=["a config key leaked into the log line"],
        )
        content = target.read_text(encoding="utf-8")
        self.assertNotIn("sk-" + "a" * 40, content)
        self.assertIn("[REDACTED-API-KEY]", content)

    def test_written_entry_has_failure_incident_frontmatter_and_body(self):
        target = writer.write_failure_incident(
            self.vault,
            project="crickets",
            fingerprint="fp-frontmatter-test",
            namespace="test",
            symptom="assertion failed in test_foo",
            root_cause="off-by-one in the loop bound",
            fix_or_workaround="use range(n) not range(n+1)",
            hypotheses=["off-by-one", "stale fixture data"],
        )
        content = target.read_text(encoding="utf-8")
        self.assertIn("kind: failure-incident", content)
        self.assertIn("fingerprint: fp-frontmatter-test", content)
        self.assertIn("## Symptom", content)
        self.assertIn("assertion failed in test_foo", content)
        self.assertIn("## Root cause", content)
        self.assertIn("off-by-one in the loop bound", content)
        self.assertIn("## Fix / workaround", content)
        self.assertIn("## Hypotheses", content)
        self.assertIn("stale fixture data", content)

    def test_written_entry_round_trips_through_layer1_recall(self):
        writer.write_failure_incident(
            self.vault,
            project="crickets",
            fingerprint="fp-round-trip",
            namespace="build",
            symptom="build failed: missing dependency",
            hypotheses=["lockfile drift"],
        )
        result = ladder.recall(
            vault=self.vault,
            fingerprint="fp-round-trip",
            project="crickets",
            query_text="build failed: missing dependency",
            namespace="build",
        )
        self.assertEqual(result["layer"], 1)
        self.assertTrue(result["path"].endswith(".md"))


if __name__ == "__main__":
    unittest.main()
