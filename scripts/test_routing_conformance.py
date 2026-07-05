#!/usr/bin/env python3
"""Tests for src/token-audit/scripts/routing_conformance.py (PLAN-efficiency-automation task 8).

A fixture set of dispatch records — some matching the routing table, some
not, some with no announced model at all — is correctly classified as
model-used vs. work-type, with no-announcement cases counted as violations
regardless of what the expected model would have been.

stdlib only — no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "token-audit" / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


rc = _load("routing_conformance")


class TestConformanceReport(unittest.TestCase):
    RECORDS = [
        # matches: explorer -> mechanical-log-scraping -> claude-sonnet-5
        rc.DispatchRecord(role="explorer", agent_count=1, model_id="claude-sonnet-5", tier_source="ROLE-MATCH"),
        # mismatches: documenter's expected is claude-sonnet-5 (wiki-mechanical-plus), announced opus
        rc.DispatchRecord(role="documenter", agent_count=1, model_id="claude-opus-4-8", tier_source="FRONTMATTER"),
        # violation: no announcement at all
        rc.DispatchRecord(role="verification-clerk", agent_count=3, model_id=None, tier_source=None),
        # another match: adversarial-reviewer -> research-adversarial-audit -> claude-opus-4-8
        rc.DispatchRecord(role="adversarial-reviewer", agent_count=2, model_id="claude-opus-4-8", tier_source="ROLE-MATCH"),
        # another violation: unmatched role, no announcement
        rc.DispatchRecord(role="totally-unknown-role", agent_count=1, model_id=None, tier_source=None),
    ]

    def test_totals(self):
        report = rc.conformance_report(self.RECORDS)
        self.assertEqual(report["total"], 5)

    def test_matches_counted_correctly(self):
        report = rc.conformance_report(self.RECORDS)
        self.assertEqual(report["matches"], 2)

    def test_mismatches_counted_correctly(self):
        report = rc.conformance_report(self.RECORDS)
        self.assertEqual(report["mismatches"], 1)

    def test_no_announcement_cases_counted_as_violations(self):
        report = rc.conformance_report(self.RECORDS)
        self.assertEqual(report["violations_no_announcement"], 2)

    def test_violation_counted_regardless_of_role_being_known_or_not(self):
        # one violation has a known role (verification-clerk), the other doesn't
        # (totally-unknown-role) — both count as violations identically.
        report = rc.conformance_report(self.RECORDS)
        violation_roles = {
            d["role"] for d in report["details"] if d["status"] == "VIOLATION-NO-ANNOUNCEMENT"
        }
        self.assertEqual(violation_roles, {"verification-clerk", "totally-unknown-role"})

    def test_details_carry_expected_model_id(self):
        report = rc.conformance_report(self.RECORDS)
        by_role = {d["role"]: d for d in report["details"]}
        self.assertEqual(by_role["documenter"]["expected_model_id"], "claude-sonnet-5")
        self.assertEqual(by_role["documenter"]["status"], "MISMATCH")

    def test_empty_records_report_all_zero(self):
        report = rc.conformance_report([])
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["matches"], 0)
        self.assertEqual(report["mismatches"], 0)
        self.assertEqual(report["violations_no_announcement"], 0)
        self.assertEqual(report["inherited_or_default"], 0)


class TestInheritedLabelHandling(unittest.TestCase):
    """R2.5 task 9 / P12 addendum: below host 2.1.198, a built-in agent's own
    fixed model default and true `model:` frontmatter inheritance surface
    identically — no agent-def introspection exists yet to tell them apart.
    An INHERITED record must count as its own class, never guessed into
    MATCH/MISMATCH/VIOLATION either way."""

    RECORDS = [
        rc.DispatchRecord(role="explorer", agent_count=1, model_id="claude-sonnet-5", tier_source="ROLE-MATCH"),
        rc.DispatchRecord(role="documenter", agent_count=1, model_id="claude-opus-4-8", tier_source="INHERITED"),
        rc.DispatchRecord(role="tech-lead", agent_count=1, model_id="claude-sonnet-5", tier_source="INHERITED"),
        rc.DispatchRecord(role="verification-clerk", agent_count=3, model_id=None, tier_source=None),
    ]

    def test_inherited_records_counted_in_their_own_bucket(self):
        report = rc.conformance_report(self.RECORDS)
        self.assertEqual(report["inherited_or_default"], 2)

    def test_inherited_records_never_counted_as_match_mismatch_or_violation(self):
        report = rc.conformance_report(self.RECORDS)
        self.assertEqual(report["matches"], 1)          # explorer only
        self.assertEqual(report["mismatches"], 0)        # neither INHERITED record guessed as a mismatch
        self.assertEqual(report["violations_no_announcement"], 1)  # verification-clerk only

    def test_inherited_records_status_is_its_own_label(self):
        report = rc.conformance_report(self.RECORDS)
        inherited = {d["role"] for d in report["details"] if d["status"] == "INHERITED-OR-DEFAULT"}
        self.assertEqual(inherited, {"documenter", "tech-lead"})

    def test_re_audit_trigger_named_explicitly_in_report_output(self):
        # Not just in the module's docstring — a session reading the report
        # dict alone (without opening the source) must still see the caveat.
        report = rc.conformance_report(self.RECORDS)
        self.assertIn("2.1.198", report["re_audit_trigger"])
        self.assertIn("introspection", report["re_audit_trigger"])

    def test_re_audit_trigger_present_even_with_no_inherited_records(self):
        report = rc.conformance_report([
            rc.DispatchRecord(role="explorer", agent_count=1, model_id="claude-sonnet-5", tier_source="ROLE-MATCH"),
        ])
        self.assertIn("2.1.198", report["re_audit_trigger"])


if __name__ == "__main__":
    unittest.main()
