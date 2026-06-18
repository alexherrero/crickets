#!/usr/bin/env python3
"""Tests for the diataxis-author edit-driven voice-lesson capture
(src/wiki-maintenance/skills/diataxis-author/scripts/capture.py +
agentmemory_conventions.confirm_save_lesson) — crickets ④ wiki-maintenance
part 3/5, task 3.

Deterministic-only (DC-7): the diff -> cluster bucketing, the scope write-path
(round-tripping with the resolver), the not-_always-load guarantee, the
never-auto-commit gate, and the DC-3 degraded-write surface. The LLM-judgment
parts (generalization = gate 1, scope recommendation = gate 2 via the
style-scope-evaluator sub-agent) are operator-gated and not unit-tested.
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
_SKILL = _ROOT / "src" / "wiki-maintenance" / "skills" / "diataxis-author"
_SKILL_SCRIPTS = _SKILL / "scripts"


def _load(name: str):
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


cap = _load("capture")
amc = _load("agentmemory_conventions")
sr = _load("style_resolver")

_STAMP = "2026-06-05"

# A fixture draft/edited pair engineered (stable ANCHOR lines isolate each edit)
# to exercise all five clustering kinds with one change apiece.
_DRAFT = "\n".join([
    "# Doc",
    "This is a very seamless feature.",
    "ANCHOR-A",
    "We support many options here today.",
    "ANCHOR-B",
    "This sentence is pure slop and must go.",
    "ANCHOR-C",
    "## Old Heading",
    "ANCHOR-D",
    "Final stable line.",
])
_EDITED = "\n".join([
    "# Doc",
    "This is a clean feature.",
    "ANCHOR-A",
    "We support options. Many of them.",
    "ANCHOR-B",
    "ANCHOR-C",
    "## New Heading",
    "ANCHOR-D",
    "A freshly added explanatory sentence.",
    "Final stable line.",
])


class TestClusterBucketing(unittest.TestCase):
    def setUp(self):
        self.buckets = cap.cluster_changes(cap.diff_changes(_DRAFT, _EDITED))

    def _texts(self, kind, side):
        return " ".join(getattr(c, side) for c in self.buckets.get(kind, []))

    def test_all_five_kinds_present(self):
        self.assertEqual(set(self.buckets), set(cap.KINDS),
                         f"expected all 5 kinds, got {sorted(self.buckets)}")

    def test_word_choice_is_the_wording_swap(self):
        self.assertIn("seamless", self._texts("word-choice", "before"))
        self.assertIn("clean", self._texts("word-choice", "after"))

    def test_rhythm_is_the_sentence_reshape(self):
        # one sentence -> two: a cadence change, not a word swap.
        self.assertIn("many options here today", self._texts("rhythm", "before"))
        self.assertIn("Many of them", self._texts("rhythm", "after"))

    def test_cuts_is_the_removed_prose_line(self):
        self.assertIn("slop", self._texts("cuts", "before"))
        self.assertEqual("", self._texts("cuts", "after").strip())

    def test_structure_is_the_heading_change(self):
        self.assertIn("Heading", self._texts("structure", "before"))

    def test_additions_is_the_inserted_prose_line(self):
        self.assertIn("freshly added", self._texts("additions", "after"))
        self.assertEqual("", self._texts("additions", "before").strip())

    def test_unchanged_text_yields_no_changes(self):
        self.assertEqual(cap.diff_changes(_DRAFT, _DRAFT), [])

    def test_inline_emphasis_in_parenthetical_is_word_choice_not_rhythm(self):
        # Guards the deliberately-simple _SENTENCE_END_RE: a mid-clause edit that
        # puts terminal punctuation before a closing bracket/quote (`(it works!)`)
        # must NOT be miscounted as a sentence end and flipped to rhythm. (A prior
        # widening to catch `"done."`-style ends regressed exactly this.)
        buckets = cap.cluster_changes(cap.diff_changes(
            "anchor\nUse the helper (it works) for this.",
            "anchor\nUse the helper (it works!) for this."))
        self.assertIn("word-choice", buckets)
        self.assertNotIn("rhythm", buckets)

    def test_list_item_insert_clusters_as_structure_not_additions(self):
        buckets = cap.cluster_changes(cap.diff_changes("# T\nkeep", "# T\nkeep\n- new item"))
        self.assertIn("structure", buckets)
        self.assertNotIn("additions", buckets)


class TestProposeLessons(unittest.TestCase):
    def test_one_proposal_per_bucket_in_canonical_order(self):
        buckets = cap.cluster_changes(cap.diff_changes(_DRAFT, _EDITED))
        proposals = cap.propose_lessons(buckets)
        kinds = [p.cluster_kind for p in proposals]
        self.assertEqual(kinds, [k for k in cap.KINDS if k in buckets])
        # trigger defaults to the kind; guidance is the non-empty template scaffold.
        for p in proposals:
            self.assertEqual(p.trigger, p.cluster_kind)
            self.assertTrue(p.guidance.strip())


class TestWritePathRoundTrip(unittest.TestCase):
    def test_global_writes_to_on_demand_store_and_round_trips(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            written = amc.confirm_save_lesson(
                "peacock-words", "In any page, cut peacock words like 'seamless'.",
                "global", vault_path=vault, mode="silent", datestamp=_STAMP)
            self.assertIsNotNone(written)
            self.assertTrue(written.is_file())
            # Correct on-demand store, NOT _always-load.
            self.assertEqual(
                written,
                vault / "projects" / "_global" / "wiki-style"
                / f"{_STAMP}-peacock-words.md")
            self.assertNotIn("_always-load", str(written))
            self.assertFalse((vault / "personal" / "_always-load").exists())
            # Round-trips through the resolver's reader.
            lessons = sr.read_scope_lessons(written.parent, "global")
            self.assertEqual([lz.trigger for lz in lessons], ["peacock-words"])
            self.assertIn("cut peacock words", lessons[0].guidance)

    def test_trigger_with_newline_is_sanitized_no_frontmatter_injection(self):
        # A trigger carrying a newline + a forged `key: value` must NOT inject a
        # frontmatter key the resolver would honor; it canonicalizes to a slug
        # that round-trips exactly (regression for the raw-interpolation defect).
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            written = amc.confirm_save_lesson(
                "x\ninjected: PWNED", "Body guidance.", "global",
                vault_path=vault, mode="silent", datestamp=_STAMP)
            fm, _ = sr._split_frontmatter(written.read_text(encoding="utf-8"))
            self.assertNotIn("injected", fm)
            self.assertEqual(set(fm), {"trigger", "scope", "updated", "source"})
            lessons = sr.read_scope_lessons(written.parent, "global")
            self.assertEqual([lz.trigger for lz in lessons], ["x-injected-pwned"])

    def test_per_project_needs_slug(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            # No slug -> nothing written.
            self.assertIsNone(amc.confirm_save_lesson(
                "t", "g", "per-project", vault_path=vault, mode="silent", datestamp=_STAMP))
            # With slug -> writes under projects/<slug>/wiki-style/ and round-trips.
            written = amc.confirm_save_lesson(
                "domain-term", "Prefer 'plugin' over 'extension' in this project.",
                "per-project", vault_path=vault, project_slug="crickets",
                mode="silent", datestamp=_STAMP)
            self.assertEqual(
                written,
                vault / "projects" / "crickets" / "wiki-style"
                / f"{_STAMP}-domain-term.md")
            resolved = sr.resolve_style(
                vault_path=vault, project_slug="crickets", base_text="")
            self.assertIn("domain-term", [lz.trigger for lz in resolved.lessons])

    def test_per_repo_writes_single_file_and_surfaces_degraded_mode(self):
        with tempfile.TemporaryDirectory() as td:
            wiki_root = Path(td)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                written = amc.confirm_save_lesson(
                    "active-voice", "Prefer active voice throughout this repo's wiki.",
                    "per-repo", wiki_root=wiki_root, mode="silent", datestamp=_STAMP)
            self.assertEqual(written, wiki_root / ".diataxis-conventions.md")
            # DC-3: per-repo lands OUTSIDE the vault; the agentm kernel is absent in
            # crickets, so the cross-boundary write must announce its degraded mode.
            self.assertIn("permeable_boundary unavailable", err.getvalue())
            # Round-trips as the single per-repo lesson.
            lessons = sr._read_per_repo_lessons(wiki_root)
            self.assertEqual(len(lessons), 1)
            self.assertEqual(lessons[0].trigger, "active-voice")
            self.assertIn("active voice", lessons[0].guidance)

    def test_per_repo_merge_preserves_existing_conventions(self):
        with tempfile.TemporaryDirectory() as td:
            wiki_root = Path(td)
            conv = wiki_root / ".diataxis-conventions.md"
            conv.write_text(
                "# Diataxis conventions\n\nFilename style: CamelCase-With-Dashes\n",
                encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                amc.confirm_save_lesson(
                    "active-voice", "Prefer active voice.", "per-repo",
                    wiki_root=wiki_root, mode="silent", datestamp=_STAMP)
            text = conv.read_text(encoding="utf-8")
            # Existing key:value convention survives; new guidance appended.
            self.assertIn("Filename style: CamelCase-With-Dashes", text)
            self.assertIn("Prefer active voice", text)
            # load_conventions still reads the preserved key:value line.
            self.assertEqual(
                amc.load_conventions(wiki_root=wiki_root)["filename_style"],
                "CamelCase-With-Dashes")


class TestNeverAutoCommit(unittest.TestCase):
    def test_auto_mode_non_tty_denies_write(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            with contextlib.redirect_stderr(io.StringIO()):
                written = amc.confirm_save_lesson(
                    "t", "g", "global", vault_path=vault,
                    mode="auto", stdin=io.StringIO(""), datestamp=_STAMP)
            self.assertIsNone(written)
            # Denied write created nothing under the (now top-level) projects root.
            self.assertFalse((vault / "projects").exists())

    def test_interactive_non_tty_defaults_to_deny(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            with contextlib.redirect_stderr(io.StringIO()):
                written = amc.confirm_save_lesson(
                    "t", "g", "global", vault_path=vault,
                    mode="interactive", stdin=io.StringIO("y\n"), datestamp=_STAMP)
            # StringIO is not a TTY -> interactive defaults to deny (no surprise saves).
            self.assertIsNone(written)

    def test_propose_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "draft.md").write_text(_DRAFT, encoding="utf-8")
            (d / "edited.md").write_text(_EDITED, encoding="utf-8")
            before = sorted(p.name for p in d.iterdir())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cap.main(["propose", "--draft", str(d / "draft.md"),
                               "--edited", str(d / "edited.md")])
            self.assertEqual(rc, 0)
            self.assertEqual(sorted(p.name for p in d.iterdir()), before)
            self.assertIn("proposals", buf.getvalue())

    def test_unknown_scope_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertIsNone(amc.confirm_save_lesson(
                    "t", "g", "everywhere", vault_path=Path(td),
                    mode="silent", datestamp=_STAMP))


if __name__ == "__main__":
    unittest.main()
