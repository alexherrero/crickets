#!/usr/bin/env python3
"""Tests for scripts/check-capability-naming.py (AG Phase-2, C2).

Asserts the naming rule: bans the reserved `-workflows` suffix (except the spine
`developer-workflows`) and Opinion names; proves the *current* src set conforms.
Run: python3 scripts/test_check_capability_naming.py
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_capability_naming", _HERE / "check-capability-naming.py")
ccn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ccn)

try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


class TestNamingRule(unittest.TestCase):
    # --- pure logic (no fixtures) ---

    def test_clean_set_passes(self):
        self.assertEqual(
            ccn.find_naming_violations(
                {"code-review": ["adversarial-review"], "pii": ["privacy"],
                 "github-ci": ["ci-repair"]}),
            [])

    def test_banned_workflows_suffix_capability(self):
        v = ccn.find_naming_violations({"x": ["review-workflows"]})
        self.assertTrue(any("review-workflows" in m and "-workflows" in m for m in v), v)

    def test_banned_workflows_suffix_plugin_slug(self):
        v = ccn.find_naming_violations({"release-workflows": ["release"]})
        self.assertTrue(any("release-workflows" in m for m in v), v)

    def test_developer_workflows_is_exempt(self):
        # The spine keeps the reserved suffix — as a plugin slug AND a capability.
        self.assertEqual(
            ccn.find_naming_violations(
                {"developer-workflows": ["developer-workflows", "plan", "work"]}),
            [])

    def test_developer_safety_prefix_allowed(self):
        # The developer- *prefix* is fine; only the -workflows *suffix* is gated.
        self.assertEqual(
            ccn.find_naming_violations({"developer-safety": ["recoverability"]}),
            [])

    def test_opinion_names_banned(self):
        # The canonical nine-name catalog (agentm-opinion-registry.md,
        # 2026-06-26) — reconciled from a stale 4-name set that missed 6 of
        # these and banned 2 ("efficiency", "quality") never in the catalog.
        for bad in ("done", "good", "efficient", "how-we-engineer",
                    "recoverable", "private", "ready", "simple", "worth-knowing"):
            v = ccn.find_naming_violations({"x": [bad]})
            self.assertTrue(any(bad in m and "Opinion" in m for m in v), (bad, v))

    def test_stale_pre_reconciliation_names_no_longer_banned(self):
        # "efficiency" and "quality" were never real Opinion names — the old
        # 4-name set banned them by mistake. Confirms the fix actually
        # narrows as well as widens the guard, not just adds to it.
        for not_an_opinion in ("efficiency", "quality"):
            v = ccn.find_naming_violations({"x": [not_an_opinion]})
            self.assertEqual(v, [])

    # --- the live set conforms (regression on real src/) ---

    @unittest.skipUnless(HAVE_YAML, "PyYAML required")
    def test_current_src_conforms(self):
        src = _HERE.parent / "src"
        self.assertEqual(ccn.find_naming_violations(ccn.load_caps_by_slug(src)), [])

    # --- main() exit codes via a temp src fixture ---

    @unittest.skipUnless(HAVE_YAML, "PyYAML required")
    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "src"
            (src / "alpha").mkdir(parents=True)
            (src / "alpha" / "group.yaml").write_text(
                "name: A\ndescription: d\nstandalone: true\nrequires: []\n"
                "capabilities: [design]\n", encoding="utf-8")
            self.assertEqual(ccn.main(["--src", str(src)]), 0)
            (src / "bad").mkdir(parents=True)
            (src / "bad" / "group.yaml").write_text(
                "name: B\ndescription: d\nstandalone: true\nrequires: []\n"
                "capabilities: [ready]\n", encoding="utf-8")
            self.assertEqual(ccn.main(["--src", str(src)]), 1)


if __name__ == "__main__":
    unittest.main()
