#!/usr/bin/env python3
"""Tests for scripts/lint_src.py (crickets v3.0 #40, part 1).

Builds temp src/ fixtures and asserts lint_tree() flags each schema violation.
Run: python3 scripts/test_lint_src.py
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lint_src", _HERE / "lint_src.py")
lint_src = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint_src)

try:
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


@unittest.skipUnless(HAVE_YAML, "PyYAML required")
class TestLintSrc(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "src"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _group(self, slug, *, name="G", standalone=True, requires=None, body=None):
        d = self.src / slug
        d.mkdir(parents=True, exist_ok=True)
        if body is None:
            body = (f"name: {name}\ndescription: d\n"
                    f"standalone: {str(standalone).lower()}\nrequires: {requires or []}\n")
        (d / "group.yaml").write_text(body, encoding="utf-8")
        return d

    def _skill(self, group, name, *, hosts="[claude-code]", drop=None):
        d = self.src / group / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        fields = {"name": name, "description": "d", "kind": "skill", "supported_hosts": hosts}
        for k in (drop or []):
            fields.pop(k, None)
        fm = "\n".join(f"{k}: {v}" for k, v in fields.items())
        (d / "SKILL.md").write_text(f"---\n{fm}\n---\n# {name}\n", encoding="utf-8")
        return d

    def test_valid_tree_passes(self):
        self._group("developer", standalone=True, requires=[])
        self._skill("developer", "foo")
        self.assertEqual(lint_src.lint_tree(self.src), [])

    def test_missing_standalone_fails(self):
        self._group("developer", body="name: G\ndescription: d\nrequires: []\n")
        errs = lint_src.lint_tree(self.src)
        self.assertTrue(any("missing required field 'standalone'" in e for e in errs), errs)

    def test_dangling_requires_fails(self):
        self._group("github-ci", standalone=False, requires=["nonexistent"])
        errs = lint_src.lint_tree(self.src)
        self.assertTrue(any("not an existing group" in e for e in errs), errs)

    def test_invariant_violation_fails(self):
        self._group("developer", standalone=True, requires=[])
        self._group("bad", standalone=True, requires=["developer"])
        errs = lint_src.lint_tree(self.src)
        self.assertTrue(any("invariant violated" in e for e in errs), errs)

    def test_primitive_missing_kind_fails(self):
        self._group("developer")
        self._skill("developer", "foo", drop=["kind"])
        errs = lint_src.lint_tree(self.src)
        self.assertTrue(any("missing required field 'kind'" in e for e in errs), errs)

    def test_primitive_missing_supported_hosts_fails(self):
        self._group("developer")
        self._skill("developer", "foo", drop=["supported_hosts"])
        errs = lint_src.lint_tree(self.src)
        self.assertTrue(any("missing required field 'supported_hosts'" in e for e in errs), errs)

    def test_unknown_host_fails(self):
        self._group("developer")
        self._skill("developer", "foo", hosts="[gemini-cli]")
        errs = lint_src.lint_tree(self.src)
        self.assertTrue(any("unknown host" in e for e in errs), errs)

    def test_name_mismatch_fails(self):
        self._group("developer")
        d = self._skill("developer", "foo")
        (d / "SKILL.md").write_text(
            "---\nname: bar\ndescription: d\nkind: skill\nsupported_hosts: [claude-code]\n---\n",
            encoding="utf-8",
        )
        errs = lint_src.lint_tree(self.src)
        self.assertTrue(any("is named 'foo'" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
