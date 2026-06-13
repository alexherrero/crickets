#!/usr/bin/env python3
"""Tests for src/developer-workflows/scripts/doctor_worktrees.py (V5-10 sibling #3, Task 4).

The read-only health probe over the coordinator's `worker/<slug>` worktrees
(Risk #6). Every test builds a throwaway temp git repo, drives real
`git worktree add` / `git merge` / `shutil.rmtree`, and exercises the actual
classifier — there is no stubbing of git here, because the whole contract is
"observe real worktree state without mutating it".

Load-bearing assertions:
  - each of the five reachable states is classified correctly and mapped to its
    bare-slug plan: active / merged-but-unpruned / orphaned (dir gone) /
    orphaned (no worktree) / dangling-marker (missing OR blank);
  - the probe is **read-only** — a full snapshot (worktree list, every ref,
    HEAD, on-disk dirs) is byte-identical before and after `diagnose()` runs,
    even with a prunable worktree present (the probe must NOT prune it);
  - `_format` tallies + lines up every report; `main()` returns 0 always
    (a report, never a gate), including on a repo with no workers at all.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
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


dw = _load("doctor_worktrees")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=check)


def _init_repo(repo: Path) -> None:
    """A throwaway git repo on `main` with one commit; `.harness/` gitignored."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".harness/\n", encoding="utf-8")
    _git(repo, "add", "README.md", ".gitignore")
    _git(repo, "commit", "-q", "-m", "seed")


def _add_worktree(repo: Path, tmp: Path, slug: str, *, commit: bool = True,
                  marker: str | None = "__slug__") -> tuple[str, Path]:
    """Create a real `worker/<slug>` worktree.

    `commit` adds a distinct file + commit so the branch is ahead of main (it
    won't be a trivial ancestor). `marker` writes `.harness/active-plan`:
    the sentinel `"__slug__"` writes the bare slug (the well-formed case); a
    literal string writes that verbatim (e.g. `"   \\n"` for a blank marker);
    `None` writes no marker at all (the missing-marker case).
    """
    branch = f"worker/{slug}"
    wt = tmp / f"wt-{slug}"
    _git(repo, "worktree", "add", "-b", branch, str(wt))
    if commit:
        (wt / f"worker-{slug}.txt").write_text("work\n", encoding="utf-8")
        _git(wt, "add", ".")
        _git(wt, "commit", "-q", "-m", f"worker {slug}")
    if marker is not None:
        md = wt / ".harness"
        md.mkdir(parents=True, exist_ok=True)
        text = f"{slug}\n" if marker == "__slug__" else marker
        (md / "active-plan").write_text(text, encoding="utf-8")
    return branch, wt


def _snapshot(repo: Path, dirs: list[Path]) -> tuple:
    """Everything the probe could possibly mutate, captured for a before/after diff.

    The worktree registry, every local ref + its sha, HEAD, and the on-disk
    presence of each tracked worktree dir. A read-only probe must leave all of
    this byte-identical.
    """
    wt = _git(repo, "worktree", "list", "--porcelain").stdout
    refs = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/").stdout
    head = _git(repo, "rev-parse", "HEAD").stdout
    present = tuple(d.is_dir() for d in dirs)
    return (wt, refs, head, present)


class TestDiagnoseClassification(unittest.TestCase):
    """All five reachable states, in one repo, each classified + mapped correctly."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dw-class-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_each_state_classified_and_plan_mapped(self):
        # active: on disk, marker present, branch NOT merged → ACTIVE.
        _add_worktree(self.repo, self.tmp, "act")
        # merged: on disk, marker present, branch merged into main → MERGED.
        _add_worktree(self.repo, self.tmp, "done")
        # dangling (missing marker) and blank (blank marker) → DANGLING.
        _add_worktree(self.repo, self.tmp, "nomark", marker=None)
        _add_worktree(self.repo, self.tmp, "blank", marker="   \n")
        # dir-gone: registered worktree whose directory was removed → ORPHANED.
        _, wt_gone = _add_worktree(self.repo, self.tmp, "gone")
        # no-worktree: a bare worker branch with no checkout → ORPHANED.
        _git(self.repo, "branch", "worker/lone")

        # Land `worker/done` on main (no prune) so it reads as merged-but-unpruned.
        _git(self.repo, "merge", "--no-ff", "worker/done", "-m", "land done")
        # Remove the dir-gone worktree's directory behind git's back.
        shutil.rmtree(wt_gone)

        reports = {r.slug: r for r in dw.diagnose(str(self.repo))}
        self.assertEqual(set(reports), {"act", "done", "nomark", "blank", "gone", "lone"})

        self.assertEqual(reports["act"].status, dw.ACTIVE)
        self.assertEqual(reports["done"].status, dw.MERGED)
        self.assertEqual(reports["nomark"].status, dw.DANGLING)
        self.assertEqual(reports["blank"].status, dw.DANGLING)
        self.assertEqual(reports["gone"].status, dw.ORPHANED)
        self.assertEqual(reports["lone"].status, dw.ORPHANED)

        # Plan mapping is the bare slug; branch carries the worker/ prefix.
        for slug, r in reports.items():
            self.assertEqual(r.slug, slug)
            self.assertEqual(r.branch, f"worker/{slug}")
        # The no-worktree orphan has no path; the active one does.
        self.assertIsNone(reports["lone"].worktree)
        self.assertIsNotNone(reports["act"].worktree)

    def test_active_marker_text_surfaces_in_detail(self):
        # The active detail names the plan the worktree is bound to (its marker).
        _add_worktree(self.repo, self.tmp, "act")
        report = {r.slug: r for r in dw.diagnose(str(self.repo))}["act"]
        self.assertEqual(report.status, dw.ACTIVE)
        self.assertIn("act", report.detail)

    def test_branch_equal_to_main_is_merged_not_active(self):
        # A worker branch with no commits ahead is trivially an ancestor of HEAD;
        # with a marker present it must read MERGED (a prune candidate), not ACTIVE.
        _add_worktree(self.repo, self.tmp, "even", commit=False)
        report = {r.slug: r for r in dw.diagnose(str(self.repo))}["even"]
        self.assertEqual(report.status, dw.MERGED)


class TestReadOnly(unittest.TestCase):
    """The probe mutates nothing — even with a prunable worktree, it must not prune."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dw-ro-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_diagnose_does_not_mutate_repo(self):
        _, wt_act = _add_worktree(self.repo, self.tmp, "act")
        _, wt_done = _add_worktree(self.repo, self.tmp, "done")
        _, wt_gone = _add_worktree(self.repo, self.tmp, "gone")
        _git(self.repo, "branch", "worker/lone")
        _git(self.repo, "merge", "--no-ff", "worker/done", "-m", "land done")
        shutil.rmtree(wt_gone)  # leaves a prunable entry git would clean on `prune`

        tracked = [wt_act, wt_done, wt_gone]
        before = _snapshot(self.repo, tracked)
        reports = dw.diagnose(str(self.repo))
        after = _snapshot(self.repo, tracked)

        self.assertEqual(before, after, "diagnose() must leave the repo byte-identical")
        # And it actually saw the prunable worktree (didn't silently drop it).
        self.assertEqual({r.slug for r in reports}, {"act", "done", "gone", "lone"})
        # The prunable entry is still registered (the probe refused to prune it).
        self.assertIn("worker/gone", _git(self.repo, "worktree", "list", "--porcelain").stdout)
        # And the worker branches survive (no `branch -d` happened).
        for slug in ("act", "done", "gone", "lone"):
            self.assertEqual(
                _git(self.repo, "rev-parse", "--verify", "--quiet",
                     f"refs/heads/worker/{slug}", check=False).returncode, 0)


class TestFormatAndMain(unittest.TestCase):
    """Formatting + the CLI: a report, never a gate (exit 0 always)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dw-fmt-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = dw.main(["doctor_worktrees.py", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_empty_repo_reports_nothing_and_exits_zero(self):
        rc, out, err = self._run_main("--project-root", str(self.repo))
        self.assertEqual(rc, 0)
        self.assertIn("no worker", out)

    def test_main_lists_each_worktree_with_status_and_plan(self):
        _add_worktree(self.repo, self.tmp, "act")
        _add_worktree(self.repo, self.tmp, "nomark", marker=None)
        rc, out, err = self._run_main("--project-root", str(self.repo))
        self.assertEqual(rc, 0)  # read-only diagnostic — never a gate
        self.assertIn("worker/act", out)
        self.assertIn("worker/nomark", out)
        self.assertIn(dw.ACTIVE, out)
        self.assertIn(dw.DANGLING, out)
        self.assertIn("plan: act", out)

    def test_format_tally_counts_every_status(self):
        reports = [
            dw.WorkerWorktree("a", "worker/a", "/x/a", dw.ACTIVE, "d"),
            dw.WorkerWorktree("b", "worker/b", "/x/b", dw.MERGED, "d"),
            dw.WorkerWorktree("c", "worker/c", None, dw.ORPHANED, "d"),
        ]
        text = dw._format(reports)
        self.assertIn("3 worker", text)
        self.assertIn("1 active", text)
        self.assertIn("1 merged-but-unpruned", text)
        self.assertIn("1 orphaned", text)


if __name__ == "__main__":
    unittest.main()
