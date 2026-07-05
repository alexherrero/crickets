#!/usr/bin/env python3
"""Tests for src/token-audit/scripts/pricing.py and analyzer.py.

All expected values are hand-computed from the synthesized fixture
(scripts/fixtures/token_audit_synthesized.jsonl) — no real transcript content
is used anywhere in this file.

Fixture messages (hand-computed totals):
  msg1: Opus 4.8  T=00:02 phase=plan  input=1000 write=2000 read=0    out=100  $0.020000
  msg2: Opus 4.8  T=00:12 phase=plan  input=500  write=0    read=3000  out=200  $0.009000
  msg3: Sonnet 4.6 T=00:22 phase=work  input=800  write=1000 read=2000  out=150  $0.009000
  msg4: Haiku 4.5  T=06:32 phase=work  input=400  write=0    read=0     out=50   $0.000650

  total cost:      $0.038650
  cache split:     fresh=2700 write=3000 read=5000  pct=46.7289...%
  floor cost:      $0.000650  (msg4 only: read=0 and write=0)
  window 1 (00:02): msgs 1-3  $0.038000
  window 2 (06:32): msg4      $0.000650
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "token-audit" / "scripts"
_FIXTURE = _ROOT / "scripts" / "fixtures" / "token_audit_synthesized.jsonl"
_REAL_ENCODING_FIXTURE = _ROOT / "scripts" / "fixtures" / "token_audit_real_encoding.jsonl"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


pricing = _load("pricing")
analyzer = _load("analyzer")


class TestCostUsd(unittest.TestCase):
    """pricing.cost_usd produces correct per-message costs."""

    def _usage(self, *, it=0, cw=0, cr=0, ot=0):
        return {
            "input_tokens": it,
            "cache_creation_input_tokens": cw,
            "cache_read_input_tokens": cr,
            "output_tokens": ot,
        }

    def test_opus_fresh_input_only(self):
        c = pricing.cost_usd(self._usage(it=1_000_000), "claude-opus-4-8")
        self.assertAlmostEqual(c, 5.00, places=6)

    def test_fable_5_priced_nonzero(self):
        # R0.7 regression: pricing.py used to pin only opus/sonnet/haiku, so a
        # pure claude-fable-5 session priced at $0.00 (unknown-model fallback).
        c = pricing.cost_usd(self._usage(it=1_000_000, ot=1_000_000), "claude-fable-5")
        self.assertGreater(c, 0.0)
        self.assertAlmostEqual(c, 60.00, places=6)

    def test_sonnet_5_priced_nonzero(self):
        c = pricing.cost_usd(self._usage(it=1_000_000, ot=1_000_000), "claude-sonnet-5")
        self.assertGreater(c, 0.0)
        self.assertAlmostEqual(c, 12.00, places=6)

    def test_opus_output_only(self):
        c = pricing.cost_usd(self._usage(ot=1_000_000), "claude-opus-4-8")
        self.assertAlmostEqual(c, 25.00, places=6)

    def test_opus_cache_write(self):
        c = pricing.cost_usd(self._usage(cw=1_000_000), "claude-opus-4-8")
        self.assertAlmostEqual(c, 6.25, places=6)

    def test_opus_cache_read(self):
        c = pricing.cost_usd(self._usage(cr=1_000_000), "claude-opus-4-8")
        self.assertAlmostEqual(c, 0.50, places=6)

    def test_sonnet_input(self):
        c = pricing.cost_usd(self._usage(it=1_000_000), "claude-sonnet-4-6")
        self.assertAlmostEqual(c, 3.00, places=6)

    def test_haiku_output(self):
        c = pricing.cost_usd(self._usage(ot=1_000_000), "claude-haiku-4-5")
        self.assertAlmostEqual(c, 5.00, places=6)

    def test_unknown_model_returns_zero(self):
        c = pricing.cost_usd(self._usage(it=1000), "claude-unknown-99")
        self.assertEqual(c, 0.0)

    def test_msg1_exact(self):
        # input=1000 write=2000 read=0 out=100 — Opus 4.8
        c = pricing.cost_usd(
            self._usage(it=1000, cw=2000, cr=0, ot=100), "claude-opus-4-8"
        )
        self.assertAlmostEqual(c, 0.020000, places=6)

    def test_msg2_exact(self):
        # input=500 write=0 read=3000 out=200 — Opus 4.8
        c = pricing.cost_usd(
            self._usage(it=500, cw=0, cr=3000, ot=200), "claude-opus-4-8"
        )
        self.assertAlmostEqual(c, 0.009000, places=6)

    def test_msg3_exact(self):
        # input=800 write=1000 read=2000 out=150 — Sonnet 4.6
        c = pricing.cost_usd(
            self._usage(it=800, cw=1000, cr=2000, ot=150), "claude-sonnet-4-6"
        )
        self.assertAlmostEqual(c, 0.009000, places=6)

    def test_msg4_exact(self):
        # input=400 write=0 read=0 out=50 — Haiku 4.5
        c = pricing.cost_usd(
            self._usage(it=400, cw=0, cr=0, ot=50), "claude-haiku-4-5"
        )
        self.assertAlmostEqual(c, 0.000650, places=6)


class TestAnalyzer(unittest.TestCase):
    """analyzer.analyze_session produces correct totals and window sums."""

    @classmethod
    def setUpClass(cls):
        cls.report = analyzer.analyze_session(_FIXTURE)

    def test_message_count(self):
        self.assertEqual(len(self.report.messages), 4)

    def test_total_cost(self):
        self.assertAlmostEqual(self.report.total_cost_usd, 0.038650, places=6)

    def test_floor_cost(self):
        # Only msg4 has cache_read=0 and cache_write=0
        self.assertAlmostEqual(self.report.floor_cost_usd, 0.000650, places=6)

    def test_floor_message_count(self):
        floor_msgs = [m for m in self.report.messages if m.is_floor]
        self.assertEqual(len(floor_msgs), 1)
        self.assertEqual(floor_msgs[0].model, "claude-haiku-4-5")

    def test_two_windows(self):
        self.assertEqual(len(self.report.windows), 2)

    def test_window_1_cost(self):
        # msgs 1-3 all within 5h of 00:02 → window 1
        self.assertAlmostEqual(self.report.windows[0].total_cost_usd, 0.038000, places=6)

    def test_window_1_count(self):
        self.assertEqual(self.report.windows[0].message_count, 3)

    def test_window_2_cost(self):
        # msg4 at 06:32 → 6h30m from 00:02 → new window
        self.assertAlmostEqual(self.report.windows[1].total_cost_usd, 0.000650, places=6)

    def test_window_2_count(self):
        self.assertEqual(self.report.windows[1].message_count, 1)

    def test_per_message_models(self):
        models = [m.model for m in self.report.messages]
        self.assertEqual(models, [
            "claude-opus-4-8",
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ])

    def test_msg1_cost(self):
        self.assertAlmostEqual(self.report.messages[0].cost_usd, 0.020000, places=6)

    def test_msg2_cost(self):
        self.assertAlmostEqual(self.report.messages[1].cost_usd, 0.009000, places=6)

    def test_msg3_cost(self):
        self.assertAlmostEqual(self.report.messages[2].cost_usd, 0.009000, places=6)

    def test_msg4_cost(self):
        self.assertAlmostEqual(self.report.messages[3].cost_usd, 0.000650, places=6)

    def test_non_assistant_lines_skipped(self):
        # user and summary lines in the fixture must not appear in messages
        types = {m.model for m in self.report.messages}
        self.assertNotIn("user", types)
        self.assertNotIn("summary", types)


class TestCacheSplit(unittest.TestCase):
    """cache_split returns correct totals and percentage."""

    @classmethod
    def setUpClass(cls):
        cls.report = analyzer.analyze_session(_FIXTURE)
        cls.split = cls.report.cache_split

    def test_fresh_input_tokens(self):
        # 1000 + 500 + 800 + 400 = 2700
        self.assertEqual(self.split.fresh_input_tokens, 2700)

    def test_cache_write_tokens(self):
        # 2000 + 0 + 1000 + 0 = 3000
        self.assertEqual(self.split.cache_write_tokens, 3000)

    def test_cache_read_tokens(self):
        # 0 + 3000 + 2000 + 0 = 5000
        self.assertEqual(self.split.cache_read_tokens, 5000)

    def test_output_tokens(self):
        # 100 + 200 + 150 + 50 = 500
        self.assertEqual(self.split.output_tokens, 500)

    def test_pct_served_from_cache(self):
        # 5000 / (2700 + 3000 + 5000) * 100 = 5000/10700*100
        expected = 5000 / 10700 * 100
        self.assertAlmostEqual(self.split.pct_served_from_cache, expected, places=6)

    def test_pct_range(self):
        self.assertGreater(self.split.pct_served_from_cache, 0)
        self.assertLess(self.split.pct_served_from_cache, 100)

    def test_empty_messages(self):
        split = analyzer.cache_split([])
        self.assertEqual(split.pct_served_from_cache, 0.0)
        self.assertEqual(split.fresh_input_tokens, 0)


class TestPhaseAttribution(unittest.TestCase):
    """Phase markers from /plan and /work user lines are attached to subsequent assistant messages."""

    @classmethod
    def setUpClass(cls):
        cls.report = analyzer.analyze_session(_FIXTURE, track_phases=True)

    def test_plan_phase_messages(self):
        plan_msgs = [m for m in self.report.messages if m.phase == "plan"]
        self.assertEqual(len(plan_msgs), 2)

    def test_work_phase_messages(self):
        work_msgs = [m for m in self.report.messages if m.phase == "work"]
        self.assertEqual(len(work_msgs), 2)

    def test_plan_phase_cost(self):
        # msgs 1 + 2 = $0.020000 + $0.009000 = $0.029000
        plan_cost = sum(m.cost_usd for m in self.report.messages if m.phase == "plan")
        self.assertAlmostEqual(plan_cost, 0.029000, places=6)

    def test_work_phase_cost(self):
        # msgs 3 + 4 = $0.009000 + $0.000650 = $0.009650
        work_cost = sum(m.cost_usd for m in self.report.messages if m.phase == "work")
        self.assertAlmostEqual(work_cost, 0.009650, places=6)

    def test_phase_total_matches_session_total(self):
        by_phase = sum(m.cost_usd for m in self.report.messages)
        self.assertAlmostEqual(by_phase, 0.038650, places=6)

    def test_no_unknown_phase(self):
        # Every message in this fixture is preceded by a phase command
        unknown = [m for m in self.report.messages if m.phase == "unknown"]
        self.assertEqual(len(unknown), 0)


class TestPhaseAttributionRealEncoding(unittest.TestCase):
    """R0.7 regression: --by-phase must fire on the real Claude Code XML
    encoding, not just a raw '/work' prefix.

    fixtures/token_audit_real_encoding.jsonl's user line is a literal
    transcript snippet captured from a real crickets session (2026-06-03,
    `80d0ddda-9cc1-4b48-b339-b359950468ed`) — not a synthesized approximation.
    A plain `text.startswith('/work')` check never matches it, because the
    text begins with '<command-message>work</command-message>', not '/work'.
    """

    @classmethod
    def setUpClass(cls):
        cls.report = analyzer.analyze_session(_REAL_ENCODING_FIXTURE, track_phases=True)

    def test_real_encoding_fires_work_phase(self):
        phases = [m.phase for m in self.report.messages]
        self.assertEqual(phases, ["work"])


if __name__ == "__main__":
    # R2.1 — dashboard visibility for cricketsPluginsB#0 (the already-fixed
    # pricing re-pin). Scoped to TestCostUsd specifically (not the whole
    # file, which also covers the unrelated analyzer/cache-split/phase-
    # attribution behavior) — a bare namespace stands in for "module" so
    # run_module_as_health_check's loadTestsFromModule sees only that class.
    sys.path.insert(0, str(_HERE / "health"))
    import jsonl_emit as _je  # noqa: E402

    class _PricingOnly:
        TestCostUsd = TestCostUsd

    sys.exit(_je.run_module_as_health_check(
        _PricingOnly, sys.argv,
        suite="test_token_audit", check="cricketsPluginsB#0: pricing re-pin",
    ))
