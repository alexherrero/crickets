#!/usr/bin/env python3
"""Tests for the genre filter on the author-time voice overlay.

The overlay store holds both small universal voice rules and heavy
genre-specific conventions — a docs register, an email register, a
letter-of-recommendation register, a design-doc register. Every draft used to
load all of them: ~18k tokens of overlay on a wiki page, two thirds of it
speaking to surfaces that page is not.

A lesson now declares `genres:` to opt INTO being narrow. The asymmetry is the
safety property and most of what these tests pin: absent, empty, or misspelled
means universal, so no lesson written before this feature — and no lesson whose
frontmatter has a typo — can be filtered out of anything. The filter can only
ever drop a lesson that explicitly asked to be narrow.

The second property is that an exclusion is never silent. This overlay has
already shipped one invisible absence; a filter that quietly drops the wrong
lesson would be the same bug wearing a feature's clothes. Held-back lessons come
back in `.excluded` and are named in the composed block.

stdlib only.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL_SCRIPTS = _ROOT / "src" / "wiki" / "skills" / "diataxis-author" / "scripts"


def _load(name: str):
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


sr = _load("style_resolver")
author = _load("author")

BASE = "BASE FLOOR TEXT"


def _lesson(d: Path, name: str, *, trigger: str, guidance: str, genres: str | None = None):
    d.mkdir(parents=True, exist_ok=True)
    fm = [f"trigger: {trigger}"]
    if genres is not None:
        fm.append(f"genres: {genres}")
    (d / name).write_text("---\n" + "\n".join(fm) + "\n---\n" + guidance + "\n",
                          encoding="utf-8")


def _store(vault: Path) -> Path:
    return vault / "desk" / "projects" / "_global" / "wiki-style"


def _build(vault: Path) -> None:
    """One universal lesson and three that opted into a genre."""
    d = _store(vault)
    _lesson(d, "a-universal.md", trigger="cut-hedges", guidance="UNIVERSAL")
    _lesson(d, "b-docs.md", trigger="docs-style", guidance="DOCSONLY", genres="[docs]")
    _lesson(d, "c-comms.md", trigger="comms-style", guidance="COMMSONLY", genres="[comms]")
    _lesson(d, "d-multi.md", trigger="multi", guidance="MULTI", genres="[docs, design]")


def _triggers(resolved) -> set:
    return {lz.trigger for lz in resolved.lessons}


# ── Parsing the declaration ──────────────────────────────────────────────────

class TestGenreParsing(unittest.TestCase):
    def test_bracketed_list(self):
        self.assertEqual(sr._parse_genres("[docs, design]"), frozenset({"docs", "design"}))

    def test_bare_comma_list(self):
        self.assertEqual(sr._parse_genres("docs, design"), frozenset({"docs", "design"}))

    def test_single_value(self):
        self.assertEqual(sr._parse_genres("docs"), frozenset({"docs"}))

    def test_case_and_whitespace_normalized(self):
        self.assertEqual(sr._parse_genres("  [ Docs ,  DESIGN ] "),
                         frozenset({"docs", "design"}))

    def test_absent_or_empty_is_universal(self):
        for raw in (None, "", "   ", "[]", "[ ]"):
            self.assertEqual(sr._parse_genres(raw), frozenset(),
                             f"{raw!r} must parse as universal, not as a genre")


# ── The safety asymmetry ────────────────────────────────────────────────────

class TestUndeclaredIsUniversal(unittest.TestCase):
    """Narrowing is opt-in. Nothing else can be dropped."""

    def test_no_genres_field_applies_to_every_genre(self):
        lz = sr.StyleLesson(scope="global", trigger="t", guidance="g", source="s.md")
        for asked in ({"docs"}, {"design"}, {"comms"}, {"anything-at-all"}):
            self.assertTrue(sr.lesson_applies(lz, asked))

    def test_no_genre_asked_loads_everything(self):
        narrow = sr.StyleLesson(scope="global", trigger="t", guidance="g",
                                source="s.md", genres=frozenset({"comms"}))
        self.assertTrue(sr.lesson_applies(narrow, None))
        self.assertTrue(sr.lesson_applies(narrow, frozenset()))

    def test_a_misspelled_field_name_widens_rather_than_drops(self):
        """`genre:` / `genres :` don't parse -> the lesson stays universal.

        A typo must never make a lesson vanish from every draft. That failure
        would be invisible in exactly the way this overlay has already been
        burned by once.
        """
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            d = _store(vault)
            d.mkdir(parents=True)
            (d / "typo.md").write_text(
                "---\ntrigger: typo\ngenre: [comms]\n---\nSTILL HERE\n", encoding="utf-8")
            r = sr.resolve_style(vault_path=vault, base_text=BASE, genres={"docs"})
            self.assertIn("typo", _triggers(r))
            self.assertEqual(r.excluded, [])


# ── Filtering ────────────────────────────────────────────────────────────────

class TestFiltering(unittest.TestCase):
    def test_unfiltered_default_is_unchanged_behavior(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            r = sr.resolve_style(vault_path=vault, base_text=BASE)
            self.assertEqual(_triggers(r),
                             {"cut-hedges", "docs-style", "comms-style", "multi"})
            self.assertEqual(r.excluded, [])

    def test_docs_keeps_universal_and_docs_drops_comms(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            r = sr.resolve_style(vault_path=vault, base_text=BASE, genres={"docs"})
            self.assertEqual(_triggers(r), {"cut-hedges", "docs-style", "multi"})
            self.assertEqual([t for t, _ in r.excluded], ["comms-style"])

    def test_a_multi_genre_lesson_matches_any_of_its_genres(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            r = sr.resolve_style(vault_path=vault, base_text=BASE, genres={"design"})
            self.assertIn("multi", _triggers(r))
            self.assertEqual(sorted(t for t, _ in r.excluded),
                             ["comms-style", "docs-style"])

    def test_an_unknown_genre_still_keeps_every_universal_lesson(self):
        """The floor never collapses to nothing: ask for a genre no lesson
        declares and the universal ones still come through."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            r = sr.resolve_style(vault_path=vault, base_text=BASE, genres={"no-such-genre"})
            self.assertEqual(_triggers(r), {"cut-hedges"})
            self.assertEqual(r.base_text, BASE)

    def test_base_floor_is_never_filtered(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            for asked in (None, {"docs"}, {"nothing-matches"}):
                r = sr.resolve_style(vault_path=vault, base_text=BASE, genres=asked)
                self.assertEqual(r.base_text, BASE)

    def test_per_repo_scope_is_filtered_too(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "wiki"
            repo.mkdir(parents=True)
            (repo / ".diataxis-conventions.md").write_text(
                "---\ntrigger: repo-rule\ngenres: [comms]\n---\nREPO\n", encoding="utf-8")
            kept = sr.resolve_style(wiki_root=repo, base_text=BASE, genres={"comms"})
            self.assertEqual(_triggers(kept), {"repo-rule"})
            held = sr.resolve_style(wiki_root=repo, base_text=BASE, genres={"docs"})
            self.assertEqual(_triggers(held), set())
            self.assertEqual([t for t, _ in held.excluded], ["repo-rule"])

    def test_narrower_scope_still_wins_before_the_filter_runs(self):
        """Precedence is resolved on the merged trigger, then genres apply — so
        a per-project override of a global lesson is what gets tested for
        applicability, not the global one it replaced."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            base = vault / "desk" / "projects"
            _lesson(base / "_global" / "wiki-style", "g.md",
                    trigger="shared", guidance="GLOBAL", genres="[docs]")
            _lesson(base / "demo" / "wiki-style", "p.md",
                    trigger="shared", guidance="PROJECT", genres="[docs]")
            r = sr.resolve_style(vault_path=vault, project_slug="demo",
                                 base_text=BASE, genres={"docs"})
            self.assertEqual([lz.guidance for lz in r.lessons], ["PROJECT"])


# ── Visibility: an exclusion is never silent ────────────────────────────────

class TestExclusionsAreVisible(unittest.TestCase):
    def test_block_names_what_it_held_back_and_why(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            r = sr.resolve_style(vault_path=vault, base_text=BASE, genres={"docs"})
            block = sr.compose_voice_block(r)
            self.assertIn("NOT LOADED", block)
            self.assertIn("comms-style", block)      # which lesson
            self.assertIn("genres: comms", block)    # what it declares
            self.assertIn("[docs]", block)           # what was asked for

    def test_the_guidance_of_an_excluded_lesson_is_not_in_the_block(self):
        """Naming the exclusion must not re-spend the tokens it saved."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            r = sr.resolve_style(vault_path=vault, base_text=BASE, genres={"docs"})
            self.assertNotIn("COMMSONLY", sr.compose_voice_block(r))

    def test_no_exclusions_means_no_notice(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _build(vault)
            r = sr.resolve_style(vault_path=vault, base_text=BASE)
            self.assertNotIn("NOT LOADED", sr.compose_voice_block(r))


# ── The CLI contract ────────────────────────────────────────────────────────

class TestGenreArgParsing(unittest.TestCase):
    def test_default_is_docs_because_this_command_authors_wiki_pages(self):
        self.assertEqual(author._DEFAULT_GENRE, "docs")
        self.assertEqual(author._parse_genre_arg("docs"), frozenset({"docs"}))

    def test_all_disables_the_filter(self):
        for raw in ("all", "ALL", "  all  ", ""):
            self.assertIsNone(author._parse_genre_arg(raw),
                              f"{raw!r} must disable filtering, not become a genre")

    def test_comma_list(self):
        self.assertEqual(author._parse_genre_arg("docs,design"),
                         frozenset({"docs", "design"}))


if __name__ == "__main__":
    unittest.main()
