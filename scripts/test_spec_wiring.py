#!/usr/bin/env python3
"""Wiring tests for /spec: the command's prose calls spec_doc.py the way the
script's own contract says, caps its questions, keeps agentm optional, and the
old six-section /spec and /interview-me are gone from every live surface.

test_spec_doc.py proves the helper; this proves the command uses it, and that
the callers were pointed at the new owner of /spec.

stdlib only.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import wiring_checks as wc  # noqa: E402

_ROOT = _HERE.parent
SPEC_COMMAND = _ROOT / "src" / "development-lifecycle" / "commands" / "spec.md"
PLAN_COMMAND = _ROOT / "src" / "development-lifecycle" / "commands" / "plan.md"
SPEC_DOC = _ROOT / "src" / "development-lifecycle" / "scripts" / "spec_doc.py"


class WiringChecksSelfTests(unittest.TestCase):
    """The shared checks must catch the regressions they exist for."""

    def test_an_unguarded_agentm_call_is_caught(self):
        text = "Run `python3 project_homes.py home designs` and read the result."
        self.assertEqual(len(wc.unguarded_agentm_calls(text)), 1)

    def test_a_guarded_call_passes(self):
        text = "Run `project_homes.py home designs`; on exit 3 skip it."
        self.assertEqual(wc.unguarded_agentm_calls(text), [])

    def test_a_dispatch_without_a_model_is_caught(self):
        self.assertEqual(len(wc.dispatches_without_a_model("Dispatch the reviewer sub-agent.")), 1)

    def test_a_dispatch_with_a_model_passes(self):
        self.assertEqual(
            wc.dispatches_without_a_model("Dispatch the reviewer sub-agent with model sonnet."), [])


class SpecCommandWiringTests(unittest.TestCase):
    def setUp(self):
        self.text = SPEC_COMMAND.read_text(encoding="utf-8")

    def test_the_helper_and_its_three_verbs_are_named(self):
        self.assertTrue(SPEC_DOC.is_file())
        self.assertIn("scripts/spec_doc.py", self.text)
        for verb in ("place", "check", "render"):
            self.assertRegex(self.text, rf"`spec_doc\.py {verb}\b|\({verb}|`{verb}`",
                             f"/spec never names the helper's `{verb}` verb")

    def test_questions_are_capped_at_five_and_batched(self):
        self.assertRegex(self.text, r"at most 5 questions")
        self.assertIn("batched in one message", self.text)

    def test_every_section_the_helper_requires_is_named_in_order(self):
        order = [self.text.index(f"**{h}**") for h in (
            "Goal", "Done when", "Rules", "Not doing", "Open questions", "Reference", "Likeness list")]
        self.assertEqual(order, sorted(order))

    def test_it_names_the_placements_the_helper_computes(self):
        self.assertIn("--multi", self.text)
        self.assertIn(".harness/spec-<slug>.md", self.text)

    def test_one_approval_and_a_proposal_not_an_edit_of_the_design(self):
        self.assertIn("Approve / Revise", self.text)
        self.assertIn("Never edit the design here", self.text)

    def test_agentm_is_optional(self):
        self.assertEqual(wc.unguarded_agentm_calls(self.text), [])
        self.assertNotIn("agentm_bridge", self.text)

    def test_nothing_is_dispatched(self):
        # /spec asks the operator and writes a file; it fans out to no agent.
        self.assertEqual([], re.findall(r"\bdispatch", self.text, re.IGNORECASE))

    def test_the_routing_nudge_names_the_models_table_row(self):
        self.assertIn("Recommended model for this phase:", self.text)


class OldSurfacesAreGoneTests(unittest.TestCase):
    """`/spec` has one owner now, and `/interview-me` is retired."""

    _LIVE = ("commands", "agents", "skills", "scripts", "hooks", "templates")

    def _live_files(self):
        for plugin in sorted((_ROOT / "src").iterdir()):
            if not plugin.is_dir():
                continue
            for sub in self._LIVE:
                base = plugin / sub
                if not base.is_dir():
                    continue
                for f in base.rglob("*"):
                    if f.is_file() and f.suffix in (".md", ".py", ".sh", ".json", ".yaml", ".yml"):
                        yield f

    def test_the_old_commands_are_not_in_the_design_plugin(self):
        for name in ("spec.md", "interview-me.md"):
            self.assertFalse((_ROOT / "src" / "design" / "commands" / name).exists(), name)
        self.assertFalse((_ROOT / "src" / "development-lifecycle" / "commands" / "interview-me.md").exists())

    def test_no_live_surface_names_interview_me(self):
        hits = [str(f.relative_to(_ROOT)) for f in self._live_files()
                if re.search(r"/interview-me\b|interview-me\.md", f.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(hits, [])

    def test_no_live_surface_sends_you_to_the_old_spec(self):
        # The old /spec wrote SPEC.md / <desk>/briefs/<slug>-spec.md and had "six sections".
        hits = []
        for f in self._live_files():
            text = f.read_text(encoding="utf-8", errors="replace")
            if (re.search(r"\bSPEC\.md\b", text)  # the old file name, upper-case only
                    or re.search(r"briefs/<slug>-spec|six required sections", text, re.IGNORECASE)):
                hits.append(str(f.relative_to(_ROOT)))
        self.assertEqual(hits, [])

    def test_plan_points_at_the_new_spec(self):
        text = PLAN_COMMAND.read_text(encoding="utf-8")
        self.assertIn("run `/spec` first", text)
        self.assertNotIn("interview-me", text)


class BothHostsEmitTests(unittest.TestCase):
    def test_spec_is_emitted_for_claude_code_and_antigravity(self):
        claude = _ROOT / "dist" / "claude-code" / "plugins" / "development-lifecycle" / "commands" / "spec.md"
        agy = _ROOT / "dist" / "antigravity" / "plugins" / "development-lifecycle" / "skills" / "spec" / "SKILL.md"
        self.assertTrue(claude.is_file(), claude)
        self.assertTrue(agy.is_file(), agy)
        for host in ("claude-code", "antigravity"):
            self.assertTrue(
                (_ROOT / "dist" / host / "plugins" / "development-lifecycle" / "scripts" / "spec_doc.py").is_file(),
                f"spec_doc.py not emitted for {host}")

    def test_the_old_design_spec_is_not_emitted(self):
        design_claude = _ROOT / "dist" / "claude-code" / "plugins" / "design" / "commands"
        self.assertFalse((design_claude / "spec.md").exists())
        self.assertFalse((design_claude / "interview-me.md").exists())
        design_agy = _ROOT / "dist" / "antigravity" / "plugins" / "design" / "skills"
        self.assertFalse((design_agy / "spec").exists())
        self.assertFalse((design_agy / "interview-me").exists())


if __name__ == "__main__":
    unittest.main()
