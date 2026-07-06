#!/usr/bin/env python3
"""Drift lock: preflight_reconcile.py's duplicated `_FRONTMATTER_RE` constant
stays byte-identical to design_doc.py's own copy of the same regex.

The two used to be a plain same-directory `import design_doc` before the AG
Wave A rename 2 (PLAN-wave-a-renames-2 task 4) moved design_doc.py out of
development-lifecycle/scripts/ into the design plugin's own scripts/ —
discovered live when PLAN-wave-a-repoints tried to activate and stage_plan.py
crashed with ModuleNotFoundError. A cross-plugin Python import is DC-2's
"siblings not layers" violation, so preflight_reconcile.py now carries its own
copy (the same duplicate-with-drift-test pattern the PR helpers use); this
test is that drift guard.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFrontmatterRegexParity(unittest.TestCase):
    def test_regexes_are_byte_identical(self):
        preflight = _load(
            "preflight_reconcile",
            _REPO_ROOT / "src" / "development-lifecycle" / "scripts" / "preflight_reconcile.py",
        )
        design_doc = _load(
            "design_doc",
            _REPO_ROOT / "src" / "design" / "scripts" / "design_doc.py",
        )
        self.assertEqual(preflight._FRONTMATTER_RE.pattern, design_doc._FRONTMATTER_RE.pattern)
        self.assertEqual(preflight._FRONTMATTER_RE.flags, design_doc._FRONTMATTER_RE.flags)


if __name__ == "__main__":
    unittest.main()
