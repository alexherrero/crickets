#!/usr/bin/env python3
"""Tests for scripts/check_conventions_conformance.py -- the Phase-2
conformance gate (crickets wave-c-design-and-conventions, task 6).

Checks DECLARATION, not content correctness (Locked design call) -- a
fixture that consults a conventions domain without declaring the
dependency must be flagged; a fixture that declares correctly must pass
clean.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


check = _load("check_conventions_conformance_module", _HERE / "check_conventions_conformance.py")


def _write_plugin(src: Path, slug: str, *, group_yaml: str, command_body: str) -> None:
    plugin_dir = src / slug
    (plugin_dir / "commands").mkdir(parents=True)
    (plugin_dir / "group.yaml").write_text(group_yaml, encoding="utf-8")
    (plugin_dir / "commands" / f"{slug}.md").write_text(command_body, encoding="utf-8")


@unittest.skipUnless(check.yaml is not None, "PyYAML required")
class ConventionsConformanceTests(unittest.TestCase):
    def test_plugin_consulting_a_domain_without_declaring_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write_plugin(
                src, "non-declaring-plugin",
                group_yaml="name: NonDeclaring\ndescription: d\nstandalone: true\nrequires: []\n",
                command_body=(
                    "---\nname: non-declaring-plugin\ndescription: d\nkind: command\n"
                    "supported_hosts: [claude-code]\nversion: 0.1.0\n---\n\n"
                    "<!-- consults-conventions-domain: documentation -->\n"
                    "Consult the documentation domain before authoring.\n"
                ),
            )
            findings = check.scan(src)
            self.assertEqual(len(findings), 1)
            self.assertIn("non-declaring-plugin", findings[0])
            self.assertIn("documentation", findings[0])

    def test_plugin_that_declares_correctly_passes_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write_plugin(
                src, "declaring-plugin",
                group_yaml="name: Declaring\ndescription: d\nstandalone: false\nrequires: [conventions]\n",
                command_body=(
                    "---\nname: declaring-plugin\ndescription: d\nkind: command\n"
                    "supported_hosts: [claude-code]\nversion: 0.1.0\n---\n\n"
                    "<!-- consults-conventions-domain: documentation -->\n"
                    "Consult the documentation domain before authoring.\n"
                ),
            )
            findings = check.scan(src)
            self.assertEqual(findings, [])

    def test_plugin_that_declares_via_enhances_also_passes_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write_plugin(
                src, "enhances-plugin",
                group_yaml="name: Enhances\ndescription: d\nstandalone: true\nenhances: [conventions]\n",
                command_body=(
                    "---\nname: enhances-plugin\ndescription: d\nkind: command\n"
                    "supported_hosts: [claude-code]\nversion: 0.1.0\n---\n\n"
                    "<!-- consults-conventions-domain: ci-battery -->\n"
                ),
            )
            findings = check.scan(src)
            self.assertEqual(findings, [])

    def test_plugin_with_no_marker_is_never_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write_plugin(
                src, "unrelated-plugin",
                group_yaml="name: Unrelated\ndescription: d\nstandalone: true\nrequires: []\n",
                command_body=(
                    "---\nname: unrelated-plugin\ndescription: d\nkind: command\n"
                    "supported_hosts: [claude-code]\nversion: 0.1.0\n---\n\n"
                    "Nothing to do with conventions here.\n"
                ),
            )
            findings = check.scan(src)
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
