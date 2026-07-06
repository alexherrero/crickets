#!/usr/bin/env python3
"""Red-test-first lock for AG Wave A rename 1 (PLAN-wave-a-renames-1 task 1).

Asserts src/development-lifecycle/group.yaml exists and its `capabilities:`
list declares both the old (`developer-workflows`) and new
(`development-lifecycle`) names — the declare-both-names mechanism
(crickets-composition.md, 2026-06-28 amendment), not a separate alias map.
"""
from __future__ import annotations

import unittest
from pathlib import Path

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

_REPO_ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestWaveARename1(unittest.TestCase):
    def test_development_lifecycle_group_declares_both_names(self):
        group_path = _REPO_ROOT / "src" / "development-lifecycle" / "group.yaml"
        self.assertTrue(group_path.is_file(), f"{group_path} does not exist")
        data = yaml.safe_load(group_path.read_text(encoding="utf-8"))
        caps = data.get("capabilities") or []
        self.assertIn("developer-workflows", caps)
        self.assertIn("development-lifecycle", caps)


if __name__ == "__main__":
    unittest.main()
