#!/usr/bin/env python3
"""Tests for the roster anti-drift guard (PLAN-efficiency-automation task 3).

Guards two already-fired drifts: (1) `claude-sonnet-4-6` lingering in
developer-workflows agent-defs / command nudges after the model roster moved
on to `claude-sonnet-5`; (2) a concrete model-id string creeping back into
agentm's model-effort-routing tier chart, which the 2026-07-04 pressure-test
correction deliberately stripped down to tier + effort only (model ids now
live solely in token-audit's routing_table.py).

stdlib only — no pytest.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CRICKETS_ROOT = _HERE.parent
_AGENTM_ROOT = _CRICKETS_ROOT.parent / "agentm"

_STALE = "claude-sonnet-4-6"


class TestNoStaleModelRoster(unittest.TestCase):
    def test_no_stale_sonnet_4_6_in_agent_defs_or_commands(self):
        hits = []
        for pattern_dir in ("agents", "commands"):
            d = _CRICKETS_ROOT / "src" / "development-lifecycle" / pattern_dir
            for f in sorted(d.glob("*.md")):
                text = f.read_text(encoding="utf-8")
                if _STALE in text:
                    hits.append(str(f.relative_to(_CRICKETS_ROOT)))
        self.assertEqual(hits, [], f"stale {_STALE!r} found in: {hits}")

    def test_work_and_bugfix_name_opusplan_not_bare_opus(self):
        for name in ("work.md", "bugfix.md"):
            f = _CRICKETS_ROOT / "src" / "development-lifecycle" / "commands" / name
            text = f.read_text(encoding="utf-8")
            self.assertIn("opusplan", text, f"{name} should name opusplan explicitly")

    def test_model_effort_routing_chart_carries_no_concrete_model_id(self):
        design = _AGENTM_ROOT / "wiki" / "designs" / "agentm-model-effort-routing.md"
        if not design.is_file():
            self.skipTest("agentm sibling repo / design doc not present in this checkout")
        text = design.read_text(encoding="utf-8")
        # Only the markdown *table* rows (lines starting with '|') are in
        # scope — historical amendment-log prose is allowed to name model ids
        # when recording what happened on a given date.
        table_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith("|")]
        model_id_re = re.compile(r"claude-[a-z0-9-]+")
        offending = [ln for ln in table_lines if model_id_re.search(ln)]
        self.assertEqual(offending, [], f"concrete model id in tier-chart table row(s): {offending}")


if __name__ == "__main__":
    unittest.main()
