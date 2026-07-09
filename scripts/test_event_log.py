#!/usr/bin/env python3
"""Tests for src/tokens/scripts/event_log.py -- the observability ledger's
write path (PLAN-observability-ledger tasks 1-2, `wiki/designs/
agentm-autonomy.md` Design section).

Covers: the event schema shape, the graceful no-op append contract, monthly
log-file rotation, and attribution-tag resolution from the worktree-local
`.harness/active-plan` marker.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
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


event_log = _load("event_log_under_test", _SRC / "event_log.py")


class BuildEventTests(unittest.TestCase):
    def test_default_shape_has_every_schema_field(self):
        record = event_log.build_event("session-cost")
        for key in ("ts", "schema_version", "device", "session_id", "parent_id",
                    "event", "model", "tokens_by_kind", "cost_usd", "tags"):
            self.assertIn(key, record)
        self.assertEqual(record["event"], "session-cost")
        self.assertEqual(record["schema_version"], event_log.SCHEMA_VERSION)

    def test_default_tokens_by_kind_has_all_four_kinds(self):
        record = event_log.build_event("run-start")
        for kind in ("input", "cache_write", "cache_read", "output"):
            self.assertIn(kind, record["tokens_by_kind"])
            self.assertEqual(record["tokens_by_kind"][kind], 0)

    def test_default_tags_has_all_four_tags_as_none(self):
        record = event_log.build_event("run-start")
        self.assertEqual(record["tags"], {"plan": None, "task": None, "arc": None, "grade": None})

    def test_explicit_fields_are_used_verbatim(self):
        record = event_log.build_event(
            "spawn", session_id="s1", parent_id="p1", model="claude-opus-4-8",
            tokens_by_kind={"input": 5, "cache_write": 0, "cache_read": 0, "output": 2},
            cost_usd=1.23, tags={"plan": "myplan", "task": "3", "arc": "AA3", "grade": "green"},
            device="devbox", ts="2026-01-01T00:00:00Z",
        )
        self.assertEqual(record["session_id"], "s1")
        self.assertEqual(record["parent_id"], "p1")
        self.assertEqual(record["model"], "claude-opus-4-8")
        self.assertEqual(record["cost_usd"], 1.23)
        self.assertEqual(record["device"], "devbox")
        self.assertEqual(record["ts"], "2026-01-01T00:00:00Z")
        self.assertEqual(record["tags"]["plan"], "myplan")


class AppendEventTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_append_creates_monthly_rotated_file(self):
        when = datetime(2026, 7, 7, tzinfo=timezone.utc)
        record = event_log.build_event("session-cost", ts=when.isoformat())
        ok = event_log.append_event(record, telemetry_root=self.tmp)
        self.assertTrue(ok)
        files = list(self.tmp.glob("events-*.jsonl"))
        self.assertEqual(len(files), 1)

    def test_two_appends_land_two_lines_in_same_file(self):
        r1 = event_log.build_event("session-cost", model="a")
        r2 = event_log.build_event("session-cost", model="b")
        event_log.append_event(r1, telemetry_root=self.tmp)
        event_log.append_event(r2, telemetry_root=self.tmp)
        files = list(self.tmp.glob("events-*.jsonl"))
        self.assertEqual(len(files), 1)
        lines = files[0].read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)
        parsed = [json.loads(l) for l in lines]
        self.assertEqual({p["model"] for p in parsed}, {"a", "b"})

    def test_append_never_raises_on_unwritable_root(self):
        blocker = self.tmp / "not-a-dir"
        blocker.write_text("x", encoding="utf-8")
        record = event_log.build_event("session-cost")
        ok = event_log.append_event(record, telemetry_root=blocker / "child")
        self.assertFalse(ok)

    def test_append_returns_false_on_unserializable_record(self):
        record = {"bad": object()}
        ok = event_log.append_event(record, telemetry_root=self.tmp)
        self.assertFalse(ok)


class ResolveAttributionTagsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_marker_yields_plan_none_never_a_crash(self):
        tags = event_log.resolve_attribution_tags(root=self.tmp)
        self.assertIsNone(tags["plan"])
        self.assertIsNone(tags["task"])
        self.assertIsNone(tags["arc"])

    def test_marker_present_yields_the_slug(self):
        harness = self.tmp / ".harness"
        harness.mkdir()
        (harness / "active-plan").write_text("observability-ledger\n", encoding="utf-8")
        tags = event_log.resolve_attribution_tags(root=self.tmp)
        self.assertEqual(tags["plan"], "observability-ledger")

    def test_blank_marker_yields_plan_none(self):
        harness = self.tmp / ".harness"
        harness.mkdir()
        (harness / "active-plan").write_text("   \n", encoding="utf-8")
        tags = event_log.resolve_attribution_tags(root=self.tmp)
        self.assertIsNone(tags["plan"])

    def test_grade_passthrough(self):
        tags = event_log.resolve_attribution_tags(root=self.tmp, grade="advisory")
        self.assertEqual(tags["grade"], "advisory")

    def test_task_marker_present_yields_the_slug(self):
        harness = self.tmp / ".harness"
        harness.mkdir()
        (harness / "active-task").write_text("3\n", encoding="utf-8")
        tags = event_log.resolve_attribution_tags(root=self.tmp)
        self.assertEqual(tags["task"], "3")

    def test_plan_and_task_markers_resolve_independently(self):
        harness = self.tmp / ".harness"
        harness.mkdir()
        (harness / "active-plan").write_text("observability-residue-trio\n", encoding="utf-8")
        (harness / "active-task").write_text("1\n", encoding="utf-8")
        tags = event_log.resolve_attribution_tags(root=self.tmp)
        self.assertEqual(tags["plan"], "observability-residue-trio")
        self.assertEqual(tags["task"], "1")
        self.assertIsNone(tags["arc"])

    def test_blank_task_marker_yields_task_none(self):
        harness = self.tmp / ".harness"
        harness.mkdir()
        (harness / "active-task").write_text("   \n", encoding="utf-8")
        tags = event_log.resolve_attribution_tags(root=self.tmp)
        self.assertIsNone(tags["task"])


class DeviceIdTests(unittest.TestCase):
    def test_device_id_is_a_nonempty_string(self):
        self.assertIsInstance(event_log.device_id(), str)
        self.assertGreater(len(event_log.device_id()), 0)


if __name__ == "__main__":
    unittest.main()
