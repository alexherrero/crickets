#!/usr/bin/env python3
"""Regression tests: the PowerShell (.ps1) developer-plugin hooks must resolve the
WORKSPACE root from the host's hook-input contract, not trust cwd — the same
contract the bash twins are held to in test_developer_hooks_workspace.py.

Bug (crickets v3.0 #40 follow-through): the bash twins were fixed to resolve the
workspace (stdin `workspacePaths[0]` / `cwd`, or `$CLAUDE_PROJECT_DIR`, else cwd)
but their .ps1 twins were left doing bare cwd-relative `.harness/...` checks. On a
Windows / pwsh host (and on Antigravity, which runs plugin hooks from the PLUGIN
dir and passes the workspace on stdin as `{"workspacePaths":["<root>"]}`) that
made the .ps1 hooks functionally inert.

Each test invokes the real .ps1 hook from a FOREIGN cwd (simulating AG's plugin
dir) and supplies the workspace only via the host input contract. These are the
behavioral mirror of the bash matrix; together with the static `check-hook-parity`
gate they keep the twins paired.

**Runs anywhere pwsh exists** — pwsh ships on all three CI runners
(ubuntu/macos/windows), so this exercises the *real* .ps1 on the actual
windows-latest host inside the existing `unittest discover` step, with no
CI-yaml change. It **graceful-skips** where pwsh is absent (e.g. a bare dev box),
so the local suite stays green.
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
_HOOKS = _ROOT / "src" / "developer-safety" / "hooks"
KILL_SWITCH = _HOOKS / "kill-switch" / "kill-switch.ps1"
STEER = _HOOKS / "steer" / "steer.ps1"
COMMIT_ON_STOP = _HOOKS / "commit-on-stop" / "commit-on-stop.ps1"

_PWSH = shutil.which("pwsh")
_SKIP = "pwsh not on PATH; .ps1 behavior is exercised on the CI runners (all ship pwsh)"


def _run(hook: Path, cwd: Path, stdin: str = "", env_extra: dict | None = None):
    env = dict(os.environ)
    # Neutralize any ambient signal so tests are hermetic.
    env.pop("CLAUDE_PROJECT_DIR", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [_PWSH, "-NoProfile", "-File", str(hook)],
        cwd=str(cwd),
        input=stdin,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _ag_payload(workspace: Path) -> str:
    return json.dumps({
        "workspacePaths": [str(workspace)],
        "toolCall": {"args": {"Cwd": str(workspace)}, "name": "run_command"},
        "conversationId": "test",
    })


def _claude_payload(workspace: Path) -> str:
    return json.dumps({
        "cwd": str(workspace),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
    })


@unittest.skipUnless(_PWSH, _SKIP)
class TestKillSwitchWorkspacePs1(unittest.TestCase):
    def setUp(self):
        self._ws = tempfile.TemporaryDirectory()
        self._foreign = tempfile.TemporaryDirectory()
        self.ws = Path(self._ws.name)
        self.foreign = Path(self._foreign.name)   # simulates AG's plugin-dir cwd
        (self.ws / ".harness").mkdir()

    def tearDown(self):
        self._ws.cleanup()
        self._foreign.cleanup()

    def _stop(self):
        (self.ws / ".harness" / "STOP").write_text("", encoding="utf-8")

    # ---- the core regression: workspace via stdin, cwd is elsewhere ----
    def test_ag_payload_blocks_from_foreign_cwd(self):
        self._stop()
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin=_ag_payload(self.ws))
        self.assertEqual(r.returncode, 2, f"AG payload must halt; stderr={r.stderr!r}")
        self.assertIn(".harness/STOP", r.stderr)

    def test_claude_cwd_payload_blocks_from_foreign_cwd(self):
        self._stop()
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin=_claude_payload(self.ws))
        self.assertEqual(r.returncode, 2, f"Claude cwd payload must halt; stderr={r.stderr!r}")

    def test_claude_project_dir_env_blocks_from_foreign_cwd(self):
        self._stop()
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin="",
                 env_extra={"CLAUDE_PROJECT_DIR": str(self.ws)})
        self.assertEqual(r.returncode, 2, f"CLAUDE_PROJECT_DIR must halt; stderr={r.stderr!r}")

    # ---- backward-compat: Claude's original cwd=workspace path still works ----
    def test_cwd_fallback_blocks(self):
        self._stop()
        r = _run(KILL_SWITCH, cwd=self.ws, stdin="")
        self.assertEqual(r.returncode, 2, f"cwd fallback must halt; stderr={r.stderr!r}")

    # ---- robust JSON parsing (mirror of the bash adversarial-review defects) ----
    def test_nested_decoy_cwd_does_not_win(self):
        # A decoy "cwd" nested in a tool-call payload must NOT override the real
        # top-level workspace (ConvertFrom-Json reads only the keys we ask for).
        self._stop()
        decoy = Path(self._foreign.name)  # foreign cwd, no STOP
        payload = json.dumps({
            "cwd": str(self.ws),
            "tool_input": {"command": f'echo "cwd":"{decoy}"'},
            "meta": {"cwd": str(decoy)},
        })
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin=payload)
        self.assertEqual(r.returncode, 2,
                         f"top-level cwd must win over nested decoy; stderr={r.stderr!r}")

    def test_ag_workspacepaths_wins_over_nested_toolcall_cwd(self):
        # Real AG payloads carry toolCall.args.Cwd; workspacePaths must win.
        self._stop()
        decoy = Path(self._foreign.name)
        payload = json.dumps({
            "workspacePaths": [str(self.ws)],
            "toolCall": {"args": {"Cwd": str(decoy)}, "name": "run_command"},
        })
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin=payload)
        self.assertEqual(r.returncode, 2, f"workspacePaths must win; stderr={r.stderr!r}")

    def test_pretty_printed_payload_resolves(self):
        # Pretty-printed JSON must still parse.
        self._stop()
        payload = json.dumps({"workspacePaths": [str(self.ws)]}, indent=2)
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin=payload)
        self.assertEqual(r.returncode, 2, f"pretty-printed payload must resolve; stderr={r.stderr!r}")

    def test_malformed_json_falls_back_safely(self):
        # Garbage stdin must not crash the hook; falls back to cwd (no STOP there).
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin="{not json at all")
        self.assertEqual(r.returncode, 0, f"malformed payload must fall back, not error; stderr={r.stderr!r}")

    # ---- must not false-positive ----
    def test_no_stop_allows(self):
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin=_ag_payload(self.ws))
        self.assertEqual(r.returncode, 0)

    def test_foreign_cwd_no_signal_allows(self):
        # STOP exists in ws, but no workspace signal given and cwd is elsewhere.
        self._stop()
        r = _run(KILL_SWITCH, cwd=self.foreign, stdin="")
        self.assertEqual(r.returncode, 0, "without a workspace signal, must not halt foreign cwd")


@unittest.skipUnless(_PWSH, _SKIP)
class TestSteerWorkspacePs1(unittest.TestCase):
    def setUp(self):
        self._ws = tempfile.TemporaryDirectory()
        self._foreign = tempfile.TemporaryDirectory()
        self.ws = Path(self._ws.name)
        self.foreign = Path(self._foreign.name)
        (self.ws / ".harness").mkdir()

    def tearDown(self):
        self._ws.cleanup()
        self._foreign.cleanup()

    def test_ag_payload_injects_and_consumes_from_foreign_cwd(self):
        guidance = "Actually, do it this way."
        (self.ws / ".harness" / "STEER.md").write_text(guidance, encoding="utf-8")
        r = _run(STEER, cwd=self.foreign, stdin=_ag_payload(self.ws))
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        self.assertIn(guidance, r.stdout, "steer must emit workspace STEER.md contents")
        self.assertFalse((self.ws / ".harness" / "STEER.md").exists(),
                         "steer must consume (rename) the workspace STEER.md")
        consumed = list((self.ws / ".harness").glob("STEER.consumed-*.md"))
        self.assertTrue(consumed, "steer must leave an audit-trail consumed file in the workspace")


@unittest.skipUnless(_PWSH, _SKIP)
class TestCommitOnStopWorkspacePs1(unittest.TestCase):
    def setUp(self):
        self._ws = tempfile.TemporaryDirectory()
        self._foreign = tempfile.TemporaryDirectory()
        self.ws = Path(self._ws.name)
        self.foreign = Path(self._foreign.name)

    def tearDown(self):
        self._ws.cleanup()
        self._foreign.cleanup()

    def _git(self, *args):
        env = dict(os.environ)
        env.update({
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        })
        return subprocess.run(["git", *args], cwd=str(self.ws), env=env,
                              capture_output=True, text=True)

    def test_ag_payload_snapshots_workspace_repo_from_foreign_cwd(self):
        # workspace is a git repo with an initial commit + a dirty change.
        self._git("init", "-q")
        (self.ws / "f.txt").write_text("v1", encoding="utf-8")
        self._git("add", "-A"); self._git("commit", "-qm", "init")
        (self.ws / "f.txt").write_text("v2-dirty", encoding="utf-8")

        r = _run(COMMIT_ON_STOP, cwd=self.foreign, stdin=_ag_payload(self.ws))
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        refs = self._git("for-each-ref", "--format=%(refname)", "refs/auto-save")
        self.assertTrue(refs.stdout.strip(),
                        "commit-on-stop must snapshot the WORKSPACE repo, not skip from a foreign cwd")

    # ---- pwsh-7.4 native-command throw: the three states the .sh twin handles ----
    # On pwsh >= 7.4, $PSNativeCommandUseErrorActionPreference defaults $true, so under
    # $ErrorActionPreference='Stop' a non-zero `git` exit throws a terminating
    # NativeCommandExitException instead of setting $LASTEXITCODE for the hook's guards.
    # These three assert the non-fatal probes opt out of the throw (exit 0 + snapshot),
    # matching commit-on-stop.sh. Each FAILS on the unfixed hook (crash → exit 1).
    def test_non_git_workspace_exits_zero(self):
        # `git rev-parse --is-inside-work-tree` exits 128 in a non-git dir — must skip,
        # not crash, before the snapshot logic runs.
        (self.ws / "f.txt").write_text("dirty", encoding="utf-8")
        r = _run(COMMIT_ON_STOP, cwd=self.foreign, stdin=_ag_payload(self.ws))
        self.assertEqual(r.returncode, 0,
                         f"non-git workspace must skip cleanly (exit 0), not crash; stderr={r.stderr!r}")
        self.assertNotIn("Exception", r.stderr,
                         f"no PowerShell exception should leak; stderr={r.stderr!r}")

    def test_detached_head_snapshots(self):
        # Detached HEAD makes `git symbolic-ref --short HEAD` exit non-zero — must fall
        # back to the short SHA and still snapshot, not crash.
        self._git("init", "-q")
        (self.ws / "f.txt").write_text("v1", encoding="utf-8")
        self._git("add", "-A"); self._git("commit", "-qm", "init")
        self._git("checkout", "--detach")
        (self.ws / "f.txt").write_text("v2-dirty", encoding="utf-8")
        r = _run(COMMIT_ON_STOP, cwd=self.foreign, stdin=_ag_payload(self.ws))
        self.assertEqual(r.returncode, 0,
                         f"detached HEAD must snapshot, not crash; stderr={r.stderr!r}")
        refs = self._git("for-each-ref", "--format=%(refname)", "refs/auto-save")
        self.assertTrue(refs.stdout.strip(),
                        "detached HEAD must still produce an auto-save snapshot")

    def test_unborn_branch_snapshots_empty_tree(self):
        # An unborn branch (init, no commit) makes `git rev-parse --verify --quiet HEAD`
        # exit 1 — must fall back to the empty-tree parent and still snapshot, not crash.
        self._git("init", "-q")
        (self.ws / "f.txt").write_text("untracked-dirty", encoding="utf-8")
        r = _run(COMMIT_ON_STOP, cwd=self.foreign, stdin=_ag_payload(self.ws))
        self.assertEqual(r.returncode, 0,
                         f"unborn branch must snapshot empty-tree, not crash; stderr={r.stderr!r}")
        refs = self._git("for-each-ref", "--format=%(refname)", "refs/auto-save")
        self.assertTrue(refs.stdout.strip(),
                        "unborn branch must still produce an auto-save snapshot (empty-tree parent)")


if __name__ == "__main__":
    unittest.main()
