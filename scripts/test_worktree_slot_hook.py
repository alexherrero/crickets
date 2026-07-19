#!/usr/bin/env python3
"""Tests for the worktree-slot integrity check in
`harness-context-session-start.sh` / `.ps1` (the SessionStart fake-slot guard).

`.claude/worktrees/<name>` is supposed to be a real, `git worktree add`-created
checkout. A host worktree primitive can leave a plain directory behind a slot
path instead (observed live: a directory that never appears in `git worktree
list`), in which case every git command run inside it silently walks up to the
PARENT repo's `.git` and the session unknowingly shares HEAD/index/working-tree
with every other session on that checkout. The hook now detects this on every
SessionStart and prints a loud warning into session context rather than
degrading silently.

Each test drives the real hook script (not a reimplementation) against a real
temp git repo, exercising the actual `.git`-existence check, not a mock.

The `.sh` twin is POSIX-only (mirrors `test_developer_hooks_workspace.py`'s
own `@unittest.skipUnless(os.name == "posix", ...)` precedent) — the
production Windows host runs the `.ps1` twin, and `bash <script>` via
git-bash on a Windows CI runner is not a reliable stand-in for that (observed
live: uniform, silent exit-1 failures across every `.sh`-invoking test here,
including ones that never touch the new worktree-slot logic at all — an
environment quirk unrelated to the hook's own behavior). The `.ps1` twin
gets real dual-host coverage instead, gated on `pwsh` being on PATH (ships on
all three CI runners) rather than on OS name.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_HOOK_DIR = (_ROOT / "src" / "development-lifecycle" / "hooks"
             / "harness-context-session-start")
_SH = _HOOK_DIR / "harness-context-session-start.sh"
_PS1 = _HOOK_DIR / "harness-context-session-start.ps1"

_PWSH = shutil.which("pwsh")
_SKIP_PS1 = "pwsh not on PATH; .ps1 behavior is exercised on the CI runners (all ship pwsh)"

_WARNING_MARKER = "[worktree-integrity] WARNING"
_FAKE_SLOT_MARKER = "FAKE SLOT"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "seed")


def _run_sh(cwd: Path) -> subprocess.CompletedProcess:
    payload = json.dumps({"cwd": str(cwd)})
    return subprocess.run(["bash", str(_SH)], input=payload,
                          capture_output=True, text=True, timeout=15)


def _run_ps1(cwd: Path) -> subprocess.CompletedProcess:
    payload = json.dumps({"cwd": str(cwd)})
    return subprocess.run(["pwsh", "-NoProfile", "-File", str(_PS1)], input=payload,
                          capture_output=True, text=True, timeout=15)


class WorktreeSlotHookTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="wsh-"))
        self.repo = self.tmp / "repo"
        _init_repo(self.repo)
        self.slot = self.repo / ".claude" / "worktrees" / "some-slot"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


@unittest.skipUnless(os.name == "posix", "bash hooks are posix; Windows uses .ps1")
class TestShFakeSlotGuard(WorktreeSlotHookTestCase):
    def test_bare_directory_under_worktrees_triggers_warning(self):
        self.slot.mkdir(parents=True, exist_ok=True)  # never `git worktree add`-ed
        r = _run_sh(self.slot)
        self.assertEqual(r.returncode, 0, r.stderr)  # never blocks boot
        self.assertIn(_WARNING_MARKER, r.stdout)
        self.assertIn(str(self.slot), r.stdout)
        self.assertIn(_FAKE_SLOT_MARKER, r.stderr)

    def test_real_worktree_under_worktrees_is_silent(self):
        self.slot.parent.mkdir(parents=True, exist_ok=True)
        _git(self.repo, "worktree", "add", "-b", "wt-some-slot", str(self.slot))
        r = _run_sh(self.slot)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(_WARNING_MARKER, r.stdout)
        self.assertNotIn(_FAKE_SLOT_MARKER, r.stderr)

    def test_path_outside_worktrees_convention_is_never_checked(self):
        # The main checkout itself is not a `.claude/worktrees/<name>` slot —
        # the guard must not fire there even though rev-parse --show-toplevel
        # trivially resolves to itself anyway (this proves the `case` gate,
        # not just the comparison).
        r = _run_sh(self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(_WARNING_MARKER, r.stdout)

    def test_fake_slot_warning_survives_alongside_harness_context(self):
        # The new check must not clobber the existing .harness/ context
        # injection when both fire in the same boot.
        self.slot.mkdir(parents=True, exist_ok=True)
        (self.slot / ".harness").mkdir()
        (self.slot / ".harness" / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
        (self.slot / ".harness" / "progress.md").write_text("", encoding="utf-8")
        r = _run_sh(self.slot)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(_WARNING_MARKER, r.stdout)
        self.assertIn("developer-workflows", r.stdout)


@unittest.skipUnless(_PWSH, _SKIP_PS1)
class TestPs1FakeSlotGuard(WorktreeSlotHookTestCase):
    def test_bare_directory_under_worktrees_triggers_warning(self):
        self.slot.mkdir(parents=True, exist_ok=True)
        r = _run_ps1(self.slot)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(_WARNING_MARKER, r.stdout)
        self.assertIn(_FAKE_SLOT_MARKER, r.stderr)

    def test_real_worktree_under_worktrees_is_silent(self):
        self.slot.parent.mkdir(parents=True, exist_ok=True)
        _git(self.repo, "worktree", "add", "-b", "wt-some-slot", str(self.slot))
        r = _run_ps1(self.slot)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(_WARNING_MARKER, r.stdout)


if __name__ == "__main__":
    unittest.main()
