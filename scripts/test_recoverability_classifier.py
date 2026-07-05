#!/usr/bin/env python3
"""Tests for src/developer-safety/scripts/recoverability_classifier.py
(R2.2 / PLAN-r2-enforcement-and-sync task 4).

One test per named scenario in the recoverability doctrine's own examples
table (skills/recoverability/SKILL.md). Each fixture builds a REAL scratch
git repo (+ a bare "remote") and exercises the classifier against it — no
mocking of git itself.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "developer-safety" / "scripts" / "recoverability_classifier.py"


def _load():
    spec = importlib.util.spec_from_file_location("recoverability_classifier", _SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["recoverability_classifier"] = m
    spec.loader.exec_module(m)
    return m


rc = _load()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result


def _commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"add {name}")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


class _GitFixture(unittest.TestCase):
    """A local repo + a bare 'remote' it can actually push to/from."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.remote = root / "remote.git"
        self.repo = root / "repo"
        self.remote.mkdir()
        self.repo.mkdir()
        _git(self.remote, "init", "-q", "--bare")
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "t@t")
        _git(self.repo, "config", "user.name", "t")
        _git(self.repo, "remote", "add", "origin", str(self.remote))

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestClassifyRefDelete(_GitFixture):
    """Doctrine: 'delete a branch whose tip is still reachable' (recoverable)
    vs. 'sole-ref delete of unmerged work' (unrecoverable)."""

    def test_tip_reachable_from_another_branch_is_recoverable(self) -> None:
        sha = _commit(self.repo, "a.txt", "1")
        _git(self.repo, "branch", "other-ref", sha)  # same commit, a second ref
        verdict = rc.classify_ref_delete(self.repo, sha, exclude_ref="refs/heads/main")
        self.assertEqual(verdict, rc.Verdict.RECOVERABLE)

    def test_sole_ref_delete_of_unmerged_work_is_unrecoverable(self) -> None:
        _commit(self.repo, "a.txt", "1")
        _git(self.repo, "checkout", "-qb", "feature")
        sha = _commit(self.repo, "b.txt", "2")  # only reachable via 'feature'
        verdict = rc.classify_ref_delete(self.repo, sha, exclude_ref="refs/heads/feature")
        self.assertEqual(verdict, rc.Verdict.UNRECOVERABLE)

    def test_malformed_sha_needs_judgment_not_a_crash(self) -> None:
        verdict = rc.classify_ref_delete(self.repo, "not-a-real-sha")
        self.assertEqual(verdict, rc.Verdict.NEEDS_JUDGMENT)


class TestClassifyTagOverwrite(_GitFixture):
    """Doctrine: 'gh release create' / a new tag (recoverable) vs.
    'overwriting an already-published tag' (unrecoverable)."""

    def test_local_only_tag_is_recoverable(self) -> None:
        _commit(self.repo, "a.txt", "1")
        _git(self.repo, "tag", "v1.0.0")
        verdict = rc.classify_tag_overwrite(self.repo, "v1.0.0")
        self.assertEqual(verdict, rc.Verdict.RECOVERABLE)

    def test_published_tag_is_unrecoverable(self) -> None:
        _commit(self.repo, "a.txt", "1")
        _git(self.repo, "tag", "v1.0.0")
        _git(self.repo, "push", "-q", "origin", "refs/tags/v1.0.0")
        verdict = rc.classify_tag_overwrite(self.repo, "v1.0.0")
        self.assertEqual(verdict, rc.Verdict.UNRECOVERABLE)


class TestClassifyPush(_GitFixture):
    """Doctrine: 'git push origin main' (recoverable, fast-forward) vs.
    'git push --force origin main' rewriting published history — the real
    dividing line ("shared" vs "your own") is a judgment call, not a git
    fact, so the classifier must say so rather than guess."""

    def test_brand_new_branch_push_is_recoverable(self) -> None:
        sha = _commit(self.repo, "a.txt", "1")
        verdict = rc.classify_push(self.repo, local_sha=sha, remote_sha=None)
        self.assertEqual(verdict, rc.Verdict.RECOVERABLE)

    def test_fast_forward_push_is_recoverable(self) -> None:
        sha1 = _commit(self.repo, "a.txt", "1")
        _git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        sha2 = _commit(self.repo, "b.txt", "2")  # sha1 is an ancestor of sha2
        verdict = rc.classify_push(self.repo, local_sha=sha2, remote_sha=sha1)
        self.assertEqual(verdict, rc.Verdict.RECOVERABLE)

    def test_history_rewriting_push_needs_judgment(self) -> None:
        # Doctrine names TWO scenarios that both rewrite history — "your own
        # un-shared branch" (recoverable) and "published shared history"
        # (unrecoverable) — and they are INDISTINGUISHABLE from local git
        # state alone (git records no notion of "who else has fetched this").
        # A classifier that guessed either way would be wrong half the time;
        # NEEDS_JUDGMENT is the honest answer for both, which is exactly
        # what "a scenario the doctrine doesn't yet cover [mechanically] is
        # flagged as a gap rather than silently skipped" (task 4's
        # verification bullet) means in practice.
        sha1 = _commit(self.repo, "a.txt", "1")
        _git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        # Rewrite history: amend instead of building on sha1.
        (self.repo / "a.txt").write_text("1-amended", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "--amend", "-m", "amend a.txt")
        sha2 = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(sha1, sha2)

        # This exact (local_sha, remote_sha) pair is what BOTH doctrine
        # scenarios look like from git's side — there is no second call to
        # make with different inputs, because the doctrine's own dividing
        # line (has anyone else fetched this branch?) isn't a git fact at
        # all. NEEDS_JUDGMENT for this input is therefore the only honest
        # answer, for either real-world case it might represent.
        verdict = rc.classify_push(self.repo, local_sha=sha2, remote_sha=sha1)
        self.assertEqual(verdict, rc.Verdict.NEEDS_JUDGMENT,
                         "a history-rewriting push must never be guessed as recoverable or unrecoverable")

    def test_unchanged_tip_is_recoverable(self) -> None:
        sha = _commit(self.repo, "a.txt", "1")
        verdict = rc.classify_push(self.repo, local_sha=sha, remote_sha=sha)
        self.assertEqual(verdict, rc.Verdict.RECOVERABLE)


if __name__ == "__main__":
    unittest.main()
