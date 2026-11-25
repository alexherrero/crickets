#!/usr/bin/env python3
"""Wiring tests for /build-it: the command's prose calls each helper the way the
helper's own contract says, so a renamed verb or flag fails here rather than in
front of the operator.

test_loop_record.py, test_review_material.py and test_spec_doc.py prove the helpers;
this proves the command uses them, names a model on every dispatch, keeps agentm off
the required path, has its --check mode, and is emitted for both hosts.

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
COMMAND = _DL / "commands" / "build-it.md"
EVALUATOR = _DL / "agents" / "evaluator.md"
REVIEW_MATERIAL = _ROOT / "src" / "code-review" / "scripts" / "review_material.py"
CROSS_REVIEW = _ROOT / "src" / "code-review" / "scripts" / "cross-review.sh"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


lr = _load("loop_record", _DL / "scripts" / "loop_record.py")
rm = _load("review_material_for_wiring", REVIEW_MATERIAL)


def code_spans(text: str):
    return re.findall(r"`([^`\n]+)`", text)


def verb_flags(verb: str):
    """The option strings loop_record's parser accepts for one verb."""
    parser = lr._build_parser()
    sub = next(a for a in parser._actions if a.dest == "cmd")
    return {o for a in sub.choices[verb]._actions for o in a.option_strings}


class HelpersAreNamedTests(unittest.TestCase):
    def setUp(self):
        self.text = COMMAND.read_text(encoding="utf-8")

    def test_every_helper_it_relies_on_is_named_and_exists(self):
        for helper, path in (("spec_doc.py", _DL / "scripts" / "spec_doc.py"),
                             ("loop_record.py", _DL / "scripts" / "loop_record.py"),
                             ("review_material.py", REVIEW_MATERIAL),
                             ("cross-review.sh", CROSS_REVIEW),
                             ("sibling_plugin.py", _DL / "scripts" / "sibling_plugin.py")):
            self.assertIn(helper, self.text, "build-it never names %s" % helper)
            self.assertTrue(path.is_file(), path)

    def test_it_reaches_the_code_review_scripts_through_the_resolver_with_its_exit_code(self):
        self.assertIn('sibling_plugin.py" code-review scripts/', self.text)
        self.assertRegex(self.text, r"\*\*Exit 1\*\* means `code-review` is not installed")

    def test_every_loop_record_verb_it_calls_exists_with_those_flags(self):
        seen = set()
        for span in code_spans(self.text):
            m = re.match(r"loop_record\.py (?P<verb>[a-z-]+)(?P<rest>.*)$", span)
            if not m:
                continue
            verb = m.group("verb")
            seen.add(verb)
            flags = set(re.findall(r"--[a-z-]+", m.group("rest")))
            self.assertLessEqual(flags, verb_flags(verb), "%s: %s" % (verb, span))
        for verb in ("init", "passes", "open-round", "add", "dispose", "stop", "status", "report",
                     "requirement", "not-checked", "add-security"):
            self.assertIn(verb, seen, "build-it never calls `loop_record.py %s`" % verb)

    def test_the_review_material_flags_it_uses_are_real(self):
        for span in code_spans(self.text):
            if not span.startswith("review_material.py"):
                continue
            for flag in re.findall(r"--[a-z-]+", span):
                self.assertIn('"%s"' % flag, REVIEW_MATERIAL.read_text(encoding="utf-8"), span)

    def test_the_tiers_it_names_are_the_ones_the_helpers_know(self):
        for tier in re.findall(r"--tier (\w+)", self.text):
            self.assertIn(tier, rm.TIER_CEILINGS)
            self.assertIn("    %s)" % tier, CROSS_REVIEW.read_text(encoding="utf-8"))

    def test_the_finding_classes_are_loop_records(self):
        for cls in lr.CLASSES:
            self.assertIn("**%s**" % cls, self.text)

    def test_the_spec_is_checked_and_spec_is_the_fallback_anchor(self):
        self.assertIn("`spec_doc.py check <spec>`", self.text)
        self.assertIn("`/spec`", self.text)

    def test_the_done_check_uses_the_evaluators_sections(self):
        ev = EVALUATOR.read_text(encoding="utf-8")
        for label in ("ARTIFACT:", "ANCHOR:", "RECORD:"):
            self.assertIn(label, self.text)
            self.assertIn(label, ev)


class ModesAndRulesTests(unittest.TestCase):
    def setUp(self):
        self.text = COMMAND.read_text(encoding="utf-8")

    def test_check_mode_exists_and_never_fixes(self):
        self.assertIn("`--check <PR number | A..B | diff file>`", self.text)
        self.assertIn("It never edits the code and never fixes", self.text)
        self.assertIn("Skip steps 3 and 4", self.text)

    def test_the_arguments_are_documented(self):
        head = self.text.split("---", 2)[1]
        for arg in ("--spec", "--size", "--check"):
            self.assertIn(arg, head)

    def test_passes_run_one_at_a_time(self):
        self.assertIn("**One at a time, never in parallel.**", self.text)

    def test_a_wrong_direction_pauses_even_mid_work(self):
        self.assertIn("**A wrong direction** says the approach would not meet the anchor", self.text)
        self.assertIn("**Stop and ask the operator**, even in the middle of `/work`", self.text)

    def test_a_detail_is_corrected_and_rechecked_without_a_stop(self):
        self.assertIn("**A detail** is a mistake inside an approach that otherwise stands", self.text)
        self.assertIn("open the next direction round. No stop.", self.text)

    def test_the_operators_call_is_recorded_with_decide(self):
        self.assertIn("loop_record.py decide --record <record> --pass direction", self.text)
        self.assertIn("loop_record.py decide --record <record> --pass <name>", self.text)

    def test_free_checks_come_before_any_reviewer(self):
        self.assertIn("They pass before any reviewer is called.", self.text)

    def test_the_reviewer_never_sees_reasoning_or_a_suspected_bug(self):
        self.assertIn("never your reasoning, and never your guess at the bug", self.text)

    def test_a_degraded_review_is_announced_and_falls_back_to_a_named_model(self):
        self.assertIn("CROSS-REVIEW-DEGRADED:", self.text)
        self.assertIn("say so in one line", self.text)
        self.assertIn("model sonnet", self.text)

    def test_an_escalation_hands_the_operator_the_open_findings(self):
        self.assertIn("**escalate** (exit 3", self.text)

    def test_a_not_met_requirement_or_open_finding_is_never_called_done(self):
        self.assertIn("Never write \"done\" over a NOT MET requirement or an OPEN finding", self.text)

    def test_it_names_every_pass_the_record_can_hold_for_build_work(self):
        entries = lr.passes_for("build", "large", security=True)
        for e in entries:
            self.assertIn(e["name"], self.text, e["name"])


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.text = COMMAND.read_text(encoding="utf-8")

    def test_every_dispatch_names_its_model(self):
        self.assertEqual(wc.dispatches_without_a_model(self.text), [])

    def test_no_agentm_call_is_unguarded(self):
        self.assertEqual(wc.unguarded_agentm_calls(self.text), [])

    def test_agentm_is_not_on_the_required_path(self):
        for name in ("agentm_bridge", "harness_memory", "process_seam", "project_homes", "resolve_plan"):
            self.assertNotIn(name, self.text, name)

    def test_it_stays_under_what_antigravity_will_load(self):
        self.assertLess(len(self.text.encode("utf-8")), 24000)


class EmittedTests(unittest.TestCase):
    def test_both_hosts_carry_it(self):
        claude = _ROOT / "dist" / "claude-code" / "plugins" / "development-lifecycle" / "commands" / "build-it.md"
        agy = _ROOT / "dist" / "antigravity" / "plugins" / "development-lifecycle" / "skills" / "build-it" / "SKILL.md"
        self.assertTrue(claude.is_file(), claude)
        self.assertTrue(agy.is_file(), agy)


if __name__ == "__main__":
    unittest.main()
