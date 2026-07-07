#!/usr/bin/env python3
"""Tests for src/research/scripts/codebase_improvement.py (crickets
wave-c-research, PLAN-wave-c-research-forward-learning task 2).

Not a bridge test -- codebase-improvement scans a target repo directly
(stdlib-only pattern match, no agentm dependency for the detection itself)
and writes its finding in the same watchlist entry shape
forward_learning.py uses, so agentm's watchlist_review.py picks it up as
one merged review surface without needing to call back into agentm.

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
_SRC = _ROOT / "src" / "research" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


codebase_improvement = _load("research_codebase_improvement", _SRC / "codebase_improvement.py")


def _snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class CodebaseImprovementTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "old_module.py").write_text(
            "import legacy_json_parser\n\ndef load(data):\n    return legacy_json_parser.parse(data)\n",
            encoding="utf-8",
        )
        (self.repo / "fine_module.py").write_text(
            "import json\n\ndef load(data):\n    return json.loads(data)\n",
            encoding="utf-8",
        )
        self.insight = codebase_improvement.ResearchInsight(
            slug="drop-legacy-json-parser",
            title="legacy_json_parser is superseded by stdlib json",
            stale_pattern="legacy_json_parser",
            recommendation="Replace legacy_json_parser with the stdlib json module.",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_stale_pattern_produces_exactly_one_watchlist_finding(self):
        written = codebase_improvement.improve(self.vault, self.repo, self.insight, now=1_700_000_000.0)
        self.assertEqual(len(written), 1)
        entry_text = written[0].read_text(encoding="utf-8")
        self.assertIn("old_module.py", entry_text)
        self.assertNotIn("fine_module.py", entry_text)

    def test_no_stale_pattern_produces_zero_findings(self):
        clean_insight = codebase_improvement.ResearchInsight(
            slug="nothing-stale",
            title="a pattern that matches nothing in this fixture repo",
            stale_pattern="totally_absent_symbol_xyz",
            recommendation="n/a",
        )
        written = codebase_improvement.improve(self.vault, self.repo, clean_insight, now=1_700_000_000.0)
        self.assertEqual(written, [])

    def test_fixture_repo_source_is_byte_identical_before_and_after(self):
        pre = _snapshot(self.repo)
        codebase_improvement.improve(self.vault, self.repo, self.insight, now=1_700_000_000.0)
        post = _snapshot(self.repo)
        self.assertEqual(pre, post)

    def test_main_cli_smoke(self):
        rc = codebase_improvement.main(
            [
                "--vault-path", str(self.vault),
                "--repo-path", str(self.repo),
                "--insight-slug", self.insight.slug,
                "--insight-title", self.insight.title,
                "--stale-pattern", self.insight.stale_pattern,
                "--recommendation", self.insight.recommendation,
            ]
        )
        self.assertEqual(rc, 0)


class RescanNeverResetsOperatorReviewTests(unittest.TestCase):
    """Regression test for an adversarial-review finding: a rescan (a
    scheduled job re-running over the same insight, or simply a new file
    joining an already-surfaced pattern) must never silently reset an
    operator's already-recorded review decision back to pending-review --
    that decision is the entire point of the watchlist review workflow."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "a.py").write_text("legacy_json_parser\n", encoding="utf-8")
        self.insight = codebase_improvement.ResearchInsight(
            slug="drop-legacy-json-parser",
            title="legacy_json_parser is superseded by stdlib json",
            stale_pattern="legacy_json_parser",
            recommendation="Replace legacy_json_parser with the stdlib json module.",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_reviewed_entry_survives_a_rescan_with_a_new_match(self):
        written = codebase_improvement.improve(self.vault, self.repo, self.insight, now=1_700_000_000.0)
        entry = written[0]
        entry.write_text(
            entry.read_text(encoding="utf-8").replace("status: pending-review", "status: reviewed-rejected"),
            encoding="utf-8",
        )

        # A second matching file appears -- the kind of thing a scheduled
        # rescan would naturally pick up.
        (self.repo / "b.py").write_text("legacy_json_parser\n", encoding="utf-8")
        result = codebase_improvement.improve(self.vault, self.repo, self.insight, now=1_700_100_000.0)

        self.assertEqual(result, [])  # no-op: already reviewed, never rewritten
        self.assertIn("status: reviewed-rejected", entry.read_text(encoding="utf-8"))

    def test_pending_entry_is_updated_on_rescan_with_created_preserved(self):
        written = codebase_improvement.improve(self.vault, self.repo, self.insight, now=1_700_000_000.0)
        entry = written[0]
        first_text = entry.read_text(encoding="utf-8")
        self.assertIn("status: pending-review", first_text)
        self.assertNotIn("b.py", first_text)

        (self.repo / "b.py").write_text("legacy_json_parser\n", encoding="utf-8")
        result = codebase_improvement.improve(self.vault, self.repo, self.insight, now=1_700_100_000.0)

        self.assertEqual(len(result), 1)
        second_text = entry.read_text(encoding="utf-8")
        self.assertIn("status: pending-review", second_text)
        self.assertIn("b.py", second_text)  # matched-file list refreshed
        self.assertIn("created: 2023-11-14T22:13:20+00:00", second_text)  # preserved from the first write
        self.assertIn("updated: 2023-11-16T02:00:00+00:00", second_text)  # advanced


if __name__ == "__main__":
    unittest.main()
