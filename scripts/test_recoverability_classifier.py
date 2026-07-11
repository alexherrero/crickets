#!/usr/bin/env python3
"""Tests for src/developer-safety/scripts/recoverability_classifier.py
(R2.2 / PLAN-r2-enforcement-and-sync task 4).

One test per named scenario in the recoverability doctrine's own examples
table (skills/recoverability/SKILL.md). Each fixture builds a REAL scratch
git repo (+ a bare "remote") and exercises the classifier against it — no
mocking of git itself.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
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
        # Pin the initial branch name explicitly rather than relying on the
        # environment's `init.defaultBranch` (still "master" unless a global
        # gitconfig overrides it — this repo's own dev machines commonly do,
        # CI runners commonly don't). TestPushCLI's fixtures push to a
        # hardcoded `refs/heads/main` and then resolve "the current branch"
        # to default the remote-branch name; if the local branch isn't
        # actually named "main", that resolution silently targets the wrong
        # remote ref, `ls-remote` finds nothing, and `classify_push` gets a
        # `remote_sha=None` it reads as "brand-new push" — RECOVERABLE — even
        # when the real answer is NEEDS_JUDGMENT. Symbolic-ref before the
        # first commit sets this deterministically on every git version/config.
        _git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
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


class TestPushCLI(_GitFixture):
    """The `push` CLI (CONS-2 task 8) is the actual mechanism the
    `recoverability` skill's push-classification guidance now invokes — these
    exercise `rc.main()` end-to-end (real repo, real subprocess-level git
    resolution of branch/remote SHAs), not just the library function it
    wraps, since the resolution logic itself (current-branch lookup,
    `ls-remote` parsing) has no coverage anywhere else."""

    def _run(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = rc.main(list(argv))
        return exit_code, buf.getvalue().strip()

    def test_brand_new_branch_push_is_recoverable_exit_0(self) -> None:
        _commit(self.repo, "a.txt", "1")
        exit_code, out = self._run("push", "--repo", str(self.repo))
        self.assertEqual(exit_code, 0)
        self.assertEqual(out, "recoverable")

    def test_fast_forward_push_is_recoverable_exit_0(self) -> None:
        _commit(self.repo, "a.txt", "1")
        _git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        _commit(self.repo, "b.txt", "2")
        exit_code, out = self._run("push", "--repo", str(self.repo))
        self.assertEqual(exit_code, 0)
        self.assertEqual(out, "recoverable")

    def test_history_rewriting_push_needs_judgment_exit_2(self) -> None:
        _commit(self.repo, "a.txt", "1")
        _git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        (self.repo / "a.txt").write_text("1-amended", encoding="utf-8")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "--amend", "-m", "amend a.txt")
        exit_code, out = self._run("push", "--repo", str(self.repo))
        self.assertEqual(exit_code, 2)
        self.assertEqual(out, "needs-judgment")

    def test_detached_head_without_branch_flag_is_usage_error_exit_3(self) -> None:
        _commit(self.repo, "a.txt", "1")
        _git(self.repo, "checkout", "-q", "--detach")
        exit_code, out = self._run("push", "--repo", str(self.repo))
        self.assertEqual(exit_code, 3)
        self.assertEqual(out, "")  # the error goes to stderr, not stdout

    def test_unknown_branch_flag_is_usage_error_exit_3(self) -> None:
        _commit(self.repo, "a.txt", "1")
        exit_code, out = self._run("push", "--repo", str(self.repo), "--branch", "does-not-exist")
        self.assertEqual(exit_code, 3)
        self.assertEqual(out, "")

    def test_explicit_branch_and_remote_branch_flags_are_honored(self) -> None:
        # A fast-forward push from a differently-named local branch onto a
        # differently-named remote branch — proves --branch/--remote-branch
        # aren't just accepted but actually change which SHAs get compared.
        _commit(self.repo, "a.txt", "1")
        _git(self.repo, "branch", "feature")
        _git(self.repo, "push", "-q", "origin", "feature:refs/heads/upstream-name")
        _git(self.repo, "checkout", "-q", "feature")
        _commit(self.repo, "b.txt", "2")
        exit_code, out = self._run(
            "push", "--repo", str(self.repo),
            "--branch", "feature", "--remote-branch", "upstream-name",
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(out, "recoverable")


if __name__ == "__main__":
    unittest.main()
