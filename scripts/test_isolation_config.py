#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/isolation_config.py (task 2).

Covers:
  - read_isolation: missing / malformed / wrong-type → default; valid → set value
  - should_auto_isolate: all three precedence layers (arg > file > default-ON)
  - is_inside_worktree / resolve_main_worktree: real git repos where git is available

Auto-discovered by check-all's `unit tests` gate.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "developer-workflows" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ic = _load("isolation_config")


def _write_project_json(harness_dir: Path, data: dict) -> None:
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / "project.json").write_text(json.dumps(data), encoding="utf-8")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")


class TestReadIsolation(unittest.TestCase):
    def test_missing_harness_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")
            self.assertEqual(cfg["integration"], "pull-request")

    def test_missing_project_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / ".harness").mkdir()
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")
            self.assertEqual(cfg["integration"], "pull-request")

    def test_malformed_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            h = Path(t) / ".harness"
            h.mkdir()
            (h / "project.json").write_text("not json {{{", encoding="utf-8")
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")

    def test_json_array_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", [1, 2, 3])  # type: ignore[arg-type]
            # write_project_json is for dicts; write directly
            (Path(t) / ".harness" / "project.json").write_text("[1,2,3]", encoding="utf-8")
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")

    def test_isolation_block_not_object_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness",
                                {"vault_project": "x", "github": {}, "isolation": "bad"})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")

    def test_valid_mode_worktree_per_plan(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness",
                                {"isolation": {"mode": "worktree-per-plan"}})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")

    def test_valid_mode_direct(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", {"isolation": {"mode": "direct"}})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "direct")

    def test_valid_integration_direct_push(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness",
                                {"isolation": {"integration": "direct-push"}})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["integration"], "direct-push")

    def test_unknown_mode_value_returns_default(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", {"isolation": {"mode": "auto"}})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")

    def test_unknown_integration_value_returns_default(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness",
                                {"isolation": {"integration": "squash"}})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["integration"], "pull-request")

    def test_wrong_type_mode_returns_default(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", {"isolation": {"mode": 42}})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")

    def test_absent_isolation_key_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", {"vault_project": "x"})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "worktree-per-plan")
            self.assertEqual(cfg["integration"], "pull-request")


class TestShouldAutoIsolatePrecedence(unittest.TestCase):
    """Precedence: command-arg > project.json > code-default-ON."""

    def _root_with_mode(self, mode: str) -> tempfile.TemporaryDirectory:
        t = tempfile.TemporaryDirectory()
        _write_project_json(Path(t.name) / ".harness", {"isolation": {"mode": mode}})
        return t

    def test_default_on_no_config_no_arg(self):
        with tempfile.TemporaryDirectory() as t:
            # No project.json → default-ON, but we're not in a git worktree so
            # is_inside_worktree returns False (or graceful False on non-git dir).
            result = ic.should_auto_isolate(t, arg_no_isolate=False)
            self.assertTrue(result)

    def test_arg_no_isolate_overrides_default_on(self):
        with tempfile.TemporaryDirectory() as t:
            result = ic.should_auto_isolate(t, arg_no_isolate=True)
            self.assertFalse(result)

    def test_arg_no_isolate_overrides_config_worktree_per_plan(self):
        with self._root_with_mode("worktree-per-plan") as t:
            result = ic.should_auto_isolate(t, arg_no_isolate=True)
            self.assertFalse(result)

    def test_config_direct_overrides_default_on(self):
        with self._root_with_mode("direct") as t:
            result = ic.should_auto_isolate(t)
            self.assertFalse(result)

    def test_config_worktree_per_plan_enables(self):
        with self._root_with_mode("worktree-per-plan") as t:
            result = ic.should_auto_isolate(t)
            self.assertTrue(result)


class TestWorktreeDetection(unittest.TestCase):
    """is_inside_worktree / resolve_main_worktree against real git repos."""

    def test_main_tree_is_not_inside_worktree(self):
        with tempfile.TemporaryDirectory() as t:
            _init_repo(Path(t) / "repo")
            self.assertFalse(ic.is_inside_worktree(Path(t) / "repo"))

    def test_main_tree_resolve_main_worktree_returns_itself(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            main = ic.resolve_main_worktree(repo)
            self.assertEqual(main, repo.resolve())

    def test_inside_worktree_detected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            wt = Path(t) / "wt"
            _git(repo, "worktree", "add", "-b", "wt-branch", str(wt))
            self.assertTrue(ic.is_inside_worktree(wt))

    def test_resolve_main_worktree_from_inside_worktree(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            wt = Path(t) / "wt"
            _git(repo, "worktree", "add", "-b", "wt2-branch", str(wt))
            main = ic.resolve_main_worktree(wt)
            self.assertEqual(main, repo.resolve())

    def test_non_git_dir_graceful(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertFalse(ic.is_inside_worktree(t))
            resolved = ic.resolve_main_worktree(t)
            self.assertEqual(resolved, Path(t).resolve())

    def test_single_owner_guard_blocks_auto_isolate_inside_worktree(self):
        """should_auto_isolate returns False when already inside a worktree."""
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            wt = Path(t) / "wt"
            _git(repo, "worktree", "add", "-b", "guard-branch", str(wt))
            result = ic.should_auto_isolate(wt)
            self.assertFalse(result, "single-owner guard must block auto-spawn when already inside a worktree")


if __name__ == "__main__":
    unittest.main()
