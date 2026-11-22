#!/usr/bin/env python3
"""Wiring tests for /create-it: the command's prose calls each helper the way the
helper's own contract says, and the formats it describes (the likeness list, the
paired images, the playtest checklist) are the ones the helpers really write and read.

test_asset_checks.py, test_loop_record.py and test_spec_doc.py prove the helpers; this
proves the command uses them, names a model on every dispatch, keeps agentm off the
required path, and is emitted for both hosts.

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
COMMAND = _DL / "commands" / "create-it.md"
EVALUATOR = _DL / "agents" / "evaluator.md"
REVIEW_MATERIAL = _ROOT / "src" / "code-review" / "scripts" / "review_material.py"
CROSS_REVIEW = _ROOT / "src" / "code-review" / "scripts" / "cross-review.sh"
PROSE_PASS = _ROOT / "src" / "design" / "scripts" / "prose_pass.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


lr = _load("loop_record", _DL / "scripts" / "loop_record.py")
sd = _load("spec_doc", _DL / "scripts" / "spec_doc.py")
ac = _load("asset_checks", _DL / "scripts" / "asset_checks.py")


def code_spans(text: str):
    return re.findall(r"`([^`\n]+)`", text)


def verb_flags(verb: str):
    parser = lr._build_parser()
    sub = next(a for a in parser._actions if a.dest == "cmd")
    return {o for a in sub.choices[verb]._actions for o in a.option_strings}


class HelpersAreNamedTests(unittest.TestCase):
    def setUp(self):
        self.text = COMMAND.read_text(encoding="utf-8")

    def test_every_helper_it_relies_on_is_named_and_exists(self):
        for helper, path in (("spec_doc.py", _DL / "scripts" / "spec_doc.py"),
                             ("asset_checks.py", _DL / "scripts" / "asset_checks.py"),
                             ("loop_record.py", _DL / "scripts" / "loop_record.py"),
                             ("review_material.py", REVIEW_MATERIAL),
                             ("cross-review.sh", CROSS_REVIEW),
                             ("prose_pass.py", PROSE_PASS),
                             ("sibling_plugin.py", _DL / "scripts" / "sibling_plugin.py")):
            self.assertIn(helper, self.text, "create-it never names %s" % helper)
            self.assertTrue(path.is_file(), path)

    def test_sibling_scripts_are_reached_through_the_resolver_with_an_exit_code(self):
        self.assertIn('sibling_plugin.py" <plugin> scripts/<file>', self.text)
        self.assertIn('sibling_plugin.py" design scripts/prose_pass.py', self.text)
        self.assertRegex(self.text, r"\*\*Exit 1\*\* means that plugin is not installed")

    def test_every_loop_record_verb_it_calls_exists_with_those_flags(self):
        seen = set()
        for span in code_spans(self.text):
            m = re.match(r"loop_record\.py (?P<verb>[a-z-]+)(?P<rest>.*)$", span)
            if not m:
                continue
            seen.add(m.group("verb"))
            flags = set(re.findall(r"--[a-z-]+", m.group("rest")))
            self.assertLessEqual(flags, verb_flags(m.group("verb")), span)
        for verb in ("init", "passes", "open-round", "add", "dispose", "stop", "status", "report",
                     "requirement", "not-checked", "pair", "playtest"):
            self.assertIn(verb, seen, "create-it never calls `loop_record.py %s`" % verb)

    def test_the_asset_checks_flags_it_uses_exist(self):
        parser = ac._build_parser()
        sub = next(a for a in parser._actions if a.dest == "cmd")
        known = {o for a in sub.choices["check"]._actions for o in a.option_strings}
        used = set()
        for span in code_spans(self.text) + re.findall(r"asset_checks\.py\"? check[^\n]*", self.text):
            if "asset_checks.py" in span or span.startswith("--grid") or span.startswith("--frame-size"):
                used |= set(re.findall(r"--[a-z-]+", span))
        self.assertTrue({"--reference", "--out-dir"} <= used, used)
        self.assertLessEqual(used, known)

    def test_the_review_material_flags_and_tiers_are_real(self):
        rm = REVIEW_MATERIAL.read_text(encoding="utf-8")
        cr = CROSS_REVIEW.read_text(encoding="utf-8")
        for span in code_spans(self.text):
            if span.startswith("review_material.py"):
                for flag in re.findall(r"--[a-z-]+", span):
                    self.assertIn('"%s"' % flag, rm, span)
        for tier in re.findall(r"--tier (\w+)", self.text):
            self.assertIn("    %s)" % tier, cr)

    def test_the_prose_pass_flags_it_uses_exist_and_the_model_is_the_wording_tier(self):
        pp = PROSE_PASS.read_text(encoding="utf-8")
        for flag in ("--fact-guard-text", "--model", "-o"):
            self.assertIn(flag, self.text)
            self.assertIn('"%s"' % flag, pp)
        model = re.search(r'--model "([^"]+)"', self.text).group(1)
        cr = CROSS_REVIEW.read_text(encoding="utf-8")
        wording = re.search(r'wording\)\s+MODEL="([^"]+)"', cr).group(1)
        self.assertEqual(model, wording, "the voice pass must ask for the wording tier's model")


class FormatsMatchTests(unittest.TestCase):
    """The command describes the spec's and the report's shapes; they must be the real ones."""

    def setUp(self):
        self.text = COMMAND.read_text(encoding="utf-8")

    def test_the_spec_sections_it_names_are_the_specs(self):
        self.assertIn("**Reference**", self.text)
        self.assertIn("**Likeness list**", self.text)
        self.assertEqual(sd.SECTIONS["reference"], "Reference")
        self.assertEqual(sd.SECTIONS["likeness"], "Likeness list")

    def test_the_likeness_list_size_is_the_specs(self):
        self.assertIn("%d to %d likeness lines" % (sd.LIKENESS_MIN, sd.LIKENESS_MAX), self.text)
        self.assertIn("%d lines or fewer" % sd.LIKENESS_MAX, self.text)

    def test_a_proposed_likeness_line_is_a_bullet_the_spec_parses(self):
        spec = sd.Spec(title="t", profile="create", goal="g", done_when=["`x` exits 0"], rules=[],
                       not_doing=[], open_questions=[], reference="reference/",
                       likeness=["the outline is one pixel", "it feels weighty"] * 3)
        parsed = sd.parse(sd.render(spec))
        self.assertEqual(len(parsed.likeness), 6)
        self.assertEqual(sd.check(parsed), [])

    def test_the_report_headings_it_promises_are_the_ones_the_report_writes(self):
        rec = lr.new_record("create", "large", prose=True)
        lr.add_pair(rec, "ref/a.png", "out/a.png")
        lr.add_playtest(rec, "plays")
        report = lr.render_report(rec)
        for heading in ("Paired images", "Playtest checklist", "Not checked"):
            self.assertIn("## " + heading, report)
            self.assertIn("**%s**" % heading if heading != "Not checked" else heading, self.text)

    def test_the_passes_it_names_are_the_record_for_prose_create_work(self):
        entries = lr.passes_for("create", "large", prose=True)
        for e in entries:
            self.assertIn(e["name"], self.text, e["name"])

    def test_the_likeness_pass_uses_the_evaluators_sections_and_the_spec_line_as_the_cited_line(self):
        ev = EVALUATOR.read_text(encoding="utf-8")
        for label in ("ARTIFACT:", "ANCHOR:", "RECORD:"):
            self.assertIn(label, self.text)
            self.assertIn(label, ev)
        self.assertIn("one rubric item per likeness-list line", self.text)
        self.assertIn("cite the likeness-list line (`<spec>:LINE`)", self.text)


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.text = COMMAND.read_text(encoding="utf-8")

    def test_it_stops_when_there_is_no_reference_and_no_human_to_ask(self):
        self.assertIn("stop and say the reference folder and likeness list are missing", self.text)

    def test_passes_run_one_at_a_time(self):
        self.assertIn("**One at a time, never in parallel.**", self.text)

    def test_a_wrong_direction_pauses_even_mid_work(self):
        self.assertIn("stop and ask the operator", self.text)
        self.assertIn("even in the middle of `/work`", self.text)

    def test_a_longer_revision_is_not_accepted(self):
        self.assertIn("A revision that comes back longer than the original is not accepted", self.text)

    def test_what_nobody_looked_at_or_listened_to_is_said(self):
        self.assertIn("nobody has listened", self.text)
        self.assertIn("reads text and measurements, never pixels or sound", self.text)

    def test_asset_differences_are_looked_at_not_auto_failed(self):
        self.assertIn("exit 1 is a difference to look at, not an automatic fail", self.text)

    def test_general_feedback_becomes_a_proposed_likeness_line_and_is_not_written_unasked(self):
        self.assertIn("offer it as one new bullet for the spec's Likeness list", self.text)
        self.assertIn("and ask", self.text)

    def test_both_degraded_markers_are_named_with_fallbacks(self):
        self.assertIn("CROSS-REVIEW-DEGRADED:", self.text)
        self.assertIn("PROSE-PASS-DEGRADED:", self.text)

    def test_a_not_met_requirement_or_open_finding_is_never_called_done(self):
        self.assertIn("Never write \"done\" over a NOT MET requirement or an OPEN finding", self.text)


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

    def test_both_hosts_carry_it(self):
        claude = _ROOT / "dist" / "claude-code" / "plugins" / "development-lifecycle" / "commands" / "create-it.md"
        agy = _ROOT / "dist" / "antigravity" / "plugins" / "development-lifecycle" / "skills" / "create-it" / "SKILL.md"
        self.assertTrue(claude.is_file(), claude)
        self.assertTrue(agy.is_file(), agy)


if __name__ == "__main__":
    unittest.main()
