#!/usr/bin/env python3
"""Structural spec for the developer-workflows Terse output-style primitive.

Locks the load-bearing facts so a later edit can't silently regress them:

  * Valid YAML frontmatter (kind, supported_hosts, version, name).
  * Three required prose sections covering: inter-tool silence default,
    keep-coding-instructions carve-out, and end-of-task status-report carve-out.
  * `lint_src.py` passes on the new primitive (indirectly confirmed by
    `check-all.sh`'s lint_src gate; a separate integration check).

`generate.py check` separately proves `dist/` mirrors the source, so asserting
the source spec here is sufficient.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_TERSE = _ROOT / "src" / "developer-workflows" / "output-styles" / "terse.md"

sys.path.insert(0, str(_HERE))
from src_model import read_frontmatter  # noqa: E402


class TestTerseOutputStyleFrontmatter(unittest.TestCase):
    """The terse.md frontmatter satisfies the output-style manifest contract."""

    @classmethod
    def setUpClass(cls):
        cls.fm = read_frontmatter(_TERSE) or {}
        cls.text = _TERSE.read_text(encoding="utf-8")

    def test_file_exists(self):
        self.assertTrue(_TERSE.exists(), f"Missing: {_TERSE}")

    def test_kind_is_output_style(self):
        self.assertEqual(self.fm.get("kind"), "output-style")

    def test_name_is_terse(self):
        self.assertEqual(self.fm.get("name"), "terse")

    def test_has_description(self):
        self.assertTrue(str(self.fm.get("description", "")).strip(), "description is empty")

    def test_supported_hosts_present_and_non_empty(self):
        hosts = self.fm.get("supported_hosts")
        self.assertIsInstance(hosts, list, "supported_hosts must be a list")
        self.assertTrue(hosts, "supported_hosts must be non-empty")

    def test_version_present(self):
        self.assertIn("version", self.fm, "version field missing")
        self.assertTrue(str(self.fm["version"]).strip())


class TestTerseOutputStyleBody(unittest.TestCase):
    """The terse.md body contains the three required prose sections."""

    @classmethod
    def setUpClass(cls):
        cls.text = _TERSE.read_text(encoding="utf-8").lower()

    def test_silence_default_section_present(self):
        # The inter-tool silence default must be stated.
        self.assertIn("silent", self.text, "silence-default section missing")

    def test_keep_coding_instructions_carveout_present(self):
        # The keep-coding-instructions carve-out must be stated.
        self.assertTrue(
            "keep-coding-instructions" in self.text or "coding-instructions" in self.text,
            "keep-coding-instructions carve-out section missing",
        )

    def test_status_report_carveout_present(self):
        # The status-report carve-out must be stated and marked load-bearing.
        self.assertIn("status report", self.text, "status-report carve-out section missing")
        self.assertIn("load-bearing", self.text, "status-report carve-out must be marked load-bearing")


if __name__ == "__main__":
    unittest.main()
