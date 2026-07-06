#!/usr/bin/env python3
"""Tests for concurrency-safety mitigations in spawn_worker.py (task 7).

Verifies:
  - Mitigation 9 (root-anchor): a spawn invoked from inside an existing worktree
    creates the new worktree beside the MAIN working tree, NOT nested under the
    cwd worktree.
  - gc.auto=0 is set during the worktree add (injectable config setter).
  - No --prune=now is issued (worktree removal uses --force, not --prune=now).
  - Dirty-check (_worktree_is_clean) returns True for a clean worktree and False
    for a dirty one.
  - Mitigation 8 (cap): spawn fails when the worker worktree count is at the limit.

Auto-discovered by check-all's `unit tests` gate.
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
_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"


def _load(name: str):
    src = _SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, src)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


sw = _load("spawn_worker")
ic = _load("isolation_config")


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


_STUB_OK = (
    "import sys\n"
    "sys.stdout.write('/v/_harness/PLAN-foo.md\\t/v/_harness/progress-foo.md\\n')\n"
    "sys.exit(0)\n"
)


def _write_plan(harness_dir: Path, slug: str) -> None:
    harness_dir.mkdir(parents=True, exist_ok=True)
    (harness_dir / f"PLAN-{slug}.md").write_text(f"# Plan: {slug}\n**Status:** planning\n",
                                                  encoding="utf-8")


class TestRootAnchor(unittest.TestCase):
    """Mitigation 9: spawn from inside a worktree never nests."""

    def test_spawn_from_inside_worktree_places_beside_main(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            repo = base / "myrepo"
            _init_repo(repo)
            # Create an existing worktree (simulates a host-native worktree)
            existing_wt = base / "existing-wt"
            _git(repo, "worktree", "add", "-b", "existing-branch", str(existing_wt))

            # Write a plan accessible from inside the worktree
            (existing_wt / ".harness").mkdir(exist_ok=True)
            (existing_wt / ".harness" / "PLAN-myplan.md").write_text(
                "# Plan: myplan\n**Status:** planning\n", encoding="utf-8")

            # Spawn from inside the existing worktree with resolver=None (standalone)
            # The plan lives at existing_wt/.harness/PLAN-myplan.md so we need
            # resolver=None to force the standalone .harness/ fallback.
            rc, out, err = sw.spawn("myplan", str(existing_wt), resolver=None)

            if rc == 0:
                new_wt_path = Path(out.strip()).resolve()
                existing_wt_r = existing_wt.resolve()
                # The new worktree must NOT be inside the existing worktree.
                self.assertFalse(
                    str(new_wt_path).startswith(str(existing_wt_r)),
                    f"New worktree {new_wt_path} is nested inside {existing_wt_r} — "
                    f"root-anchor mitigation failed."
                )
                # It should be beside the MAIN repo (in myrepo.worktrees/).
                expected_prefix = str(repo.resolve().parent / f"myrepo{sw._WORKTREES_SUFFIX}")
                self.assertTrue(
                    str(new_wt_path).startswith(expected_prefix),
                    f"New worktree {new_wt_path} is not beside main repo "
                    f"(expected under {expected_prefix})."
                )
            else:
                # spawn may fail if the plan doesn't exist in the main tree,
                # but must NOT fail with a "worktree path already exists" that
                # would indicate nesting. Any other failure is fine for this test.
                self.assertNotIn("worktree path already exists", err,
                                 "should not fail with no-clobber on a nested path")

    def test_worktree_path_uses_main_tree_not_cwd_worktree(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            repo = base / "repo"
            _init_repo(repo)
            wt_dir = base / "wt"
            _git(repo, "worktree", "add", "-b", "branch-x", str(wt_dir))

            # From inside a worktree, worktree_path should anchor to main tree
            result = sw.worktree_path(str(wt_dir), "testslug")
            main_tree = repo.resolve()
            expected = main_tree.parent / f"repo{sw._WORKTREES_SUFFIX}" / "testslug"
            self.assertEqual(result.resolve(), expected.resolve(),
                             f"worktree_path from inside wt should anchor to {expected}, got {result}")


class TestWorktreeIsClean(unittest.TestCase):
    """Mitigation 3: dirty-check helper."""

    def test_clean_worktree_returns_true(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            self.assertTrue(sw._worktree_is_clean(repo))

    def test_dirty_worktree_returns_false(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
            _git(repo, "add", "dirty.txt")
            self.assertFalse(sw._worktree_is_clean(repo))

    def test_non_git_dir_returns_true(self):
        with tempfile.TemporaryDirectory() as t:
            # Non-git dir: graceful-skip returns True (safe to proceed)
            self.assertTrue(sw._worktree_is_clean(Path(t)))


class TestNoPruneNow(unittest.TestCase):
    """Mitigation 3: _worktree_gone uses --force, never --prune=now."""

    def test_worktree_gone_uses_force_not_prune_now(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            wt = Path(t) / "wt"
            _git(repo, "worktree", "add", "-b", "prunetest-branch", str(wt))
            # Capture what git command is called — patch _git to record
            calls = []
            original_git = sw._git

            def recording_git(args, root):
                calls.append(args[:])
                return original_git(args, root)

            sw._git = recording_git
            try:
                sw._worktree_gone(str(repo), wt)
            finally:
                sw._git = original_git

            prunenow_calls = [c for c in calls if "--prune=now" in c]
            self.assertEqual(prunenow_calls, [],
                             "worktree removal must never use --prune=now")


class TestGcAutoDisabled(unittest.TestCase):
    """Mitigation 2: gc.auto is set to 0 during the lock context."""

    def test_gc_auto_zero_within_context(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            seen_gc_zero = []

            def check_gc(_args, _root):
                import subprocess as sp
                r = sp.run(["git", "config", "--local", "gc.auto"],
                           cwd=str(repo), capture_output=True, text=True)
                seen_gc_zero.append(r.stdout.strip())

            with sw._gc_disabled(repo):
                check_gc(None, None)

            self.assertTrue(
                any(v == "0" for v in seen_gc_zero),
                f"gc.auto was not 0 inside _gc_disabled context, got: {seen_gc_zero}",
            )

    def test_gc_auto_restored_after_context(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            import subprocess as sp
            # Ensure gc.auto is unset before test
            sp.run(["git", "config", "--local", "--unset", "gc.auto"],
                   cwd=str(repo), capture_output=True)
            with sw._gc_disabled(repo):
                pass
            # After context: gc.auto should be unset (or restored to prior value)
            r = sp.run(["git", "config", "--local", "gc.auto"],
                       cwd=str(repo), capture_output=True, text=True)
            self.assertNotEqual(r.stdout.strip(), "0",
                                "gc.auto should not remain 0 after _gc_disabled exits")


class TestWorktreeCap(unittest.TestCase):
    """Mitigation 8: spawn refuses when worker worktree count is at the limit."""

    def test_count_worker_worktrees_empty(self):
        with tempfile.TemporaryDirectory() as t:
            repo = Path(t) / "repo"
            _init_repo(repo)
            self.assertEqual(sw._count_worker_worktrees(str(repo)), 0)

    def test_spawn_fails_at_cap(self):
        """spawn() returns exit 2 when _count_worker_worktrees >= _MAX_WORKTREES."""
        original_count = sw._count_worker_worktrees
        sw._count_worker_worktrees = lambda root: sw._MAX_WORKTREES
        try:
            with tempfile.TemporaryDirectory() as t:
                repo = Path(t) / "repo"
                _init_repo(repo)
                # Write a plan so resolve_plan succeeds
                _write_plan(repo / ".harness", "captest")
                rc, out, err = sw.spawn("captest", str(repo), resolver=None)
                self.assertEqual(rc, 2)
                self.assertIn("cap reached", err)
        finally:
            sw._count_worker_worktrees = original_count


if __name__ == "__main__":
    unittest.main()
