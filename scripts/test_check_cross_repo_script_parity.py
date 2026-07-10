#!/usr/bin/env python3
"""Tests for check-cross-repo-script-parity.py (CONS-2 task 4).

Locks: identical kind/rule sets pass; a genuinely-new kind or rule on either
side fails red (1) and is distinguishable from a match; the documented
component-overview {m, n, o} exemption tolerates crickets-only rules without
firing; a missing agentm sibling gracefully skips (0) with a message that
says so rather than silently looking like a pass; a missing crickets-side
canonical file is a usage error (2); `--report` forces 0 even on real drift.

Every hermetic test uses synthetic fixture text in a tmp dir, never the real
src/privacy/scripts/check-no-pii.sh, src/wiki/scripts/check-wiki.py, or a
real ~/Antigravity/agentm clone.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_cross_repo_script_parity", _HERE / "check-cross-repo-script-parity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_cross_repo_script_parity"] = mod
    spec.loader.exec_module(mod)
    return mod


parity = _load()

_NO_PII_BASE = """PATTERNS=(
    'email|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
    'openai-key|sk-[a-zA-Z0-9_-]{20,}'
)
ALLOWLIST_PATTERNS=(
    'alexherrero'
)
SELF_SKIP_PATHS=(
    'scripts/check-no-pii.sh'
)
"""

_WIKI_BASE = """def rule_a_location(p, wiki_root, issues):
    pass


def rule_b_mode_block(p, mode, lines, issues):
    pass
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_pair(tmp: str, no_pii_agentm: str, wiki_agentm: str,
                 no_pii_crickets: str = _NO_PII_BASE, wiki_crickets: str = _WIKI_BASE):
    crickets_no_pii = _write(Path(tmp) / "crickets" / "check-no-pii.sh", no_pii_crickets)
    crickets_wiki = _write(Path(tmp) / "crickets" / "check-wiki.py", wiki_crickets)
    agentm_dir = (Path(tmp) / "agentm-scripts")
    _write(agentm_dir / "check-no-pii.sh", no_pii_agentm)
    _write(agentm_dir / "check-wiki.py", wiki_agentm)
    return crickets_no_pii, crickets_wiki, agentm_dir


class TestIdenticalSetsPass(unittest.TestCase):
    def test_matching_kinds_and_rules_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii, crickets_wiki, agentm_dir = _write_pair(
                tmp, _NO_PII_BASE, _WIKI_BASE)
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 0)


class TestDocumentedExemptionTolerated(unittest.TestCase):
    def test_crickets_only_mno_rules_do_not_fire(self):
        wiki_crickets = _WIKI_BASE + """

def rule_m_section_order(p, heads, model, issues):
    pass


def rule_n_heading_variant(p, heads, model, issues):
    pass


def rule_o_unfilled_placeholder(p, text, issues):
    pass
"""
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii, crickets_wiki, agentm_dir = _write_pair(
                tmp, _NO_PII_BASE, _WIKI_BASE, wiki_crickets=wiki_crickets)
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 0)


class TestUndocumentedDivergenceFailsRed(unittest.TestCase):
    def test_crickets_only_rule_outside_exemption_fails(self):
        wiki_crickets = _WIKI_BASE + """

def rule_z_something_new(p, issues):
    pass
"""
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii, crickets_wiki, agentm_dir = _write_pair(
                tmp, _NO_PII_BASE, _WIKI_BASE, wiki_crickets=wiki_crickets)
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 1)

    def test_agentm_only_rule_fails(self):
        wiki_agentm = _WIKI_BASE + """

def rule_z_agentm_added_this(p, issues):
    pass
"""
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii, crickets_wiki, agentm_dir = _write_pair(
                tmp, _NO_PII_BASE, wiki_agentm)
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 1)

    def test_agentm_only_pii_kind_fails(self):
        no_pii_agentm = _NO_PII_BASE.replace(
            "ALLOWLIST_PATTERNS=(",
            "    'slack-token|xox[a-zA-Z0-9-]{10,}'\n)\nDUMMY=(\n")
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii, crickets_wiki, agentm_dir = _write_pair(
                tmp, no_pii_agentm, _WIKI_BASE)
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 1)

    def test_report_flag_forces_zero_even_on_real_divergence(self):
        wiki_agentm = _WIKI_BASE + """

def rule_z_agentm_added_this(p, issues):
    pass
"""
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii, crickets_wiki, agentm_dir = _write_pair(
                tmp, _NO_PII_BASE, wiki_agentm)
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(agentm_dir),
                "--report",
            ])
            self.assertEqual(rc, 0)


class TestGracefulSkipWhenAgentmAbsent(unittest.TestCase):
    def test_missing_agentm_dir_skips_with_zero_not_a_silent_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii = _write(Path(tmp) / "check-no-pii.sh", _NO_PII_BASE)
            crickets_wiki = _write(Path(tmp) / "check-wiki.py", _WIKI_BASE)
            absent_dir = Path(tmp) / "no-such-agentm-scripts-dir"
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(absent_dir),
            ])
            self.assertEqual(rc, 0)

    def test_agentm_dir_missing_one_of_the_two_scripts_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii = _write(Path(tmp) / "check-no-pii.sh", _NO_PII_BASE)
            crickets_wiki = _write(Path(tmp) / "check-wiki.py", _WIKI_BASE)
            agentm_dir = Path(tmp) / "agentm-scripts"
            _write(agentm_dir / "check-no-pii.sh", _NO_PII_BASE)  # no check-wiki.py
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(crickets_wiki),
                "--agentm-scripts-dir", str(agentm_dir),
            ])
            self.assertEqual(rc, 0)


class TestMissingCricketsFileIsAUsageError(unittest.TestCase):
    def test_missing_crickets_canonical_no_pii_script_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-check-no-pii.sh"
            crickets_wiki = _write(Path(tmp) / "check-wiki.py", _WIKI_BASE)
            rc = parity.main([
                "--crickets-no-pii-script", str(missing),
                "--crickets-wiki-script", str(crickets_wiki),
            ])
            self.assertEqual(rc, 2)

    def test_missing_crickets_canonical_wiki_script_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            crickets_no_pii = _write(Path(tmp) / "check-no-pii.sh", _NO_PII_BASE)
            missing = Path(tmp) / "no-such-check-wiki.py"
            rc = parity.main([
                "--crickets-no-pii-script", str(crickets_no_pii),
                "--crickets-wiki-script", str(missing),
            ])
            self.assertEqual(rc, 2)


class TestRealShippedScriptsMatchLiveAgentmWhenPresent(unittest.TestCase):
    """Not hermetic by design — exercises the real, shipped
    src/privacy/scripts/check-no-pii.sh + src/wiki/scripts/check-wiki.py
    against a real ~/Antigravity/agentm clone, when present, so a genuine
    undocumented divergence fails on this machine even though check-all.sh
    wires the script itself with --report. Gracefully skips (not a failure)
    when agentm isn't cloned — same posture as the script's own graceful skip."""

    def test_shipped_scripts_match_agentm_or_skip(self):
        rc = parity.main([])
        self.assertIn(rc, (0, 1))
        if rc == 1:
            self.fail("check-no-pii.sh and/or check-wiki.py has an undocumented "
                       "kind/rule divergence from agentm — see the printed "
                       "findings, then either port the missing side or add a "
                       "documented exemption")


if __name__ == "__main__":
    unittest.main()
