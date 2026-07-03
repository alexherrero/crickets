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
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class TestFinalizeUnitMainExitCodes(unittest.TestCase):
    """Regression tests for exit-code contract in main() — fixes for DEFECT 1 + DEFECT 2
    found by adversarial review (2026-06-15, issue #27).

    Tests patch finalize_unit() to return a pre-canned DispatchResult so that
    main()'s exit-code decision logic is exercised in isolation.
    """

    def _result(self, ok: bool, action: str, steps: list) -> "DispatchResult":
        import pr_helpers as ph
        r = ph.DispatchResult(ok=ok, action=action)
        r.steps = steps
        return r

    def test_push_ok_pr_create_fails_returns_exit1(self):
        """DEFECT 1 regression: push landed, gh pr create failed → exit 1, not 2.

        Exit 2 = 'nothing pushed'; branch IS on the remote after push. Returning
        exit 2 here causes callers to retry and push again (duplicate push).
        """
        result = self._result(
            ok=False, action="pr",
            steps=[("add", 0), ("commit", 0), ("pii-guard", 0), ("push", 0), ("pr-create", 1)],
        )
        from unittest.mock import patch
        with patch.object(fu, "finalize_unit", return_value=result):
            ec = fu.main(["prog", "testslug", "--project-root", "/tmp"])
        self.assertEqual(ec, 1,
            "push landed but PR failed → exit 1 (partial success), not exit 2 (nothing pushed)")

    def test_push_rejected_returns_exit2(self):
        """DEFECT 2 regression: push rejected (direct path) → exit 2, not 1.

        Exit 1 = 'partial success / graceful-skip'; nothing reached the remote.
        Returning exit 1 here causes callers to silently miss the push failure.
        """
        result = self._result(
            ok=False, action="direct",
            steps=[("add", 0), ("commit", 0), ("pii-guard", 0), ("push", 1)],
        )
        from unittest.mock import patch
        with patch.object(fu, "finalize_unit", return_value=result):
            ec = fu.main(["prog", "testslug", "--project-root", "/tmp"])
        self.assertEqual(ec, 2,
            "push rejected → exit 2 (nothing pushed), not exit 1 (graceful-skip)")

    def test_pr_push_itself_fails_returns_exit2(self):
        """PR path push rejected → nothing on remote → exit 2."""
        result = self._result(
            ok=False, action="pr",
            steps=[("add", 0), ("commit", 0), ("pii-guard", 0), ("push", 1)],
        )
        from unittest.mock import patch
        with patch.object(fu, "finalize_unit", return_value=result):
            ec = fu.main(["prog", "testslug", "--project-root", "/tmp"])
        self.assertEqual(ec, 2, "PR path push failed → exit 2 (nothing on remote)")

    def test_pii_blocked_no_push_step_returns_exit2(self):
        """PII guard blocked before push — steps has no push entry → exit 2."""
        result = self._result(
            ok=False, action="pr",
            steps=[("add", 0), ("commit", 0), ("pii-guard", 1)],
        )
        from unittest.mock import patch
        with patch.object(fu, "finalize_unit", return_value=result):
            ec = fu.main(["prog", "testslug", "--project-root", "/tmp"])
        self.assertEqual(ec, 2, "PII blocked → no push happened → exit 2")

    def test_success_returns_exit0(self):
        """Happy path: result.ok=True → exit 0 regardless of steps."""
        result = self._result(
            ok=True, action="pr",
            steps=[("add", 0), ("commit", 0), ("pii-guard", 0), ("push", 0), ("pr-create", 0)],
        )
        from unittest.mock import patch
        with patch.object(fu, "finalize_unit", return_value=result):
            ec = fu.main(["prog", "testslug", "--project-root", "/tmp"])
        self.assertEqual(ec, 0)


class TestDefaultPiiGuard(unittest.TestCase):
    """R0.6 regression: the default `_pii_guard` must be fail-open when the
    real scanner (check-no-pii.sh) can't be found — not fail-closed. The
    phantom `python3 -m pii_scrubber` entrypoint blocked every push on any
    machine without a pip-importable pii_scrubber module, which is every
    machine (the pii plugin ships only prose, no importable module)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fu-pii-"))
        self.env_backup = dict(os.environ)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.clear()
        os.environ.update(self.env_backup)

    def _write_scanner(self, path: Path, exit_code: int) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"#!/usr/bin/env bash\nexit {exit_code}\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_scanner_absent_is_fail_open(self):
        repo_root = self.tmp / "repo"
        repo_root.mkdir()
        home = self.tmp / "empty_home"
        home.mkdir()
        with mock.patch.dict(os.environ, {"AGENT_TOOLKIT_PATH": ""}, clear=False):
            with mock.patch.object(Path, "home", return_value=home):
                result = fu._pii_guard(str(repo_root))
        self.assertTrue(result, "scanner absent must fail OPEN (pass), not closed")

    def test_scanner_present_and_clean_passes(self):
        repo_root = self.tmp / "repo"
        repo_root.mkdir()
        scanner = self._write_scanner(
            self.tmp / "toolkit" / "scripts" / "check-no-pii.sh", exit_code=0
        )
        with mock.patch.dict(os.environ, {"AGENT_TOOLKIT_PATH": str(self.tmp / "toolkit")}):
            result = fu._pii_guard(str(repo_root))
        self.assertTrue(result)

    def test_scanner_present_and_finds_pii_blocks(self):
        repo_root = self.tmp / "repo"
        repo_root.mkdir()
        scanner = self._write_scanner(
            self.tmp / "toolkit" / "scripts" / "check-no-pii.sh", exit_code=1
        )
        with mock.patch.dict(os.environ, {"AGENT_TOOLKIT_PATH": str(self.tmp / "toolkit")}):
            result = fu._pii_guard(str(repo_root))
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
