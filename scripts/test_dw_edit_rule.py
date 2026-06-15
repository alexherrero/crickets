#!/usr/bin/env python3
"""Structural spec for the developer-workflows Edit-over-Write rule primitive
and the /clear-not-/compact reminder injected into plan.md and release.md.

Locks the load-bearing facts:

  * edit-over-write.md has valid frontmatter (kind: rule, hosts, version).
  * The rule body contains the Edit-over-Write rationale and the billed-output
    explanation (5× cost).
  * plan.md contains the /clear-not-/compact reminder in its close-out section.
  * release.md contains the /clear-not-/compact reminder in its close-out section.

`generate.py check` separately proves `dist/` mirrors the source.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_RULE = _ROOT / "src" / "developer-workflows" / "rules" / "edit-over-write.md"
_PLAN_CMD = _ROOT / "src" / "developer-workflows" / "commands" / "plan.md"
_RELEASE_CMD = _ROOT / "src" / "developer-workflows" / "commands" / "release.md"

sys.path.insert(0, str(_HERE))
from src_model import read_frontmatter  # noqa: E402


class TestEditOverWriteRuleFrontmatter(unittest.TestCase):
    """edit-over-write.md satisfies the rule manifest contract."""

    @classmethod
    def setUpClass(cls):
        cls.fm = read_frontmatter(_RULE) or {}

    def test_file_exists(self):
        self.assertTrue(_RULE.exists(), f"Missing: {_RULE}")

    def test_kind_is_rule(self):
        self.assertEqual(self.fm.get("kind"), "rule")

    def test_name_matches_file_stem(self):
        self.assertEqual(self.fm.get("name"), "edit-over-write")

    def test_has_description(self):
        self.assertTrue(str(self.fm.get("description", "")).strip(), "description is empty")

    def test_supported_hosts_present_and_non_empty(self):
        hosts = self.fm.get("supported_hosts")
        self.assertIsInstance(hosts, list, "supported_hosts must be a list")
        self.assertTrue(hosts, "supported_hosts must be non-empty")

    def test_version_present(self):
        self.assertIn("version", self.fm, "version field missing")


class TestEditOverWriteRuleBody(unittest.TestCase):
    """The rule body states the Edit-over-Write rationale and billed-output cost."""

    @classmethod
    def setUpClass(cls):
        cls.text = _RULE.read_text(encoding="utf-8").lower()

    def test_edit_over_write_rationale_present(self):
        # The rule must state the Edit-over-Write preference.
        self.assertIn("edit", self.text)
        self.assertIn("write", self.text)
        self.assertIn("existing", self.text)

    def test_billed_output_explanation_present(self):
        # Must explain why: Write re-emits the whole file (~5× billed output tokens).
        self.assertTrue(
            "5×" in self.text or "5x" in self.text or "five" in self.text,
            "billed-output cost explanation (5×) missing from rule body",
        )
        self.assertTrue(
            "output token" in self.text or "billed" in self.text,
            "billed-output explanation missing from rule body",
        )


class TestClearNotCompactReminder(unittest.TestCase):
    """plan.md and release.md each contain the /clear-not-/compact reminder."""

    def _assert_has_reminder(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        self.assertIn("/clear", text, f"{path.name} missing /clear reminder")
        self.assertIn("/compact", text, f"{path.name} missing /compact reference")
        self.assertIn("state is on disk", low, f"{path.name} missing 'state is on disk' rationale")

    def test_plan_md_has_clear_reminder(self):
        self._assert_has_reminder(_PLAN_CMD)

    def test_release_md_has_clear_reminder(self):
        self._assert_has_reminder(_RELEASE_CMD)


if __name__ == "__main__":
    unittest.main()
