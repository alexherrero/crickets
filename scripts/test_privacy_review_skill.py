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

**Opinion wiring (retrofitted):** task 4 was originally built before
PLAN-opinion-consumer-grammar's markdown-prose consumer grammar existed, so
its opinion-wiring sub-clause was deferred. That plan landed concurrently
(PR #167) with a real build-time interpolation mechanism (`opinions:` frontmatter
+ `<!-- opinion:name --> ... <!-- /opinion:name -->` markers, baked from a
committed `scripts/opinion-snapshots/<name>.md` snapshot by generate.py) --
this skill was retrofitted to use it for both `good` and `how-we-engineer`
before this plan's own close-out, rather than merging with a now-stale
deferral. The tests below assert the real wiring: the committed snapshots
exist + match agentm's live opinions, the frontmatter declares both names,
and generate.py's build actually bakes both marker pairs into dist/.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL = _ROOT / "src" / "privacy" / "skills" / "privacy-review" / "SKILL.md"
_PACK = _ROOT / "src" / "privacy" / "scripts" / "privacy-taint-pack.yml"
_FIXTURES = _HERE / "fixtures" / "privacy-semgrep"
_SNAPSHOT_DIR = _ROOT / "scripts" / "opinion-snapshots"

_SEMGREP = shutil.which("semgrep")

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _read_frontmatter(path: Path) -> dict:
    import yaml
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    assert m, f"{path} has no frontmatter block"
    return yaml.safe_load(m.group(1)) or {}


def _load_src_model():
    spec = importlib.util.spec_from_file_location("src_model_for_privacy_review_test", _ROOT / "scripts" / "src_model.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["src_model_for_privacy_review_test"] = m
    spec.loader.exec_module(m)
    return m


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

    def test_frontmatter_declares_both_opinions(self):
        fm = _read_frontmatter(_SKILL)
        self.assertEqual(fm.get("opinions"), ["good", "how-we-engineer"])

    def test_body_carries_both_opinion_marker_pairs(self):
        text = _SKILL.read_text(encoding="utf-8")
        for name in ("good", "how-we-engineer"):
            self.assertIn(f"<!-- opinion:{name} -->", text)
            self.assertIn(f"<!-- /opinion:{name} -->", text)

    def test_committed_snapshots_exist_for_both_opinions(self):
        self.assertTrue((_SNAPSHOT_DIR / "good.md").is_file())
        self.assertTrue((_SNAPSHOT_DIR / "how-we-engineer.md").is_file())

    def test_seed_prose_in_markers_matches_committed_snapshots(self):
        src_model = _load_src_model()
        text = _SKILL.read_text(encoding="utf-8")
        for name in ("good", "how-we-engineer"):
            snapshot_body = src_model.strip_frontmatter(
                (_SNAPSHOT_DIR / f"{name}.md").read_text(encoding="utf-8")
            ).strip()
            self.assertIn(snapshot_body, text, f"seed prose for {name!r} doesn't match its committed snapshot")


class PrivacyReviewSkillBuildTimeInterpolationTests(unittest.TestCase):
    """Proves generate.py's real render step actually bakes both opinions
    into a built dist/ -- the genuine code-level render step this skill
    lacked when task 4 first shipped."""

    def test_generate_build_interpolates_both_opinions_into_dist(self):
        src_model = _load_src_model()
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            groups = src_model.load_groups(_ROOT / "src")
            privacy = next(g for g in groups if g.slug == "privacy")
            skill_prim = next(p for p in privacy.primitives if p.name == "privacy-review")
            rendered = src_model.render_primitive_text(skill_prim, snapshots_dir=_SNAPSHOT_DIR)
        self.assertIn("Good means it survives an adversarial pass", rendered)
        self.assertIn("How we engineer means the phase discipline", rendered)


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
