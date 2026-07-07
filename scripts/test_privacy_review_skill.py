#!/usr/bin/env python3
"""Tests for src/privacy/skills/privacy-review/SKILL.md (PLAN-wave-d-tokens-
and-privacy task 4).

privacy-review is a static markdown skill (agent-executed prompt, no code-
level render step) -- the same shape as its own named model, security-
review. Its own agent-facing reasoning ("is this diff missing a retention
policy") isn't unit-testable without dispatching a real LLM, but the ONE
genuinely mechanical piece the skill's own Step 1 documents -- shelling out
to the bundled Semgrep pack -- is fully deterministic and IS tested here,
end to end, exactly as the skill instructs an agent to invoke it: given a
fixture file with a known privacy issue, the documented command emits a
correctly-shaped PRIVACY-RISK <file>:<line> [ASVS-id] finding; given a clean
fixture, it emits none. This is the falsifiable half of the skill's
contract; the LLM-judged half is exercised by an agent following the skill
body, not by this suite.

Also asserts the skill file's own frontmatter conforms to this repo's
skill-kind contract (src_model.py's read_frontmatter + the fields every
other SKILL.md in this repo carries) -- a build-pipeline-shaped assertion,
not a judgment call.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL = _ROOT / "src" / "privacy" / "skills" / "privacy-review" / "SKILL.md"
_PACK = _ROOT / "src" / "privacy" / "scripts" / "privacy-taint-pack.yml"
_FIXTURES = _HERE / "fixtures" / "privacy-semgrep"

_SEMGREP = shutil.which("semgrep")

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _read_frontmatter(path: Path) -> dict:
    import yaml
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    assert m, f"{path} has no frontmatter block"
    return yaml.safe_load(m.group(1)) or {}


class PrivacyReviewSkillContractTests(unittest.TestCase):
    def test_skill_file_exists(self):
        self.assertTrue(_SKILL.is_file(), f"{_SKILL} not present")

    def test_frontmatter_has_required_fields(self):
        fm = _read_frontmatter(_SKILL)
        self.assertEqual(fm["name"], "privacy-review")
        self.assertEqual(fm["kind"], "skill")
        self.assertIn("claude-code", fm["supported_hosts"])
        self.assertIn("antigravity", fm["supported_hosts"])
        self.assertIn("version", fm)
        self.assertIn("install_scope", fm)

    def test_body_documents_the_privacy_risk_output_contract(self):
        text = _SKILL.read_text(encoding="utf-8")
        self.assertIn("PRIVACY-RISK", text)
        self.assertIn("NO PRIVACY ISSUES FOUND", text)

    def test_body_references_the_bundled_semgrep_pack(self):
        text = _SKILL.read_text(encoding="utf-8")
        self.assertIn("privacy-taint-pack.yml", text)

    def test_body_documents_the_opinion_wiring_deferral_honestly(self):
        # Per the plan's own caveat: a static markdown skill has no render
        # step to inject a resolved opinion into today -- this must be
        # documented as deferred, not silently omitted or falsely claimed
        # as wired.
        text = _SKILL.read_text(encoding="utf-8")
        self.assertIn("Deferred", text)
        self.assertIn("opinion_resolve", text)


@unittest.skipUnless(_SEMGREP, "semgrep binary not installed — end-to-end skill test skipped")
@unittest.skipUnless(_SKILL.is_file() and _PACK.is_file(), "skill or pack missing")
class PrivacyReviewSkillStep1EndToEndTests(unittest.TestCase):
    """Drives the skill's own documented Step 1 command verbatim (modulo
    substituting the real pack path for ${CLAUDE_PLUGIN_ROOT}) against the
    task 5 fixtures -- the plan's own verification wording: a fixture with a
    known privacy issue emits a correctly-shaped PRIVACY-RISK finding citing
    the right ASVS id; a clean fixture emits none."""

    def _run_documented_semgrep_command(self, fixture: Path) -> list[dict]:
        result = subprocess.run(
            [_SEMGREP, "--config", str(_PACK), "--json", str(fixture)],
            capture_output=True, text=True, timeout=60,
        )
        return json.loads(result.stdout)["results"]

    def test_known_privacy_issue_fixture_yields_correctly_shaped_finding(self):
        results = self._run_documented_semgrep_command(
            _FIXTURES / "positive" / "pii_in_url.py"
        )
        self.assertTrue(results, "expected at least one finding on the known-issue fixture")
        finding = results[0]
        self.assertIn("PRIVACY-RISK", finding["extra"]["message"])
        self.assertIn("ASVS-8.3.4", finding["extra"]["message"])
        self.assertEqual(finding["extra"]["metadata"]["category"], "pii-in-url")

    def test_clean_fixture_yields_no_findings(self):
        results = self._run_documented_semgrep_command(
            _FIXTURES / "negative" / "pii_in_url.py"
        )
        self.assertEqual(results, [])

    def test_third_party_sink_fixture_cites_correct_asvs_id(self):
        results = self._run_documented_semgrep_command(
            _FIXTURES / "positive" / "third_party_sink.py"
        )
        self.assertTrue(results)
        self.assertIn("ASVS-8.3.6", results[0]["extra"]["message"])


if __name__ == "__main__":
    unittest.main()
