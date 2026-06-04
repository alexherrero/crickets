#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/capability_probe.py (crickets ④ part 5)."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PROBE = _ROOT / "src" / "developer-workflows" / "scripts" / "capability_probe.py"


def _load():
    spec = importlib.util.spec_from_file_location("capability_probe", _PROBE)
    m = importlib.util.module_from_spec(spec)
    sys.modules["capability_probe"] = m
    spec.loader.exec_module(m)
    return m


cp = _load()

# A realistic `claude plugin list` rendering: list decoration + ANSI + @marketplace.
_CLAUDE_LIST = (
    "  \x1b[32m❯\x1b[0m developer@crickets\n"
    "  ❯ developer-workflows@crickets\n"
    "  ❯ code-review@crickets\n"
)


class TestCapabilityProbe(unittest.TestCase):
    def test_parse_strips_decoration_and_marketplace(self):
        self.assertEqual(cp.parse_enabled_slugs(_CLAUDE_LIST),
                         ["developer", "developer-workflows", "code-review"])

    def test_parse_empty(self):
        self.assertEqual(cp.parse_enabled_slugs(""), [])

    def test_available_when_present(self):
        self.assertTrue(cp.is_available("code-review", output=_CLAUDE_LIST))

    def test_unavailable_when_absent(self):
        absent = "  ❯ developer@crickets\n  ❯ developer-workflows@crickets\n"
        self.assertFalse(cp.is_available("code-review", output=absent))

    def test_no_slug_substring_false_match(self):
        # "review" must NOT match "code-review@crickets" (whole-slug check)
        self.assertFalse(cp.is_available("review", output=_CLAUDE_LIST))

    def test_graceful_skip_no_cli(self):
        # no host CLI on PATH → unavailable, never crashes
        saved = cp._host_cli
        cp._host_cli = lambda: None
        try:
            self.assertFalse(cp.is_available("code-review"))
        finally:
            cp._host_cli = saved

    def test_deterministic(self):
        a = cp.is_available("code-review", output=_CLAUDE_LIST)
        b = cp.is_available("code-review", output=_CLAUDE_LIST)
        self.assertEqual(a, b)
        self.assertTrue(a)

    def test_main_usage(self):
        self.assertEqual(cp.main(["capability_probe.py"]), 2)  # wrong arg count


if __name__ == "__main__":
    unittest.main()
