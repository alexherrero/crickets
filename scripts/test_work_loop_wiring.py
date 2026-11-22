#!/usr/bin/env python3
"""Wiring tests for /plan's loop tags and /work's pointer to the loop (plan 103, step 11).

/plan writes `**Anchor:**`, `**Profile:**` and `**Size:**` on each step and gets the
spec from /spec; /work reads them and runs the step's loop by pointing at /build-it or
/create-it, not by copying them. These tests pin the two commands to each other and to
the loop commands, and pin how much /work was allowed to grow.

stdlib only.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import wiring_checks as wc  # noqa: E402

_ROOT = _HERE.parent
_DL = _ROOT / "src" / "development-lifecycle"
PLAN = _DL / "commands" / "plan.md"
WORK = _DL / "commands" / "work.md"
BUILD_IT = _DL / "commands" / "build-it.md"
CREATE_IT = _DL / "commands" / "create-it.md"

# /work's word count (split on whitespace) just before this step. The loop is written
# once, in /build-it and /create-it; /work only points at it, so it may grow by a few
# lines and no more.
WORK_WORDS_BEFORE = 5548
WORK_MAY_GROW_BY = 300


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


lr = _load("loop_record", _DL / "scripts" / "loop_record.py")


class PlanTemplateTests(unittest.TestCase):
    def setUp(self):
        self.text = PLAN.read_text(encoding="utf-8")
        # the step shape: the fenced template's "### 1. <Step title>" block
        m = re.search(r"### 1\. <Step title>\n(?P<block>(?:- .*\n)+)", self.text)
        self.assertIsNotNone(m, "plan.md has no step template")
        self.block = m.group("block")

    def test_a_step_carries_anchor_profile_and_size(self):
        self.assertIn("- **Anchor:** <path to the spec", self.block)
        self.assertIn("- **Profile:** build | create | both", self.block)
        self.assertIn("- **Size:** small | medium | large", self.block)

    def test_the_tag_values_are_the_ones_the_loop_knows(self):
        self.assertIn("build | create | both", self.block)
        for size in lr.SIZES:
            self.assertIn(size, self.block)
        for profile in lr.PROFILES:
            self.assertIn(profile, self.block)

    def test_the_tags_sit_between_what_and_verification(self):
        order = [self.block.index(k) for k in ("**What:**", "**Anchor:**", "**Profile:**", "**Size:**",
                                               "**Verification:**", "**Status:**")]
        self.assertEqual(order, sorted(order))

    def test_plan_runs_spec_with_the_plan_path_for_each_task(self):
        self.assertIn("run **`/spec`** now, with `--plan <the resolved plan path>`", self.text)
        self.assertIn("(add `--multi` when one spec covers several tasks)", self.text)

    def test_no_stale_pointer_to_the_old_interview_or_spec(self):
        self.assertNotIn("/interview-me", self.text)
        self.assertNotIn("### 2. Interview", self.text)
        self.assertNotIn("SPEC.md", self.text)
        self.assertNotRegex(self.text, r"\bno interview\b")

    def test_a_legacy_step_default_is_stated(self):
        self.assertIn("A step with none of the three is a legacy step", self.text)
        self.assertIn("`build`, `medium`, anchored to the plan", self.text)

    def test_the_spec_step_does_not_ask_the_old_questions_twice(self):
        self.assertIn("Its Done when is this plan's success criterion", self.text)


class WorkPointerTests(unittest.TestCase):
    def setUp(self):
        self.text = WORK.read_text(encoding="utf-8")

    def test_work_reads_the_three_tags(self):
        for tag in ("**Anchor:**", "**Profile:**", "**Size:**"):
            self.assertIn(tag, self.text)

    def test_work_points_to_both_loop_commands(self):
        self.assertIn("`/build-it --spec <Anchor> --size <Size>`", self.text)
        self.assertIn("`/create-it`", self.text)
        self.assertTrue(BUILD_IT.is_file() and CREATE_IT.is_file())

    def test_the_flags_it_passes_are_the_loop_commands_own(self):
        head = BUILD_IT.read_text(encoding="utf-8").split("---", 2)[1]
        for flag in ("--spec", "--size"):
            self.assertIn(flag, head)

    def test_untagged_steps_default_to_build_medium_and_the_plan(self):
        self.assertIn("A step with none of the three tags is a legacy step: `build`, `medium`, anchored to the plan.",
                      self.text)

    def test_the_direction_check_runs_before_implementing_inside_the_safety_pre_check(self):
        pre = self.text.split("### 2. Safety pre-check", 1)[1].split("### 2.5", 1)[0]
        self.assertIn("**direction check**", pre)
        self.assertIn("`medium` or `large`", pre)
        implement = self.text.split("### 4. Implement", 1)[1].split("### 5.", 1)[0]
        self.assertIn("The direction check comes first, before any code", implement)

    def test_free_checks_are_the_gates_and_run_once(self):
        self.assertIn("the loop's free checks are step 5's gates (run them once)", self.text)

    def test_the_done_report_goes_into_progress(self):
        update = self.text.split("### 7. Update state", 1)[1].split("### 8.", 1)[0]
        self.assertIn("`loop_record.py report`", update)
        self.assertIn("progress", update)

    def test_the_loop_is_pointed_at_not_copied(self):
        # None of the loop's own mechanics are repeated here.
        for needle in ("review_material.py", "cross-review.sh", "open-round", "asset_checks.py", "prose_pass.py"):
            self.assertNotIn(needle, self.text, needle)

    def test_work_grew_by_under_300_words(self):
        grew = len(self.text.split()) - WORK_WORDS_BEFORE
        self.assertLess(grew, WORK_MAY_GROW_BY, "/work grew by %d words; the loop lives in /build-it and /create-it" % grew)

    def test_the_added_lines_call_no_agentm_script_and_dispatch_nothing(self):
        start = self.text.index("- **Run the step's loop.**")
        added = self.text[start:self.text.index("\n", start)]
        self.assertEqual(wc.unguarded_agentm_calls(added), [])
        self.assertEqual(wc.dispatches_without_a_model(added), [])
        for call in wc.AGENTM_CALLS:
            self.assertNotIn(call, added, call)


class PlanAndWorkAgreeTests(unittest.TestCase):
    def test_both_describe_the_same_legacy_default(self):
        plan = PLAN.read_text(encoding="utf-8")
        work = WORK.read_text(encoding="utf-8")
        for needle in ("build", "medium", "anchored to the plan"):
            self.assertIn(needle, plan)
            self.assertIn(needle, work)

    def test_the_sizes_plan_defines_are_the_sizes_the_loop_commands_define(self):
        plan = PLAN.read_text(encoding="utf-8")
        build = BUILD_IT.read_text(encoding="utf-8")
        for phrase in ("roughly 300 changed lines or 8 files", "a few lines"):
            self.assertIn(phrase, plan)
            self.assertIn(phrase, build)

    def test_plan_and_work_are_emitted_for_both_hosts(self):
        for name in ("plan", "work"):
            claude = _ROOT / "dist" / "claude-code" / "plugins" / "development-lifecycle" / "commands" / ("%s.md" % name)
            self.assertTrue(claude.is_file(), claude)


if __name__ == "__main__":
    unittest.main()
