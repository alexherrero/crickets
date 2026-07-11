#!/usr/bin/env python3
"""Tests for check-slop.py (PLAN-r3-voice-mechanism task 2).

Locks: markdown-aware stripping, inline-ignore, exit-code tiers, JSONL
emission, and the two corpus-calibration verification criteria from the
plan — zero error-tier findings + near-zero warning rate on prose-audit.json's
72 clean pages, and the same tells surfacing on the 3 named score-2/3 pages.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
# Repo roots resolved relative to this file (never a hardcoded absolute
# literal — see AGENTS.md's vault-path convention: "resolve, don't recall").
# This script lives at <crickets>/scripts/; agentm is the documented sibling
# checkout (env override for a non-standard layout).
_CRICKETS_ROOT = _SCRIPTS.parent
_REPO_ROOTS = {
    "crickets": _CRICKETS_ROOT,
    "agentm": Path(os.environ.get("AGENTM_REPO_ROOT", "").strip() or (_CRICKETS_ROOT.parent / "agentm")),
}


def _resolve_vault_prose_audit() -> Path | None:
    """Resolve prose-audit.json via agentm_config.py's vault_path (never a
    hardcoded absolute path — the vault mount point is machine-specific)."""
    config_script = _REPO_ROOTS["agentm"] / "scripts" / "agentm_config.py"
    if not config_script.is_file():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(config_script), "--get", "vault_path"],
            capture_output=True, text=True, timeout=10,
        )
    except OSError:
        return None
    vault_path = result.stdout.strip()
    if result.returncode != 0 or not vault_path:
        return None
    candidate = (
        Path(vault_path) / "projects" / "agentm" / "_harness"
        / "mythos-readiness-handoff" / "prose-audit.json"
    )
    return candidate if candidate.is_file() else None


_VAULT_PROSE_AUDIT = _resolve_vault_prose_audit() or Path("/nonexistent-prose-audit.json")


def _load(filename: str, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, _SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


slop = _load("check-slop.py", "check_slop_under_test")


class TestMarkdownAwareStripping(unittest.TestCase):
    def test_fenced_code_block_not_scanned(self):
        text = "prose\n```\nleverage this seamless robust thing\n```\nmore prose"
        stripped = slop.strip_markdown_noise(text)
        self.assertNotIn("leverage", stripped)

    def test_link_url_stripped_text_kept(self):
        text = "see [the seamless guide](https://example.com/leverage-this)"
        stripped = slop.strip_markdown_noise(text)
        self.assertIn("seamless", stripped)
        self.assertNotIn("example.com", stripped)

    def test_ignore_block_stripped(self):
        text = ("keep this\n<!-- slop-ignore-start -->\nrobust leverage\n"
                "<!-- slop-ignore-end -->\nkeep this too")
        stripped = slop.strip_ignore_blocks(text)
        self.assertNotIn("robust", stripped)
        self.assertIn("keep this too", stripped)


class TestInlineIgnore(unittest.TestCase):
    def test_line_level_ignore_suppresses_named_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "page.md"
            f.write_text("this is robust <!-- slop-ignore: voice-a4-robust -->\n")
            rules = [{"id": "voice-a4-robust", "severity": "suggestion", "kind": "word",
                      "pattern": "robust", "hint": "h", "weight": 1, "source-url": "u"}]
            findings = slop.scan_file(f, rules)
            self.assertEqual(findings, [])

    def test_unignored_rule_still_fires(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "page.md"
            f.write_text("this is robust and comprehensive <!-- slop-ignore: voice-a4-robust -->\n")
            rules = [
                {"id": "voice-a4-robust", "severity": "suggestion", "kind": "word",
                 "pattern": "robust", "hint": "h", "weight": 1, "source-url": "u"},
                {"id": "voice-a4-comprehensive", "severity": "suggestion", "kind": "word",
                 "pattern": "comprehensive", "hint": "h", "weight": 1, "source-url": "u"},
            ]
            findings = slop.scan_file(f, rules)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].rule_id, "voice-a4-comprehensive")


class TestMetricThresholds(unittest.TestCase):
    def test_ceiling_metric_trips_above_threshold(self):
        text = "word " * 100 + "—" * 20
        metrics = slop.compute_metrics(text)
        self.assertGreater(metrics["em_dash_rate_per_1k"], 0)

    def test_floor_metric_direction(self):
        rule = {"id": "x", "severity": "warning", "kind": "metric",
                "pattern": "paragraph_length_variance_floor", "hint": "h",
                "weight": 1, "threshold": 100, "source-url": "u"}
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "uniform.md"
            para = "word " * 20
            f.write_text(f"{para}\n\n{para}\n\n{para}\n")
            findings = slop.scan_file(f, [rule])
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].rule_id, "x")

    def test_structural_nav_files_skip_tier_b_metrics(self):
        # Task 6 sweep finding: _Sidebar.md tripped bold-span-count (a bold-
        # heavy link index is not prose) — nav files are exempt from Tier-B.
        rule = {"id": "x", "severity": "warning", "kind": "metric",
                "pattern": "bold_span_count_per_1k", "hint": "h",
                "weight": 1, "threshold": 1, "source-url": "u"}
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("_Sidebar.md", "Home.md", "_Footer.md", "README.md"):
                f = Path(tmp) / name
                f.write_text("**a** **b** **c** **d** **e**\n")
                findings = slop.scan_file(f, [rule])
                self.assertEqual(findings, [], f"{name} should skip Tier-B metrics")
            f = Path(tmp) / "Storage-Seam-Concepts.md"
            f.write_text("**a** **b** **c** **d** **e**\n")
            findings = slop.scan_file(f, [rule])
            self.assertEqual(len(findings), 1, "ordinary prose pages still scan Tier-B")


class TestExitCodeTiers(unittest.TestCase):
    def _finding(self, severity):
        return slop.Finding(file="f.md", line=1, rule_id="x", severity=severity,
                             kind="word", snippet="x", hint="h")

    def test_error_always_fails(self):
        self.assertEqual(
            slop.compute_exit_code([self._finding("error")], strict=False, report_only=False), 1)

    def test_warning_fails_only_under_strict(self):
        findings = [self._finding("warning")]
        self.assertEqual(slop.compute_exit_code(findings, strict=False, report_only=False), 0)
        self.assertEqual(slop.compute_exit_code(findings, strict=True, report_only=False), 1)

    def test_suggestion_never_fails(self):
        findings = [self._finding("suggestion")]
        self.assertEqual(slop.compute_exit_code(findings, strict=True, report_only=False), 0)

    def test_report_forces_zero_even_with_error(self):
        findings = [self._finding("error")]
        self.assertEqual(slop.compute_exit_code(findings, strict=True, report_only=True), 0)


class TestJsonlEmission(unittest.TestCase):
    def test_emits_valid_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.jsonl"
            slop.emit_jsonl(str(out), passed=True)
            lines = out.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["suite"], "check-slop")
            self.assertEqual(record["axis"], "docs+voice health")
            self.assertEqual(record["check"], "voice-vocabulary-drift")
            self.assertTrue(record["pass"])
            self.assertEqual(record["weight"], 5)


class TestRatifiedCarveOuts(unittest.TestCase):
    """PLAN-r3-voice-mechanism task 5 verification 2 — the operator role-noun
    and term-of-art carve-outs produce no error/warning-tier finding."""

    def setUp(self):
        import rule_pack
        self.rules = rule_pack.load_shipped_pack()["rules"]

    def test_role_noun_use_of_the_operator_produces_no_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "page.md"
            f.write_text(
                "The operator reviews the plan before the worker starts, "
                "then the operator approves the release.\n"
            )
            findings = slop.scan_file(f, self.rules)
            self.assertEqual(findings, [])

    def test_term_of_art_first_class_produces_no_error_or_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "page.md"
            f.write_text("The resolver treats named plans as a first-class primitive.\n")
            findings = slop.scan_file(f, self.rules)
            blocking = [f for f in findings if f.severity in ("error", "warning")]
            self.assertEqual(blocking, [], f"expected no error/warning finding, got: {blocking}")
            # It should still surface as a low-severity suggestion (findings, not failures).
            ids = {fnd.rule_id for fnd in findings}
            self.assertIn("voice-a4-first-class", ids)

    def test_term_of_art_load_bearing_produces_no_error_or_warning(self):
        """CONS-3 task 3 — the carve-out extension: 'load-bearing' was already
        suggestion-tier (never blocking), but its hint didn't say so explicitly
        the way first-class/robust do. Locks the behavior + the documented
        carve-out together, mirroring the first-class test above exactly."""
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "page.md"
            f.write_text(
                "PyYAML is a real, permanent, load-bearing dependency "
                "(manifest parsing needs a YAML parser).\n"
            )
            findings = slop.scan_file(f, self.rules)
            blocking = [f for f in findings if f.severity in ("error", "warning")]
            self.assertEqual(blocking, [], f"expected no error/warning finding, got: {blocking}")
            ids = {fnd.rule_id for fnd in findings}
            self.assertIn("voice-a4-load-bearing", ids)


@unittest.skipUnless(_VAULT_PROSE_AUDIT.is_file(), "vault not reachable in this environment")
class TestCorpusCalibration(unittest.TestCase):
    """Plan Task 2 verification 1 + 2 — run against the real calibration corpus."""

    @classmethod
    def setUpClass(cls):
        with open(_VAULT_PROSE_AUDIT, encoding="utf-8") as f:
            cls.data = json.load(f)
        import rule_pack  # noqa: E402  (path already inserted by check-slop.py import)
        cls.rules = rule_pack.load_shipped_pack()["rules"]

    def _resolve(self, page: str) -> Path | None:
        repo, relpath = page.split(" ", 1)
        root = _REPO_ROOTS.get(repo)
        if root is None:
            return None
        full = root / relpath
        return full if full.is_file() else None

    def test_clean_corpus_zero_errors_near_zero_warnings(self):
        clean_pages = [p["page"] for p in self.data["pages"] if p["slop_score"] == 0]
        total_findings = 0
        error_findings = []
        warning_findings = []
        scanned = 0
        for page in clean_pages:
            path = self._resolve(page)
            if path is None:
                continue
            scanned += 1
            findings = slop.scan_file(path, self.rules)
            total_findings += len(findings)
            error_findings.extend(f for f in findings if f.severity == "error")
            warning_findings.extend(f for f in findings if f.severity == "warning")
        self.assertGreater(scanned, 60, "expected most of the 72 clean pages to resolve on disk")
        self.assertEqual(error_findings, [],
                          f"error-tier findings on clean corpus: {error_findings}")
        # near-zero: allow a small warning rate (investigate-worthy, not a hard bug)
        warning_rate = len(warning_findings) / scanned
        self.assertLess(warning_rate, 0.15,
                         f"warning rate {warning_rate:.2%} too high on clean corpus: {warning_findings}")

    def test_known_score2_score3_pages_surface_expected_tells(self):
        # Use-AgentMemory-In-Any-Agent.md's audit-named tells (arrow-notation,
        # bold-colon fragment leads in body prose) are deliberately excluded:
        # calibration confirmed a blanket bold-colon-lead rule would collide
        # with check-wiki.py's own sanctioned NOTE-block convention
        # ("**Goal:**" / "**Prereqs:**" are required fields, not slop) — these
        # tells are Tier-C judgment calls per research-slop-detection-voice.md
        # ("needs judgment ... NEVER the gate"), not this mechanical gate's scope.
        # Storage-Seam-Concepts.md's load-bearing hit was thinned by the task-6
        # sweep (PLAN-r3-voice-mechanism) -- it now surfaces the antithesis tell
        # instead, still confirming the mechanism catches a real tell on this page.
        expected_rule_hits = {
            "agentm wiki/explanation/Named-Plans.md": None,  # score 3, any finding expected
            "agentm wiki/explanation/Storage-Seam-Concepts.md": "voice-a3-antithesis-comma-not",
        }
        for page, expected_id in expected_rule_hits.items():
            path = self._resolve(page)
            if path is None:
                self.skipTest(f"{page} not resolvable on disk in this environment")
            findings = slop.scan_file(path, self.rules)
            self.assertTrue(findings, f"expected at least one finding on {page}")
            if expected_id:
                ids = {f.rule_id for f in findings}
                self.assertIn(expected_id, ids,
                              f"expected {expected_id} on {page}, got {ids}")


if __name__ == "__main__":
    unittest.main()
