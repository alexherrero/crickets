#!/usr/bin/env python3
"""Docs are an opt-in pass, not a pipeline step (plan 104 step 2).

This replaces `test_documenter_routed_dispatch_drift.py`, which kept the
documenter dispatch's routed-dispatch trailer byte-identical across the five
phase commands. None of them dispatches the documenter any more: wiki pages
change through `wiki-author` on request or `wiki-watch` on a schedule. These
tests pin that the dispatch is gone and that each phase says where docs went.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CMDS = _ROOT / "src" / "development-lifecycle" / "commands"
_COMMANDS = ("work.md", "plan.md", "bugfix.md", "release.md", "setup.md")


def _read(name: str) -> str:
    return (_CMDS / name).read_text(encoding="utf-8")


class TestNoPhaseDispatchesTheDocumenter(unittest.TestCase):
    def test_no_documenter_dispatch_or_wiki_probe(self):
        for name in _COMMANDS:
            text = _read(name)
            self.assertNotIn("documenter", text, name)
            self.assertNotIn("capability wiki-maintenance", text, name)

    def test_each_phase_names_the_opt_in_path(self):
        for name in ("work.md", "plan.md", "release.md", "bugfix.md"):
            self.assertIn("`wiki-author`", _read(name), name)
        for name in ("work.md", "plan.md", "release.md"):
            self.assertIn("`wiki-watch`", _read(name), name)
        self.assertIn("`/wiki-init`", _read("setup.md"))

    def test_numbered_items_keep_their_numbers(self):
        # release.md points at "constraint 4" and work.md at "constraint 8":
        # the removed items stay as one-line stubs so those references hold.
        self.assertIn("\n4. **Docs are not part of the release gate.**", _read("release.md"))
        self.assertIn("(constraint 4)", _read("release.md"))
        self.assertIn("\n8. **Docs are an opt-in pass, later:**", _read("work.md"))
        self.assertIn("### 8. Docs\n\nNothing happens here (constraint 8).", _read("work.md"))
        self.assertIn("### 6. Docs\n\nNothing happens here (constraint 6).", _read("plan.md"))

    def test_work_edits_wiki_only_when_the_step_names_the_page(self):
        self.assertIn("Edit `wiki/` only when the step's **What** names the page.", _read("work.md"))


class TestNoPhasePostsToTheBoard(unittest.TestCase):
    """Plan 104 step 3: board sync left /plan, /work, /release and /bugfix."""

    def test_no_board_probe_or_post(self):
        for name in ("work.md", "plan.md", "bugfix.md", "release.md"):
            text = _read(name)
            for needle in ("capability board-sync", "project_sync.py", "planner_maintain.py", "board-items.json"):
                self.assertNotIn(needle, text, "%s still names %s" % (name, needle))

    def test_release_keeps_arc_coalescence_and_names_the_board_cycle(self):
        text = _read("release.md")
        self.assertIn("7. **The board is not part of the release gate.**", text)
        self.assertIn("8. **Board** — nothing happens here (constraint 7).", text)
        self.assertIn("coalescence", text)
        self.assertIn("`report-board-drift`", text)

    def test_development_lifecycle_declares_no_board_enhance(self):
        group = (_ROOT / "src" / "development-lifecycle" / "group.yaml").read_text(encoding="utf-8")
        self.assertNotIn("capability: board-sync", group)
        planner = (_ROOT / "src" / "github-projects" / "commands" / "planner-maintain.md").read_text(encoding="utf-8")
        self.assertIn("## When it runs", planner)
        self.assertNotIn("step 10", planner)

    def test_setup_keeps_its_one_time_board_offer(self):
        self.assertIn("### 9. Offer GitHub Project creation (optional)", _read("setup.md"))


class TestNoPersonasOrRoutedDispatch(unittest.TestCase):
    """Plan 104 step 4: personas, token-audit routed dispatch and fan-out
    announcements left the phase commands."""

    def test_no_routed_dispatch_or_announcement_in_any_command(self):
        needles = ("workflow-persona", "Workflow-step persona", "fanout_announcement", "render_announcement",
                   "classify_work_type", "agent_tool_alias", "capability token-audit",
                   "Mandatory fan-out announcement", "Routed dispatch")
        for path in sorted(_CMDS.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertNotIn(needle, text, "%s still names %s" % (path.name, needle))

    def test_explorer_dispatches_name_a_model(self):
        for name in ("work.md", "bugfix.md"):
            self.assertIn("dispatch the `explorer` sub-agent on model `sonnet`", _read(name), name)

    def test_token_audit_no_longer_expects_an_announcement(self):
        text = (_ROOT / "src" / "tokens" / "commands" / "token-audit.md").read_text(encoding="utf-8")
        self.assertNotIn("Until it ships", text)
        self.assertNotIn("[PENDING-IMPL]", text)

    def test_the_three_failure_stop_stays(self):
        text = _read("work.md")
        self.assertIn("3 consecutive failures on the same gate", text)


class TestDesignHooksRetired(unittest.TestCase):
    """Plan 104 step 5: Hooks 3, 4, 5 and 7 left the phase commands; /plan's
    step 1b (resolve the governing design, then the vault) stays."""

    def test_no_hook_text_in_the_phase_commands(self):
        import re
        pattern = re.compile(r"Hook [13457]\b|design-conformance|check-plan-grounding|touches_architecture")
        for name in _COMMANDS:
            self.assertIsNone(pattern.search(_read(name)), name)

    def test_plan_still_grounds_in_its_design(self):
        text = _read("plan.md")
        self.assertIn("### 1b. Ground in the governing design", text)
        self.assertIn("governing-design <target>", text)
        self.assertIn("vault_designs.py\" find <target>", text)
        self.assertIn("parent_design_doc:", text)

    def test_release_says_design_notes_are_not_a_gate(self):
        self.assertIn("10. **Design notes are not a release gate.**", _read("release.md"))


class TestRetiredReviewCommands(unittest.TestCase):
    """Plan 104 step 6: /doubt, crickets' /code-review, /simplify and the
    test-engineer agent retired into /build-it's passes."""

    _LENS = "a behaviour change with no test that would catch its regression"

    def test_gone_from_src_and_both_hosts(self):
        cr = _ROOT / "src" / "code-review"
        for rel in ("commands/doubt.md", "commands/code-review.md", "commands/simplify.md",
                    "agents/test-engineer.md"):
            self.assertFalse((cr / rel).exists(), rel)
        cc = _ROOT / "dist" / "claude-code" / "plugins" / "code-review"
        ag = _ROOT / "dist" / "antigravity" / "plugins" / "code-review"
        for name in ("doubt", "code-review", "simplify"):
            self.assertFalse((cc / "commands" / (name + ".md")).exists(), name)
            self.assertFalse((ag / "skills" / name).exists(), name)
        self.assertFalse((cc / "agents" / "test-engineer.md").exists())
        self.assertFalse((ag / "agents" / "test-engineer.md").exists())

    def test_the_missing_test_lens_reaches_every_correctness_reviewer(self):
        cr = _ROOT / "src" / "code-review"
        self.assertIn("Missing tests: " + self._LENS,
                      (cr / "scripts" / "cross-review.sh").read_text(encoding="utf-8"))
        self.assertIn("missing tests (" + self._LENS + ")",
                      (cr / "agents" / "adversarial-reviewer.md").read_text(encoding="utf-8"))
        self.assertIn("In the correctness pass, " + self._LENS + " is a real finding",
                      _read("build-it.md"))

    def test_security_auditor_stays_the_conditional_pass(self):
        self.assertTrue((_ROOT / "src" / "code-review" / "agents" / "security-auditor.md").exists())
        self.assertIn("The `security` pass is a dispatch of the `security-auditor` agent", _read("build-it.md"))


if __name__ == "__main__":
    unittest.main()
