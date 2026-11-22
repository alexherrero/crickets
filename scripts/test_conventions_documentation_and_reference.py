#!/usr/bin/env python3
"""Tests for the documentation domain + reference/ shape (crickets
wave-c-design-and-conventions, task 5).

stdlib only -- no pytest.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CONVENTIONS_ROOT = _ROOT / "src" / "conventions"


class DocumentationDomainTests(unittest.TestCase):
    def test_documentation_domain_declares_the_named_standards(self):
        # Plan 105 step 3 retired the conventions_domain.py resolver (no caller);
        # the documentation domain is its one rule file.
        content = (_CONVENTIONS_ROOT / "rules" / "documentation.md").read_text(encoding="utf-8")
        self.assertIn("Single-mode-per-page", content)
        self.assertIn("Length ceilings", content)
        self.assertIn("Naming style", content)


class ReferenceShapeTests(unittest.TestCase):
    def test_gate_inventory_and_features_schema_exist_as_reference_entries(self):
        reference_dir = _CONVENTIONS_ROOT / "reference"
        self.assertTrue((reference_dir / "gate-inventory.md").is_file())
        self.assertTrue((reference_dir / "features-json-schema.md").is_file())

    def test_reference_entries_are_objective_facts_not_gated_primitives(self):
        # No name/description/kind/supported_hosts/version frontmatter block --
        # a reference/ doc is cited, not a lifecycle-bearing primitive.
        for name in ("gate-inventory.md", "features-json-schema.md"):
            text = (_CONVENTIONS_ROOT / "reference" / name).read_text(encoding="utf-8")
            self.assertFalse(text.startswith("---"), f"{name} should not carry primitive frontmatter")

    def test_a_consumer_cites_the_reference_fact_instead_of_duplicating_it(self):
        documentation_rule = (_CONVENTIONS_ROOT / "rules" / "documentation.md").read_text(encoding="utf-8")
        # Cites the gate-inventory reference doc by link...
        self.assertIn("reference/gate-inventory.md", documentation_rule)
        # ...rather than duplicating its table rows inline.
        gate_inventory = (_CONVENTIONS_ROOT / "reference" / "gate-inventory.md").read_text(encoding="utf-8")
        self.assertIn("| `lint_src` |", gate_inventory)
        self.assertNotIn("| `lint_src` |", documentation_rule)


if __name__ == "__main__":
    unittest.main()
