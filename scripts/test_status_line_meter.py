#!/usr/bin/env python3
"""Tests for src/status-line-meter/scripts/status_line_meter.py.

All expected costs are hand-computed from the synthesized fixture
(scripts/fixtures/token_audit_synthesized.jsonl) — the same fixture used by
test_token_audit.py, so the status-line meter and the batch analyzer agree.

Fixture totals (hand-computed):
  msg1: Opus 4.8  input=1000 write=2000 read=0   out=100  floor=No  $0.020000
  msg2: Opus 4.8  input=500  write=0    read=3000 out=200  floor=No  $0.009000
  msg3: Sonnet 4.6 input=800  write=1000 read=2000 out=150  floor=No  $0.009000
  msg4: Haiku 4.5  input=400  write=0    read=0    out=50   floor=Yes $0.000650

  total_cost: $0.038650
  floor_cost: $0.000650  (msg4 only: cr=0 and cw=0)
  floor_pct:  1.68...%   (0.000650/0.038650*100)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "tokens" / "scripts"
_FIXTURE_TRANSCRIPT = _ROOT / "scripts" / "fixtures" / "token_audit_synthesized.jsonl"


def _load_slm():
    """Load status_line_meter with the src/token-audit/scripts/ on sys.path
    so runtime discovery finds pricing.py (the same as the installed case)."""
    ta_scripts = _ROOT / "src" / "tokens" / "scripts"
    if str(ta_scripts) not in sys.path:
        sys.path.insert(0, str(ta_scripts))
    spec = importlib.util.spec_from_file_location(
        "status_line_meter", _SRC / "status_line_meter.py"
    )
    m = importlib.util.module_from_spec(spec)
    # Reload ensures the path injection above takes effect for the module.
    spec.loader.exec_module(m)
    return m


slm = _load_slm()


def _make_payload(**kwargs) -> dict:
    """Build a minimal status-line JSON payload with optional overrides."""
    base: dict = {
        "session_id": "test-session-001",
        "transcript_path": None,
        "model": {"id": "claude-opus-4-8"},
        "context_window": {
            "used_percentage": 42,
            "context_window_size": 200000,
        },
        "cost": {"total_cost_usd": 0.05},
    }
    base.update(kwargs)
    return base


class TestRenderBasic(unittest.TestCase):
    """render() produces correct output for standard payloads."""

    def test_used_pct_badge_present(self):
        data = _make_payload()
        result = slm.render(data)
        self.assertIn("42%", result)

    def test_used_pct_badge_has_marker(self):
        data = _make_payload()
        result = slm.render(data)
        self.assertIn("▌", result)

    def test_used_pct_rounds(self):
        data = _make_payload(context_window={"used_percentage": 42.7, "context_window_size": 200000})
        result = slm.render(data)
        self.assertIn("43%", result)

    def test_used_pct_zero(self):
        data = _make_payload(context_window={"used_percentage": 0, "context_window_size": 200000})
        result = slm.render(data)
        self.assertIn("0%", result)


class TestRenderGracefulSkip(unittest.TestCase):
    """render() degrades gracefully when fields are missing or null."""

    def test_null_used_pct_omits_badge(self):
        data = _make_payload(context_window={"used_percentage": None})
        result = slm.render(data)
        self.assertNotIn("▌", result)
        self.assertNotIn("%", result)

    def test_missing_context_window(self):
        data = _make_payload()
        del data["context_window"]
        result = slm.render(data)
        # Should not raise; used-% badge absent
        self.assertNotIn("▌", result)

    def test_empty_payload(self):
        result = slm.render({})
        self.assertIsInstance(result, str)

    def test_nonexistent_transcript_path(self):
        data = _make_payload(transcript_path="/tmp/nonexistent_crickets_slm_test.jsonl")
        # Should not crash; returns whatever it can render
        result = slm.render(data)
        self.assertIsInstance(result, str)

    def test_none_transcript_path(self):
        data = _make_payload(transcript_path=None)
        result = slm.render(data)
        self.assertIsInstance(result, str)


class TestIncrementalTranscriptReader(unittest.TestCase):
    """_get_session_stats reads transcript and returns correct totals."""

    @classmethod
    def setUpClass(cls):
        if not _FIXTURE_TRANSCRIPT.exists():
            raise unittest.SkipTest("fixture transcript not found")
        if not slm._HAS_PRICING:
            raise unittest.SkipTest("pricing module not found — token-audit not installed")

    def _make_data(self, path: str, session_id: str = "test-incr-001") -> dict:
        return _make_payload(transcript_path=path, session_id=session_id)

    def test_total_cost_matches_analyzer(self):
        sid = "test-total-cost-001"
        _cache = slm._cache_path(sid)
        _cache.unlink(missing_ok=True)

        data = self._make_data(str(_FIXTURE_TRANSCRIPT), session_id=sid)
        stats = slm._get_session_stats(data)
        self.assertIsNotNone(stats)
        self.assertAlmostEqual(stats["total_cost"], 0.038650, places=6)
        _cache.unlink(missing_ok=True)

    def test_floor_cost_matches_analyzer(self):
        sid = "test-floor-cost-001"
        _cache = slm._cache_path(sid)
        _cache.unlink(missing_ok=True)

        data = self._make_data(str(_FIXTURE_TRANSCRIPT), session_id=sid)
        stats = slm._get_session_stats(data)
        self.assertIsNotNone(stats)
        self.assertAlmostEqual(stats["floor_cost"], 0.000650, places=6)
        _cache.unlink(missing_ok=True)

    def test_incremental_reads_only_new_bytes(self):
        """Second call with no new lines returns cached totals without re-reading."""
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".jsonl", delete=False
        ) as f:
            tmp = Path(f.name)
            # Write first message (msg1)
            line1 = (
                b'{"type":"assistant","message":{"model":"claude-opus-4-8","usage":'
                b'{"input_tokens":1000,"cache_creation_input_tokens":2000,'
                b'"cache_read_input_tokens":0,"output_tokens":100}}}\n'
            )
            f.write(line1)
            pos_after_line1 = len(line1)

        sid = "test-incremental-001"
        _cache = slm._cache_path(sid)
        _cache.unlink(missing_ok=True)

        try:
            data = self._make_data(str(tmp), session_id=sid)
            stats1 = slm._get_session_stats(data)
            self.assertIsNotNone(stats1)
            self.assertAlmostEqual(stats1["total_cost"], 0.020000, places=6)
            self.assertEqual(stats1["last_pos"], pos_after_line1)

            # Second call with no new bytes → cache hit
            stats2 = slm._get_session_stats(data)
            self.assertIsNotNone(stats2)
            self.assertAlmostEqual(stats2["total_cost"], 0.020000, places=6)

            # Append a second message
            line2 = (
                b'{"type":"assistant","message":{"model":"claude-haiku-4-5","usage":'
                b'{"input_tokens":400,"cache_creation_input_tokens":0,'
                b'"cache_read_input_tokens":0,"output_tokens":50}}}\n'
            )
            with open(tmp, "ab") as f:
                f.write(line2)

            # Third call reads only line2 (O(new-line), not O(N))
            stats3 = slm._get_session_stats(data)
            self.assertIsNotNone(stats3)
            # 0.020000 (msg1) + 0.000650 (haiku msg) = 0.020650
            self.assertAlmostEqual(stats3["total_cost"], 0.020650, places=6)
        finally:
            tmp.unlink(missing_ok=True)
            _cache.unlink(missing_ok=True)

    def test_truncated_transcript_resets_cache(self):
        """Regression: transcript truncation (e.g. /compact) must not return stale cost."""
        line1 = (
            b'{"type":"assistant","message":{"model":"claude-haiku-4-5","usage":'
            b'{"input_tokens":400,"cache_creation_input_tokens":0,'
            b'"cache_read_input_tokens":0,"output_tokens":50}}}\n'
        )
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".jsonl", delete=False) as f:
            f.write(line1)
            tmp = Path(f.name)

        sid = "test-truncation-stale-001"
        slm._cache_path(sid).unlink(missing_ok=True)
        try:
            data = self._make_data(str(tmp), session_id=sid)
            stats1 = slm._get_session_stats(data)
            self.assertIsNotNone(stats1)
            self.assertGreater(stats1["total_cost"], 0)

            # Truncate the file — simulates /compact rewriting the transcript
            with open(tmp, "wb"):
                pass

            stats2 = slm._get_session_stats(data)
            if stats2 is not None:
                self.assertAlmostEqual(
                    stats2.get("total_cost", 0.0), 0.0, places=6,
                    msg="Stale cached cost returned after transcript truncation"
                )
        finally:
            tmp.unlink(missing_ok=True)
            slm._cache_path(sid).unlink(missing_ok=True)

    def test_cache_invalidated_on_path_change(self):
        """Changing transcript_path resets the cache."""
        sid = "test-path-change-001"
        _cache = slm._cache_path(sid)
        _cache.unlink(missing_ok=True)
        tmp = None  # guard: only set if NamedTemporaryFile succeeds

        try:
            data1 = self._make_data(str(_FIXTURE_TRANSCRIPT), session_id=sid)
            stats1 = slm._get_session_stats(data1)
            self.assertIsNotNone(stats1)

            # Point to a different path
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False
            ) as f:
                f.write("")
                tmp = Path(f.name)

            data2 = self._make_data(str(tmp), session_id=sid)
            stats2 = slm._get_session_stats(data2)
            # Empty file → no messages → stats may be empty dict or None
            if stats2 is not None:
                self.assertAlmostEqual(stats2.get("total_cost", 0.0), 0.0, places=6)
        finally:
            _cache.unlink(missing_ok=True)
            if tmp is not None:
                tmp.unlink(missing_ok=True)


class TestRenderWithTranscript(unittest.TestCase):
    """render() includes cost and floor-share badges when transcript is present."""

    @classmethod
    def setUpClass(cls):
        if not _FIXTURE_TRANSCRIPT.exists():
            raise unittest.SkipTest("fixture transcript not found")
        if not slm._HAS_PRICING:
            raise unittest.SkipTest("pricing module not found")

    def setUp(self):
        self.sid = "test-render-with-transcript-001"
        slm._cache_path(self.sid).unlink(missing_ok=True)

    def tearDown(self):
        slm._cache_path(self.sid).unlink(missing_ok=True)

    def _data(self) -> dict:
        return _make_payload(
            transcript_path=str(_FIXTURE_TRANSCRIPT),
            session_id=self.sid,
        )

    def test_cost_badge_present(self):
        result = slm.render(self._data())
        self.assertIn("$", result)

    def test_floor_badge_present(self):
        result = slm.render(self._data())
        self.assertIn("⌊", result)
        self.assertIn("⌋", result)

    def test_cost_matches_analyzer_total(self):
        result = slm.render(self._data())
        # $0.038650 rounds to $0.04 at 2 decimal places
        self.assertIn("$0.04", result)

    def test_all_three_badges(self):
        result = slm.render(self._data())
        self.assertIn("▌", result)
        self.assertIn("⌊", result)
        self.assertIn("$", result)

    def test_separator_between_badges(self):
        result = slm.render(self._data())
        self.assertIn("  ·  ", result)

    def test_floor_pct_correct(self):
        # floor = 0.000650 / 0.038650 * 100 ≈ 1.68% → rounds to "2%"
        result = slm.render(self._data())
        import re
        m = re.search(r"⌊(\d+)%⌋", result)
        self.assertIsNotNone(m, f"floor badge not found in: {result!r}")
        floor_pct = int(m.group(1))
        self.assertAlmostEqual(floor_pct, 2, delta=1)


class TestPricingDiscovery(unittest.TestCase):
    """Pricing module is found from the expected relative path."""

    def test_has_pricing(self):
        self.assertTrue(slm._HAS_PRICING, "pricing.py not found — check token-audit path")

    def test_ta_scripts_path(self):
        self.assertTrue(slm._TA_SCRIPTS.is_dir(), f"token-audit scripts dir missing: {slm._TA_SCRIPTS}")

    def test_cost_usd_callable(self):
        self.assertIsNotNone(slm.cost_usd)
        self.assertTrue(callable(slm.cost_usd))


class TestFloorShareEdgeCases(unittest.TestCase):
    """floor-share badge omitted when no cost (avoids division by zero)."""

    def test_zero_total_cost_omits_floor_badge(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write("")
            tmp = Path(f.name)
        sid = "test-zero-cost-001"
        slm._cache_path(sid).unlink(missing_ok=True)
        try:
            data = _make_payload(transcript_path=str(tmp), session_id=sid)
            result = slm.render(data)
            self.assertNotIn("⌊", result)
            self.assertNotIn("⌋", result)
        finally:
            tmp.unlink(missing_ok=True)
            slm._cache_path(sid).unlink(missing_ok=True)


class TestGoldenRender(unittest.TestCase):
    """R2.3 task 8: one exact end-to-end string, not just per-badge assertIn
    checks — locks in the full composed contract so a formatting/ordering/
    separator regression is caught even if every individual badge is still
    technically present."""

    @classmethod
    def setUpClass(cls):
        if not _FIXTURE_TRANSCRIPT.exists():
            raise unittest.SkipTest("fixture transcript not found")
        if not slm._HAS_PRICING:
            raise unittest.SkipTest("pricing module not found")

    def setUp(self):
        self.sid = "test-golden-render-001"
        slm._cache_path(self.sid).unlink(missing_ok=True)
        self._env_backup = {
            k: os.environ.pop(k, None)
            for k in ("CRICKETS_BUDGET_5H", "CRICKETS_BUDGET_WEEKLY", "CRICKETS_SESSION_COST_LOG")
        }

    def tearDown(self):
        slm._cache_path(self.sid).unlink(missing_ok=True)
        for k, v in self._env_backup.items():
            if v is not None:
                os.environ[k] = v

    def test_full_payload_exact_string_no_budget_configured(self):
        # Budget env vars unset (the default, out-of-the-box state) -> only
        # the three transcript-analysis badges render; Badge 4 is absent.
        data = _make_payload(transcript_path=str(_FIXTURE_TRANSCRIPT), session_id=self.sid)
        result = slm.render(data)
        self.assertEqual(result, "▌42%  ·  ⌊2%⌋  ·  $0.04")


class TestBudgetReadoutPure(unittest.TestCase):
    """budget_readout() is a pure function: fixture records + ceiling + now
    -> readout string. No env vars, no filesystem — the seam CI can exercise
    directly regardless of whether the write-side (task 4, deferred per the
    module's own header note) exists yet."""

    def test_no_ceiling_returns_empty(self):
        self.assertEqual(slm.budget_readout([{"timestamp": 1000, "cost_usd": 5}], None, 1000), "")

    def test_5h_window_sums_only_records_within_window(self):
        now = 100_000.0
        records = [
            {"timestamp": now - 60, "cost_usd": 1.0},          # 1 min ago -> in window
            {"timestamp": now - slm._FIVE_HOURS_SECONDS - 1, "cost_usd": 99.0},  # just outside
        ]
        readout = slm.budget_readout(records, {"window_5h": 10.0}, now)
        self.assertEqual(readout, "5h $1.00/$10.00")

    def test_weekly_sums_only_records_within_week(self):
        now = 1_000_000.0
        records = [
            {"timestamp": now - 3600, "cost_usd": 2.0},                     # 1h ago -> in window
            {"timestamp": now - slm._WEEK_SECONDS - 1, "cost_usd": 50.0},   # just outside
        ]
        readout = slm.budget_readout(records, {"weekly": 20.0}, now)
        self.assertEqual(readout, "wk $2.00/$20.00")

    def test_both_ceilings_render_both_parts_separated(self):
        now = 100_000.0
        records = [{"timestamp": now - 10, "cost_usd": 3.0}]
        readout = slm.budget_readout(records, {"window_5h": 10.0, "weekly": 20.0}, now)
        self.assertEqual(readout, "5h $3.00/$10.00  ·  wk $3.00/$20.00")

    def test_malformed_record_skipped_not_raised(self):
        now = 100_000.0
        records = [{"timestamp": None, "cost_usd": 5.0}, {"timestamp": now, "cost_usd": "bad"}]
        readout = slm.budget_readout(records, {"window_5h": 10.0}, now)
        self.assertEqual(readout, "5h $0.00/$10.00")

    def test_future_timestamp_excluded(self):
        # A record newer than "now" (clock skew / bad data) must not count —
        # age < 0 is excluded, never treated as "definitely recent."
        now = 100_000.0
        records = [{"timestamp": now + 3600, "cost_usd": 5.0}]
        readout = slm.budget_readout(records, {"window_5h": 10.0}, now)
        self.assertEqual(readout, "5h $0.00/$10.00")


class TestBudgetReadoutIntegration(unittest.TestCase):
    """render()'s Badge 4 wiring end-to-end: env-var config + a real
    session-cost JSONL log on disk, through render() itself — not just the
    pure budget_readout() helper. Confirms the "no config -> omitted, never
    an error" degrade the wiki advertises actually holds, and that the badge
    genuinely appears once configured (closing cricketsPluginsB#8's gap:
    this path had zero coverage before task 8)."""

    def setUp(self):
        self.sid = "test-budget-integration-001"
        slm._cache_path(self.sid).unlink(missing_ok=True)
        self._env_backup = {
            k: os.environ.pop(k, None)
            for k in ("CRICKETS_BUDGET_5H", "CRICKETS_BUDGET_WEEKLY", "CRICKETS_SESSION_COST_LOG")
        }

    def tearDown(self):
        slm._cache_path(self.sid).unlink(missing_ok=True)
        for k, v in self._env_backup.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def test_badge_absent_when_unconfigured(self):
        data = _make_payload(transcript_path=None, session_id=self.sid)
        result = slm.render(data)
        self.assertNotIn("5h $", result)
        self.assertNotIn("wk $", result)

    def test_badge_present_when_configured_with_matching_log(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"timestamp": time.time(), "cost_usd": 1.23}) + "\n")
            log_path = Path(f.name)
        try:
            os.environ["CRICKETS_BUDGET_5H"] = "10.00"
            os.environ["CRICKETS_SESSION_COST_LOG"] = str(log_path)
            data = _make_payload(transcript_path=None, session_id=self.sid)
            result = slm.render(data)
            self.assertIn("5h $1.23/$10.00", result)
        finally:
            log_path.unlink(missing_ok=True)

    def test_badge_omitted_when_log_missing_even_if_configured(self):
        # The write-side (task 4) is deferred — an operator who configures
        # the env vars today gets an empty record set, not an error string.
        os.environ["CRICKETS_BUDGET_5H"] = "10.00"
        os.environ["CRICKETS_SESSION_COST_LOG"] = "/nonexistent/path/no-such-file.jsonl"
        data = _make_payload(transcript_path=None, session_id=self.sid)
        result = slm.render(data)
        self.assertIn("5h $0.00/$10.00", result)


if __name__ == "__main__":
    unittest.main()
