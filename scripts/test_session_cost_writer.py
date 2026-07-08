#!/usr/bin/env python3
"""Tests for src/tokens/scripts/session_cost_writer.py -- the session-cost
Stop-hook capture half (PLAN-wave-d-tokens-and-privacy task 1, absorbing the
2026-07-05 decision record's PLAN-session-cost-capture scope verbatim).

**Retargeted (PLAN-observability-ledger task 1):** the capture no longer
writes the vault via agentm's `save_entry()` bridge -- it appends telemetry
events to the device-local event log (`event_log.py`). Fully hermetic now:
no agentm sibling checkout dependency survives this module.

Hermetic unit tests cover summarize_by_model() + the graceful no-op paths
(missing/empty transcript, unwritable telemetry dir) + a red-test-first grep
confirming the retired vault-write call site is actually gone.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "tokens" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


writer = _load("session_cost_writer_under_test", _SRC / "session_cost_writer.py")
analyzer = sys.modules["analyzer"]
event_log = sys.modules["event_log"]


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


class VaultWriteRetiredTests(unittest.TestCase):
    """Red-test-first: the old vault-write call site must actually be gone,
    not just superseded by a new one sitting alongside it."""

    def test_no_save_entry_call_site_remains(self):
        source = (_SRC / "session_cost_writer.py").read_text(encoding="utf-8")
        self.assertNotIn("save.save_entry(", source)
        self.assertNotIn("load_save_module", source)
        self.assertNotIn("vault_path", source)


class CaptureSessionCostGracefulNoOpTests(unittest.TestCase):
    """The hook must never block session close, even on a bad transcript
    path or an unwritable event log."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_transcript_is_a_clean_noop(self):
        written = writer.capture_session_cost(
            self.tmp / "no-such-transcript.jsonl",
            telemetry_root=self.tmp / "telemetry",
        )
        self.assertEqual(written, [])

    def test_empty_transcript_is_a_clean_noop(self):
        empty = self.tmp / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        written = writer.capture_session_cost(empty, telemetry_root=self.tmp / "telemetry")
        self.assertEqual(written, [])

    def test_unwritable_telemetry_root_is_a_clean_noop(self):
        # A telemetry "root" that is actually a file, not a directory --
        # mkdir(parents=True) on the child path raises NotADirectoryError
        # (an OSError subclass), which append_event() must swallow.
        transcript = _fixture_transcript(self.tmp)
        blocker = self.tmp / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        written = writer.capture_session_cost(
            transcript, telemetry_root=blocker / "telemetry",
        )
        self.assertEqual(written, [])

    def test_main_never_raises_and_always_exits_zero(self):
        rc = writer.main(["/no/such/path/session.jsonl", "--session-id", "s1"])
        self.assertEqual(rc, 0)


class CaptureSessionCostRealWriteTests(unittest.TestCase):
    """Proves a real session-cost event lands in the event log with the
    expected shape."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.telemetry_root = self.tmp / "telemetry"

    def tearDown(self):
        self._tmp.cleanup()

    def _written_lines(self) -> list[dict]:
        files = sorted(self.telemetry_root.glob("events-*.jsonl"))
        self.assertEqual(len(files), 1)
        return [json.loads(l) for l in files[0].read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_writes_one_event_per_model(self):
        transcript = _fixture_transcript(self.tmp)
        written = writer.capture_session_cost(
            transcript, session_id="s-fire", telemetry_root=self.telemetry_root, root=self.tmp,
        )
        self.assertEqual(len(written), 2)
        lines = self._written_lines()
        self.assertEqual(len(lines), 2)
        models = {l["model"] for l in lines}
        self.assertEqual(models, {"claude-sonnet-5", "claude-opus-4-8"})

    def test_event_shape_matches_schema(self):
        transcript = _fixture_transcript(self.tmp)
        writer.capture_session_cost(
            transcript, session_id="s-fire", telemetry_root=self.telemetry_root, root=self.tmp,
        )
        record = self._written_lines()[0]
        for key in ("ts", "schema_version", "device", "session_id", "parent_id",
                    "event", "model", "tokens_by_kind", "cost_usd", "tags"):
            self.assertIn(key, record)
        self.assertEqual(record["event"], "session-cost")
        self.assertEqual(record["schema_version"], event_log.SCHEMA_VERSION)
        self.assertEqual(record["session_id"], "s-fire")
        for tk in ("input", "cache_write", "cache_read", "output"):
            self.assertIn(tk, record["tokens_by_kind"])
        for tag in ("plan", "task", "arc", "grade"):
            self.assertIn(tag, record["tags"])


if __name__ == "__main__":
    unittest.main()
