#!/usr/bin/env python3
"""Tests for src/privacy/semgrep/privacy-taint-pack.yml (PLAN-wave-d-tokens-
and-privacy task 5) -- the four mechanizable privacy checks (PII-in-URL,
PII-in-client-storage, plaintext-columns, third-party-sinks).

Each category has a positive fixture (semgrep must flag it) and a negative
fixture (semgrep must stay silent) under scripts/fixtures/privacy-semgrep/.
Graceful-skip when the `semgrep` binary isn't installed -- matches this
codebase's own convention for an optional external tool (mirrors how the
gemini-cli cross-review tests / sqlite-vec tests degrade).

stdlib only -- no pytest. Shells out to the real `semgrep` CLI (not mocked)
so a rule-syntax regression or a pattern that silently stops matching is
caught for real, not just YAML-parsed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PACK = _ROOT / "src" / "privacy" / "scripts" / "privacy-taint-pack.yml"
_FIXTURES = _HERE / "fixtures" / "privacy-semgrep"

_SEMGREP = shutil.which("semgrep")


def _run_semgrep(fixture: Path) -> list[dict]:
    result = subprocess.run(
        [_SEMGREP, "--config", str(_PACK), str(fixture), "--quiet", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(result.stdout)
    return data["results"]


@unittest.skipUnless(_SEMGREP, "semgrep binary not installed — pack tests skipped")
@unittest.skipUnless(_PACK.is_file(), f"{_PACK} not present")
class PrivacyTaintPackValidityTests(unittest.TestCase):
    def test_pack_yaml_is_valid_semgrep_config(self):
        result = subprocess.run(
            [_SEMGREP, "--validate", "--config", str(_PACK)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(_SEMGREP, "semgrep binary not installed — pack tests skipped")
@unittest.skipUnless(_PACK.is_file(), f"{_PACK} not present")
class PrivacyTaintPackFixtureTests(unittest.TestCase):
    """Each of the four named categories: a positive fixture that must be
    flagged, and a negative fixture that must stay silent."""

    def test_pii_in_url_positive_is_flagged(self):
        results = _run_semgrep(_FIXTURES / "positive" / "pii_in_url.py")
        self.assertTrue(any("pii-in-url" in r["check_id"] for r in results), results)

    def test_pii_in_url_negative_is_silent(self):
        results = _run_semgrep(_FIXTURES / "negative" / "pii_in_url.py")
        self.assertEqual(results, [])

    def test_pii_in_client_storage_positive_is_flagged(self):
        results = _run_semgrep(_FIXTURES / "positive" / "pii_in_client_storage.js")
        self.assertTrue(any("pii-in-client-storage" in r["check_id"] for r in results), results)

    def test_pii_in_client_storage_negative_is_silent(self):
        results = _run_semgrep(_FIXTURES / "negative" / "pii_in_client_storage.js")
        self.assertEqual(results, [])

    def test_plaintext_columns_positive_is_flagged(self):
        results = _run_semgrep(_FIXTURES / "positive" / "plaintext_columns.py")
        self.assertTrue(any("plaintext-personal-column" in r["check_id"] for r in results), results)

    def test_plaintext_columns_negative_is_silent(self):
        # Hashed before insert — must not be flagged.
        results = _run_semgrep(_FIXTURES / "negative" / "plaintext_columns.py")
        self.assertEqual(results, [])

    def test_third_party_sink_positive_is_flagged(self):
        results = _run_semgrep(_FIXTURES / "positive" / "third_party_sink.py")
        self.assertTrue(any("third-party-sink" in r["check_id"] for r in results), results)

    def test_third_party_sink_negative_is_silent(self):
        results = _run_semgrep(_FIXTURES / "negative" / "third_party_sink.py")
        self.assertEqual(results, [])


@unittest.skipUnless(_SEMGREP, "semgrep binary not installed — pack tests skipped")
@unittest.skipUnless(_PACK.is_file(), f"{_PACK} not present")
class PrivacyTaintPackFindingShapeTests(unittest.TestCase):
    """Findings carry the ASVS id + PRIVACY-RISK message shape the
    privacy-review skill's own falsifiable output contract expects."""

    def test_finding_message_carries_privacy_risk_and_asvs_id(self):
        results = _run_semgrep(_FIXTURES / "positive" / "pii_in_url.py")
        self.assertTrue(results)
        msg = results[0]["extra"]["message"]
        self.assertIn("PRIVACY-RISK", msg)
        self.assertIn("ASVS-", msg)


if __name__ == "__main__":
    unittest.main()
