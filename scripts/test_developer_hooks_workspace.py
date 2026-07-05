#!/usr/bin/env python3
"""Regression tests: developer-plugin hooks must resolve the WORKSPACE root from
the host's hook-input contract, not trust cwd.

Bug (crickets v3.0 #40, part-6 T2 dogfood): kill-switch / steer / commit-on-stop
checked `.harness/...` relative to cwd. That holds on Claude Code (runs hooks
from the project root) but NOT on Antigravity, which runs plugin hooks with
cwd = the plugin dir and passes the workspace on stdin as
`{"workspacePaths":["<root>"]}`. So the hooks were functionally inert on AG.

Each test invokes the real hook script from a FOREIGN cwd (simulating AG's
plugin dir) and supplies the workspace only via the host input contract. Against
the pre-fix hooks these FAIL (the hook looks in the foreign cwd); after the fix
(resolve workspace from stdin `workspacePaths[0]` / `cwd`, or
`$CLAUDE_PROJECT_DIR`, else cwd) they pass — while the plain cwd-relative path
(Claude's original behavior) still works.

posix-only: the hooks are bash; Windows host uses the .ps1 variants.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_HOOKS = _ROOT / "src" / "developer-safety" / "hooks"  # control hooks' home post-seed-retirement
KILL_SWITCH = _HOOKS / "kill-switch" / "kill-switch.sh"
STEER = _HOOKS / "steer" / "steer.sh"
COMMIT_ON_STOP = _HOOKS / "commit-on-stop" / "commit-on-stop.sh"


def _run(hook: Path, cwd: Path, stdin: str = "", env_extra: dict | None = None):
    env = dict(os.environ)
    # Neutralize any ambient signal so tests are hermetic.
    env.pop("CLAUDE_PROJECT_DIR", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(hook)],
        cwd=str(cwd),
        input=stdin,
        env=env,
        capture_output=True,
        text=True,
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


@unittest.skipUnless(os.name == "posix", "bash hooks are posix; Windows uses .ps1")
class TestKillSwitchWorkspace(unittest.TestCase):
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

    # ---- robust JSON parsing (adversarial-review defects) ----
    def test_nested_decoy_cwd_does_not_win(self):
        # A decoy "cwd" nested in a tool-call payload must NOT override the real
        # top-level workspace (greedy-regex defect 1).
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
        # Pretty-printed JSON must still parse (line-based-sed defect 2).
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

    def test_blocks_next_call_then_unblocks_after_deactivation(self):
        # R2.2 / PLAN-r2-enforcement-and-sync task 2: the individual states
        # above are each tested in isolation (fresh STOP per test) — this
        # proves the actual OPERATOR SEQUENCE as one fixture: activate, the
        # very next tool call is blocked, deactivate, and a call issued
        # AFTER deactivation succeeds normally (not just "some call, some
        # time, in isolation, happens to return the right code").
        payload = _ag_payload(self.ws)

        # A call BEFORE activation succeeds — establishes the baseline.
        before = _run(KILL_SWITCH, cwd=self.foreign, stdin=payload)
        self.assertEqual(before.returncode, 0, "must be unblocked before activation")

        # Activate (operator: touch .harness/STOP) — the NEXT call is blocked.
        self._stop()
        blocked = _run(KILL_SWITCH, cwd=self.foreign, stdin=payload)
        self.assertEqual(blocked.returncode, 2, "next call after activation must block")
        self.assertIn(".harness/STOP", blocked.stderr)

        # Deactivate (operator: rm .harness/STOP) — a call issued AFTER
        # deactivation succeeds normally again.
        (self.ws / ".harness" / "STOP").unlink()
        after = _run(KILL_SWITCH, cwd=self.foreign, stdin=payload)
        self.assertEqual(after.returncode, 0, "call issued after deactivation must succeed")


@unittest.skipUnless(os.name == "posix", "bash hooks are posix; Windows uses .ps1")
class TestSteerWorkspace(unittest.TestCase):
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
        self.assertFalse((self.ws / ".harness" / "STEER.md").exists(),
                         "steer must consume (rename) the workspace STEER.md")
        consumed = list((self.ws / ".harness").glob("STEER.consumed-*.md"))
        self.assertTrue(consumed, "steer must leave an audit-trail consumed file in the workspace")

    def test_emits_additionalcontext_json_not_plain_text(self):
        # R2.2 task 5: PreToolUse stdout injection was live-verified false;
        # UserPromptSubmit's real injection contract is a JSON object with an
        # `additionalContext` key, never raw text — a regression net for the
        # v0.1.0->v0.2.0 mechanism migration.
        guidance = "Three corrections:\n1. Use the helper.\n2. Don't add os.system."
        (self.ws / ".harness" / "STEER.md").write_text(guidance, encoding="utf-8")
        payload = json.dumps({
            "cwd": str(self.ws), "hook_event_name": "UserPromptSubmit", "prompt": "continue",
        })
        r = _run(STEER, cwd=self.ws, stdin=payload)
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        parsed = json.loads(r.stdout)
        self.assertEqual(parsed, {"additionalContext": guidance},
                         "steer must emit exactly {'additionalContext': <STEER.md contents>}, not plain text")


@unittest.skipUnless(os.name == "posix", "bash hooks are posix; Windows uses .ps1")
class TestCommitOnStopWorkspace(unittest.TestCase):
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

    def test_no_branch_or_tag_ref_touched_across_many_stop_events(self):
        # R2.2 / PLAN-r2-enforcement-and-sync task 3: the documented contract
        # (HEAD, the current branch, the real index, and the working tree are
        # all unchanged) has no executable assertion — prove it holds across
        # several real Stop events, not just one.
        self._git("init", "-q")
        (self.ws / "f.txt").write_text("v0", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "init")
        branch_before = self._git("symbolic-ref", "--short", "HEAD").stdout
        head_before = self._git("rev-parse", "HEAD").stdout
        branches_before = self._git("for-each-ref", "refs/heads").stdout
        tags_before = self._git("for-each-ref", "refs/tags").stdout

        for i in range(3):
            (self.ws / "f.txt").write_text(f"v{i}-dirty", encoding="utf-8")
            r = _run(COMMIT_ON_STOP, cwd=self.ws, stdin="{}")
            self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")

        self.assertEqual(branch_before, self._git("symbolic-ref", "--short", "HEAD").stdout,
                         "current branch must never change")
        self.assertEqual(head_before, self._git("rev-parse", "HEAD").stdout, "HEAD must never move")
        self.assertEqual(branches_before, self._git("for-each-ref", "refs/heads").stdout,
                         "no branch ref may be created or moved")
        self.assertEqual(tags_before, self._git("for-each-ref", "refs/tags").stdout,
                         "no tag ref may be created")

    def test_prunes_to_most_recent_ten_across_twelve_snapshots(self):
        # R2.2 task 3: the "history pruned to the last 10" contract has no
        # executable assertion. 11 synthetic prior snapshots are pre-seeded
        # with fabricated, strictly-increasing timestamps (bypassing the
        # hook's own 1-second-granularity clock — 12 REAL invocations 1s
        # apart would add ~13s per battery run for no extra coverage of the
        # prune LOGIC itself, which runs identically regardless of how the
        # prior refs got there); the 12th snapshot comes from one REAL
        # invocation, which is also what actually exercises the prune step.
        self._git("init", "-q")
        (self.ws / "f.txt").write_text("v0", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "init")
        head = self._git("rev-parse", "HEAD").stdout.strip()

        fake_timestamps = [f"20260101T0000{i:02d}Z" for i in range(11)]
        for ts in fake_timestamps:
            r = self._git("update-ref", f"refs/auto-save/{ts}", head)
            self.assertEqual(r.returncode, 0, r.stderr)

        (self.ws / "f.txt").write_text("v-dirty", encoding="utf-8")
        r = _run(COMMIT_ON_STOP, cwd=self.ws, stdin="{}")
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")

        refs = self._git("for-each-ref", "--sort=-refname", "--format=%(refname)", "refs/auto-save")
        surviving = [line for line in refs.stdout.splitlines() if line]
        self.assertEqual(len(surviving), 10,
                         f"expected exactly 10 surviving snapshots after pruning, got {len(surviving)}: {surviving}")
        # The two OLDEST fakes (lexicographically smallest timestamps) must
        # be the ones pruned — a non-tautological check: an off-by-one or a
        # disabled prune step would leave 11 or 12 refs and fail the count
        # assertion above; a wrong sort direction would prune the newest
        # instead and fail this one.
        for old_ts in fake_timestamps[:2]:
            self.assertNotIn(f"refs/auto-save/{old_ts}", surviving,
                             f"refs/auto-save/{old_ts} (one of the two oldest) should have been pruned")


if __name__ == "__main__":
    unittest.main()
