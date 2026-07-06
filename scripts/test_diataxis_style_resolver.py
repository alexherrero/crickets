#!/usr/bin/env python3
"""Tests for the diataxis-author author-time voice resolver
(src/wiki-maintenance/skills/diataxis-author/scripts/style_resolver.py +
author.py integration) — crickets ④ wiki-maintenance part 3/5, task 1.

Deterministic-only (DC-7): the resolver compose + scope precedence + the
graceful base-floor fallback + the page-injection structure. The LLM-judgment
parts of the learning loop (generalization, scope recommendation) are
operator-gated and not unit-tested here.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SKILL = _ROOT / "src" / "wiki" / "skills" / "diataxis-author"
_SKILL_SCRIPTS = _SKILL / "scripts"
_BASE_STYLE_GUIDE = _SKILL / "style" / "base-style-guide.md"


def _load(name: str):
    # The skill scripts import each other by bare name (they insert their own
    # dir on sys.path at import); make that dir importable for this test too.
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


sr = _load("style_resolver")
author = _load("author")


def _lesson_file(d: Path, name: str, *, trigger: str | None, guidance: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    fm = f"---\ntrigger: {trigger}\n---\n" if trigger else ""
    (d / name).write_text(fm + guidance + "\n", encoding="utf-8")


# ── The committed base floor ─────────────────────────────────────────────────

class TestBaseStyleGuide(unittest.TestCase):
    def test_base_ships_committed_and_nonempty(self):
        self.assertTrue(_BASE_STYLE_GUIDE.is_file(),
                        f"base style-guide must ship committed at {_BASE_STYLE_GUIDE}")
        text = _BASE_STYLE_GUIDE.read_text(encoding="utf-8")
        self.assertTrue(text.strip())
        # A couple of load-bearing house-voice rules are present.
        self.assertIn("Second person", text)
        self.assertIn("Peacock words", text)

    def test_loader_reads_the_committed_base(self):
        self.assertIn("Second person", sr.load_base_style_guide())


# ── Resolver: compose + precedence ───────────────────────────────────────────

class TestResolvePrecedence(unittest.TestCase):
    def test_base_only_when_no_vault_no_repo(self):
        r = sr.resolve_style(wiki_root=None, vault_path=None, project_slug=None)
        self.assertEqual(r.lessons, [])
        self.assertIn("Second person", r.base_text)  # committed floor present
        self.assertEqual(r.provenance, [])

    def test_distinct_triggers_accumulate(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            _lesson_file(vault / "projects" / "_global" / "wiki-style",
                         "a.md", trigger="word-choice", guidance="prefer plain verbs")
            repo = Path(td) / "repo" / "wiki"
            repo.mkdir(parents=True)
            (repo / ".diataxis-conventions.md").write_text(
                "---\ntrigger: headings\n---\nsentence case headings\n", encoding="utf-8")
            r = sr.resolve_style(wiki_root=repo, vault_path=vault, project_slug=None)
            triggers = {l.trigger for l in r.lessons}
            self.assertEqual(triggers, {"word-choice", "headings"})

    def test_repo_overrides_project_overrides_global(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            pp = vault / "projects"
            _lesson_file(pp / "_global" / "wiki-style", "g.md",
                         trigger="headings", guidance="GLOBAL guidance")
            _lesson_file(pp / "demo" / "wiki-style", "p.md",
                         trigger="headings", guidance="PROJECT guidance")
            repo = Path(td) / "repo" / "wiki"
            repo.mkdir(parents=True)
            (repo / ".diataxis-conventions.md").write_text(
                "---\ntrigger: headings\n---\nREPO guidance\n", encoding="utf-8")
            r = sr.resolve_style(wiki_root=repo, vault_path=vault, project_slug="demo")
            by_trigger = {l.trigger: l for l in r.lessons}
            self.assertEqual(by_trigger["headings"].guidance, "REPO guidance")
            self.assertEqual(by_trigger["headings"].scope, "per-repo")
            # global + project both contributed to provenance even though repo won
            self.assertEqual(r.provenance, ["global:g.md", "per-project:p.md", "per-repo:.diataxis-conventions.md"])

    def test_project_overrides_global_when_no_repo(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            pp = vault / "projects"
            _lesson_file(pp / "_global" / "wiki-style", "g.md",
                         trigger="rhythm", guidance="GLOBAL")
            _lesson_file(pp / "demo" / "wiki-style", "p.md",
                         trigger="rhythm", guidance="PROJECT")
            r = sr.resolve_style(wiki_root=None, vault_path=vault, project_slug="demo")
            by_trigger = {l.trigger: l for l in r.lessons}
            self.assertEqual(by_trigger["rhythm"].guidance, "PROJECT")
            self.assertEqual(by_trigger["rhythm"].scope, "per-project")

    def test_per_project_skipped_without_slug(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            pp = vault / "projects"
            _lesson_file(pp / "demo" / "wiki-style", "p.md",
                         trigger="x", guidance="PROJECT")
            r = sr.resolve_style(wiki_root=None, vault_path=vault, project_slug=None)
            self.assertEqual(r.lessons, [])  # no slug → per-project scope not read

    def test_recent_wins_within_scope(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            gdir = vault / "projects" / "_global" / "wiki-style"
            _lesson_file(gdir, "01-x.md", trigger="cuts", guidance="OLD")
            _lesson_file(gdir, "02-x.md", trigger="cuts", guidance="NEW")
            r = sr.resolve_style(wiki_root=None, vault_path=vault, project_slug=None)
            by_trigger = {l.trigger: l for l in r.lessons}
            self.assertEqual(by_trigger["cuts"].guidance, "NEW")  # later-sorted wins

    def test_trigger_defaults_to_filename_stem(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            gdir = vault / "projects" / "_global" / "wiki-style"
            _lesson_file(gdir, "no-fm.md", trigger=None, guidance="bare guidance")
            r = sr.resolve_style(wiki_root=None, vault_path=vault, project_slug=None)
            self.assertEqual(r.lessons[0].trigger, "no-fm")
            self.assertEqual(r.lessons[0].guidance, "bare guidance")

    def test_missing_scope_dirs_graceful(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"  # nothing created under it
            r = sr.resolve_style(wiki_root=Path(td) / "nope", vault_path=vault, project_slug="x")
            self.assertEqual(r.lessons, [])
            self.assertIn("Second person", r.base_text)


# ── Page composition ─────────────────────────────────────────────────────────

class TestPageComposition(unittest.TestCase):
    def test_voice_block_contains_base_and_lessons(self):
        r = sr.ResolvedStyle(
            base_text="HOUSE FLOOR TEXT",
            lessons=[sr.StyleLesson(scope="global", trigger="t1", guidance="g1", source="a.md")],
            provenance=["global:a.md"],
        )
        block = sr.compose_voice_block(r)
        self.assertIn("HOUSE FLOOR TEXT", block)
        self.assertIn("[global] t1: g1", block)
        self.assertTrue(block.startswith("<!--"))
        self.assertTrue(block.rstrip().endswith("-->"))

    def test_voice_block_sanitizes_stray_comment_closer(self):
        r = sr.ResolvedStyle(
            base_text="ends with --> here",
            lessons=[sr.StyleLesson(scope="global", trigger="t", guidance="also --> embedded", source="a.md")],
            provenance=[],
        )
        block = sr.compose_voice_block(r)
        # exactly one real comment-closer: the block's own terminator
        self.assertEqual(block.count("-->"), 1)
        self.assertTrue(block.rstrip().endswith("-->"))

    def test_apply_injects_after_h1_preserving_structure(self):
        template = "# How to do X\n\n<!-- mode scaffold -->\n\nBody paragraph.\n"
        r = sr.resolve_style(wiki_root=None, vault_path=None)  # base floor only
        out = sr.apply_style_to_page(template, r)
        lines = out.splitlines()
        self.assertEqual(lines[0], "# How to do X")          # H1 still first
        self.assertIn("house style", out)                    # voice block injected
        self.assertIn("<!-- mode scaffold -->", out)         # template body intact
        self.assertIn("Body paragraph.", out)

    def test_apply_prepends_when_no_h1(self):
        template = "no heading here\njust text\n"
        r = sr.resolve_style(wiki_root=None, vault_path=None)
        out = sr.apply_style_to_page(template, r)
        self.assertTrue(out.lstrip().startswith("<!--"))
        self.assertIn("no heading here", out)


# ── author.py integration ────────────────────────────────────────────────────

class TestAuthorPageIntegration(unittest.TestCase):
    def _wiki(self, td: Path) -> Path:
        w = td / "wiki"
        w.mkdir(parents=True)
        return w

    def test_authored_page_is_not_template_verbatim(self):
        with tempfile.TemporaryDirectory() as td:
            w = self._wiki(Path(td))
            res = author.author_page("Install Foo", "how-to", wiki_root=w, vault_path=None)
            self.assertTrue(res["style_composed"])
            written = Path(res["target"]).read_text(encoding="utf-8")
            template = (_SKILL / "templates" / "how-to.md").read_text(encoding="utf-8")
            self.assertNotEqual(written, template)        # not verbatim
            self.assertIn("BASE VOICE (committed floor)", written)  # base floor injected
            self.assertTrue(written.splitlines()[0].startswith("# "))  # H1 preserved

    def test_authored_page_includes_vault_overlay(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            w = self._wiki(tdp)
            vault = tdp / "vault"
            gdir = vault / "projects" / "_global" / "wiki-style"
            _lesson_file(gdir, "lesson.md", trigger="voice",
                         guidance="OVERLAY-LESSON-MARKER")
            res = author.author_page("Install Bar", "how-to", wiki_root=w,
                                     vault_path=vault, project_slug=None)
            written = Path(res["target"]).read_text(encoding="utf-8")
            self.assertIn("OVERLAY-LESSON-MARKER", written)
            self.assertIn("global:lesson.md", res["style_scopes"])


if __name__ == "__main__":
    unittest.main()
