#!/usr/bin/env python3
"""Tests for src/tokens/scripts/session_cost_writer.py -- the session-cost
Stop-hook capture half (PLAN-wave-d-tokens-and-privacy task 1, absorbing the
2026-07-05 decision record's PLAN-session-cost-capture scope verbatim).

Hermetic unit tests cover summarize_by_model() + the graceful no-memory-
backend no-op. A real-bridge test (skipped when no agentm sibling checkout is
reachable) proves capture_session_cost() writes a real `kind: session-cost`
entry via agentm's actual save_entry() path -- mirrors
test_diagnostics_writer.py's integration-style precedent.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "tokens" / "scripts"

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


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


writer = _load("session_cost_writer_under_test", _SRC / "session_cost_writer.py")
analyzer = sys.modules["analyzer"]


def _fixture_transcript(tmp: Path) -> Path:
    """A minimal 2-message real-shape transcript, one message per model."""
    lines = [
        json.dumps({
            "type": "assistant",
            "timestamp": "2026-07-06T10:00:00Z",
            "message": {
                "model": "claude-sonnet-5",
                "usage": {
                    "input_tokens": 100, "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0, "output_tokens": 50,
                },
            },
        }),
        json.dumps({
            "type": "assistant",
            "timestamp": "2026-07-06T10:05:00Z",
            "message": {
                "model": "claude-opus-4-8",
                "usage": {
                    "input_tokens": 200, "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0, "output_tokens": 80,
                },
            },
        }),
    ]
    p = tmp / "session.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


class SummarizeByModelTests(unittest.TestCase):
    def test_groups_and_sums_per_model(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            path = _fixture_transcript(Path(tmp.name))
            report = analyzer.analyze_session(path)
            summaries = writer.summarize_by_model(report.messages)
            by_model = {s.model: s for s in summaries}
            self.assertEqual(set(by_model), {"claude-sonnet-5", "claude-opus-4-8"})
            self.assertEqual(by_model["claude-sonnet-5"].tokens_by_kind["input"], 100)
            self.assertEqual(by_model["claude-sonnet-5"].tokens_by_kind["output"], 50)
            self.assertGreater(by_model["claude-sonnet-5"].cost_usd, 0)
            self.assertGreater(by_model["claude-opus-4-8"].cost_usd, 0)
        finally:
            tmp.cleanup()

    def test_empty_messages_yields_no_summaries(self):
        self.assertEqual(writer.summarize_by_model([]), [])


class CaptureSessionCostGracefulNoOpTests(unittest.TestCase):
    """No-memory-backend fixture: the hook must never block session close."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_vault_path_is_a_clean_noop(self):
        transcript = _fixture_transcript(self.tmp)
        written = writer.capture_session_cost(transcript, vault_path=None, project="crickets")
        self.assertEqual(written, [])

    def test_nonexistent_vault_dir_is_a_clean_noop(self):
        transcript = _fixture_transcript(self.tmp)
        written = writer.capture_session_cost(
            transcript, vault_path=self.tmp / "no-such-vault", project="crickets",
        )
        self.assertEqual(written, [])

    def test_agentm_unresolvable_is_a_clean_noop(self):
        vault = self.tmp / "vault"
        vault.mkdir()
        transcript = _fixture_transcript(self.tmp)
        empty_home = self.tmp / "empty_home"
        empty_home.mkdir()
        with mock.patch.dict(os.environ, {"AGENTM_SCRIPTS_DIR": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=empty_home):
                writer._reset_cache_for_tests()
                written = writer.capture_session_cost(
                    transcript, vault_path=vault, project="crickets",
                )
                writer._reset_cache_for_tests()
        self.assertEqual(written, [])

    def test_missing_transcript_is_a_clean_noop(self):
        vault = self.tmp / "vault"
        vault.mkdir()
        written = writer.capture_session_cost(
            self.tmp / "no-such-transcript.jsonl", vault_path=vault, project="crickets",
        )
        self.assertEqual(written, [])

    def test_main_never_raises_and_always_exits_zero(self):
        # CLI entry point contract: even a garbage transcript path must not
        # raise or exit non-zero -- the hook wrapper always continues.
        rc = writer.main(["/no/such/path/session.jsonl", "--project", "crickets"])
        self.assertEqual(rc, 0)


class CaptureSessionCostRealBridgeTests(unittest.TestCase):
    """Integration-style: proves a real `kind: session-cost` entry lands via
    agentm's actual save_entry() path. Skipped without a sibling checkout."""

    @classmethod
    def setUpClass(cls):
        cls._pre_existing_modules = set(sys.modules)
        if writer.load_save_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.vault = self.tmp / "vault"
        self.vault.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_one_session_cost_entry_per_model(self):
        transcript = _fixture_transcript(self.tmp)
        written = writer.capture_session_cost(transcript, vault_path=self.vault, project="crickets")
        self.assertEqual(len(written), 2)
        contents = [p.read_text(encoding="utf-8") for p in written]
        self.assertTrue(any("model: claude-sonnet-5" in c for c in contents))
        self.assertTrue(any("model: claude-opus-4-8" in c for c in contents))
        for c in contents:
            self.assertIn("kind: session-cost", c)
            self.assertIn("group: projects/crickets/session-cost", c)

    def test_written_entry_carries_cost_usd_and_timestamp(self):
        transcript = _fixture_transcript(self.tmp)
        written = writer.capture_session_cost(transcript, vault_path=self.vault, project="crickets")
        content = written[0].read_text(encoding="utf-8")
        self.assertIn("cost_usd:", content)
        self.assertIn("timestamp:", content)
        self.assertIn("input_tokens:", content)


if __name__ == "__main__":
    unittest.main()
