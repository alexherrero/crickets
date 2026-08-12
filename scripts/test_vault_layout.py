#!/usr/bin/env python3
"""Tests for the vault project-space probe chain — the regression net for the
silent overlay miss the stage-2 four-space migration caused (2026-08-11).

The migration moved the vault's project-keyed space from `<vault>/projects/`
down to `<vault>/desk/projects/`. Every crickets surface that resolved the
operator's learned voice overlays kept the old literal, `read_scope_lessons`
reported the missing directory as "no lessons yet", and nine real voice
lessons went silently absent from every authored draft. Nothing errored.

So these tests pin, for each surface, that BOTH layouts resolve — and that the
write side lands where the read side looks, on either one. Every expected value
here is hand-written: a literal relative path, a literal lesson body. None is
computed by calling the code under test, because a check that derives its
expectation from the implementation's own formula only proves they agree.

Four surfaces, four plugin groups (the probe chain is duplicated per group —
plugins emit independently into dist/, so they cannot share an import):

  * wiki       — vault_layout.py, used by style_resolver / rule_pack /
                 agentmemory_conventions / relocate
  * design     — prose_pass.wiki_style_dir
  * dev-lifecycle — resolve_project.vault_projects_dir

stdlib only.
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
_SKILL = _ROOT / "src" / "wiki" / "skills" / "diataxis-author"
_SKILL_SCRIPTS = _SKILL / "scripts"


def _load_skill(name: str):
    """Load one diataxis-author script; they import each other by bare name."""
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, _SKILL_SCRIPTS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _load_file(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m


vl = _load_skill("vault_layout")
sr = _load_skill("style_resolver")
rp_pack = _load_skill("rule_pack")
conv = _load_skill("agentmemory_conventions")
relocate = _load_skill("relocate")
prose_pass = _load_file("prose_pass_for_layout",
                        _ROOT / "src" / "design" / "scripts" / "prose_pass.py")
resolve_project = _load_file("resolve_project_for_layout",
                             _ROOT / "src" / "development-lifecycle" / "scripts" / "resolve_project.py")


# The two layouts under test, written out by hand rather than read from the
# module — if someone reorders PROJECT_SPACE_SEGMENTS these tests must notice.
NEW_LAYOUT = "desk/projects"
OLD_LAYOUT = "projects"
OLDEST_LAYOUT = "personal-projects"


def _write_lesson(d: Path, name: str, *, trigger: str, guidance: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(f"---\ntrigger: {trigger}\n---\n{guidance}\n", encoding="utf-8")


def _rel(p: Path, vault: Path) -> str:
    return p.relative_to(vault).as_posix()


# ── The probe chain itself ───────────────────────────────────────────────────

class TestProbeChain(unittest.TestCase):
    def test_new_layout_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "desk" / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(vl.global_wiki_style_dir(vault), vault),
                             "desk/projects/_global/wiki-style")

    def test_old_layout_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(vl.global_wiki_style_dir(vault), vault),
                             "projects/_global/wiki-style")

    def test_oldest_layout_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "personal-projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(vl.global_wiki_style_dir(vault), vault),
                             "personal-projects/_global/wiki-style")

    def test_empty_vault_defaults_to_current_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)  # nothing created
            self.assertEqual(_rel(vl.global_wiki_style_dir(vault), vault),
                             "desk/projects/_global/wiki-style")

    def test_newest_wins_when_several_layouts_carry_the_store(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "desk" / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(vl.global_wiki_style_dir(vault), vault),
                             "desk/projects/_global/wiki-style")

    def test_probes_the_leaf_not_just_the_projects_root(self):
        """A half-migrated vault: the new root exists but the store is still
        in the old one. Probing only the root would resolve to the new, empty
        rung — the exact silent miss. The leaf probe finds the lessons."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "desk" / "projects" / "some-other-project").mkdir(parents=True)
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(vl.global_wiki_style_dir(vault), vault),
                             "projects/_global/wiki-style")

    def test_per_project_store_probes_the_same_chain(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "projects" / "crickets" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(vl.project_wiki_style_dir(vault, "crickets"), vault),
                             "projects/crickets/wiki-style")

    def test_if_present_returns_none_when_absent_everywhere(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(vl.global_wiki_style_dir_if_present(Path(td)))

    def test_if_present_returns_an_empty_but_existing_store(self):
        """An empty store is a legitimate state, not an absence."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "desk" / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            found = vl.global_wiki_style_dir_if_present(vault)
            self.assertIsNotNone(found)
            self.assertEqual(_rel(found, vault), "desk/projects/_global/wiki-style")


# ── The read path, both layouts ──────────────────────────────────────────────

class TestResolveStyleAcrossLayouts(unittest.TestCase):
    """The bug, pinned. Same lessons, same expected output, either layout."""

    def _build(self, vault: Path, layout: str) -> None:
        gdir = vault.joinpath(*layout.split("/"), "_global", "wiki-style")
        _write_lesson(gdir, "2026-06-07-user-facing-prose.md",
                      trigger="user-facing-prose",
                      guidance="Second person. Say what the reader does.")
        _write_lesson(gdir, "2026-07-05-warm-complete-sentences.md",
                      trigger="warm-complete-sentences",
                      guidance="Complete sentences with real predicates.")
        pdir = vault.joinpath(*layout.split("/"), "crickets", "wiki-style")
        _write_lesson(pdir, "2026-07-01-plugin-vocab.md",
                      trigger="plugin-vocab",
                      guidance="Say plugin, never extension.")

    def _assert_lessons(self, resolved) -> None:
        by_trigger = {lz.trigger: lz for lz in resolved.lessons}
        self.assertEqual(
            sorted(by_trigger),
            ["plugin-vocab", "user-facing-prose", "warm-complete-sentences"],
        )
        self.assertEqual(by_trigger["user-facing-prose"].guidance,
                         "Second person. Say what the reader does.")
        self.assertEqual(by_trigger["user-facing-prose"].scope, "global")
        self.assertEqual(by_trigger["warm-complete-sentences"].guidance,
                         "Complete sentences with real predicates.")
        self.assertEqual(by_trigger["plugin-vocab"].guidance,
                         "Say plugin, never extension.")
        self.assertEqual(by_trigger["plugin-vocab"].scope, "per-project")
        self.assertEqual(
            resolved.provenance,
            ["global:2026-06-07-user-facing-prose.md",
             "global:2026-07-05-warm-complete-sentences.md",
             "per-project:2026-07-01-plugin-vocab.md"],
        )

    def test_new_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            self._build(vault, NEW_LAYOUT)
            self._assert_lessons(sr.resolve_style(
                wiki_root=None, vault_path=vault, project_slug="crickets"))

    def test_old_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            self._build(vault, OLD_LAYOUT)
            self._assert_lessons(sr.resolve_style(
                wiki_root=None, vault_path=vault, project_slug="crickets"))


# ── The guard: absent-everywhere is loud, empty-but-present is silent ────────

class TestNoOverlayStoreGuard(unittest.TestCase):
    def _stderr_of_resolve(self, vault: Path) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            sr.resolve_style(wiki_root=None, vault_path=vault, project_slug=None)
        return buf.getvalue()

    def test_absent_on_every_layout_says_so(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            err = self._stderr_of_resolve(vault)
            self.assertIn("no voice-overlay store", err)
            self.assertIn("committed base style guide alone", err)
            self.assertIn(str(vault), err)

    def test_present_but_empty_stays_silent(self):
        """A store with no lessons in it is an operator who has captured none
        yet — legitimate. Warning there would train the operator to ignore it."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            (vault / "desk" / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(self._stderr_of_resolve(vault), "")

    def test_populated_old_layout_stays_silent(self):
        """The pre-fix state must NOT warn once the probe finds the lessons."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            gdir = vault / "projects" / "_global" / "wiki-style"
            _write_lesson(gdir, "a.md", trigger="x", guidance="y")
            self.assertEqual(self._stderr_of_resolve(vault), "")

    def test_no_vault_stays_silent(self):
        """No vault at all is the documented base-floor-only mode, not a miss."""
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            sr.resolve_style(wiki_root=None, vault_path=None, project_slug=None)
        self.assertEqual(buf.getvalue(), "")


# ── Write paths land where the read path looks ───────────────────────────────

class TestWritePathsAgreeWithReadPath(unittest.TestCase):
    def test_capture_targets_the_new_layout_on_a_migrated_vault(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            (vault / "desk" / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            target, outside = conv.lesson_target(
                "global", vault_path=vault, project_slug=None, wiki_root=None,
                trigger="Warm Complete Sentences", datestamp="2026-08-11")
            self.assertFalse(outside)
            self.assertEqual(
                _rel(target, vault),
                "desk/projects/_global/wiki-style/2026-08-11-warm-complete-sentences.md")

    def test_capture_targets_the_old_layout_on_an_unmigrated_vault(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            target, _ = conv.lesson_target(
                "global", vault_path=vault, project_slug=None, wiki_root=None,
                trigger="tone", datestamp="2026-08-11")
            self.assertEqual(_rel(target, vault),
                             "projects/_global/wiki-style/2026-08-11-tone.md")

    def test_capture_per_project_follows_the_same_chain(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            (vault / "projects" / "crickets" / "wiki-style").mkdir(parents=True)
            target, _ = conv.lesson_target(
                "per-project", vault_path=vault, project_slug="crickets",
                wiki_root=None, trigger="vocab", datestamp="2026-08-11")
            self.assertEqual(_rel(target, vault),
                             "projects/crickets/wiki-style/2026-08-11-vocab.md")

    def test_a_captured_lesson_reads_back(self):
        """The round trip the fork would have broken: write via the capture
        target, read via the resolver, on a vault whose store is on the OLD
        rung while the new root already exists."""
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            (vault / "desk" / "projects" / "unrelated").mkdir(parents=True)
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            target, _ = conv.lesson_target(
                "global", vault_path=vault, project_slug=None, wiki_root=None,
                trigger="hedging", datestamp="2026-08-11")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("---\ntrigger: hedging\n---\nCut the hedges.\n",
                              encoding="utf-8")
            resolved = sr.resolve_style(wiki_root=None, vault_path=vault, project_slug=None)
            self.assertEqual([lz.trigger for lz in resolved.lessons], ["hedging"])
            self.assertEqual(resolved.lessons[0].guidance, "Cut the hedges.")

    def test_relocate_destination_follows_the_chain(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(relocate._global_wiki_style_dir(vault), vault),
                             "projects/_global/wiki-style")

    def test_relocate_destination_defaults_to_current_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            self.assertEqual(_rel(relocate._global_wiki_style_dir(vault), vault),
                             "desk/projects/_global/wiki-style")


# ── The voice rule-pack overlay ──────────────────────────────────────────────

class TestRulePackOverlayAcrossLayouts(unittest.TestCase):
    OVERLAY = ('{"schema_version": 1, "era": "2026-08", "rules": ['
               '{"id": "voice-a4-groundbreaking", "severity": "error",'
               ' "kind": "word", "pattern": "groundbreaking", "hint": "overlaid",'
               ' "weight": 1, "source-url": "local"}]}')

    def _composed_hint(self, vault: Path) -> str:
        composed = rp_pack.load_rule_pack(vault_path=vault)
        by_id = {r["id"]: r for r in composed["rules"]}
        return by_id["voice-a4-groundbreaking"]["hint"]

    def test_new_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            d = vault / "desk" / "projects" / "_global" / "wiki-style"
            d.mkdir(parents=True)
            (d / "voice-rules-overlay.json").write_text(self.OVERLAY, encoding="utf-8")
            self.assertEqual(self._composed_hint(vault), "overlaid")

    def test_old_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            d = vault / "projects" / "_global" / "wiki-style"
            d.mkdir(parents=True)
            (d / "voice-rules-overlay.json").write_text(self.OVERLAY, encoding="utf-8")
            self.assertEqual(self._composed_hint(vault), "overlaid")

    def test_no_overlay_keeps_the_shipped_hint(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td) / "vault"
            vault.mkdir()
            self.assertEqual(self._composed_hint(vault),
                             "peacock word — strip, name the concrete mechanism instead")


# ── design plugin: prose_pass's own copy of the chain ────────────────────────

class TestProsePassOverlayDir(unittest.TestCase):
    def test_new_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "desk" / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(prose_pass.wiki_style_dir(vault), vault),
                             "desk/projects/_global/wiki-style")

    def test_old_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            self.assertEqual(_rel(prose_pass.wiki_style_dir(vault), vault),
                             "projects/_global/wiki-style")

    def test_empty_vault_defaults_to_current_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            self.assertEqual(_rel(prose_pass.wiki_style_dir(vault), vault),
                             "desk/projects/_global/wiki-style")

    def test_bare_overlay_filename_resolves_into_the_store(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "desk" / "projects" / "_global" / "wiki-style").mkdir(parents=True)
            got = prose_pass.resolve_overlay(vault, "2026-06-09-design-doc-prose.md")
            self.assertEqual(
                _rel(got, vault),
                "desk/projects/_global/wiki-style/2026-06-09-design-doc-prose.md")

    def test_absolute_overlay_is_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            abs_overlay = Path(td) / "elsewhere" / "x.md"
            self.assertEqual(prose_pass.resolve_overlay(vault, str(abs_overlay)),
                             abs_overlay)


# ── development-lifecycle plugin: the /open project scan ─────────────────────

class TestResolveProjectSpace(unittest.TestCase):
    def test_scan_finds_projects_on_the_new_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "desk" / "projects" / "widgets").mkdir(parents=True)
            got = resolve_project.scan_vault_projects(vault=vault)
            self.assertEqual([p["slug"] for p in got], ["widgets"])
            self.assertEqual(got[0]["vault_project_path"],
                             str(vault / "desk" / "projects" / "widgets"))

    def test_scan_finds_projects_on_the_old_layout(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            (vault / "projects" / "widgets").mkdir(parents=True)
            got = resolve_project.scan_vault_projects(vault=vault)
            self.assertEqual([p["slug"] for p in got], ["widgets"])

    def test_scan_is_empty_when_no_project_space_exists(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(resolve_project.scan_vault_projects(vault=Path(td)), [])

    def test_recall_slug_extraction_both_layouts(self):
        f = resolve_project._project_slug_from_vault_relpath
        self.assertEqual(f("desk/projects/agentm/_harness/PLAN.md"), "agentm")
        self.assertEqual(f("projects/agentm/_harness/PLAN.md"), "agentm")
        self.assertEqual(f("personal-projects/agentm/_harness/PLAN.md"), "agentm")

    def test_recall_slug_extraction_rejects_non_project_paths(self):
        f = resolve_project._project_slug_from_vault_relpath
        self.assertIsNone(f("memory/2026/07/voice-kernel.md"))
        self.assertIsNone(f("desk/briefs/note.md"))
        self.assertIsNone(f("projects"))          # root alone, no slug
        self.assertIsNone(f("desk/projects"))     # ditto
        self.assertIsNone(f(""))


if __name__ == "__main__":
    unittest.main()
