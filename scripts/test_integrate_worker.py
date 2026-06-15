#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/integrate_worker.py (V5-10 sibling #3).

The coordinator-side keystone that lands a finished `worker/<slug>` branch on the
integration branch, gated on the *merged* tree. Every test builds a throwaway temp
git repo, drives a real `git worktree add` + real merges, and injects a STUB gate
(green or red) — never the real `check-all.sh` (which runs this very suite →
recursion). Both resolution backends are exercised: the standalone `.harness/`
fallback (`resolver=None`) and a planted stub for agentm's verb (`resolver=<path>`).

Load-bearing assertions:
  Task 1 — merge + gate + rollback core:
    (b) a merge conflict is `git merge --abort`-ed, `main` is back at the pre-merge
        HEAD, the worktree is intact, exit 2;
    (c) green merge + RED gate → `main` hard-reset to the pre-merge HEAD (zero
        commits added), the worktree intact, exit 2, the gate output surfaced;
    (d)-(g) the pre-mutation guards (dirty tree / missing branch / singleton /
        unresolvable plan) refuse loud and mutate nothing.
  Task 2 — green-path consolidation (promote + prune):
    (a) green merge + green gate → an explicit `--no-ff` merge commit on `main`,
        worker commits are ancestors, the worker's `progress-<slug>.md` is folded
        (additive) into mainline `progress.md` + an integration record line, and
        the worktree + now-merged branch are pruned; rc 0;
    promotion is additive (named file kept) and runs BEFORE prune; a forced prune
    failure leaves the merge + promotion intact and reports the survivor (rc 0).
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
    """A throwaway git repo on `main` with one commit.

    `.harness/` is gitignored — mirroring the real project (its `.harness/` is
    gitignored, the vault `_harness/` lives outside the repo). This keeps a seeded
    `.harness/progress*.md` from dirtying the tree and tripping the clean-tree
    guard in the `resolver=None` promotion tests.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".harness/\n", encoding="utf-8")
    _git(repo, "add", "README.md", ".gitignore")
    _git(repo, "commit", "-q", "-m", "seed")


def _seed_progress(harness: Path, *, worker: str | None, mainline: str) -> Path:
    """Plant a worker `progress-foo.md` (unless None) + a mainline `progress.md`.

    Returns the mainline path. `harness` is the dir the resolver maps to — the
    repo's `.harness/` for the `resolver=None` fallback, or an out-of-repo vault
    for the delegate stub.
    """
    harness.mkdir(parents=True, exist_ok=True)
    if worker is not None:
        (harness / "progress-foo.md").write_text(worker, encoding="utf-8")
    mainline_path = harness / "progress.md"
    mainline_path.write_text(mainline, encoding="utf-8")
    return mainline_path


def _dyn_stub(path: Path, harness: Path) -> Path:
    """A delegate-backend stub that maps name → a pair under `harness` (out-of-repo).

    Unlike a static stub, it honors the `--plan <name>` the bridge passes, so
    `resolve('foo')` → `progress-foo.md` and `resolve('')` (the mainline lookup in
    `_promote`) → `progress.md`. Mirrors `resolve_plan`'s naming so promotion
    resolves the right two files through the delegate path, not just the fallback.
    """
    body = (
        "import sys\n"
        "from pathlib import Path\n"
        f"H = Path(r{str(harness)!r})\n"
        "a = sys.argv\n"
        "name = a[a.index('--plan') + 1] if '--plan' in a else ''\n"
        "s = name\n"
        "if s.endswith('.md'): s = s[:-3]\n"
        "if s.startswith('PLAN-'): s = s[5:]\n"
        "if s in ('', 'PLAN'):\n"
        "    plan, prog = 'PLAN.md', 'progress.md'\n"
        "else:\n"
        "    plan, prog = 'PLAN-' + s + '.md', 'progress-' + s + '.md'\n"
        "sys.stdout.write(str(H / plan) + chr(9) + str(H / prog) + chr(10))\n"
        "sys.exit(0)\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def _write_stub(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


# Stub resolvers standing in for the located agentm verb (the delegate backend).
# The rc-0 case uses the dynamic `_dyn_stub` (name-aware, out-of-repo paths); the
# skip/refuse cases are static — they never reach promotion.
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
    """(a) green merge + green gate → a --no-ff merge commit, progress promoted, pruned."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-happy-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        # The `resolver=None` fallback maps to the repo's (gitignored) `.harness/`.
        self.mainline = _seed_progress(
            self.repo / ".harness",
            worker="2026-06-13 10:00 /work — completed task 1 in the worker\n",
            mainline="2026-06-13 09:00 /plan — created plan\n",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_green_merge_promotes_progress_and_prunes(self):
        branch, wt = _add_worker(self.repo, self.tmp)
        worker_tip = _git(self.repo, "rev-parse", branch).stdout.strip()
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "", "a fully clean green path emits no warnings")
        self.assertIn("merged worker/foo into main", out)

        # HEAD advanced to an explicit merge commit (two parents: old main + worker).
        parents = _parents(self.repo)
        self.assertEqual(len(parents), 2, "a --no-ff merge must have two parents")
        self.assertIn(pre, parents)
        self.assertIn(worker_tip, parents)
        # The worker's commit is now an ancestor of main.
        anc = _git(self.repo, "merge-base", "--is-ancestor", worker_tip, "HEAD", check=False)
        self.assertEqual(anc.returncode, 0, "worker commits must be ancestors of main")

        # Promotion (additive): mainline progress gained the worker's line + the
        # integration record, and the named worker file is KEPT.
        body = self.mainline.read_text(encoding="utf-8")
        self.assertIn("2026-06-13 09:00 /plan — created plan", body)  # original mainline
        self.assertIn("/work — completed task 1 in the worker", body)  # worker's content
        self.assertIn("/integrate-worker — merged worker/foo", body)  # the record
        self.assertTrue((self.repo / ".harness" / "progress-foo.md").is_file(),
                        "promotion is additive — the named file is kept")
        self.assertIn("Promoted the worker's progress", out)

        # Prune: the worktree is gone and the now-merged branch is deleted.
        self.assertFalse(wt.exists())
        self.assertIsNone(iw._find_worktree_for_branch(self.repo, branch))
        self.assertFalse(iw._branch_exists(self.repo, branch))
        self.assertIn("Pruned the worktree", out)


class TestIntegrateConsolidation(unittest.TestCase):
    """Task 2 green-path consolidation: promote-before-prune, additive, fault-tolerant."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-consol-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_promote_runs_before_prune(self):
        # The order matters: promotion reads the worker's progress, prune removes
        # its worktree. Promote MUST run first. Spy on both, preserving behavior.
        _seed_progress(self.repo / ".harness", worker="w\n", mainline="m\n")
        _add_worker(self.repo, self.tmp)
        calls = []
        orig_promote, orig_prune = iw._promote, iw._prune

        def spy_promote(*a, **k):
            calls.append("promote")
            return orig_promote(*a, **k)

        def spy_prune(*a, **k):
            calls.append("prune")
            return orig_prune(*a, **k)

        with mock.patch.object(iw, "_promote", spy_promote), \
             mock.patch.object(iw, "_prune", spy_prune):
            rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(calls, ["promote", "prune"])

    def test_forced_prune_failure_keeps_merge_and_promotion(self):
        # A prune that can't remove the worktree must NOT undo the verified merge
        # or the promotion — it reports the survivor on stderr and returns rc 0.
        mainline = _seed_progress(self.repo / ".harness", worker="worker work\n",
                                  mainline="seed\n")
        branch, wt = _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        with mock.patch.object(iw.spawn_worker, "_worktree_gone", lambda root, w: False):
            rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 0, err)  # merge stands despite the prune failure
        # The merge happened (HEAD moved past pre to a two-parent commit).
        self.assertNotEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)
        self.assertEqual(len(_parents(self.repo)), 2)
        # Promotion still landed.
        self.assertIn("worker work", mainline.read_text(encoding="utf-8"))
        self.assertIn("Promoted the worker's progress", out)
        # The survivor is reported on stderr for manual cleanup.
        self.assertIn("prune incomplete", err)
        self.assertIn("worker/foo", err)

    def test_promotion_when_named_progress_absent_appends_only_the_record(self):
        # No worker `progress-foo.md` → promotion appends ONLY its own record line,
        # never crashes, merge + prune still succeed.
        mainline = _seed_progress(self.repo / ".harness", worker=None, mainline="seed only\n")
        branch, wt = _add_worker(self.repo, self.tmp)

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 0, err)
        body = mainline.read_text(encoding="utf-8")
        self.assertIn("seed only", body)
        self.assertIn("/integrate-worker — merged worker/foo", body)
        self.assertFalse(wt.exists())
        self.assertFalse(iw._branch_exists(self.repo, branch))


class TestIntegratePromotionNewline(unittest.TestCase):
    """Regression: promotion must not fuse records onto a newline-less mainline.

    `_promote` appends the worker chunk + an integration record in append mode. If
    the pre-existing `progress.md` does not end in a newline (printf, heredocs, many
    editors leave it that way), the first appended byte lands mid-line and glues two
    records into one. The append must emit a leading newline iff the existing file is
    non-empty and unterminated — symmetric to the trailing-newline normalization the
    worker chunk already gets. Both branches are covered: a worker chunk present, and
    no worker file (the bare integration record). Fails against the pre-fix code.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-nl-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_newlineless_mainline_with_worker_chunk_does_not_fuse(self):
        last = "2026-06-13 09:00 /plan — created plan"
        # No trailing newline on the mainline — the production trigger.
        mainline = _seed_progress(
            self.repo / ".harness",
            worker="2026-06-13 10:00 /work — task 1 done\n",
            mainline=f"# Mainline progress\n{last}",
        )
        _add_worker(self.repo, self.tmp)

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 0, err)
        body = mainline.read_text(encoding="utf-8")
        lines = body.split("\n")
        # The pre-existing last record survives as its OWN complete line (not fused).
        self.assertIn(last, lines)
        # The worker's record is its own complete line too.
        self.assertIn("2026-06-13 10:00 /work — task 1 done", lines)
        # And the integration record landed on its own line.
        self.assertTrue(any("/integrate-worker — merged worker/foo" in ln for ln in lines))
        # The smoking gun: the two records were never glued.
        self.assertNotIn(f"{last}2026-06-13 10:00", body)

    def test_newlineless_mainline_without_worker_chunk_does_not_fuse(self):
        last = "2026-06-13 09:00 /plan — created plan"
        mainline = _seed_progress(
            self.repo / ".harness",
            worker=None,  # no worker progress file → the bare integration record
            mainline=f"# Mainline progress\n{last}",
        )
        _add_worker(self.repo, self.tmp)

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=None)
        self.assertEqual(rc, 0, err)
        body = mainline.read_text(encoding="utf-8")
        lines = body.split("\n")
        # The pre-existing record is intact on its own line.
        self.assertIn(last, lines)
        # The integration record is a separate line, not fused onto `created plan`.
        self.assertTrue(any("/integrate-worker — merged worker/foo" in ln for ln in lines))
        self.assertFalse(any(ln.startswith(last) and "/integrate-worker" in ln for ln in lines),
                         "the integration record must not be glued onto the last record")


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
        # The delegate backend resolves to an OUT-OF-REPO vault (not the repo's
        # `.harness/`), so promotion writes there — proving `_promote` honors the
        # injected resolver, not a hard-coded fallback.
        vault = self.tmp / "vault"
        mainline = _seed_progress(vault, worker="worker delegate line\n",
                                  mainline="mainline delegate seed\n")
        stub = _dyn_stub(self.tmp / "stub_ok.py", vault)
        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate, resolver=stub)
        self.assertEqual(rc, 0, err)
        self.assertEqual(len(_parents(self.repo)), 2)
        # Promotion resolved + appended through the delegate path.
        body = mainline.read_text(encoding="utf-8")
        self.assertIn("worker delegate line", body)
        self.assertIn("/integrate-worker — merged worker/foo", body)

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


class TestIntegratePrepare(unittest.TestCase):
    """ADR 0030: the artifact-prepare step runs on the merged tree BEFORE the gate.

    The single-writer integrator bumps the deferred version(s) + regenerates the
    shared registry between the merge and the gate. A prepare that fails (or
    raises) rolls the merge back exactly like a red gate — a half-applied bump
    must never land. The production default (`_artifact_prepare`) runs the
    project's `scripts/integrate-prepare.sh` if present, else no-ops (rc 0) so the
    pre-Model-A flow is unchanged.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-prep-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_prepare_runs_on_merged_tree_before_gate(self):
        # The prepare writes a file on the merged tree + commits; the gate then
        # asserts that file is present — proving prepare ran first, on the merged
        # tree, and its commit is part of what the gate sees.
        _seed_progress(self.repo / ".harness", worker="w\n", mainline="m\n")
        _add_worker(self.repo, self.tmp)
        order = []

        def committing_prepare(root, pre_sha):
            order.append("prepare")
            (Path(root) / "BUMPED.txt").write_text("bumped\n", encoding="utf-8")
            _git(Path(root), "add", "BUMPED.txt")
            _git(Path(root), "commit", "-q", "-m", "chore: bump (stub prepare)")
            return (0, "[stub prepare] bumped\n")

        def asserting_gate(root):
            order.append("gate")
            present = (Path(root) / "BUMPED.txt").is_file()
            return (0 if present else 1, f"gate saw BUMPED.txt={present}\n")

        rc, out, err = iw.integrate("foo", str(self.repo), gate=asserting_gate,
                                    prepare=committing_prepare, resolver=None)
        self.assertEqual(rc, 0, err)
        self.assertEqual(order, ["prepare", "gate"], "prepare must run before the gate")
        # The prepare's commit is on main (its file survives in the working tree).
        self.assertTrue((self.repo / "BUMPED.txt").is_file())
        self.assertIn("chore: bump (stub prepare)", _git(self.repo, "log", "--oneline").stdout)

    def test_failing_prepare_rolls_back_and_skips_gate(self):
        _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        gate_called = []

        def red_prepare(root, pre_sha):
            return (3, "[stub prepare] bump failed: garbage version\n")

        def tracking_gate(root):
            gate_called.append(True)
            return (0, "should not run\n")

        rc, out, err = iw.integrate("foo", str(self.repo), gate=tracking_gate,
                                    prepare=red_prepare, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("artifact-prepare FAILED", err)
        self.assertIn("bump failed", err)  # the prepare output is surfaced
        self.assertEqual(gate_called, [], "the gate must NOT run after a failed prepare")
        # main hard-reset to the pre-merge HEAD — zero commits added.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)
        self.assertFalse(iw._merge_in_progress(self.repo))
        # The worktree + branch are intact for the operator to inspect.
        self.assertTrue((self.tmp / "wt-foo").is_dir())
        self.assertTrue(iw._branch_exists(self.repo, "worker/foo"))

    def test_prepare_that_raises_is_treated_as_red(self):
        _add_worker(self.repo, self.tmp)
        pre = _git(self.repo, "rev-parse", "HEAD").stdout.strip()

        def boom_prepare(root, pre_sha):
            raise RuntimeError("prepare process crashed")

        rc, out, err = iw.integrate("foo", str(self.repo), gate=_green_gate,
                                    prepare=boom_prepare, resolver=None)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("artifact-prepare", err)
        # Rolled back, worktree intact — a raising prepare never leaves a merge.
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), pre)
        self.assertTrue((self.tmp / "wt-foo").is_dir())

    def test_default_prepare_no_ops_without_script(self):
        # _artifact_prepare is the production default; a repo with no
        # scripts/integrate-prepare.sh must no-op (rc 0) so the pre-Model-A flow
        # (and every gate-only test) is unchanged.
        rc, out = iw._artifact_prepare(str(self.repo), "deadbeef")
        self.assertEqual(rc, 0)
        self.assertIn("no artifact-prepare step", out)

    def test_default_prepare_runs_present_script_with_pre_sha(self):
        scripts = self.repo / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        # A stub prepare script echoes its $1 (the pre-merge SHA) + exits 0.
        # write_bytes (not write_text): a .sh must be LF — write_text's default
        # CRLF translation on Windows would turn `exit 0` into `exit 0\r`, which
        # bash rejects as a non-numeric arg. Bytes are written verbatim.
        (scripts / "integrate-prepare.sh").write_bytes(
            b'#!/usr/bin/env bash\necho "prepare ran with sha=$1"\nexit 0\n')
        rc, out = iw._artifact_prepare(str(self.repo), "abc123")
        self.assertEqual(rc, 0, out)
        self.assertIn("prepare ran with sha=abc123", out)

    def test_default_prepare_surfaces_script_failure(self):
        scripts = self.repo / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "integrate-prepare.sh").write_bytes(
            b"#!/usr/bin/env bash\necho 'boom' >&2\nexit 7\n")
        rc, out = iw._artifact_prepare(str(self.repo), "abc123")
        self.assertEqual(rc, 7)
        self.assertIn("boom", out)


class TestPosixBashResolver(unittest.TestCase):
    """`_posix_bash` must dodge the Windows WSL `bash.exe` stub (CI regression).

    The GitHub windows-2025 runner puts `C:\\Windows\\System32\\bash.exe` (the WSL
    launcher) on PATH; with no distro installed it exits 1 ("no installed
    distributions"), which spuriously reddened the gate/prepare. The resolver
    prefers Git-for-Windows bash. `name`/`candidates`/`which` are injected so this
    branch is exercised on any host.
    """

    def test_posix_host_returns_plain_bash(self):
        self.assertEqual(iw._posix_bash(name="posix"), "bash")

    def test_windows_prefers_existing_git_bash_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / "bash.exe"
            real.write_text("", encoding="utf-8")
            got = iw._posix_bash(name="nt", candidates=(str(real),),
                                 which=lambda _n: r"C:\Windows\System32\bash.exe")
            self.assertEqual(got, str(real))

    def test_windows_skips_system32_wsl_stub_from_path(self):
        # No Git candidate exists; PATH lookup yields the WSL stub → reject it.
        got = iw._posix_bash(name="nt", candidates=(),
                             which=lambda _n: r"C:\Windows\System32\bash.exe")
        self.assertEqual(got, "bash")

    def test_windows_accepts_non_system32_path_bash(self):
        got = iw._posix_bash(name="nt", candidates=(),
                             which=lambda _n: r"C:\tools\msys64\usr\bin\bash.exe")
        self.assertEqual(got, r"C:\tools\msys64\usr\bin\bash.exe")

    def test_windows_falls_back_to_bash_when_nothing_found(self):
        got = iw._posix_bash(name="nt", candidates=(), which=lambda _n: None)
        self.assertEqual(got, "bash")


class TestIntegrateSerializeLock(unittest.TestCase):
    """Integration is serialized — build N-wide, integrate one-at-a-time (LC-1/LC-5).

    `integrate()` holds an exclusive advisory lock across the whole merge → gate
    critical section so a second concurrent integration blocks rather than racing
    on the shared integration branch + version registry (ADR 0030). The lock is
    injectable (mirrors `gate`/`prepare`); the default is `fcntl.flock`-backed.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-lock-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        _seed_progress(self.repo / ".harness", worker="w\n", mainline="m\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lock_is_held_across_the_merge_and_gate(self):
        # The post-merge gate must run strictly inside the lock — proving the lock
        # wraps the mutation, not just bracketing a no-op.
        events = []

        @contextlib.contextmanager
        def recording_lock(root):
            events.append("lock-enter")
            try:
                yield
            finally:
                events.append("lock-exit")

        def recording_gate(root):
            events.append("gate")
            return (0, "green\n")

        _add_worker(self.repo, self.tmp)
        rc, out, err = iw.integrate("foo", str(self.repo), gate=recording_gate,
                                    resolver=None, lock=recording_lock)
        self.assertEqual(rc, 0, err)
        self.assertEqual(events, ["lock-enter", "gate", "lock-exit"],
                         "the integrated-tree gate must run while the lock is held")

    def test_lock_wraps_even_an_early_refusal(self):
        # The lock brackets the whole body, so even a name-only refusal acquires +
        # releases it (no early-return path slips past the serialize point).
        events = []

        @contextlib.contextmanager
        def recording_lock(root):
            events.append("enter")
            try:
                yield
            finally:
                events.append("exit")

        rc, out, err = iw.integrate("", str(self.repo), gate=_green_gate,
                                    resolver=None, lock=recording_lock)
        self.assertEqual(rc, 2)
        self.assertEqual(events, ["enter", "exit"])

    def test_lock_path_is_a_separate_file_under_the_git_dir(self):
        # A separate file from spawn_worker's worktree-spawn.lock: build serializes
        # only its own worktree add; integration serializes the landing.
        p = iw._integrate_lock_path(str(self.repo))
        self.assertEqual(p.name, "integrate.lock")
        self.assertTrue(str(p).endswith(str(Path(".git") / "integrate.lock")), str(p))

    def test_default_lock_is_exclusive(self):
        # The real default lock genuinely serializes: while one integration holds
        # it, a second acquirer cannot take it (it would block). Proven with a
        # non-blocking probe so the test never hangs.
        try:
            import fcntl
        except ImportError:
            self.skipTest("fcntl unavailable (Windows) — the advisory lock is a "
                          "cooperative no-op there")
        lock_path = iw._integrate_lock_path(str(self.repo))
        with iw._integrate_lock(str(self.repo)):
            with open(str(lock_path), "a") as second:
                with self.assertRaises(OSError):  # BlockingIOError ⊂ OSError
                    fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # released after the context — a non-blocking acquire now succeeds.
        with open(str(lock_path), "a") as third:
            fcntl.flock(third, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(third, fcntl.LOCK_UN)


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
