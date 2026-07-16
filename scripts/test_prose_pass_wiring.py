#!/usr/bin/env python3
"""Tests pinning the prose-pass WIRING contract — not the primitive itself.

scripts/test_prose_pass.py already proves prose_pass.py's own mechanics (the
structural validators, the degradation exit codes, the argv ordering). This
file is narrower: it asserts that every calling flow (the wiki documenter, the
/design author command) actually *uses* the primitive as documented, and that
the operator's explicit requirement — the fallback is graceful AND announced,
never silent — is pinned in the caller prose itself, not just in the script.

If one of these assertions breaks, either a caller stopped relaying the
PROSE-PASS-DEGRADED marker (a silent-downgrade regression) or stopped naming
its Claude-only fallback (an announced-but-vague regression) — both are exactly
the failure mode this wiring exists to prevent.

stdlib only.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent

DOCUMENTER = _REPO / "src" / "wiki" / "agents" / "documenter.md"
DESIGN_COMMAND = _REPO / "src" / "design" / "commands" / "design.md"
DIATAXIS_AUTHOR_SKILL = _REPO / "src" / "wiki" / "skills" / "diataxis-author" / "SKILL.md"
WIKI_AUTHOR_SKILL = _REPO / "src" / "wiki" / "skills" / "wiki-author" / "SKILL.md"
PROSE_PASS_SCRIPT = _REPO / "src" / "design" / "scripts" / "prose_pass.py"
PROSE_PASS_SKILL = _REPO / "src" / "design" / "skills" / "prose-pass" / "SKILL.md"


class PrimitiveExistsTests(unittest.TestCase):
    """Sanity: the callers below assume this primitive is on disk. If it's
    ever removed without updating the callers, every other test in this file
    would still pass on stale text alone — this catches that."""

    def test_prose_pass_script_and_skill_are_present(self):
        self.assertTrue(PROSE_PASS_SCRIPT.is_file(), PROSE_PASS_SCRIPT)
        self.assertTrue(PROSE_PASS_SKILL.is_file(), PROSE_PASS_SKILL)


class CallerAnnouncementWiringTests(unittest.TestCase):
    """Every calling flow must (a) relay the script's real degradation marker,
    (b) name the Claude-only fallback it runs instead, and (c) say the
    fallback never blocks. Mirrors adversarial-reviewer-cross.md's
    relay-verbatim contract for CROSS-REVIEW-DEGRADED."""

    _CALLERS = [DOCUMENTER, DESIGN_COMMAND]

    def test_callers_relay_the_real_degradation_marker(self):
        for caller in self._CALLERS:
            with self.subTest(caller=caller.name):
                text = caller.read_text(encoding="utf-8")
                # The actual marker prose_pass.py prints — not an invented one.
                self.assertIn("PROSE-PASS-DEGRADED", text)
                # No caller may still reference the superseded duplicate
                # primitive this branch reconciled away.
                self.assertNotIn("prose_cross_pass", text)
                self.assertNotIn("PROSE-CROSS-PASS-DEGRADED", text)

    def test_callers_name_the_claude_only_fallback_and_non_blocking(self):
        for caller in self._CALLERS:
            with self.subTest(caller=caller.name):
                text = caller.read_text(encoding="utf-8")
                self.assertIn("Claude-only", text)
                self.assertIn("never block", text.lower())

    def test_callers_invoke_the_real_script_path(self):
        for caller in self._CALLERS:
            with self.subTest(caller=caller.name):
                text = caller.read_text(encoding="utf-8")
                self.assertIn("prose_pass.py", text)

    def test_documenter_overrides_the_default_overlay_for_wiki_genre(self):
        # prose_pass.py's own OVERLAY_DEFAULT is design-doc-prose — a wiki
        # page must never run under that genre's voice pack.
        text = DOCUMENTER.read_text(encoding="utf-8")
        self.assertIn("--overlay", text)
        self.assertIn("docs-prose-style", text)

    def test_design_command_relies_on_the_default_overlay_deliberately(self):
        # design.md authors design docs, the same genre prose_pass.py
        # defaults to — no override needed, and the doc should say so rather
        # than silently omitting --overlay (which would look like an oversight).
        text = DESIGN_COMMAND.read_text(encoding="utf-8")
        self.assertIn("No `--overlay` override needed", text)


class DocumentingSkillsCrossReferenceTests(unittest.TestCase):
    """diataxis-author + wiki-author document the step; the documenter agent
    owns the mechanics. A skill re-deriving the mechanics here would be the
    exact duplication the house convention (cross-reference, don't duplicate)
    forbids."""

    def test_skills_name_the_prose_pass_skill_and_point_at_the_documenter(self):
        for skill in (DIATAXIS_AUTHOR_SKILL, WIKI_AUTHOR_SKILL):
            with self.subTest(skill=skill.name):
                text = skill.read_text(encoding="utf-8")
                self.assertIn("prose-pass", text.lower())
                self.assertIn("documenter", text)
                self.assertNotIn("prose_cross_pass", text)


if __name__ == "__main__":
    unittest.main()
