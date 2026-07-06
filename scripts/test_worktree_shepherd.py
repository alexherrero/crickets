#!/usr/bin/env python3
"""Tests for src/development-lifecycle/scripts/worktree_shepherd.py.

The periodic sidecar (worktree-native-flow task 5) that: (a) reclaims orphaned
worktrees/branches that are old enough AND provably safe (no local-only commits
beyond what the remote branch already has), never guessing; (b) rebases a
stalled armed PR (GitHub reports it behind the base branch after a sibling
plan's PR merged first) via `gh pr update-branch`, surfacing any resulting
merge conflict loudly rather than leaving it stuck silently.

Real git (throwaway temp repos, real `git worktree add` / `git push` against a
bare "origin" remote) for the reclaim-safety logic — no mocking of the one
thing under test (does this branch's content survive removal). `gh` is always
injected via a fake runner — no real network/gh calls in tests.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


_load("doctor_worktrees")
ws = _load("worktree_shepherd")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=check)


def _init_repo_with_origin(tmp: Path) -> tuple[Path, Path]:
    """A real bare 'origin' + a clone, so push/fetch are genuine, not simulated."""
    origin = tmp / "origin.git"
    origin.mkdir()
    _git(origin, "init", "-q", "--bare", "-b", "main")
    repo = tmp / "repo"
    _git(tmp, "clone", "-q", str(origin), str(repo))
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".harness/\n", encoding="utf-8")
    _git(repo, "add", "README.md", ".gitignore")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "push", "-q", "-u", "origin", "main")
    return repo, origin


def _add_worktree(repo: Path, tmp: Path, slug: str, *, commit: bool = True,
                  push: bool = False) -> tuple[str, Path]:
    branch = f"worktree-{slug}"
    wt = tmp / f"wt-{slug}"
    _git(repo, "worktree", "add", "-b", branch, str(wt))
    if commit:
        (wt / f"work-{slug}.txt").write_text("work\n", encoding="utf-8")
        _git(wt, "add", ".")
        _git(wt, "commit", "-q", "-m", f"work on {slug}")
    if push:
        _git(wt, "push", "-q", "-u", "origin", branch)
    return branch, wt


class TestSafeToReclaim(unittest.TestCase):
    """`is_safe_to_reclaim`: the branch's content must be fully present on the
    remote (or never diverged at all) before this shepherd removes anything."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wsh-safe-"))
        self.repo, self.origin = _init_repo_with_origin(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fully_pushed_branch_is_safe(self):
        branch, _wt = _add_worktree(self.repo, self.tmp, "pushed", push=True)
        self.assertTrue(ws.is_safe_to_reclaim(str(self.repo), branch))

    def test_never_diverged_branch_is_safe(self):
        # A branch created but never committed to — nothing to lose either way.
        branch, _wt = _add_worktree(self.repo, self.tmp, "even", commit=False)
        self.assertTrue(ws.is_safe_to_reclaim(str(self.repo), branch))

    def test_unpushed_local_only_commits_are_unsafe(self):
        branch, _wt = _add_worktree(self.repo, self.tmp, "local-only", push=False)
        self.assertFalse(ws.is_safe_to_reclaim(str(self.repo), branch))

    def test_partially_pushed_then_more_local_commits_are_unsafe(self):
        branch, wt = _add_worktree(self.repo, self.tmp, "partial", push=True)
        (wt / "more.txt").write_text("more\n", encoding="utf-8")
        _git(wt, "add", ".")
        _git(wt, "commit", "-q", "-m", "one more, never pushed")
        self.assertFalse(ws.is_safe_to_reclaim(str(self.repo), branch))

    def test_no_remote_at_all_and_no_divergence_is_safe(self):
        # A repo with no 'origin' configured: nothing to compare against, but
        # a branch that never diverged from its creation point loses nothing.
        tmp2 = Path(tempfile.mkdtemp(prefix="wsh-noorigin-"))
        try:
            repo2 = tmp2 / "repo"
            repo2.mkdir()
            _git(repo2, "init", "-q", "-b", "main")
            _git(repo2, "config", "user.email", "test@example.com")
            _git(repo2, "config", "user.name", "t")
            _git(repo2, "config", "commit.gpgsign", "false")
            (repo2 / "README.md").write_text("seed\n", encoding="utf-8")
            _git(repo2, "add", "README.md")
            _git(repo2, "commit", "-q", "-m", "seed")
            branch, _wt = _add_worktree(repo2, tmp2, "solo", commit=False)
            self.assertTrue(ws.is_safe_to_reclaim(str(repo2), branch))
        finally:
            import shutil
            shutil.rmtree(tmp2, ignore_errors=True)


class TestReclaimOrphans(unittest.TestCase):
    """`reclaim_orphans`: only ORPHANED + old-enough + safe worktrees are removed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wsh-reclaim-"))
        self.repo, self.origin = _init_repo_with_origin(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_orphaned_old_safe_worktree_is_removed(self):
        branch, wt = _add_worktree(self.repo, self.tmp, "stale", push=True)
        import shutil
        shutil.rmtree(wt)  # orphan: worktree dir gone, branch lingers

        result = ws.reclaim_orphans(str(self.repo), age_threshold_seconds=0)
        self.assertIn(branch, [r.branch for r in result.reclaimed])
        self.assertEqual(
            _git(self.repo, "rev-parse", "--verify", "--quiet",
                 f"refs/heads/{branch}", check=False).returncode, 1,
            "the branch must actually be gone after reclaim")

    def test_orphaned_unsafe_worktree_is_left_alone(self):
        branch, wt = _add_worktree(self.repo, self.tmp, "risky", push=False)
        import shutil
        shutil.rmtree(wt)

        result = ws.reclaim_orphans(str(self.repo), age_threshold_seconds=0)
        self.assertIn(branch, [r.branch for r in result.skipped_unsafe])
        self.assertEqual(
            _git(self.repo, "rev-parse", "--verify", "--quiet",
                 f"refs/heads/{branch}", check=False).returncode, 0,
            "an unsafe orphan must survive — never guess away possibly-unpushed work")

    def test_orphaned_but_too_young_is_left_alone(self):
        branch, wt = _add_worktree(self.repo, self.tmp, "fresh", push=True)
        import shutil
        shutil.rmtree(wt)

        result = ws.reclaim_orphans(str(self.repo), age_threshold_seconds=999999)
        self.assertIn(branch, [r.branch for r in result.skipped_too_young])
        self.assertEqual(
            _git(self.repo, "rev-parse", "--verify", "--quiet",
                 f"refs/heads/{branch}", check=False).returncode, 0)

    def test_active_worktree_is_never_touched(self):
        branch, _wt = _add_worktree(self.repo, self.tmp, "live", push=True)
        result = ws.reclaim_orphans(str(self.repo), age_threshold_seconds=0)
        self.assertNotIn(branch, [r.branch for r in result.reclaimed])
        self.assertNotIn(branch, [r.branch for r in result.skipped_unsafe])

    def test_dry_run_reports_without_mutating(self):
        branch, wt = _add_worktree(self.repo, self.tmp, "dryrun", push=True)
        import shutil
        shutil.rmtree(wt)

        result = ws.reclaim_orphans(str(self.repo), age_threshold_seconds=0, dry_run=True)
        self.assertIn(branch, [r.branch for r in result.reclaimed])
        self.assertEqual(
            _git(self.repo, "rev-parse", "--verify", "--quiet",
                 f"refs/heads/{branch}", check=False).returncode, 0,
            "dry-run must report what it WOULD reclaim without touching the branch")


class TestStalledPRShepherd(unittest.TestCase):
    """`shepherd_stalled_prs`: rebase a behind-base armed PR; surface conflicts loudly."""

    def _runner(self, responses: dict) -> object:
        calls = []

        def run(cmd: list, cwd: str) -> tuple[int, str]:
            calls.append(tuple(cmd))
            key = tuple(cmd)
            if key in responses:
                return responses[key]
            for k, v in responses.items():
                if cmd[:len(k)] == list(k):
                    return v
            return (0, "")

        run.calls = calls
        return run

    def test_behind_pr_gets_updated(self):
        runner = self._runner({
            ("gh", "pr", "list"): (0, '[{"number": 42, "headRefName": "worktree-foo", '
                                       '"mergeStateStatus": "BEHIND", '
                                       '"url": "https://github.com/o/r/pull/42"}]'),
            ("gh", "pr", "update-branch"): (0, "Updated"),
        })
        report = ws.shepherd_stalled_prs("/repo", runner=runner)
        self.assertEqual(len(report.updated), 1)
        self.assertEqual(report.updated[0].pr_number, 42)
        update_calls = [c for c in runner.calls if c[:2] == ("gh", "pr") and "update-branch" in c]
        self.assertEqual(len(update_calls), 1)

    def test_clean_pr_is_left_alone(self):
        runner = self._runner({
            ("gh", "pr", "list"): (0, '[{"number": 7, "headRefName": "worktree-bar", '
                                       '"mergeStateStatus": "CLEAN", '
                                       '"url": "https://github.com/o/r/pull/7"}]'),
        })
        report = ws.shepherd_stalled_prs("/repo", runner=runner)
        self.assertEqual(len(report.updated), 0)
        update_calls = [c for c in runner.calls if "update-branch" in c]
        self.assertEqual(len(update_calls), 0)

    def test_update_conflict_is_surfaced_loudly_not_silently_left(self):
        runner = self._runner({
            ("gh", "pr", "list"): (0, '[{"number": 9, "headRefName": "worktree-baz", '
                                       '"mergeStateStatus": "BEHIND", '
                                       '"url": "https://github.com/o/r/pull/9"}]'),
            ("gh", "pr", "update-branch"): (1, "merge conflict between base and head"),
        })
        report = ws.shepherd_stalled_prs("/repo", runner=runner)
        self.assertEqual(len(report.updated), 0)
        self.assertEqual(len(report.conflicts), 1)
        self.assertEqual(report.conflicts[0].pr_number, 9)
        self.assertIn("merge conflict", report.conflicts[0].detail)

    def test_no_open_prs_is_a_clean_no_op(self):
        runner = self._runner({("gh", "pr", "list"): (0, "[]")})
        report = ws.shepherd_stalled_prs("/repo", runner=runner)
        self.assertEqual(report.updated, [])
        self.assertEqual(report.conflicts, [])


if __name__ == "__main__":
    unittest.main()
