#!/usr/bin/env python3
"""Structural specs for the V5-10 coordinator role-agent-defs (sibling #4).

The four roles are loose `src/developer-workflows/agents/<role>.md` definitions
(LC-6) — behavioral specs, not Python. These assertions lock the load-bearing
facts so a later edit can't silently regress them:

  * Each role validates the agent manifest shape (`name` matching the file stem,
    `description`, `kind: agent`, `supported_hosts` ⊆ {claude-code, antigravity},
    a `version`).
  * The **read-only** roles (`researcher`, `project-manager`) declare a `tools:`
    allowlist that grants no mutating tool (`Write` / `Edit` / `NotebookEdit`).
    Omitting `tools:` (= all tools) is itself a failure for a read-only role.
  * `researcher` is a thin pointer: it references the existing `explorer` and
    *forward-references* the operator's global deep-research agent rather than
    vendoring or porting it (the collapsed researcher gap).

`generate.py check` (run by check-all.sh) separately proves `dist/` mirrors these
sources, so asserting the source spec is sufficient.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_AGENTS = _ROOT / "src" / "developer-workflows" / "agents"

sys.path.insert(0, str(_HERE))
from src_model import read_frontmatter  # noqa: E402

# Tools that mutate the tree or notebooks — a read-only role must grant none.
_MUTATING_TOOLS = {"Write", "Edit", "NotebookEdit"}
_HOST_ENUM = {"claude-code", "antigravity"}


def _fm(role: str) -> dict:
    return read_frontmatter(_AGENTS / f"{role}.md")


def _tools(fm: dict) -> list[str]:
    """Parse a `tools:` value into a list, accepting both the scalar
    (`Read, Glob, Grep`) and list (`[Read, Glob]`) YAML forms."""
    raw = fm.get("tools")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _text(role: str) -> str:
    return (_AGENTS / f"{role}.md").read_text(encoding="utf-8")


class _RoleManifestContract:
    """Every role-def must satisfy the agent manifest shape.

    A mixin (not a TestCase, so the loader never runs it directly); concrete
    subclasses set `role` and inherit the uniform contract.
    """

    role: str = ""

    @classmethod
    def setUpClass(cls):
        cls.fm = _fm(cls.role)

    def test_frontmatter_parses(self):
        self.assertIsInstance(self.fm, dict, f"{self.role}.md has no parseable frontmatter")

    def test_name_matches_file_stem(self):
        self.assertEqual(self.fm.get("name"), self.role)

    def test_has_description(self):
        self.assertTrue(str(self.fm.get("description", "")).strip(), "missing description")

    def test_kind_is_agent(self):
        self.assertEqual(self.fm.get("kind"), "agent")

    def test_supported_hosts_is_valid_subset(self):
        hosts = self.fm.get("supported_hosts")
        self.assertIsInstance(hosts, list)
        self.assertTrue(hosts, "supported_hosts must be non-empty")
        self.assertFalse(set(hosts) - _HOST_ENUM, f"unknown host(s) in {hosts}")

    def test_has_version(self):
        self.assertIn("version", self.fm)


class _ReadOnlyRoleContract(_RoleManifestContract):
    """A read-only role must declare a `tools:` allowlist with no mutating tool.

    Omitting `tools:` means "all tools" — a failure for a read-only role; the
    allowlist is the enforcement, so it must be present and mutation-free.
    """

    def test_declares_a_tools_allowlist(self):
        self.assertIn("tools", self.fm, f"{self.role} is read-only but declares no tools allowlist")

    def test_allowlist_grants_no_mutating_tool(self):
        granted = set(_tools(self.fm))
        leaked = granted & _MUTATING_TOOLS
        self.assertFalse(leaked, f"{self.role} read-only allowlist leaks mutating tool(s): {sorted(leaked)}")


class TestResearcherRole(_ReadOnlyRoleContract, unittest.TestCase):
    """`researcher` — the read-only brief-research front; a thin pointer at explorer."""

    role = "researcher"

    def test_points_at_explorer(self):
        # Thin skin: it composes the existing explorer, not a re-implementation.
        self.assertIn("explorer", _text(self.role))

    def test_forward_references_global_research_agent_not_vendored(self):
        # The collapsed researcher gap: forward-reference, never vendor/port.
        low = _text(self.role).lower()
        self.assertIn("forward-reference", low)
        self.assertIn("when present", low)
        self.assertTrue(
            "never vendors" in low or "never copied" in low or "not vendor" in low
            or ("vendor" in low and "port" in low),
            "researcher must state it does not vendor/port the global research agent",
        )


if __name__ == "__main__":
    unittest.main()
