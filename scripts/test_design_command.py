#!/usr/bin/env python3
"""Structural specs for the `/design` command + design-doc template (sibling #5).

`commands/design.md` is a thin interactive prompt (the deterministic logic lives
in the unit-tested `design_doc.py` / `design_sequence.py` helpers). These
assertions lock the load-bearing facts of the *prompt* + the *template* so a
later edit can't silently regress them — the same discipline as
`test_role_agent_defs.py`. They check structure (documented sub-verbs, the Status
lifecycle, the deferred-external-review pointer, the crickets storage paths, the
template's 10 sections + 11 QA sub-attrs), not behavior.

`generate.py check` (run by check-all.sh) separately proves `dist/` mirrors these
sources, so asserting the source spec is sufficient. Tasks 2–4 extend this file
as each sub-verb's flow is fleshed out.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DW = _ROOT / "src" / "developer-workflows"
_COMMAND = _DW / "commands" / "design.md"
_TEMPLATE = _DW / "templates" / "design-doc.md"

sys.path.insert(0, str(_HERE))
from src_model import read_frontmatter  # noqa: E402

_HOST_ENUM = {"claude-code", "antigravity"}

# The 10 locked top-level sections (## headings) of the design-doc template.
_TEMPLATE_SECTIONS = [
    "Context",
    "Design",
    "Alternatives Considered",
    "Dependencies",
    "Migrations",
    "Technical Debt & Risks",
    "Quality Attributes",
    "Project management",
    "Operations",
    "Document History",
]

# The 11 Quality-Attributes sub-attrs (### headings) — the mandatory walk.
_QA_SUBATTRS = [
    "Security",
    "Reliability",
    "Data Integrity",
    "Privacy",
    "Scalability",
    "Latency",
    "Abuse",
    "Accessibility",
    "Testability",
    "Internationalization & Localization",
    "Compliance",
]


def _command_text() -> str:
    return _COMMAND.read_text(encoding="utf-8")


def _template_text() -> str:
    return _TEMPLATE.read_text(encoding="utf-8")


class TestCommandManifest(unittest.TestCase):
    """The command satisfies the standard manifest shape (kind: command)."""

    @classmethod
    def setUpClass(cls):
        cls.fm = read_frontmatter(_COMMAND)

    def test_frontmatter_parses(self):
        self.assertIsInstance(self.fm, dict, "design.md has no parseable frontmatter")

    def test_name_is_design(self):
        self.assertEqual(self.fm.get("name"), "design")

    def test_kind_is_command(self):
        self.assertEqual(self.fm.get("kind"), "command")

    def test_has_description(self):
        self.assertTrue(str(self.fm.get("description", "")).strip())

    def test_supported_hosts_valid_nonempty_subset(self):
        hosts = self.fm.get("supported_hosts")
        self.assertIsInstance(hosts, list)
        self.assertTrue(hosts)
        self.assertFalse(set(hosts) - _HOST_ENUM, f"unknown host(s) in {hosts}")

    def test_has_version(self):
        self.assertIn("version", self.fm)

    def test_install_scope_is_project(self):
        self.assertEqual(self.fm.get("install_scope"), "project")

    def test_has_argument_hint(self):
        self.assertTrue(str(self.fm.get("argument-hint", "")).strip())


class TestCommandBody(unittest.TestCase):
    """The prompt documents the three verbs, the gate, and the crickets idioms."""

    @classmethod
    def setUpClass(cls):
        cls.text = _command_text()
        cls.low = cls.text.lower()

    def test_uses_arguments_token(self):
        self.assertIn("$ARGUMENTS", self.text)

    def test_documents_all_three_sub_verbs(self):
        self.assertIn("/design author", self.text)
        self.assertIn("/design translate", self.text)
        self.assertIn("/design sequence", self.text)

    def test_documents_the_status_lifecycle(self):
        for state in ("draft", "review", "final", "launched"):
            self.assertIn(state, self.low, f"lifecycle state {state!r} not documented")
        # The ordered transition the author verb drives.
        self.assertIn("draft → review → final", self.text)

    def test_author_is_the_only_status_transition(self):
        self.assertTrue(
            "only verb that transitions" in self.low
            or "only one that transitions" in self.low
            or "**only** verb that transitions" in self.low,
            "command must state /design author is the only verb that transitions Status",
        )

    def test_final_is_the_hard_gate(self):
        self.assertIn("hard gate", self.low)
        # Both downstream verbs gate on final.
        self.assertIn("final", self.low)

    def test_external_review_is_deferred_not_live(self):
        self.assertIn("#5b", self.text)
        self.assertIn("defer", self.low)  # deferred / defer
        self.assertIn("external review", self.low)
        self.assertIn("inline", self.low)  # the shipped flow is inline-only

    def test_documents_tested_helper_vs_prompt_split(self):
        self.assertIn("design_doc.py", self.text)
        self.assertTrue(
            "thin" in self.low and ("helper" in self.low and "prompt" in self.low),
            "command must document the tested-helper vs thin-prompt split",
        )

    def test_storage_uses_crickets_paths_not_agentm(self):
        # Published designs at wiki/designs/, NOT agentm's wiki/explanation/designs/.
        self.assertIn("wiki/designs/", self.text)
        self.assertNotIn("wiki/explanation/designs/", self.text)

    def test_never_hardcodes_dot_harness_for_confidential(self):
        # Confidential designs resolve through the helper, never a literal .harness.
        self.assertIn("harness-root", self.text)
        self.assertTrue(
            "never" in self.low and "hardcode" in self.low,
            "command must warn against hardcoding .harness for confidential designs",
        )

    def test_sequence_wires_onto_stage_plan_not_singleton(self):
        self.assertIn("stage_plan.py", self.text)
        self.assertTrue(
            "never" in self.low and "singleton" in self.low,
            "sequence must state it never touches the singleton PLAN.md",
        )


class TestAuthorVerb(unittest.TestCase):
    """Task 2: the `/design author` body documents the full inline authoring flow.

    Structural specs only (the deterministic gate logic lives in `design_doc.py`):
    bootstrap, the section walk, all 11 QA sub-attrs, the N/A-rationale rule, the
    three lifecycle transitions, the post-`final` refusal, and that external review
    is a deferred pointer rather than a live flow.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = _command_text()
        cls.low = cls.text.lower()

    def test_documents_bootstrap_from_template(self):
        self.assertIn("Bootstrap", self.text)
        # Bootstrap copies the group template via the plugin root and seeds history.
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/templates/design-doc.md", self.text)
        self.assertIn("Initial draft created via /design author", self.text)

    def test_author_field_sourced_from_git_config_never_blank(self):
        self.assertIn(".git/config", self.text)
        self.assertTrue(
            "never leave" in self.low and "prompt" in self.low,
            "author bootstrap must source author from .git/config and never leave it blank",
        )

    def test_documents_section_walk_in_template_order(self):
        for section in ("Context", "Design", "Alternatives Considered",
                        "Quality Attributes", "Operations"):
            self.assertIn(section, self.text, f"author walk omits section: {section}")
        self.assertIn("template order", self.low)

    def test_walks_all_eleven_qa_subattrs(self):
        for sub in _QA_SUBATTRS:
            self.assertIn(sub, self.text, f"author flow omits QA sub-attr: {sub}")

    def test_documents_na_rationale_rule(self):
        self.assertIn("N/A", self.text)
        self.assertIn("rationale", self.low)
        self.assertTrue(
            "push back" in self.low or "push-back" in self.low,
            "author must push back on a bare N/A (the N/A-rationale rule)",
        )

    def test_documents_three_lifecycle_transitions(self):
        self.assertIn("draft → review", self.text)
        self.assertIn("review → final", self.text)
        self.assertIn("never advances past", self.low)  # author stops at final

    def test_refuses_reinvocation_after_final(self):
        self.assertIn("refuse", self.low)  # "refuses further invocations"
        self.assertIn("escape hatch", self.low)  # the documented manual revert

    def test_external_review_is_a_deferred_pointer_not_a_flow(self):
        # In the author flow, external review is a #5b pointer — not a live handoff.
        self.assertIn("deferred (#5b)", self.low)


class TestTemplate(unittest.TestCase):
    """The ported template carries the 10 sections + 11 QA sub-attrs + lifecycle."""

    @classmethod
    def setUpClass(cls):
        cls.text = _template_text()
        cls.fm = read_frontmatter(_TEMPLATE)

    def test_frontmatter_seeds_draft_confidential(self):
        self.assertEqual(self.fm.get("status"), "draft")
        self.assertEqual(self.fm.get("visibility"), "confidential")

    def test_has_all_ten_top_level_sections(self):
        for section in _TEMPLATE_SECTIONS:
            self.assertIn(f"## {section}", self.text, f"missing section: {section}")

    def test_has_all_eleven_qa_subattrs(self):
        for sub in _QA_SUBATTRS:
            self.assertIn(f"### {sub}", self.text, f"missing QA sub-attr: {sub}")

    def test_published_path_is_crickets_not_agentm(self):
        self.assertIn("wiki/designs/", self.text)
        self.assertNotIn("wiki/explanation/designs/", self.text)

    def test_has_document_history_table(self):
        self.assertIn("## Document History", self.text)
        self.assertIn("| Date | Change | Status |", self.text)

    def test_references_design_as_a_command_not_skill(self):
        # Ported into crickets as a command — the template's prose must say so.
        self.assertIn("/design author", self.text)
        self.assertIn("command", self.text.lower())


if __name__ == "__main__":
    unittest.main()
