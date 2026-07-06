#!/usr/bin/env python3
"""Tests for scripts/check-no-dangling-name.py (PLAN-wave-a-repoints task 1).

Builds temp src/ + wiki/ fixtures and asserts check() flags a genuinely
dangling reference while staying permissive of an old-but-still-declared
dual name — the gate's whole point per the plan's locked design call.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_no_dangling_name", _HERE / "check-no-dangling-name.py")
cndn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cndn)

try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestCheckNoDanglingName(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        self.wiki = self.root / "wiki"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _group(self, slug, *, requires=None, enhances_group=None, capabilities=("cap",)):
        d = self.src / slug
        d.mkdir(parents=True, exist_ok=True)
        caps = "[" + ", ".join(capabilities) + "]"
        body = f"name: {slug}\ndescription: d\nstandalone: {str(not requires).lower()}\n"
        body += f"requires: {requires or []}\n"
        if enhances_group:
            body += f"enhances:\n  - group: {enhances_group}\n"
        body += f"capabilities: {caps}\n"
        (d / "group.yaml").write_text(body, encoding="utf-8")

    def test_clean_tree_passes(self):
        self._group("a", capabilities=("a-cap",))
        self._group("b", requires=["a"], capabilities=("b-cap",))
        self.assertEqual(cndn.check(self.src, self.root), [])

    def test_dangling_requires_flagged(self):
        self._group("a", requires=["nonexistent"], capabilities=("a-cap",))
        findings = cndn.check(self.src, self.root)
        self.assertTrue(any("dangling reference to 'nonexistent'" in f for f in findings), findings)

    def test_dangling_enhances_group_flagged(self):
        self._group("a", enhances_group="nonexistent", capabilities=("a-cap",))
        findings = cndn.check(self.src, self.root)
        self.assertTrue(any("dangling reference to 'nonexistent'" in f for f in findings), findings)

    def test_dual_declared_old_name_not_flagged(self):
        # The whole point of declare-both-names: an old capability name that
        # still resolves via a dual declare is NOT dangling.
        self._group("renamed-group", capabilities=("old-name", "new-name"))
        cmd_dir = self.src / "consumer" / "commands"
        cmd_dir.mkdir(parents=True, exist_ok=True)
        self._group("consumer", capabilities=("consumer-cap",))
        (cmd_dir / "x.md").write_text(
            'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" old-name\n',
            encoding="utf-8",
        )
        findings = cndn.check(self.src, self.root)
        self.assertEqual(findings, [], findings)

    def test_dangling_capability_invocation_flagged(self):
        cmd_dir = self.src / "consumer" / "commands"
        cmd_dir.mkdir(parents=True, exist_ok=True)
        self._group("consumer", capabilities=("consumer-cap",))
        (cmd_dir / "x.md").write_text(
            'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_capability.py" totally-invented-name\n',
            encoding="utf-8",
        )
        findings = cndn.check(self.src, self.root)
        self.assertTrue(any("totally-invented-name" in f for f in findings), findings)


if __name__ == "__main__":
    unittest.main()
