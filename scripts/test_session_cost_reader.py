#!/usr/bin/env python3
"""Tests for src/tokens/scripts/session_cost_reader.py -- the read-side
counterpart to session_cost_writer.py's event-log write path
(PLAN-observability-ledger task 3).

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


reader = _load("session_cost_reader_under_test", _SRC / "session_cost_reader.py")
event_log = sys.modules["event_log"]
writer = _load("session_cost_writer_for_reader_test", _SRC / "session_cost_writer.py")


class LoadObservedRecordsGracefulEmptyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_telemetry_dir_is_empty(self):
        self.assertEqual(
            reader.load_observed_records(telemetry_root=self.tmp / "no-such-dir"), [],
        )

    def test_empty_telemetry_dir_is_empty(self):
        d = self.tmp / "telemetry"
        d.mkdir()
        self.assertEqual(reader.load_observed_records(telemetry_root=d), [])

    def test_malformed_line_is_skipped_not_raised(self):
        d = self.tmp / "telemetry"
        d.mkdir()
        (d / "events-202607.jsonl").write_text("not json at all\n", encoding="utf-8")
        self.assertEqual(reader.load_observed_records(telemetry_root=d), [])

    def test_non_session_cost_events_are_filtered_out(self):
        d = self.tmp / "telemetry"
        d.mkdir()
        record = event_log.build_event("run-start", model="claude-sonnet-5", cost_usd=1.0)
        event_log.append_event(record, telemetry_root=d)
        self.assertEqual(reader.load_observed_records(telemetry_root=d), [])

    def test_missing_model_or_cost_field_is_skipped(self):
        d = self.tmp / "telemetry"
        d.mkdir()
        (d / "events-202607.jsonl").write_text(
            json.dumps({"event": "session-cost", "model": None, "cost_usd": 1.0}) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(reader.load_observed_records(telemetry_root=d), [])


class LoadObservedRecordsRealDataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.telemetry_root = self.tmp / "telemetry"

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_events_written_by_the_writer(self):
        transcript = self.tmp / "session.jsonl"
        transcript.write_text(
            json.dumps({
                "type": "assistant", "timestamp": "2026-07-06T10:00:00Z",
                "message": {
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 1_000_000, "cache_creation_input_tokens": 0,
                              "cache_read_input_tokens": 0, "output_tokens": 0},
                },
            }) + "\n",
            encoding="utf-8",
        )
        written = writer.capture_session_cost(
            transcript, telemetry_root=self.telemetry_root, root=self.tmp,
        )
        self.assertEqual(len(written), 1)

        records = reader.load_observed_records(telemetry_root=self.telemetry_root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["model"], "claude-sonnet-5")
        self.assertAlmostEqual(records[0]["cost_usd"], 2.00, places=2)

    def test_multiple_events_across_models_all_read_back(self):
        for model in ("claude-sonnet-5", "claude-opus-4-8", "claude-sonnet-5"):
            record = event_log.build_event("session-cost", model=model, cost_usd=1.5)
            event_log.append_event(record, telemetry_root=self.telemetry_root)
        records = reader.load_observed_records(telemetry_root=self.telemetry_root)
        self.assertEqual(len(records), 3)
        self.assertEqual(sum(1 for r in records if r["model"] == "claude-sonnet-5"), 2)

    def test_default_telemetry_root_reads_env_override(self, *, monkeypatch=None):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"AGENTM_TELEMETRY_DIR": str(self.telemetry_root)}):
            record = event_log.build_event("session-cost", model="claude-sonnet-5", cost_usd=0.5)
            event_log.append_event(record)  # no telemetry_root -- resolves via env
            records = reader.load_observed_records()  # no telemetry_root -- resolves via env
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["model"], "claude-sonnet-5")


if __name__ == "__main__":
    unittest.main()
