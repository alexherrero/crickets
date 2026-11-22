#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/spec_doc.py.

The spec is the anchor every task is graded against, so the helper's job is to
keep that anchor well-formed: render and parse agree, the file lands in the
right place, and a spec with an unverifiable Done-when line or a rule with no
source is refused rather than waved through.

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
_SCRIPT = _ROOT / "src" / "development-lifecycle" / "scripts" / "spec_doc.py"


def _load():
    spec = importlib.util.spec_from_file_location("spec_doc", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["spec_doc"] = m
    spec.loader.exec_module(m)
    return m


sd = _load()


def good_build() -> "sd.Spec":
    return sd.Spec(
        title="Tiered routing",
        profile="build",
        goal="cross-review.sh picks its model by tier.",
        done_when=[
            "`cross-review.sh --tier high` asks agy for Gemini 4 Neon (High) with a 300s timeout",
            "an unknown tier exits 2 before agy is called",
        ],
        rules=[sd.Rule("No Co-Authored-By trailer on commits", "AGENTS.md § Commit messages")],
        not_doing=["Changing the prose pass model"],
        open_questions=[],
    )


def good_create() -> "sd.Spec":
    s = good_build()
    s.profile = "create"
    s.done_when = ["the sprite sheet is 64x64 and uses only colours from `reference/palette.png`"]
    s.reference = "reference/"
    s.likeness = [f"line {i}" for i in range(1, 6)]
    return s


class RoundTripTests(unittest.TestCase):
    def test_render_then_parse_gives_back_the_same_spec(self):
        for make in (good_build, good_create):
            with self.subTest(make=make.__name__):
                spec = make()
                again = sd.parse(sd.render(spec))
                self.assertEqual(again, spec)

    def test_the_rendered_text_has_the_sections_in_order(self):
        text = sd.render(good_create())
        order = [text.index(f"## {h}") for h in (
            "Goal", "Done when", "Rules", "Not doing", "Open questions",
            "Reference", "Likeness list")]
        self.assertEqual(order, sorted(order))
        self.assertTrue(text.startswith("# Spec: Tiered routing\n"))
        self.assertIn("**Profile:** create", text)

    def test_empty_sections_say_none_and_parse_back_empty(self):
        spec = good_build()
        spec.rules, spec.not_doing, spec.open_questions = [], [], []
        text = sd.render(spec)
        self.assertEqual(text.count("\nnone\n"), 3)
        again = sd.parse(text)
        self.assertEqual((again.rules, again.not_doing, again.open_questions), ([], [], []))

    def test_a_missing_section_parses_as_none_not_empty(self):
        spec = good_build()
        spec.not_doing = None
        again = sd.parse(sd.render(spec))
        self.assertIsNone(again.not_doing)

    def test_unknown_sections_survive_a_round_trip(self):
        spec = good_build()
        spec.extra = [("Notes", "keep this")]
        self.assertEqual(sd.parse(sd.render(spec)).extra, [("Notes", "keep this")])

    def test_rule_sources_parse_in_both_spellings(self):
        spec = sd.parse(
            "# Spec: x\n\n**Profile:** build\n\n## Rules\n\n"
            "- Use the dash form — source: AGENTS.md § A\n"
            "- Use the paren form (source: CLAUDE.md)\n"
            "- Has none\n")
        self.assertEqual(spec.rules, [
            sd.Rule("Use the dash form", "AGENTS.md § A"),
            sd.Rule("Use the paren form", "CLAUDE.md"),
            sd.Rule("Has none", ""),
        ])

    def test_a_wrapped_bullet_stays_one_item(self):
        spec = sd.parse("# Spec: x\n\n## Done when\n\n- first line\n  continues here with `x`\n- second\n")
        self.assertEqual(spec.done_when, ["first line continues here with `x`", "second"])


class PlacementTests(unittest.TestCase):
    def test_beside_the_plan(self):
        plan = Path("/v/projects/crickets/tasks/103-loop/plan.md")
        self.assertEqual(sd.place("loop", plan=plan), Path("/v/projects/crickets/tasks/103-loop/spec.md"))

    def test_one_level_up_when_it_covers_several_tasks(self):
        plan = Path("/v/projects/crickets/tasks/103-loop/plan.md")
        self.assertEqual(sd.place("loop", plan=plan, multi=True),
                         Path("/v/projects/crickets/spec-loop.md"))

    def test_multi_without_a_tasks_level_goes_one_directory_up(self):
        plan = Path("/v/projects/crickets/103-loop/plan.md")
        self.assertEqual(sd.place("loop", plan=plan, multi=True),
                         Path("/v/projects/crickets/spec-loop.md"))

    def test_no_vault_falls_to_the_harness_folder(self):
        self.assertEqual(sd.place("loop", project_root=Path("/repo")),
                         Path("/repo/.harness/spec-loop.md"))

    def test_the_plan_file_need_not_exist_and_nothing_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "tasks" / "9-new" / "plan.md"
            where = sd.place("new", plan=plan)
            self.assertEqual(where, plan.parent / "spec.md")
            self.assertFalse(plan.parent.exists())

    def test_refusals(self):
        with self.assertRaises(ValueError):
            sd.place("Bad Slug", project_root=Path("/r"))
        with self.assertRaises(ValueError):
            sd.place("ok")  # no plan, no root
        with self.assertRaises(ValueError):
            sd.place("ok", multi=True, project_root=Path("/r"))  # multi needs a plan


class ShapeTests(unittest.TestCase):
    def problems(self, spec) -> "list[str]":
        return sd.check(spec)

    def test_a_sound_build_spec_and_a_sound_create_spec_have_no_problems(self):
        self.assertEqual(self.problems(good_build()), [])
        self.assertEqual(self.problems(good_create()), [])

    def test_a_rule_without_a_source_fails(self):
        s = good_build()
        s.rules = [sd.Rule("Keep it small", "")]
        out = self.problems(s)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("Rules: "), out)
        self.assertIn("names no source", out[0])

    def test_an_unverifiable_done_when_line_is_flagged(self):
        for vague in ("It works well", "The code is clean and robust", "Handles things properly",
                      "Users find it intuitive"):
            with self.subTest(line=vague):
                s = good_build()
                s.done_when = [vague]
                out = self.problems(s)
                self.assertEqual(len(out), 1, out)
                self.assertIn("cannot be checked", out[0])
                self.assertIn(vague, out[0])

    def test_checkable_done_when_lines_pass(self):
        for line in ("`check-all.sh` exits 0",
                     "the report lists every finding with its disposition",
                     "the sheet is 64x64",
                     "no file under src/ names the old command",
                     "cross-review.sh --tier turbo exits 2"):
            with self.subTest(line=line):
                s = good_build()
                s.done_when = [line]
                self.assertEqual(self.problems(s), [])

    def test_a_vague_word_next_to_a_concrete_check_is_fine(self):
        s = good_build()
        s.done_when = ["`pytest` passes cleanly: 0 failures"]
        self.assertEqual(self.problems(s), [])

    def test_a_missing_or_empty_section_is_named(self):
        cases = {
            "Done when": lambda s: setattr(s, "done_when", None),
            "Rules": lambda s: setattr(s, "rules", None),
            "Not doing": lambda s: setattr(s, "not_doing", None),
            "Open questions": lambda s: setattr(s, "open_questions", None),
            "Goal": lambda s: setattr(s, "goal", "  "),
            "Title": lambda s: setattr(s, "title", ""),
        }
        for name, break_it in cases.items():
            with self.subTest(section=name):
                s = good_build()
                break_it(s)
                out = self.problems(s)
                self.assertEqual(len(out), 1, out)
                self.assertTrue(out[0].startswith(f"{name}: "), out)

    def test_done_when_with_no_lines_fails(self):
        s = good_build()
        s.done_when = []
        self.assertIn("has no lines", self.problems(s)[0])

    def test_open_questions_lists_blocking_questions_only(self):
        s = good_build()
        s.open_questions = ["Should the ceiling be 80 KB?", "Remember to tidy the wiki"]
        out = self.problems(s)
        self.assertEqual(len(out), 1, out)
        self.assertIn("Remember to tidy the wiki", out[0])
        self.assertIn("not a question", out[0])

    def test_none_counts_as_an_answer_for_not_doing_and_open_questions(self):
        s = good_build()
        s.not_doing, s.open_questions = [], []
        self.assertEqual(self.problems(s), [])

    def test_an_unknown_profile_fails(self):
        s = good_build()
        s.profile = "paint"
        self.assertIn("not one of build, create, both", self.problems(s)[0])

    def test_a_create_spec_needs_a_reference_and_five_to_ten_likeness_lines(self):
        s = good_create()
        s.reference = None
        self.assertTrue(any(p.startswith("Reference: ") for p in self.problems(s)))
        for n, ok in ((4, False), (5, True), (10, True), (11, False)):
            with self.subTest(lines=n):
                s = good_create()
                s.likeness = [f"l{i}" for i in range(n)]
                self.assertEqual(self.problems(s) == [], ok, self.problems(s))
        s = good_create()
        s.likeness = None
        self.assertTrue(any(p.startswith("Likeness list: ") for p in self.problems(s)))

    def test_a_build_spec_does_not_need_a_reference(self):
        s = good_build()
        self.assertIsNone(s.reference)
        self.assertEqual(self.problems(s), [])

    def test_both_profile_needs_the_create_sections_too(self):
        s = good_build()
        s.profile = "both"
        self.assertEqual(len(self.problems(s)), 2)

    def test_the_whole_text_path_flags_a_hand_written_spec(self):
        text = ("# Spec: Thing\n\n**Profile:** build\n\n## Goal\n\nDo it.\n\n"
                "## Done when\n\n- It is good\n\n## Rules\n\n- Be nice\n\n"
                "## Not doing\n\nnone\n\n## Open questions\n\nnone\n")
        out = sd.check(sd.parse(text))
        self.assertEqual(len(out), 2, out)
        self.assertTrue(out[0].startswith("Done when: "))
        self.assertTrue(out[1].startswith("Rules: "))


class CopyTests(unittest.TestCase):
    """code-review's review_material.py parses a spec's Rules with this module,
    and a cross-plugin import cannot work at runtime, so code-review ships a copy.
    development-lifecycle's is the original; the copy must not drift."""

    def test_code_review_ships_a_byte_identical_copy(self):
        copy = _ROOT / "src" / "code-review" / "scripts" / "spec_doc.py"
        self.assertTrue(copy.is_file(), "code-review ships no spec_doc.py")
        self.assertEqual(copy.read_bytes(), _SCRIPT.read_bytes(),
                         "code-review's spec_doc.py drifted from development-lifecycle's")

    def test_no_other_plugin_ships_one(self):
        found = sorted(p.parent.parent.name for p in (_ROOT / "src").glob("*/scripts/spec_doc.py"))
        self.assertEqual(found, ["code-review", "development-lifecycle"])


class CliTests(unittest.TestCase):
    def run_cli(self, *argv, stdin: str = ""):
        out, err = io.StringIO(), io.StringIO()
        saved = sys.stdin
        sys.stdin = io.StringIO(stdin)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = sd.main(list(argv))
        finally:
            sys.stdin = saved
        return code, out.getvalue(), err.getvalue()

    def test_place_prints_the_path(self):
        code, out, _ = self.run_cli("place", "--slug", "loop", "--plan", "/p/tasks/1-x/plan.md")
        self.assertEqual((code, out.strip()), (0, "/p/tasks/1-x/spec.md"))

    def test_place_error_is_exit_2(self):
        code, out, err = self.run_cli("place", "--slug", "loop")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("--project-root", err)

    def test_check_exits_1_with_problems_and_0_without(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.md"
            good.write_text(sd.render(good_build()), encoding="utf-8")
            self.assertEqual(self.run_cli("check", str(good))[0], 0)
            bad = Path(tmp) / "bad.md"
            s = good_build()
            s.rules = [sd.Rule("x", "")]
            bad.write_text(sd.render(s), encoding="utf-8")
            code, out, _ = self.run_cli("check", str(bad))
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("Rules: "))

    def test_check_of_a_missing_file_is_exit_2(self):
        self.assertEqual(self.run_cli("check", "/no/such/spec.md")[0], 2)

    def test_render_from_json_on_stdin(self):
        data = {"title": "T", "profile": "build", "goal": "G",
                "done_when": ["`x` exits 0"], "rules": [{"text": "R", "source": "S"}],
                "not_doing": [], "open_questions": []}
        code, out, _ = self.run_cli("render", stdin=json.dumps(data))
        self.assertEqual(code, 0)
        self.assertEqual(sd.check(sd.parse(out)), [])
        self.assertIn("- R — source: S", out)

    def test_runs_as_a_script_with_no_agentm_on_the_path(self):
        # The portability promise: no agentm, no vault, no extra imports.
        proc = subprocess.run(
            [sys.executable, "-I", str(_SCRIPT), "place", "--slug", "x", "--project-root", "/r"],
            capture_output=True, text=True, timeout=20)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, str(Path("/r/.harness/spec-x.md"))))

    def test_the_script_imports_nothing_from_agentm(self):
        text = _SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("agentm_bridge", text)
        self.assertNotIn("import harness_memory", text)
        self.assertNotIn("process_seam", text)


if __name__ == "__main__":
    unittest.main()
