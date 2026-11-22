#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/loop_record.py.

The loop's bookkeeping must be exact where a script can settle it: which reviews a
task of a given size and profile runs, in what order and on which tier; what a
round's findings are; when a pass stops; and when a run of reviews was theater.
A wrong pass list silently skips a review or runs one that should not run, and a
wrong stop rule either loops forever or stops with a real defect still open.

stdlib only.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "src" / "development-lifecycle" / "scripts" / "loop_record.py"


def _load():
    spec = importlib.util.spec_from_file_location("loop_record", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["loop_record"] = m
    spec.loader.exec_module(m)
    return m


lr = _load()


def names(entries):
    return [e["name"] for e in entries]


def by_name(entries):
    return {e["name"]: e for e in entries}


class PassListTests(unittest.TestCase):
    """Every size x profile."""

    def test_small_runs_no_reviews_for_any_profile(self):
        for profile in lr.PROFILES:
            self.assertEqual(lr.passes_for(profile, "small", security=True, prose=True), [])

    def test_medium_build_is_direction_one_pass_done_check(self):
        out = lr.passes_for("build", "medium")
        self.assertEqual(names(out), ["direction", "correctness", "done-check"])

    def test_large_build_is_direction_every_pass_done_check(self):
        out = lr.passes_for("build", "large")
        self.assertEqual(names(out), ["direction", "correctness", "simplicity", "done-check"])

    def test_medium_create_takes_only_the_first_pass(self):
        out = lr.passes_for("create", "medium", prose=True)
        self.assertEqual(names(out), ["direction", "likeness", "done-check"])

    def test_large_create_non_prose_has_no_voice_pass(self):
        out = lr.passes_for("create", "large")
        self.assertEqual(names(out), ["direction", "likeness", "craft", "done-check"])

    def test_large_create_prose_has_voice_last_before_the_done_check(self):
        out = lr.passes_for("create", "large", prose=True)
        self.assertEqual(names(out), ["direction", "likeness", "craft", "voice", "done-check"])

    def test_prose_voice_can_be_turned_off(self):
        out = lr.passes_for("create", "large", prose=True, voice=False)
        self.assertNotIn("voice", names(out))

    def test_both_profile_runs_build_then_create(self):
        out = lr.passes_for("both", "large", prose=True)
        self.assertEqual(names(out), ["direction", "correctness", "simplicity", "likeness",
                                      "craft", "voice", "done-check"])

    def test_both_profile_at_medium_takes_the_first_pass_of_each(self):
        out = lr.passes_for("both", "medium")
        self.assertEqual(names(out), ["direction", "correctness", "likeness", "done-check"])

    def test_every_list_is_one_sequence_of_distinct_names(self):
        # Passes run one after another, never in parallel: a duplicate would be a second
        # run of the same reviewer, and the list is the order.
        for profile in lr.PROFILES:
            for size in lr.SIZES:
                out = names(lr.passes_for(profile, size, security=True, prose=True))
                self.assertEqual(len(out), len(set(out)), (profile, size, out))

    def test_unknown_profile_or_size_is_refused(self):
        with self.assertRaises(lr.RecordError):
            lr.passes_for("nope", "large")
        with self.assertRaises(lr.RecordError):
            lr.passes_for("build", "huge")


class SecurityPassTests(unittest.TestCase):
    def test_security_pass_follows_correctness_only_when_asked(self):
        without = names(lr.passes_for("build", "large"))
        with_sec = names(lr.passes_for("build", "large", security=True))
        self.assertNotIn("security", without)
        self.assertEqual(with_sec, ["direction", "correctness", "security", "simplicity", "done-check"])

    def test_security_runs_at_medium_too(self):
        out = names(lr.passes_for("build", "medium", security=True))
        self.assertEqual(out, ["direction", "correctness", "security", "done-check"])

    def test_security_is_never_added_at_small(self):
        self.assertEqual(lr.passes_for("build", "small", security=True), [])

    def test_security_is_a_claude_agent_with_no_tier(self):
        e = by_name(lr.passes_for("build", "large", security=True))["security"]
        self.assertEqual(e["reviewer"], "agent:security-auditor")
        self.assertIsNone(e["tier"])

    def test_security_does_not_attach_to_create_only_work(self):
        # Its trigger sits inside the build correctness pass; create-it has none.
        self.assertNotIn("security", names(lr.passes_for("create", "large", security=True)))


class TierTests(unittest.TestCase):
    def test_direction_runs_on_the_high_tier(self):
        for size in ("medium", "large"):
            self.assertEqual(by_name(lr.passes_for("build", size))["direction"]["tier"], "high")

    def test_correctness_is_default_at_medium_and_high_at_large(self):
        self.assertEqual(by_name(lr.passes_for("build", "medium"))["correctness"]["tier"], "default")
        self.assertEqual(by_name(lr.passes_for("build", "large"))["correctness"]["tier"], "high")

    def test_other_review_passes_are_default_and_voice_is_wording(self):
        e = by_name(lr.passes_for("both", "large", prose=True))
        for n in ("simplicity", "likeness", "craft"):
            self.assertEqual(e[n]["tier"], "default", n)
        self.assertEqual(e["voice"]["tier"], "wording")

    def test_done_check_is_an_evaluator_with_no_tier(self):
        e = by_name(lr.passes_for("build", "medium"))["done-check"]
        self.assertEqual((e["reviewer"], e["tier"]), ("agent:evaluator", None))

    def test_every_tier_is_one_cross_review_knows(self):
        known = {"default", "high", "wording", None}
        text = (_ROOT / "src" / "code-review" / "scripts" / "cross-review.sh").read_text(encoding="utf-8")
        for t in known - {None}:
            self.assertIn("    %s)" % t, text, "cross-review.sh has no %r tier" % t)
        for profile in lr.PROFILES:
            for size in lr.SIZES:
                for e in lr.passes_for(profile, size, security=True, prose=True):
                    self.assertIn(e["tier"], known, e)


class FindingTests(unittest.TestCase):
    def setUp(self):
        self.rec = lr.new_record("build", "large")

    def test_a_finding_lands_in_the_latest_round(self):
        lr.open_round(self.rec, "correctness")
        lr.add_finding(self.rec, "correctness", "real", "src/a.py:12", "off by one")
        lr.open_round(self.rec, "correctness")
        lr.add_finding(self.rec, "correctness", "noise", "src/a.py:30-31", "naming")
        rounds = _pass(self.rec, "correctness")["rounds"]
        self.assertEqual([len(r["findings"]) for r in rounds], [1, 1])
        self.assertEqual(rounds[1]["findings"][0]["class"], "noise")

    def test_a_finding_with_no_cited_line_is_refused(self):
        lr.open_round(self.rec, "correctness")
        for bad in ("", "src/a.py", "a.py:", ":12", "a.py:x", "12"):
            with self.assertRaises(lr.RecordError, msg=bad):
                lr.add_finding(self.rec, "correctness", "real", bad, "x")

    def test_an_unknown_class_is_refused(self):
        lr.open_round(self.rec, "correctness")
        with self.assertRaises(lr.RecordError):
            lr.add_finding(self.rec, "correctness", "bug", "a.py:1", "x")

    def test_a_finding_without_text_is_refused(self):
        lr.open_round(self.rec, "correctness")
        with self.assertRaises(lr.RecordError):
            lr.add_finding(self.rec, "correctness", "real", "a.py:1", "  ")

    def test_adding_before_a_round_is_open_is_refused(self):
        with self.assertRaises(lr.RecordError):
            lr.add_finding(self.rec, "correctness", "real", "a.py:1", "x")

    def test_an_unknown_pass_is_refused_and_names_the_real_ones(self):
        with self.assertRaises(lr.RecordError) as ctx:
            lr.open_round(self.rec, "security")
        self.assertIn("correctness", str(ctx.exception))

    def test_a_refused_finding_leaves_the_record_unchanged(self):
        lr.open_round(self.rec, "correctness")
        before = json.dumps(self.rec, sort_keys=True)
        with self.assertRaises(lr.RecordError):
            lr.add_finding(self.rec, "correctness", "real", "nolineatall", "x")
        self.assertEqual(json.dumps(self.rec, sort_keys=True), before)


def _pass(rec, name):
    return next(p for p in rec["passes"] if p["name"] == name)


class StopRuleTests(unittest.TestCase):
    def setUp(self):
        self.rec = lr.new_record("build", "large")

    def _round(self, *classes, name="correctness"):
        lr.open_round(self.rec, name)
        for i, c in enumerate(classes):
            lr.add_finding(self.rec, name, c, "f.py:%d" % (i + 1), "finding %d" % i)

    def test_a_pass_with_no_round_yet_continues(self):
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "continue")

    def test_an_empty_round_is_done(self):
        self._round()
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "done")

    def test_a_round_with_a_real_finding_continues(self):
        self._round("real", "noise")
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "continue")

    def test_a_round_with_no_real_finding_is_done_whatever_else_it_holds(self):
        self._round("tradeoff", "misread", "noise")
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "done")

    def test_the_second_round_clean_ends_the_pass(self):
        self._round("real")
        self._round("noise")
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "done")

    def test_round_three_with_a_real_finding_escalates(self):
        self._round("real")
        self._round("real")
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "continue")
        self._round("real")
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "escalate")

    def test_round_three_clean_is_done_not_escalated(self):
        self._round("real")
        self._round("real")
        self._round("tradeoff")
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "done")

    def test_a_fourth_round_is_refused(self):
        self._round("real")
        self._round("real")
        self._round("real")
        with self.assertRaises(lr.RecordError):
            lr.open_round(self.rec, "correctness")

    def test_a_stopped_pass_refuses_another_round(self):
        self._round("noise")
        with self.assertRaises(lr.RecordError):
            lr.open_round(self.rec, "correctness")

    def test_passes_are_judged_independently(self):
        self._round("real")
        self._round(name="simplicity")
        self.assertEqual(lr.stop_verdict(self.rec, "correctness"), "continue")
        self.assertEqual(lr.stop_verdict(self.rec, "simplicity"), "done")


class DoubtTheaterTests(unittest.TestCase):
    def setUp(self):
        self.rec = lr.new_record("build", "large")

    def _round(self, name, *classes):
        lr.open_round(self.rec, name)
        for i, c in enumerate(classes):
            lr.add_finding(self.rec, name, c, "f.py:%d" % (i + 1), "finding")

    def test_two_rounds_of_findings_and_no_real_one_is_theater(self):
        self._round("correctness", "noise")
        self._round("simplicity", "misread", "tradeoff")
        self.assertTrue(lr.doubt_theater(self.rec))

    def test_one_round_of_findings_is_not_theater(self):
        self._round("correctness", "noise")
        self.assertFalse(lr.doubt_theater(self.rec))

    def test_empty_rounds_are_not_theater(self):
        self._round("correctness")
        self._round("simplicity")
        self.assertFalse(lr.doubt_theater(self.rec))

    def test_a_real_finding_anywhere_clears_it(self):
        self._round("correctness", "real")
        self._round("correctness", "noise")
        self._round("simplicity", "noise")
        self.assertFalse(lr.doubt_theater(self.rec))

    def test_two_noise_rounds_in_one_pass_count(self):
        # A hand-edited or imported record can hold them; the flag reads the rounds as
        # written, not how they were reached.
        finding = {"class": "noise", "line": "f.py:1", "text": "x"}
        _pass(self.rec, "correctness")["rounds"] = [{"n": 1, "findings": [finding]},
                                                    {"n": 2, "findings": [dict(finding)]}]
        self.assertTrue(lr.doubt_theater(self.rec))


class RecordFileTests(unittest.TestCase):
    def test_round_trip_through_json(self):
        rec = lr.new_record("create", "large", prose=True)
        lr.open_round(rec, "voice")
        lr.add_finding(rec, "voice", "real", "docs/a.md:3", "stiff")
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "nested" / "loop.json")
            lr.save(path, rec)
            self.assertEqual(lr.load(path), rec)
            self.assertEqual([p.name for p in Path(d, "nested").iterdir()], ["loop.json"])

    def test_a_record_that_is_not_ours_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            for body in ("not json", "[]", '{"version": 9, "passes": []}', '{"version": 1}'):
                p.write_text(body, encoding="utf-8")
                with self.assertRaises(lr.RecordError, msg=body):
                    lr.load(str(p))
            with self.assertRaises(lr.RecordError):
                lr.load(str(Path(d) / "missing.json"))

    def test_status_counts_classes_and_names_each_verdict(self):
        rec = lr.new_record("build", "large")
        lr.open_round(rec, "correctness")
        lr.add_finding(rec, "correctness", "real", "a.py:1", "x")
        lr.add_finding(rec, "correctness", "noise", "a.py:2", "y")
        s = lr.status(rec)
        self.assertEqual(s["findings"], {"real": 1, "tradeoff": 0, "misread": 0, "noise": 1})
        self.assertEqual({p["name"]: p["verdict"] for p in s["passes"]}["correctness"], "continue")
        self.assertFalse(s["doubt_theater"])


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = lr.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_passes_prints_json(self):
        rc, out, _ = self.run_cli("passes", "--profile", "build", "--size", "medium")
        self.assertEqual(rc, 0)
        self.assertEqual(names(json.loads(out)), ["direction", "correctness", "done-check"])

    def test_a_full_loop_through_the_cli(self):
        with tempfile.TemporaryDirectory() as d:
            rec = str(Path(d) / "loop.json")
            self.assertEqual(self.run_cli("init", "--record", rec, "--profile", "build", "--size", "large")[0], 0)
            rc, out, _ = self.run_cli("open-round", "--record", rec, "--pass", "correctness")
            self.assertEqual((rc, out.strip()), (0, "1"))
            rc, _, _ = self.run_cli("add", "--record", rec, "--pass", "correctness", "--class", "real",
                                    "--line", "src/a.py:9", "--text", "null deref")
            self.assertEqual(rc, 0)
            self.assertEqual(self.run_cli("stop", "--record", rec, "--pass", "correctness")[1].strip(), "continue")
            for _ in range(2):
                self.run_cli("open-round", "--record", rec, "--pass", "correctness")
                self.run_cli("add", "--record", rec, "--pass", "correctness", "--class", "real",
                             "--line", "src/a.py:9", "--text", "still there")
            rc, out, _ = self.run_cli("stop", "--record", rec, "--pass", "correctness")
            self.assertEqual((rc, out.strip()), (3, "escalate"))
            rc, out, _ = self.run_cli("status", "--record", rec)
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out)["findings"]["real"], 3)

    def test_init_never_overwrites_a_record(self):
        with tempfile.TemporaryDirectory() as d:
            rec = str(Path(d) / "loop.json")
            self.assertEqual(self.run_cli("init", "--record", rec, "--profile", "build", "--size", "small")[0], 0)
            rc, _, err = self.run_cli("init", "--record", rec, "--profile", "build", "--size", "large")
            self.assertEqual(rc, 2)
            self.assertIn("already exists", err)

    def test_bad_input_exits_2_with_a_message(self):
        with tempfile.TemporaryDirectory() as d:
            rec = str(Path(d) / "loop.json")
            self.run_cli("init", "--record", rec, "--profile", "build", "--size", "large")
            rc, _, err = self.run_cli("add", "--record", rec, "--pass", "correctness", "--class", "real",
                                      "--line", "no-line", "--text", "x")
            self.assertEqual(rc, 2)
            self.assertIn("path:LINE", err)
            self.assertEqual(self.run_cli("passes", "--profile", "nope", "--size", "large")[0], 2)

    def test_runs_as_a_script(self):
        p = subprocess.run([sys.executable, str(_SCRIPT), "passes", "--profile", "create", "--size", "large",
                            "--prose"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("voice", names(json.loads(p.stdout)))


_GOLDEN = _HERE / "fixtures" / "loop_record"


def build_record():
    """A large build-it run: two rounds of correctness, one of simplicity, a tradeoff kept."""
    rec = lr.new_record("build", "large")
    lr.add_requirement(rec, "`parse()` returns an empty list for empty input", "met",
                       "tests/test_parser.py::test_empty_input passes (gate output on disk)")
    lr.add_requirement(rec, "the CLI exits 2 on a missing file", "not-met",
                       "src/cli.py:41 raises FileNotFoundError, which exits 1")
    lr.open_round(rec, "direction")
    lr.open_round(rec, "correctness")
    lr.add_finding(rec, "correctness", "real", "src/parser.py:88", "an empty line ends the loop early")
    lr.add_finding(rec, "correctness", "noise", "src/parser.py:12", "import order")
    lr.dispose(rec, "correctness", 1, 1, "fixed in the next commit")
    lr.open_round(rec, "correctness")
    lr.add_finding(rec, "correctness", "tradeoff", "src/parser.py:60-64", "reads the whole file into memory")
    lr.open_round(rec, "simplicity")
    lr.add_finding(rec, "simplicity", "real", "src/parser.py:101", "dead branch left behind")
    lr.add_not_checked(rec, "behaviour on Windows line endings")
    return rec


def create_record():
    """A create-it run on prose: likeness and voice ran, craft never did."""
    rec = lr.new_record("create", "large", prose=True)
    lr.add_requirement(rec, "the sprite sheet has 8 walk frames", "met",
                       "assets/walk.png is 8 frames wide at 32 px (asset check output)")
    lr.open_round(rec, "likeness")
    lr.add_finding(rec, "likeness", "misread", "assets/walk.png:1", "says the palette has 12 colours; it has 9")
    lr.open_round(rec, "voice")
    lr.add_pair(rec, "reference/walk-ref.png", "assets/walk.png")
    lr.add_playtest(rec, "the walk loops without a visible hitch at 12 fps")
    lr.add_playtest(rec, "the sprite reads clearly on the dark background")
    return rec


def empty_record():
    """A medium run whose one pass came back clean. Still says what it did not check."""
    rec = lr.new_record("build", "medium")
    lr.add_requirement(rec, "`greet()` returns the name it was given", "met", "tests/test_greet.py passes")
    lr.open_round(rec, "direction")
    lr.open_round(rec, "correctness")
    lr.add_not_checked(rec, "behaviour with a non-ASCII name")
    return rec


class ReportTests(unittest.TestCase):
    def assertGolden(self, name, text):
        golden = (_GOLDEN / name).read_text(encoding="utf-8")
        self.assertEqual(text, golden, "report drifted from fixtures/loop_record/%s" % name)

    def test_build_report_matches_the_golden_file(self):
        self.assertGolden("build.report.md", lr.render_report(build_record()))

    def test_create_report_matches_the_golden_file(self):
        self.assertGolden("create.report.md", lr.render_report(create_record()))

    def test_a_clean_run_still_lists_what_was_not_checked(self):
        text = lr.render_report(empty_record())
        self.assertGolden("empty.report.md", text)
        self.assertIn("## Not checked", text)
        self.assertIn("- behaviour with a non-ASCII name", text)
        self.assertIn("round 1 · no findings", text)

    def test_not_checked_is_never_left_out(self):
        rec = lr.new_record("build", "medium")
        for name in ("direction", "correctness", "done-check"):
            lr.open_round(rec, name)
        text = lr.render_report(rec)
        self.assertIn("## Not checked", text)
        self.assertIn("Nothing recorded as unchecked.", text)

    def test_a_small_run_says_no_review_ran(self):
        text = lr.render_report(lr.new_record("build", "small"))
        self.assertIn("No review ran: free checks only (size: small).", text)
        self.assertIn("Every review: this size runs free checks only.", text)

    def test_a_pass_that_never_ran_is_named_in_both_places(self):
        text = lr.render_report(create_record())
        self.assertIn("### craft — never ran", text)
        self.assertIn("- craft: the review never ran", text)

    def test_the_done_check_is_not_listed_as_never_run(self):
        # It grades this report, so at report time it cannot have run.
        for rec in (build_record(), create_record(), empty_record()):
            self.assertNotIn("done-check", lr.render_report(rec))

    def test_an_undisposed_real_finding_reads_open_and_is_counted(self):
        text = lr.render_report(build_record())
        self.assertIn("`src/parser.py:101` — dead branch left behind → OPEN", text)
        self.assertIn("1 real finding(s) open", text)

    def test_a_disposition_replaces_the_default(self):
        text = lr.render_report(build_record())
        self.assertIn("an empty line ends the loop early → fixed in the next commit", text)

    def test_default_dispositions_by_class(self):
        text = lr.render_report(build_record())
        self.assertIn("import order → dismissed: noise", text)
        self.assertIn("reads the whole file into memory → accepted tradeoff", text)

    def test_a_build_report_has_no_create_sections(self):
        text = lr.render_report(build_record())
        self.assertNotIn("Paired images", text)
        self.assertNotIn("Playtest", text)

    def test_the_report_reads_without_changing_the_record(self):
        rec = build_record()
        before = json.dumps(rec, sort_keys=True)
        lr.render_report(rec)
        self.assertEqual(json.dumps(rec, sort_keys=True), before)

    def test_escalated_passes_and_theater_show_in_the_result_line(self):
        rec = lr.new_record("build", "large")
        for _ in range(3):
            lr.open_round(rec, "correctness")
            lr.add_finding(rec, "correctness", "real", "a.py:1", "still broken")
        self.assertIn("escalated: correctness", lr.render_report(rec))
        rec = lr.new_record("build", "large")
        lr.open_round(rec, "correctness")
        lr.add_finding(rec, "correctness", "noise", "a.py:1", "x")
        lr.open_round(rec, "simplicity")
        lr.add_finding(rec, "simplicity", "noise", "a.py:2", "y")
        self.assertIn("doubt theater: yes", lr.render_report(rec))


class ReportInputTests(unittest.TestCase):
    def setUp(self):
        self.build = lr.new_record("build", "large")
        self.create = lr.new_record("create", "large")

    def test_a_requirement_needs_evidence_met_or_not(self):
        for status in ("met", "not-met"):
            with self.assertRaises(lr.RecordError, msg=status):
                lr.add_requirement(self.build, "it works", status, "  ")

    def test_an_unknown_requirement_status_is_refused(self):
        with self.assertRaises(lr.RecordError):
            lr.add_requirement(self.build, "it works", "partly", "saw it")

    def test_pairs_and_playtest_belong_to_create_it(self):
        with self.assertRaises(lr.RecordError):
            lr.add_pair(self.build, "ref.png", "made.png")
        with self.assertRaises(lr.RecordError):
            lr.add_playtest(self.build, "feels right")
        lr.add_pair(self.create, "ref.png", "made.png")
        lr.add_playtest(self.create, "feels right")
        self.assertEqual(len(self.create["pairs"]), 1)

    def test_a_pair_needs_both_paths(self):
        with self.assertRaises(lr.RecordError):
            lr.add_pair(self.create, "ref.png", " ")

    def test_dispose_refuses_a_missing_round_or_finding(self):
        lr.open_round(self.build, "correctness")
        lr.add_finding(self.build, "correctness", "real", "a.py:1", "x")
        with self.assertRaises(lr.RecordError):
            lr.dispose(self.build, "correctness", 2, 1, "fixed")
        with self.assertRaises(lr.RecordError):
            lr.dispose(self.build, "correctness", 1, 2, "fixed")
        with self.assertRaises(lr.RecordError):
            lr.dispose(self.build, "correctness", 1, 1, " ")

    def test_an_older_record_without_the_new_keys_still_loads_and_reports(self):
        rec = lr.new_record("build", "small")
        for key in ("requirements", "not_checked", "pairs", "playtest"):
            del rec[key]
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "old.json")
            Path(path).write_text(json.dumps(rec), encoding="utf-8")
            text = lr.render_report(lr.load(path))
        self.assertIn("No requirements were recorded.", text)

    def test_the_cli_builds_and_prints_a_report(self):
        with tempfile.TemporaryDirectory() as d:
            rec = str(Path(d) / "loop.json")
            run = CliTests.run_cli
            self.assertEqual(run(None, "init", "--record", rec, "--profile", "create", "--size", "medium")[0], 0)
            self.assertEqual(run(None, "requirement", "--record", rec, "--text", "it matches",
                                 "--status", "met", "--evidence", "side by side")[0], 0)
            self.assertEqual(run(None, "pair", "--record", rec, "--reference", "r.png", "--made", "m.png")[0], 0)
            self.assertEqual(run(None, "playtest", "--record", rec, "--text", "plays")[0], 0)
            self.assertEqual(run(None, "not-checked", "--record", rec, "--text", "sound")[0], 0)
            self.assertEqual(run(None, "open-round", "--record", rec, "--pass", "likeness")[0], 0)
            self.assertEqual(run(None, "add", "--record", rec, "--pass", "likeness", "--class", "real",
                                 "--line", "m.png:1", "--text", "wrong hue", "--disposition", "fixed")[0], 0)
            self.assertEqual(run(None, "dispose", "--record", rec, "--pass", "likeness", "--round", "1",
                                 "--finding", "1", "--disposition", "fixed in the repaint")[0], 0)
            rc, out, _ = run(None, "report", "--record", rec)
        self.assertEqual(rc, 0)
        for want in ("1 of 1 requirements met", "→ fixed in the repaint", "- sound",
                     "reference `r.png` · made `m.png`", "- [ ] plays"):
            self.assertIn(want, out)


class SourceTests(unittest.TestCase):
    def test_stdlib_only_and_no_agentm(self):
        text = _SCRIPT.read_text(encoding="utf-8")
        for bad in ("agentm", "harness_memory", "process_seam", "vault"):
            self.assertNotIn(bad, text.lower().replace("no agentm, no vault", ""), bad)


if __name__ == "__main__":
    unittest.main()
