#!/usr/bin/env python3
"""Tests for the diataxis-author operator-gated overlay->base promotion
(src/wiki-maintenance/skills/diataxis-author/scripts/promote.py) — crickets ④
wiki-maintenance part 5/5 (dogfood-finale), task 2.

Deterministic-only (DC-F6): the pure compute (parse_lesson, merge_banned,
compute_promotion, resolve_base), preview-writes-nothing, apply-writes-src-not-
dist, idempotence, the never-auto-commit non-TTY gate, and the no-src-base
maintainer-only refusal. The operator's judgment (which lesson proves out, which
section) is operator-gated and not unit-tested.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL_SCRIPTS = _ROOT / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts"


def _load(name: str):
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


promote = _load("promote")

# A minimal stand-in base-style-guide.md — the three sections + a banned: line.
_BASE = """# Base style guide — house voice

The voice layer composed on top of templates.

## Voice

- **Second person, direct.** Address the reader.
- **De-perform labels.** Pick the less-prestigious framing.

## Banned

- **Machine-checkable terms.** The convention-drift check scans pages for the
  terms on the `banned:` line below; overlay lessons extend it.
  banned: groundbreaking, delve, essentially

## Structure

- **High-level over exhaustive.** Cap at what a reader needs.
"""


def _mk_repo(base_text: str = _BASE, *, with_dist: bool = False) -> tuple[Path, Path, Path | None]:
    tmp = Path(tempfile.mkdtemp())
    base = tmp / promote.REL_BASE
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_text(base_text, encoding="utf-8")
    dist = None
    if with_dist:
        dist = tmp / "dist" / "claude-code" / "plugins" / "wiki-maintenance" / \
            "skills" / "diataxis-author" / "style" / "base-style-guide.md"
        dist.parent.mkdir(parents=True, exist_ok=True)
        dist.write_text(base_text, encoding="utf-8")
    return tmp, base, dist


def _lesson(tmp: Path, name: str, text: str) -> Path:
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def _run(argv: list, *, stdin_text: str = "") -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = promote.main(argv, stdin=io.StringIO(stdin_text), stdout=out)
    return rc, out.getvalue(), err.getvalue()


_VOICE_LESSON = """---
trigger: setup-verb
scope: global
updated: 2026-06-06
---
Prefer "set up" (verb) over "setup" (noun) outside compound nouns.
"""

_BANNED_LESSON = """---
trigger: ban-leverage
scope: global
---
Drop corporate filler.
banned: leverage, Delve
"""


# ── Pure compute ─────────────────────────────────────────────────────────────

class ParseLessonTests(unittest.TestCase):
    def test_extracts_trigger_and_guidance(self):
        l = promote.parse_lesson(_VOICE_LESSON)
        self.assertEqual(l.trigger, "setup-verb")
        self.assertIn("set up", l.guidance)
        self.assertEqual(l.banned_terms, [])

    def test_guidance_excludes_banned_line(self):
        l = promote.parse_lesson(_BANNED_LESSON)
        self.assertEqual(l.guidance, "Drop corporate filler.")
        self.assertNotIn("banned:", l.guidance)

    def test_banned_terms_from_body_dedup_case_insensitive(self):
        text = "---\ntrigger: t\n---\nbody.\nbanned: leverage, Leverage, delve\n"
        l = promote.parse_lesson(text)
        # leverage/Leverage collapse to one (first-seen); delve kept.
        self.assertEqual([t.lower() for t in l.banned_terms], ["leverage", "delve"])

    def test_banned_terms_from_frontmatter(self):
        text = "---\ntrigger: t\nbanned: foo, bar\n---\nguidance here.\n"
        l = promote.parse_lesson(text)
        self.assertEqual(l.banned_terms, ["foo", "bar"])

    def test_no_frontmatter_is_all_guidance(self):
        l = promote.parse_lesson("just a guidance line, no frontmatter.")
        self.assertIsNone(l.trigger)
        self.assertEqual(l.guidance, "just a guidance line, no frontmatter.")


class MergeBannedTests(unittest.TestCase):
    def test_appends_new_preserves_order(self):
        merged, added = promote.merge_banned(["a", "b"], ["c", "d"])
        self.assertEqual(merged, ["a", "b", "c", "d"])
        self.assertEqual(added, ["c", "d"])

    def test_dedup_case_insensitive(self):
        merged, added = promote.merge_banned(["Delve", "vital"], ["delve", "new"])
        self.assertEqual(added, ["new"])
        self.assertEqual(merged, ["Delve", "vital", "new"])

    def test_all_present_no_add(self):
        merged, added = promote.merge_banned(["a", "b"], ["b", "a"])
        self.assertEqual(added, [])
        self.assertEqual(merged, ["a", "b"])


class ComputePromotionTests(unittest.TestCase):
    def test_bullet_added_under_voice_by_default(self):
        l = promote.parse_lesson(_VOICE_LESSON)
        plan = promote.compute_promotion(_BASE, l)
        self.assertTrue(plan.changed)
        self.assertIsNotNone(plan.bullet_added)
        lines = plan.new_text.split("\n")
        vi = lines.index("## Voice")
        bi = lines.index("## Banned")
        # the new bullet sits inside the Voice section span.
        self.assertTrue(any("set up" in ln for ln in lines[vi:bi]))

    def test_section_override_puts_bullet_under_structure(self):
        l = promote.parse_lesson(_VOICE_LESSON)
        plan = promote.compute_promotion(_BASE, l, section="Structure")
        lines = plan.new_text.split("\n")
        si = lines.index("## Structure")
        self.assertTrue(any("set up" in ln for ln in lines[si:]))
        # not under Voice
        vi = lines.index("## Voice")
        bi = lines.index("## Banned")
        self.assertFalse(any("set up" in ln for ln in lines[vi:bi]))

    def test_banned_merged_into_directive(self):
        l = promote.parse_lesson(_BANNED_LESSON)
        plan = promote.compute_promotion(_BASE, l)
        # 'leverage' added; 'Delve' is a case-dup of base 'delve' -> not added.
        self.assertEqual([t.lower() for t in plan.added_banned], ["leverage"])
        # the DIRECTIVE line (starts with `banned:`), not the prose reference to it.
        banned_line = next(ln for ln in plan.new_text.split("\n") if ln.strip().startswith("banned:"))
        self.assertIn("leverage", banned_line)
        self.assertEqual(banned_line.lower().count("delve"), 1)

    def test_idempotent_no_change_second_time(self):
        l = promote.parse_lesson(_VOICE_LESSON)
        once = promote.compute_promotion(_BASE, l)
        twice = promote.compute_promotion(once.new_text, l)
        self.assertFalse(twice.changed)
        self.assertEqual(twice.new_text, once.new_text)

    def test_no_bullet_flag_merges_banned_only(self):
        l = promote.parse_lesson(_BANNED_LESSON)
        plan = promote.compute_promotion(_BASE, l, add_bullet=False)
        self.assertIsNone(plan.bullet_added)
        self.assertEqual([t.lower() for t in plan.added_banned], ["leverage"])
        self.assertNotIn("Drop corporate filler", plan.new_text)

    def test_idempotent_against_wrapped_base_bullet(self):
        # Base bullets are hard-wrapped across physical lines; a lesson whose
        # guidance matches one must be detected as present (no duplicate).
        wrapped = (
            "# Base\n\n## Voice\n\n"
            "- **Second person, direct.** Address the reader directly and\n"
            "  keep every sentence plain.\n\n"
            "## Banned\n\n  banned: x\n\n"
            "## Structure\n\n- **Tables.** Use them.\n"
        )
        lesson = ("---\ntrigger: t\n---\n"
                  "**Second person, direct.** Address the reader directly and "
                  "keep every sentence plain.\n")
        plan = promote.compute_promotion(wrapped, promote.parse_lesson(lesson))
        self.assertIsNone(plan.bullet_added)
        self.assertFalse(plan.changed)


class ResolveBaseTests(unittest.TestCase):
    def test_resolves_under_repo_root(self):
        tmp, base, _ = _mk_repo()
        try:
            self.assertEqual(promote.resolve_base(tmp), base)
        finally:
            _rmtree(tmp)

    def test_none_when_no_src_tree(self):
        empty = Path(tempfile.mkdtemp())
        try:
            self.assertIsNone(promote.resolve_base(empty))
        finally:
            _rmtree(empty)


# ── CLI behavior ─────────────────────────────────────────────────────────────

class CliTests(unittest.TestCase):
    def test_preview_writes_nothing_and_prints_diff(self):
        tmp, base, _ = _mk_repo()
        try:
            lp = _lesson(tmp, "l.md", _VOICE_LESSON)
            before = base.read_text(encoding="utf-8")
            rc, out, err = _run(["--lesson", str(lp), "--repo-root", str(tmp), "--preview"])
            self.assertEqual(rc, 0)
            self.assertIn("+- Prefer", out.replace(" ", " "))  # diff add line present
            self.assertIn("PREVIEW only", err)
            self.assertEqual(base.read_text(encoding="utf-8"), before)  # unchanged
        finally:
            _rmtree(tmp)

    def test_apply_writes_src_not_dist(self):
        tmp, base, dist = _mk_repo(with_dist=True)
        try:
            lp = _lesson(tmp, "l.md", _VOICE_LESSON)
            dist_before = dist.read_text(encoding="utf-8")
            rc, out, err = _run(["--lesson", str(lp), "--repo-root", str(tmp), "--mode", "silent"])
            self.assertEqual(rc, 0)
            self.assertIn("set up", base.read_text(encoding="utf-8"))     # src changed
            self.assertEqual(dist.read_text(encoding="utf-8"), dist_before)  # dist untouched
        finally:
            _rmtree(tmp)

    def test_non_tty_default_mode_denies(self):
        tmp, base, _ = _mk_repo()
        try:
            lp = _lesson(tmp, "l.md", _VOICE_LESSON)
            before = base.read_text(encoding="utf-8")
            rc, out, err = _run(["--lesson", str(lp), "--repo-root", str(tmp)])  # interactive default
            self.assertEqual(rc, 1)
            self.assertIn("deny", err)
            self.assertEqual(base.read_text(encoding="utf-8"), before)  # never auto-wrote
        finally:
            _rmtree(tmp)

    def test_ambient_env_silent_does_not_bypass_non_tty(self):
        # promote must NOT honor MEMORY_REVIEW_MODE (unlike capture/conventions):
        # the committed base is too sensitive to silence via an inherited env var.
        import os
        tmp, base, _ = _mk_repo()
        prev = os.environ.get("MEMORY_REVIEW_MODE")
        os.environ["MEMORY_REVIEW_MODE"] = "silent"
        try:
            lp = _lesson(tmp, "l.md", _VOICE_LESSON)
            before = base.read_text(encoding="utf-8")
            rc, out, err = _run(["--lesson", str(lp), "--repo-root", str(tmp)])  # no --mode flag
            self.assertEqual(rc, 1)  # still denied despite ambient silent
            self.assertEqual(base.read_text(encoding="utf-8"), before)
        finally:
            if prev is None:
                os.environ.pop("MEMORY_REVIEW_MODE", None)
            else:
                os.environ["MEMORY_REVIEW_MODE"] = prev
            _rmtree(tmp)

    def test_idempotent_reapply_is_noop(self):
        tmp, base, _ = _mk_repo()
        try:
            lp = _lesson(tmp, "l.md", _VOICE_LESSON)
            _run(["--lesson", str(lp), "--repo-root", str(tmp), "--mode", "silent"])
            after_first = base.read_text(encoding="utf-8")
            rc, out, err = _run(["--lesson", str(lp), "--repo-root", str(tmp), "--mode", "silent"])
            self.assertEqual(rc, 0)
            self.assertIn("idempotent no-op", out)
            self.assertEqual(base.read_text(encoding="utf-8"), after_first)
        finally:
            _rmtree(tmp)

    def test_missing_lesson_file_exits_1(self):
        tmp, base, _ = _mk_repo()
        try:
            rc, out, err = _run(["--lesson", str(tmp / "nope.md"), "--repo-root", str(tmp)])
            self.assertEqual(rc, 1)
            self.assertIn("not found", err)
        finally:
            _rmtree(tmp)

    def test_empty_lesson_exits_1(self):
        tmp, base, _ = _mk_repo()
        try:
            lp = _lesson(tmp, "empty.md", "---\ntrigger: t\n---\n")
            rc, out, err = _run(["--lesson", str(lp), "--repo-root", str(tmp), "--mode", "silent"])
            self.assertEqual(rc, 1)
            self.assertIn("nothing to promote", err)
        finally:
            _rmtree(tmp)

    def test_no_src_base_refuses_exit_2(self):
        empty = Path(tempfile.mkdtemp())
        try:
            lp = _lesson(empty, "l.md", _VOICE_LESSON)
            rc, out, err = _run(["--lesson", str(lp), "--repo-root", str(empty)])
            self.assertEqual(rc, 2)
            self.assertIn("maintainer operation", err)
        finally:
            _rmtree(empty)


def _rmtree(p: Path) -> None:
    import shutil
    shutil.rmtree(p, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
