#!/usr/bin/env python3
"""Tests for scripts/check_tag_reachability.py (concurrent-release coordination, task 1).

Each test builds a throwaway temp git repo and drives real git commands — no mocked
git, never the real repo. The load-bearing assertions:
  (a) a main-reachable commit tagged → check passes (returns [])
  (b) a branch-tip commit (not reachable from main) tagged → check fails with that tag
  (c) no tags → check passes (nothing to check)
  (d) no main branch → graceful skip, check passes (don't block non-main-default repos)
  (e) mixed tags (one on main, one off) → only the off-main tag is reported
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPT = _ROOT / "scripts" / "check_tag_reachability.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_tag_reachability", _SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


mod = _load()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=True)


def _init_repo(repo: Path, *, branch: str = "main") -> None:
    """Throwaway git repo with one commit on the given branch."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


class TestMainReachableTagPasses(unittest.TestCase):
    """A tag on the current main HEAD → check returns []."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ctr-pass-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        _git(self.repo, "tag", "v1.0.0")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_main_reachable_tag_passes(self):
        off_main = mod.check_tag_reachability(cwd=self.repo)
        self.assertEqual(off_main, [],
                         "a tag on the main HEAD should pass the reachability check")


class TestBranchTipTagFails(unittest.TestCase):
    """A tag on a branch-tip commit (not reachable from main) → check returns that tag."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ctr-fail-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        # A branch commit NOT merged into main → not reachable from main
        _git(self.repo, "checkout", "-b", "worker/my-plan")
        (self.repo / "branch.txt").write_text("branch\n", encoding="utf-8")
        _git(self.repo, "add", "branch.txt")
        _git(self.repo, "commit", "-q", "-m", "branch commit")
        _git(self.repo, "tag", "v-branch-tip")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_branch_tip_tag_fails(self):
        off_main = mod.check_tag_reachability(cwd=self.repo)
        self.assertEqual(len(off_main), 1,
                         "a tag on a branch tip should fail the reachability check")
        self.assertEqual(off_main[0][0], "v-branch-tip")


class TestNoTagsPasses(unittest.TestCase):
    """No tags in the repo → check returns [] (nothing to check)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ctr-notag-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_tags_passes(self):
        off_main = mod.check_tag_reachability(cwd=self.repo)
        self.assertEqual(off_main, [], "no tags → should pass (nothing to check)")


class TestNoMainBranchGracefulSkip(unittest.TestCase):
    """No main branch → graceful skip, check returns [] (not an error)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ctr-nomain-"))
        self.repo = self.tmp / "repo"
        # Init on 'trunk' so 'main' never exists
        _init_repo(self.repo, branch="trunk")
        _git(self.repo, "tag", "v1.0.0")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_main_graceful_skip(self):
        off_main = mod.check_tag_reachability(cwd=self.repo)
        self.assertEqual(off_main, [],
                         "no main branch → graceful skip, should not fail")


class TestMixedTagsOnlyOffMainReported(unittest.TestCase):
    """One tag on main, one on a branch tip → only the off-main tag is in the result."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ctr-mixed-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        _git(self.repo, "tag", "v1.0.0")         # on main
        _git(self.repo, "checkout", "-b", "worker/other")
        (self.repo / "extra.txt").write_text("extra\n", encoding="utf-8")
        _git(self.repo, "add", "extra.txt")
        _git(self.repo, "commit", "-q", "-m", "branch commit")
        _git(self.repo, "tag", "v-bad")            # off main

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_only_off_main_tags_reported(self):
        off_main = mod.check_tag_reachability(cwd=self.repo)
        tags = [t for t, _ in off_main]
        self.assertIn("v-bad", tags)
        self.assertNotIn("v1.0.0", tags)


if __name__ == "__main__":
    unittest.main()
