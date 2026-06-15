#!/usr/bin/env python3
"""Tests for finalize_unit.py (task 4 — isolation wiring + gh-unavailable fallback).

Verifies:
  - worktree-per-plan + pull-request → finalize_pr path (PR opened)
  - gh unavailable → fall back to finalize_direct + announce downgrade
  - direct config or --no-pr → finalize_direct path
  - PII guard is respected (inherited from pr_helpers contract)

Uses injected Runner and pii_guard_fn so no real git/gh needed.
Auto-discovered by check-all's `unit tests` gate.
"""
from __future__ import annotations

import importlib.util
import json
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


_load("pr_helpers")
_load("isolation_config")
fu = _load("finalize_unit")


def _write_isolation_cfg(root: Path, mode: str, integration: str) -> None:
    (root / ".harness").mkdir(parents=True, exist_ok=True)
    (root / ".harness" / "project.json").write_text(
        json.dumps({"isolation": {"mode": mode, "integration": integration}}),
        encoding="utf-8",
    )


def _runner_sequence(responses: list[tuple[int, str]]):
    """Runner that returns pre-canned (rc, out) per call in sequence."""
    calls = []
    seq = list(responses)

    def run(cmd: list, cwd: str) -> tuple[int, str]:
        calls.append(tuple(cmd))
        if seq:
            return seq.pop(0)
        return (0, "")

    run.calls = calls  # type: ignore[attr-defined]
    return run


class TestFinalizeUnitPRPath(unittest.TestCase):
    """worktree-per-plan + pull-request → finalize_pr."""

    def test_pr_path_opens_pr(self):
        with tempfile.TemporaryDirectory() as t:
            _write_isolation_cfg(Path(t), "worktree-per-plan", "pull-request")
            # check_gh_available calls `gh auth status` first via the runner
            runner = _runner_sequence([
                (0, ""),         # gh auth status (for check_gh_available)
                (0, ""),         # git add
                (0, ""),         # git commit
                (0, "abc1234"),  # git rev-parse HEAD
                (0, ""),         # git push
                (0, "https://github.com/o/r/pull/1"),  # gh pr create
            ])
            result = fu.finalize_unit(
                "myplan", t,
                runner=runner,
                pii_guard_fn=lambda root: True,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.action, "pr")

    def test_pr_path_pii_blocked_no_push(self):
        with tempfile.TemporaryDirectory() as t:
            _write_isolation_cfg(Path(t), "worktree-per-plan", "pull-request")
            cmds: list = []

            def recording_runner(cmd, cwd):
                cmds.append(tuple(cmd))
                return (0, "")

            result = fu.finalize_unit(
                "myplan", t,
                runner=recording_runner,
                pii_guard_fn=lambda root: False,
            )
            self.assertFalse(result.ok)
            push_cmds = [c for c in cmds if "push" in c]
            self.assertEqual(push_cmds, [], "PII block must prevent push")


class TestFinalizeUnitGhUnavailableFallback(unittest.TestCase):
    """gh unavailable → fall back to direct push + announce."""

    def test_gh_unavailable_falls_back_to_direct(self):
        with tempfile.TemporaryDirectory() as t:
            _write_isolation_cfg(Path(t), "worktree-per-plan", "pull-request")
            # Patch check_gh_available in finalize_unit's own namespace
            import finalize_unit as fu_mod
            original = fu_mod.check_gh_available
            fu_mod.check_gh_available = lambda runner=None, cwd=".": False
            try:
                runner = _runner_sequence([
                    (0, ""),        # git add
                    (0, ""),        # git commit
                    (0, "abc123"),  # git rev-parse HEAD
                    (0, ""),        # git push (direct fallback)
                ])
                result = fu.finalize_unit(
                    "myplan", t,
                    runner=runner,
                    pii_guard_fn=lambda root: True,
                )
                self.assertTrue(result.ok)
                self.assertEqual(result.action, "direct")
                self.assertIn("gh unavailable", result.reason)
            finally:
                fu_mod.check_gh_available = original


class TestFinalizeUnitDirectPath(unittest.TestCase):
    """direct mode or --no-pr → finalize_direct."""

    def test_no_pr_flag_uses_direct(self):
        with tempfile.TemporaryDirectory() as t:
            _write_isolation_cfg(Path(t), "worktree-per-plan", "pull-request")
            runner = _runner_sequence([
                (0, ""),        # git add
                (0, ""),        # git commit
                (0, "abc123"),  # git rev-parse HEAD
                (0, ""),        # git push
            ])
            result = fu.finalize_unit(
                "myplan", t, no_pr=True,
                runner=runner, pii_guard_fn=lambda root: True,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.action, "direct")

    def test_direct_integration_config_uses_direct(self):
        with tempfile.TemporaryDirectory() as t:
            _write_isolation_cfg(Path(t), "worktree-per-plan", "direct-push")
            runner = _runner_sequence([
                (0, ""),
                (0, ""),
                (0, "abc123"),
                (0, ""),
            ])
            result = fu.finalize_unit(
                "myplan", t,
                runner=runner, pii_guard_fn=lambda root: True,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.action, "direct")

    def test_direct_mode_config_uses_direct(self):
        with tempfile.TemporaryDirectory() as t:
            _write_isolation_cfg(Path(t), "direct", "pull-request")
            runner = _runner_sequence([
                (0, ""),
                (0, ""),
                (0, "abc123"),
                (0, ""),
            ])
            result = fu.finalize_unit(
                "myplan", t,
                runner=runner, pii_guard_fn=lambda root: True,
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.action, "direct")


if __name__ == "__main__":
    unittest.main()
