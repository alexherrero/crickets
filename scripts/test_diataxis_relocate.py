#!/usr/bin/env python3
"""Tests for the diataxis-author _always-load -> _global relocation
(src/wiki-maintenance/skills/diataxis-author/scripts/relocate.py) — crickets
④ wiki-maintenance part 3/5, task 4.

Deterministic-only (DC-7): preview mutates nothing; relocate copies conflict-safe
+ idempotent; cleanup is gated; rollback round-trips (both after a leave-source
relocate AND after a --cleanup that deleted the source). The operator-run live
preview is exercised separately against the real vault, not here.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
import contextlib
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


rel = _load("relocate")
sr = _load("style_resolver")

_BODY = "---\ntrigger: filename-style\n---\nUse CamelCase-With-Dashes for filenames.\n"


def _seed(vault: Path, name: str = "diataxis-filename-style.md", body: str = _BODY) -> Path:
    al = rel._always_load_dir(vault)
    al.mkdir(parents=True, exist_ok=True)
    src = al / name
    src.write_text(body, encoding="utf-8")
    return src


def _verbs(actions: list) -> list:
    return [a.verb for a in actions]


class TestPreviewMutatesNothing(unittest.TestCase):
    def test_preview_is_a_pure_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            src = _seed(vault)
            before = src.read_text(encoding="utf-8")
            actions = rel.relocate(vault, preview=True)
            self.assertEqual(_verbs(actions), ["WOULD-RELOCATE"])
            # Nothing created, nothing deleted, no manifest.
            self.assertFalse(rel._global_wiki_style_dir(vault).exists())
            self.assertTrue(src.is_file())
            self.assertEqual(src.read_text(encoding="utf-8"), before)
            self.assertFalse(rel._manifest_path(vault).exists())


class TestRelocateCopies(unittest.TestCase):
    def test_relocate_copies_leaves_source_records_manifest_and_round_trips(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            src = _seed(vault)
            actions = rel.relocate(vault)
            self.assertEqual(_verbs(actions), ["RELOCATED"])
            dest = rel._global_wiki_style_dir(vault) / "diataxis-filename-style.md"
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.read_bytes(), src.read_bytes())  # byte-identical copy
            self.assertTrue(src.is_file())                         # source left in place
            self.assertEqual(rel._read_manifest(vault), ["diataxis-filename-style.md"])
            # The relocated file is now a global on-demand lesson the resolver reads.
            lessons = sr.read_scope_lessons(dest.parent, "global")
            self.assertIn("filename-style", [lz.trigger for lz in lessons])

    def test_relocate_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _seed(vault)
            rel.relocate(vault)
            actions = rel.relocate(vault)  # second run
            self.assertEqual(_verbs(actions), ["SKIP-IDENTICAL"])
            self.assertEqual(rel._read_manifest(vault), ["diataxis-filename-style.md"])

    def test_conflict_when_dest_differs_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            src = _seed(vault)
            dest_dir = rel._global_wiki_style_dir(vault)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / "diataxis-filename-style.md"
            dest.write_text("DIFFERENT pre-existing content\n", encoding="utf-8")
            actions = rel.relocate(vault)
            self.assertEqual(_verbs(actions), ["CONFLICT"])
            self.assertEqual(dest.read_text(encoding="utf-8"), "DIFFERENT pre-existing content\n")
            self.assertTrue(src.is_file())
            self.assertEqual(rel._read_manifest(vault), [])  # conflict not manifested


class TestCleanupGated(unittest.TestCase):
    def test_cleanup_without_yes_keeps_source(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            src = _seed(vault)
            actions = rel.relocate(vault, cleanup=True, assume_yes=False)
            self.assertIn("RELOCATED", _verbs(actions))
            self.assertIn("SKIP-CLEANUP", _verbs(actions))
            self.assertTrue(src.is_file())  # source NOT deleted without --yes

    def test_cleanup_with_yes_deletes_source_after_verify(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            src = _seed(vault)
            actions = rel.relocate(vault, cleanup=True, assume_yes=True)
            self.assertIn("CLEANED", _verbs(actions))
            self.assertFalse(src.exists())  # source deleted
            dest = rel._global_wiki_style_dir(vault) / "diataxis-filename-style.md"
            self.assertTrue(dest.is_file())  # dest preserved


class TestRollbackRoundTrip(unittest.TestCase):
    def test_rollback_after_leave_source_relocate(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            src = _seed(vault)
            original = src.read_bytes()
            rel.relocate(vault)  # source kept + dest created
            actions = rel.rollback(vault)
            self.assertEqual(_verbs(actions), ["ROLLED-BACK"])
            dest = rel._global_wiki_style_dir(vault) / "diataxis-filename-style.md"
            self.assertFalse(dest.exists())          # relocated copy removed
            self.assertEqual(src.read_bytes(), original)  # source intact
            self.assertEqual(rel._read_manifest(vault), [])  # manifest cleared

    def test_rollback_restores_a_cleaned_up_source(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            src = _seed(vault)
            original = src.read_bytes()
            rel.relocate(vault, cleanup=True, assume_yes=True)  # source DELETED
            self.assertFalse(src.exists())
            actions = rel.rollback(vault)
            self.assertEqual(_verbs(actions), ["ROLLED-BACK"])
            self.assertTrue(src.is_file())            # source restored from the copy
            self.assertEqual(src.read_bytes(), original)
            dest = rel._global_wiki_style_dir(vault) / "diataxis-filename-style.md"
            self.assertFalse(dest.exists())
            self.assertEqual(rel._read_manifest(vault), [])

    def test_rollback_preview_changes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _seed(vault)
            rel.relocate(vault)
            dest = rel._global_wiki_style_dir(vault) / "diataxis-filename-style.md"
            actions = rel.rollback(vault, preview=True)
            self.assertEqual(_verbs(actions), ["WOULD-ROLLBACK"])
            self.assertTrue(dest.is_file())  # untouched
            self.assertEqual(rel._read_manifest(vault), ["diataxis-filename-style.md"])

    def test_rollback_leaves_directly_captured_lessons_untouched(self):
        # A lesson captured straight into _global (never relocated -> not in the
        # manifest) must survive a rollback.
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _seed(vault)
            rel.relocate(vault, cleanup=True, assume_yes=True)
            captured = rel._global_wiki_style_dir(vault) / "2026-06-05-captured.md"
            captured.write_text("---\ntrigger: captured\n---\nKeep me.\n", encoding="utf-8")
            rel.rollback(vault)
            self.assertTrue(captured.is_file())  # not in the manifest -> untouched


class TestNoSourcesNoOp(unittest.TestCase):
    def test_empty_always_load_is_clean_no_op(self):
        # The live-vault scenario today: no diataxis-*.md exists -> nothing moves.
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            rel._always_load_dir(vault).mkdir(parents=True, exist_ok=True)
            actions = rel.relocate(vault, preview=True)
            self.assertEqual(actions, [])
            self.assertFalse(rel._global_wiki_style_dir(vault).exists())

    def test_cli_preview_prints_and_returns_zero(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _seed(vault)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = rel.main(["--preview", "--vault-path", str(vault)])
            self.assertEqual(rc, 0)
            self.assertIn("WOULD-RELOCATE", buf.getvalue())
            self.assertFalse(rel._global_wiki_style_dir(vault).exists())

    def test_cli_conflict_returns_two(self):
        with tempfile.TemporaryDirectory() as td:
            vault = Path(td)
            _seed(vault)
            dest_dir = rel._global_wiki_style_dir(vault)
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / "diataxis-filename-style.md").write_text("different\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = rel.main(["--vault-path", str(vault)])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
