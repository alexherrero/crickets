#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/isolation_config.py (task 2;
R2.5 task 11 flipped the absent-config default from 'worktree-per-plan' to
'direct' per the operator's worktree doctrine — ADR 0028 refining ADR 0022).

Covers:
  - read_isolation: missing / malformed / wrong-type → 'direct' default; valid → set value
  - should_auto_isolate: all three precedence layers (arg > file > code-default-OFF)
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
            self.assertEqual(cfg["mode"], "direct")
            self.assertEqual(cfg["integration"], "pull-request")

    def test_missing_project_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / ".harness").mkdir()
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "direct")
            self.assertEqual(cfg["integration"], "pull-request")

    def test_malformed_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            h = Path(t) / ".harness"
            h.mkdir()
            (h / "project.json").write_text("not json {{{", encoding="utf-8")
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "direct")

    def test_json_array_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", [1, 2, 3])  # type: ignore[arg-type]
            # write_project_json is for dicts; write directly
            (Path(t) / ".harness" / "project.json").write_text("[1,2,3]", encoding="utf-8")
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "direct")

    def test_isolation_block_not_object_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness",
                                {"vault_project": "x", "github": {}, "isolation": "bad"})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "direct")

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
            self.assertEqual(cfg["mode"], "direct")

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
            self.assertEqual(cfg["mode"], "direct")

    def test_absent_isolation_key_returns_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", {"vault_project": "x"})
            cfg = ic.read_isolation(t)
            self.assertEqual(cfg["mode"], "direct")
            self.assertEqual(cfg["integration"], "pull-request")


class TestShouldAutoIsolatePrecedence(unittest.TestCase):
    """Precedence: command-arg > project.json > code-default-OFF."""

    def _root_with_mode(self, mode: str) -> tempfile.TemporaryDirectory:
        t = tempfile.TemporaryDirectory()
        _write_project_json(Path(t.name) / ".harness", {"isolation": {"mode": mode}})
        return t

    def test_default_off_no_config_no_arg(self):
        # R2.5 task 11: no project.json → code-default is 'direct' (no
        # auto-spawn) — the operator's worktree doctrine requires explicit
        # authority (a durable config opt-in or an operator command), never
        # a silent default-ON with no config at all.
        with tempfile.TemporaryDirectory() as t:
            result = ic.should_auto_isolate(t, arg_no_isolate=False)
            self.assertFalse(result)

    def test_arg_no_isolate_with_no_config(self):
        with tempfile.TemporaryDirectory() as t:
            result = ic.should_auto_isolate(t, arg_no_isolate=True)
            self.assertFalse(result)

    def test_arg_no_isolate_overrides_config_worktree_per_plan(self):
        with self._root_with_mode("worktree-per-plan") as t:
            result = ic.should_auto_isolate(t, arg_no_isolate=True)
            self.assertFalse(result)

    def test_config_direct_stays_off(self):
        with self._root_with_mode("direct") as t:
            result = ic.should_auto_isolate(t)
            self.assertFalse(result)

    def test_config_worktree_per_plan_enables(self):
        with self._root_with_mode("worktree-per-plan") as t:
            result = ic.should_auto_isolate(t)
            self.assertTrue(result)


class TestIsolationAuthorityConformance(unittest.TestCase):
    """R2.5 task 11: locks the operator's worktree doctrine (~/.claude/CLAUDE.md
    § Worktrees, ADR 0028 refining ADR 0022) as a permanent, named regression
    test — distinct from the general precedence coverage above, so a future
    reader who never saw this task's history still finds the doctrine
    statement right next to the assertion it backs.

    Authority = an explicit operator command (the invocation of /work etc.
    itself, or --isolate) OR a durable `isolation.mode: worktree-per-plan`
    config opt-in in .harness/project.json. Absent authority, the answer must
    always be 'no auto-spawn' — never a silent default-ON."""

    def test_no_authority_means_no_auto_spawn(self):
        # A repo with no .harness/ at all: zero authority, zero config.
        # cricketsPluginsA#2's exact reproduction — this must be False.
        with tempfile.TemporaryDirectory() as t:
            self.assertFalse(ic.should_auto_isolate(t))

    def test_durable_config_opt_in_grants_authority(self):
        # The other half of the doctrine: a durable config opt-in IS real
        # authority, and must still work exactly as before this fix.
        with tempfile.TemporaryDirectory() as t:
            _write_project_json(Path(t) / ".harness", {"isolation": {"mode": "worktree-per-plan"}})
            self.assertTrue(ic.should_auto_isolate(t))


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
