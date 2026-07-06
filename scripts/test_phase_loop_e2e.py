#!/usr/bin/env python3
"""End-to-end phase-loop test over a real scratch git repo (R2.5 task 8).

Every phase-command helper (`resolve_plan.py`, `spawn_worker.py`,
`integrate_worker.py`) has thorough unit-level coverage in its own
`test_*.py` file — but nothing drove the real CLI chain end-to-end:
author a named plan -> spawn a worker worktree -> do the work -> integrate
it back, asserting the actual on-disk state transitions at each stage. This
fills that gap.

`/plan`'s and `/work`'s own *authoring* and *implementation* steps are
LLM-driven and can't be scripted; what this test drives is the mechanical
state machinery around them — the same scripts a real phase-loop session
invokes — using real subprocess calls against a throwaway git repo, never
mocked function calls.

Task 7 of the plan this task refines from cited "gh stubbed to a fixture
responder" for the integrate step; investigation found integrate_worker.py
has no `gh` dependency at all (it's pure local git — publishing through
protection/CI is `/release`'s job, a separate step). The gate it does call
(`scripts/check-all.sh` in the integrated tree) is genuinely a subprocess
call, so this fixture provides a real trivial gate script rather than
mocking anything, keeping the CLI chain 100% real end-to-end.

Every script here can discover this machine's real sibling `~/Antigravity/
agentm` checkout via `find_process_seam.py`'s hardcoded candidate #3,
which would make the standalone-vs-bridge behavior depend on what's
installed locally (bridge here, standalone-fallback in CI, where no
sibling agentm exists) -- a flaky, environment-dependent test. Every
subprocess below runs with HOME redirected to an empty scratch dir and
AGENTM_SCRIPTS_DIR unset, forcing the deterministic `.harness/`-only
standalone fallback on every machine, matching what CI actually sees.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DW_SCRIPTS = _ROOT / "src" / "development-lifecycle" / "scripts"
_RESOLVE_PLAN = _DW_SCRIPTS / "resolve_plan.py"
_SPAWN_WORKER = _DW_SCRIPTS / "spawn_worker.py"
_INTEGRATE_WORKER = _DW_SCRIPTS / "integrate_worker.py"

_ALWAYS_PASS_GATE = "#!/bin/sh\nexit 0\n"
_ALWAYS_FAIL_GATE = "#!/bin/sh\necho 'battery: FAIL (fixture)' >&2\nexit 1\n"


def _git(repo: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=30, env=env,
    )


def _isolated_env(base_home: Path) -> dict:
    """A subprocess env that can never discover a real sibling agentm checkout
    (see module docstring) — deterministic standalone `.harness/` fallback."""
    env = dict(os.environ)
    env.pop("AGENTM_SCRIPTS_DIR", None)
    env["HOME"] = str(base_home)
    return env


def _run_py(script: Path, *args: str, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(script), *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=60, env=env,
    )


def _init_scratch_repo(tmp: Path, *, gate_script: str) -> Path:
    """A bare-bones repo with an initial commit and a fixture check-all.sh
    (integrate_worker.py's real gate subprocess-invokes this — providing a
    trivial real script keeps the whole chain genuinely end-to-end rather
    than mocking the gate function itself)."""
    repo = tmp / "scratch-repo"
    repo.mkdir()
    env = _isolated_env(tmp / "home")
    (tmp / "home").mkdir(exist_ok=True)
    _git(repo, "init", "-q", "-b", "main", env=env)
    _git(repo, "config", "user.email", "fixture@example.com", env=env)
    _git(repo, "config", "user.name", "fixture", env=env)
    (repo / "scripts").mkdir(parents=True)
    gate_path = repo / "scripts" / "check-all.sh"
    gate_path.write_text(gate_script, encoding="utf-8")
    gate_path.chmod(0o755)
    (repo / "README.md").write_text("# scratch\n", encoding="utf-8")
    _git(repo, "add", "-A", env=env)
    _git(repo, "commit", "-q", "-m", "initial commit", env=env)
    return repo


def _author_plan(repo: Path, slug: str) -> None:
    """The mechanical shape of /plan's output — a real PLAN-<slug>.md +
    progress-<slug>.md, committed on main, as if a real /plan session
    (LLM-authored) had just produced them."""
    harness = repo / ".harness"
    harness.mkdir(exist_ok=True)
    (harness / f"PLAN-{slug}.md").write_text(
        f"# PLAN-{slug}\n\n**Status:** in-progress\n\n"
        f"### Task 1 — do the fixture thing\n\n**Status:** [ ]\n",
        encoding="utf-8",
    )
    (harness / f"progress-{slug}.md").write_text(
        f"# progress-{slug}\n", encoding="utf-8",
    )


def _do_the_work(worktree: Path, slug: str, env: dict) -> None:
    """The mechanical shape of /work's output inside the worker worktree —
    flip the task checkbox, append a progress line, commit. The actual
    task *implementation* is LLM-driven and out of scope; this is the
    state-machinery a real /work session leaves behind at task-complete."""
    plan = worktree / ".harness" / f"PLAN-{slug}.md"
    plan.write_text(plan.read_text(encoding="utf-8").replace(
        "**Status:** [ ]", "**Status:** [x]"), encoding="utf-8")
    progress = worktree / ".harness" / f"progress-{slug}.md"
    with progress.open("a", encoding="utf-8") as fh:
        fh.write("2026-07-05 12:00 /work — completed task 1: \"do the fixture thing\" (fixture)\n")
    _git(worktree, "add", "-A", env=env)
    _git(worktree, "commit", "-q", "-m", f"work: complete task 1 of {slug}", env=env)


class TestPhaseLoopEndToEnd(unittest.TestCase):
    def test_full_lifecycle_spawn_work_integrate_happy_path(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_scratch_repo(tmp, gate_script=_ALWAYS_PASS_GATE)
            env = _isolated_env(tmp / "home")
            slug = "fixture-e2e"
            _author_plan(repo, slug)
            _git(repo, "add", "-A", env=env)
            _git(repo, "commit", "-q", "-m", "plan: author fixture-e2e", env=env)
            pre_merge_sha = _git(repo, "rev-parse", "HEAD", env=env).stdout.strip()

            # Stage 1 — resolve_plan.py finds the pair via the standalone fallback.
            r = _run_py(_RESOLVE_PLAN, slug, "--project-root", str(repo), cwd=repo, env=env)
            self.assertEqual(r.returncode, 0, f"resolve_plan failed: {r.stderr}")
            plan_path, progress_path = r.stdout.strip().split("\t")
            self.assertTrue(Path(plan_path).is_file())

            # Stage 2 — spawn_worker.py: real worktree + worker/<slug> branch.
            r = _run_py(_SPAWN_WORKER, slug, "--project-root", str(repo), cwd=repo, env=env)
            self.assertEqual(r.returncode, 0, f"spawn_worker failed: {r.stderr}")
            worktree = Path(r.stdout.strip())
            self.assertTrue(worktree.is_dir(), f"worktree not created at {worktree}")
            branches = _git(repo, "branch", "--list", "worker/" + slug, env=env).stdout
            self.assertIn("worker/" + slug, branches)
            worktree_list = _git(repo, "worktree", "list", env=env).stdout
            # `git worktree list` always prints forward slashes, even on
            # Windows, while str(Path(...)) there renders backslashes —
            # compare via as_posix() so the substring check is platform-safe.
            self.assertIn(worktree.as_posix(), worktree_list)

            # Stage 3 — the mechanical shape of a completed /work session.
            _do_the_work(worktree, slug, env)

            # Stage 4 — integrate_worker.py: real merge, real gate subprocess,
            # real consolidation (progress promotion + prune) — no gh anywhere.
            r = _run_py(_INTEGRATE_WORKER, slug, "--project-root", str(repo), cwd=repo, env=env)
            self.assertEqual(r.returncode, 0, f"integrate_worker failed: {r.stderr}")

            # Assert: PLAN-<slug>.md's task-complete flip landed on main.
            merged_plan = (repo / ".harness" / f"PLAN-{slug}.md").read_text(encoding="utf-8")
            self.assertIn("**Status:** [x]", merged_plan)

            # Assert: the worker's progress got promoted into the SINGLETON
            # progress.md (integrate_worker.py's real consolidation target —
            # not a mainline copy of progress-<slug>.md).
            singleton_progress = (repo / ".harness" / "progress.md").read_text(encoding="utf-8")
            self.assertIn("completed task 1", singleton_progress)
            self.assertIn(f"merged worker/{slug}", singleton_progress)

            # Assert: worktree + branch pruned (green-path consolidation).
            self.assertFalse(worktree.exists(), "worktree should be pruned after a green integrate")
            branches_after = _git(repo, "branch", "--list", "worker/" + slug, env=env).stdout
            self.assertNotIn("worker/" + slug, branches_after)

    def test_broken_gate_blocks_integration_and_leaves_worker_intact(self):
        """Depth-rule negative case: a failing check-all.sh must roll the merge
        back and leave the worktree/branch untouched — proving this fixture
        exercises real state transitions, not a tautology that always passes."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = _init_scratch_repo(tmp, gate_script=_ALWAYS_FAIL_GATE)
            env = _isolated_env(tmp / "home")
            slug = "fixture-e2e-red"
            _author_plan(repo, slug)
            _git(repo, "add", "-A", env=env)
            _git(repo, "commit", "-q", "-m", "plan: author fixture-e2e-red", env=env)
            pre_merge_sha = _git(repo, "rev-parse", "HEAD", env=env).stdout.strip()

            r = _run_py(_SPAWN_WORKER, slug, "--project-root", str(repo), cwd=repo, env=env)
            self.assertEqual(r.returncode, 0, f"spawn_worker failed: {r.stderr}")
            worktree = Path(r.stdout.strip())
            _do_the_work(worktree, slug, env)

            r = _run_py(_INTEGRATE_WORKER, slug, "--project-root", str(repo), cwd=repo, env=env)
            self.assertNotEqual(r.returncode, 0, "a failing gate must not report success")

            # Assert: main is rolled back to the pre-merge commit — the merge
            # never lands, even though `git merge` itself succeeded cleanly.
            post_sha = _git(repo, "rev-parse", "HEAD", env=env).stdout.strip()
            self.assertEqual(post_sha, pre_merge_sha, "main must be restored after a red gate")

            # Assert: the task-complete flip from the worker's commit did NOT
            # land on main (the whole point of the rollback).
            plan_on_main = (repo / ".harness" / f"PLAN-{slug}.md").read_text(encoding="utf-8")
            self.assertIn("**Status:** [ ]", plan_on_main)

            # Assert: the worktree + branch survive a failed integration — a
            # red gate must never destroy the worker's unlanded commits.
            self.assertTrue(worktree.exists(), "worktree must survive a failed integration")
            branches = _git(repo, "branch", "--list", "worker/" + slug, env=env).stdout
            self.assertIn("worker/" + slug, branches)


if __name__ == "__main__":
    unittest.main()
