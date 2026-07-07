#!/usr/bin/env python3
"""Tests for src/conventions/scripts/conventions_domain.py and the task-4
homeless-domain migration (crickets wave-c-design-and-conventions).

Proves the migrated domains resolve as first-class conventions domains (not
just prose in a root file) and that the migration preserved wording rather
than rewriting it -- spot-checking exact phrases from the source files
(agentm AGENTS.md / harness/principles.md / the operator's global
~/.claude/CLAUDE.md) survive verbatim in the migrated skill/rule.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CONVENTIONS_ROOT = _ROOT / "src" / "conventions"
_SRC = _CONVENTIONS_ROOT / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


conventions_domain = _load("conventions_domain_module", _SRC / "conventions_domain.py")


class ConventionsDomainLookupTests(unittest.TestCase):
    def test_unknown_domain_resolves_to_all_empty_lists(self):
        found = conventions_domain.resolve("no-such-domain", _CONVENTIONS_ROOT)
        self.assertEqual(found, {"rules": [], "skills": [], "reference": []})

    def test_domain_lookup_is_graceful_on_a_missing_conventions_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            found = conventions_domain.resolve("agentic-engineering", Path(tmp))
            self.assertEqual(found, {"rules": [], "skills": [], "reference": []})


class HomelessDomainMigrationTests(unittest.TestCase):
    """The agentic-engineering and ci-battery rules currently only in
    AGENTS.md/principles.md/CLAUDE.md are also recallable/declarable as
    src/conventions/ domains after migration."""

    def test_agentic_engineering_resolves_as_a_first_class_domain(self):
        found = conventions_domain.resolve("agentic-engineering", _CONVENTIONS_ROOT)
        self.assertEqual(len(found["skills"]), 1)
        content = found["skills"][0].read_text(encoding="utf-8")
        # Wording preserved verbatim from agentm harness/principles.md and
        # AGENTS.md's non-negotiables -- a re-home, not a rewrite.
        self.assertIn(
            "Parallel implementers produce mutually-inconsistent decisions no orchestrator can reconcile.",
            content,
        )
        self.assertIn("sub-agents gather context; they never write code", content)
        self.assertIn("Rule:** every phase ends with an on-disk update", content)

    def test_ci_battery_resolves_as_a_first_class_domain(self):
        found = conventions_domain.resolve("ci-battery", _CONVENTIONS_ROOT)
        self.assertEqual(len(found["rules"]), 1)
        content = found["rules"][0].read_text(encoding="utf-8")
        self.assertIn("Always set up CI on a new project", content)
        self.assertIn("stays the single source of truth for \"is it green\"", content)

    def test_no_orphaned_duplicate_content_in_crickets_own_root_files(self):
        # crickets' own root AGENTS.md/CLAUDE.md never held this content
        # locally (it lived only in the sibling agentm repo + the operator's
        # global config) -- so there is nothing to de-duplicate or point
        # from within crickets' own tree. Confirms the negative: neither
        # root file gained a stray, now-orphaned copy of the migrated prose.
        for name in ("AGENTS.md", "CLAUDE.md"):
            p = _ROOT / name
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("Adversarial review with \"assume bugs\" framing", text)
            self.assertNotIn("Always set up CI on a new project", text)


if __name__ == "__main__":
    unittest.main()
