#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/integrate_worker.py (V5-10 sibling #3).

The coordinator-side keystone that lands a finished `worker/<slug>` branch on the
integration branch, gated on the *merged* tree. Every test builds a throwaway temp
git repo, drives a real `git worktree add` + real merges, and injects a STUB gate
(green or red) — never the real `check-all.sh` (which runs this very suite →
recursion). Both resolution backends are exercised: the standalone `.harness/`
fallback (`resolver=None`) and a planted stub for agentm's verb (`resolver=<path>`).

Load-bearing assertions (Task 1 — merge + gate + rollback core):
  (a) green merge + green gate → an explicit `--no-ff` merge commit on `main`,
      worker commits are ancestors, the worktree is left intact (no prune yet);
  (b) a merge conflict is `git merge --abort`-ed, `main` is back at the pre-merge
      HEAD, the worktree is intact, exit 2;
  (c) green merge + RED gate → `main` hard-reset to the pre-merge HEAD (zero
      commits added), the worktree intact, exit 2, the gate output surfaced;
  (d)-(g) the pre-mutation guards (dirty tree / missing branch / singleton /
      unresolvable plan) refuse loud and mutate nothing.
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


iw = _load("integrate_worker")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=check)


def _init_repo(repo: Path) -> None:
    """A throwaway git repo on `main` with one commit."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


# Stub resolvers standing in for the located agentm verb (the delegate backend).
_STUB_OK = (
    "import sys\n"
    "sys.stdout.write('/v/_harness/PLAN-foo.md\\t/v/_harness/progress-foo.md\\n')\n"
    "sys.exit(0)\n"
)
_STUB_SKIP = (
    "import sys\n"
    "sys.stderr.write('[resolver] no resolvable _harness/\\n')\n"
    "sys.exit(1)\n"
)
_STUB_REFUSE = (
    "import sys\n"
    "sys.stderr.write('[resolver] dangling active-plan marker\\n')\n"
    "sys.exit(2)\n"
)


def _green_gate(root):
    return (0, "stub gate: all green\n")


def _red_gate(root):
    return (2, "stub gate: 3 unit tests failed\nFAILED (failures=3)\n")


def _add_worker(repo: Path, tmp: Path, slug: str = "foo", *, ahead: bool = True) -> tuple[str, Path]:
    """Create a real `worker/<slug>` branch + worktree; optionally one commit ahead."""
    branch = f"worker/{slug}"
    wt = tmp / f"wt-{slug}"
    _git(repo, "worktree", "add", "-b", branch, str(wt))
    if ahead:
        (wt / f"worker-{slug}.txt").write_text("work\n", encoding="utf-8")
        _git(wt, "add", ".")
        _git(wt, "commit", "-q", "-m", f"worker {slug} work")
    return branch, wt


def _parents(repo: Path) -> list[str]:
    out = _git(repo, "rev-list", "--parents", "-n", "1", "HEAD").stdout.split()
    return out[1:]  # drop the commit's own sha; what remains are its parents


class TestIntegrateHappyPath(unittest.TestCase):
    """(a) green merge + green gate → a --no-ff merge commit; worktree left intact."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-happy-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_green_merge_and_gate_creates_no_ff_merge_commit(self):
        branch, wt = _add_worker(self.repo, self.tmp)
        worker_tip = _git(self.repo, "rev-parse", branch).stdout.strip()
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        self.assertIn("merged worker/foo into main", out)

        # HEAD advanced to an explicit merge commit (two parents: old main + worker).
        parents = _parents(self.repo)
        self.assertEqual(len(parents), 2, "a --no-ff merge must have two parents")
        self.assertIn(pre, parents)
        self.assertIn(worker_tip, parents)
        # The worker's commit is now an ancestor of main.
        anc = _git(self.repo, "merge-base", "--is-ancestor", worker_tip, "HEAD", check=False)
        self.assertEqual(anc.returncode, 0, "worker commits must be ancestors of main")
        # Task 1 does NOT prune — the worktree + branch are left intact.
        self.assertTrue(wt.is_dir())
        self.assertIsNotNone(iw._find_worktree_for_branch(self.repo, branch))
        self.assertTrue(iw._branch_exists(self.repo, branch))


class TestIntegrateConflict(unittest.TestCase):
    """(b) a merge conflict aborts, restores main to pre-merge HEAD, worktree intact."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-conflict-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_conflict_aborts_and_restores(self):
        branch, wt = _add_worker(self.repo, self.tmp, ahead=False)
        # Divergent edits to the SAME file → a guaranteed merge conflict.
        (wt / "README.md").write_text("worker change\n", encoding="utf-8")
        _git(wt, "commit", "-q", "-am", "worker edits README")
        (self.repo / "README.md").write_text("main change\n", encoding="utf-8")
        _git(self.repo, "commit", "-q", "-am", "main edits README")
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("conflicts with", err)
        # main is back at the pre-merge HEAD; no merge in progress.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)
        self.assertFalse(iw._merge_in_progress(self.repo))
        # The working tree was restored (README is main's version, no markers).
        self.assertEqual((self.repo / "README.md").read_text(encoding="utf-8"), "main change\n")
        # The worktree is intact for the operator to resolve + re-run.
        self.assertTrue(wt.is_dir())
        self.assertTrue(iw._branch_exists(self.repo, branch))


class TestIntegrateRedGate(unittest.TestCase):
    """(c) green merge + RED gate → hard-reset to pre-merge HEAD, zero commits added."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-red-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_red_gate_rolls_back_merge(self):
        branch, wt = _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        count_before = _git(self.repo, "rev-list", "--count", "HEAD").stdout.strip()

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_red_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("integration gate FAILED", err)
        self.assertIn("stub gate: 3 unit tests failed", err)  # gate output surfaced
        # main hard-reset to the pre-merge HEAD — zero commits added.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)
        self.assertEqual(_git(self.repo, "rev-list", "--count", "HEAD").stdout.strip(),
                         count_before)
        self.assertFalse(iw._merge_in_progress(self.repo))
        # The worktree is intact.
        self.assertTrue(wt.is_dir())
        self.assertTrue(iw._branch_exists(self.repo, branch))

    def test_gate_that_raises_is_treated_as_red(self):
        branch, wt = _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        def boom_gate(root):
            raise RuntimeError("gate process crashed")

        rc, out, err = iw.integrate("foo", str(self.repo), gate=boom_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("integration gate FAILED", err)
        # A raising gate must still roll the merge back — never leave it unverified.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)
        self.assertTrue(wt.is_dir())


class TestIntegrateGuards(unittest.TestCase):
    """(d)-(g) pre-mutation guards refuse loud and mutate nothing."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-guard-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dirty_integration_branch_refused(self):
        branch, _wt = _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "README.md").write_text("uncommitted change\n", encoding="utf-8")  # dirty

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("dirty working tree", err)
        # No merge happened — HEAD unchanged.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)

    def test_missing_branch_refused(self):
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("no worker branch", err)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)

    def test_branch_without_worktree_refused(self):
        # A branch with no live worktree (e.g. an already-pruned one) is refused.
        _git(self.repo, "branch", "worker/foo")
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("no worktree", err)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)

    def test_singleton_and_empty_names_refused(self):
        for form in ("", "   ", "PLAN", "PLAN.md"):
            with self.subTest(form=form):
                rc, out, err = iw.integrate(form, str(self.repo), gate=_green_gate, resolver=None)
                self.assertEqual(rc, 2, form)
                self.assertEqual(out, "", form)
                self.assertIn("named plan", err)

    def test_unsafe_slug_propagates_resolver_refusal_no_git_touched(self):
        # resolve runs first; an unsafe slug makes the `.harness/` fallback refuse
        # (exit 2 "unsafe plan name"), which propagates — and nothing in git is touched.
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        rc, out, err = iw.integrate("../evil", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("unsafe plan name", err)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)


class TestIntegrateDelegateBackend(unittest.TestCase):
    """The located resolver (agentm stub) is authoritative — it gates the integrate."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-delegate-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_resolver_ok_allows_integrate(self):
        _add_worker(self.repo, self.tmp)
        stub = _write_stub(self.tmp / "stub_ok.py", _STUB_OK)
        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=stub)
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(_parents(self.repo)), 2)

    def test_resolver_graceful_skip_propagates_rc1_no_merge(self):
        _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        stub = _write_stub(self.tmp / "stub_skip.py", _STUB_SKIP)
        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=stub)
        self.assertEqual(rc, 1)  # graceful-skip propagated, not flattened to 2
        self.assertEqual(out, "")
        self.assertIn("no resolvable", err)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)

    def test_resolver_refusal_propagates_rc2_no_merge(self):
        _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        stub = _write_stub(self.tmp / "stub_refuse.py", _STUB_REFUSE)
        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=stub)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("dangling", err)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)


class TestIntegrateMergeRaises(unittest.TestCase):
    """A raising `_git` mid-merge (a >30s hang → TimeoutExpired) rolls back, no crash."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-mergeraise-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_merge_timeout_rolls_back(self):
        _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        orig_git = iw._git

        def hang_on_merge(args, root):
            if args[:1] == ["merge"] and args[:2] != ["merge", "--abort"]:
                raise subprocess.TimeoutExpired(cmd="git merge", timeout=30)
            return orig_git(args, root)

        with mock.patch.object(iw, "_git", hang_on_merge):
            rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("raised", err)
        # No crash; main restored to pre-merge HEAD.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)


class TestMainCLI(unittest.TestCase):
    """End-to-end main() over the fallback backend with the REAL default gate."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-main-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        self._saved = iw.resolve_plan.locate_resolver
        iw.resolve_plan.locate_resolver = lambda **_k: None

    def tearDown(self):
        iw.resolve_plan.locate_resolver = self._saved
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = iw.main(["integrate_worker.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_main_missing_gate_script_treated_as_red_rolls_back(self):
        # main() wires the real `_check_all_gate`; a temp repo has no
        # scripts/check-all.sh, so the gate returns rc 127 (fail-safe → red) and the
        # merge is rolled back. This proves the default-gate wiring + rollback path
        # without recursing into the real battery.
        _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        rc, out, err = self._run("foo", "--project-root", str(self.repo))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("gate script not found", err)
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)

    def test_main_singleton_nonzero(self):
        rc, out, err = self._run("PLAN", "--project-root", str(self.repo))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("named plan", err)


if __name__ == "__main__":
    unittest.main()
