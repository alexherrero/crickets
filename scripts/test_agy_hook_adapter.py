#!/usr/bin/env python3
"""Tests for scripts/agy_hook_adapter.py.

The payloads are the ones agy 1.4.x documents for hooks (camelCase keys, the
`toolCall` / `lastUserInput` / `executionNum` fields), and the answers are the
JSON shapes it documents. The hook scripts under test are the real ones from
src/, not stand-ins, so a change to what kill-switch or steer prints fails here.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_ADAPTER = _HERE / "agy_hook_adapter.py"

_spec = importlib.util.spec_from_file_location("agy_hook_adapter", _ADAPTER)
adapter = importlib.util.module_from_spec(_spec)
sys.modules["agy_hook_adapter"] = adapter
_spec.loader.exec_module(adapter)


class TranslateTests(unittest.TestCase):
    """The mapping from a Claude hook's result to agy's answer."""

    def test_exit_2_on_a_tool_call_is_a_deny_with_the_reason(self):
        out = adapter.translate("PreToolUse", 2, "", "halted by operator\n")
        self.assertEqual(out, {"decision": "deny", "reason": "halted by operator"})

    def test_exit_0_with_no_output_prints_nothing(self):
        # Measured on agy 1.4.11: a bare {} from a PreToolUse hook is read as a
        # DENY (the tool call is refused with an empty reason), and "allow"
        # would switch agy's permission prompts off for every tool call. Empty
        # output is what leaves the tool running under agy's normal flow.
        self.assertIsNone(adapter.translate("PreToolUse", 0, "", ""))

    def test_other_nonzero_exit_is_not_a_block(self):
        self.assertIsNone(adapter.translate("PreToolUse", 1, "", "oops"))

    def test_only_a_tool_hook_prints_nothing_for_no_opinion(self):
        self.assertIsNone(adapter.no_opinion("PreToolUse"))
        for event in ("PostToolUse", "SessionStart", "UserPromptSubmit", "Stop"):
            self.assertEqual(adapter.no_opinion(event), {}, event)

    def test_claude_permission_decision_json_is_passed_on(self):
        stdout = json.dumps({"hookSpecificOutput": {
            "permissionDecision": "ask", "permissionDecisionReason": "check this"}})
        self.assertEqual(adapter.translate("PreToolUse", 0, stdout, ""),
                         {"decision": "ask", "reason": "check this"})

    def test_post_tool_use_always_answers_empty(self):
        self.assertEqual(adapter.translate("PostToolUse", 2, "text", "err"), {})

    def test_session_start_stdout_becomes_a_system_message(self):
        out = adapter.translate("SessionStart", 0, "brief for the agent\n", "")
        self.assertEqual(out, {"injectSteps": [{"systemMessage": {"systemMessage": "brief for the agent"}}]})

    def test_session_start_with_nothing_to_say_answers_empty(self):
        self.assertEqual(adapter.translate("SessionStart", 0, "  \n", ""), {})

    def test_additional_context_json_is_unwrapped(self):
        stdout = json.dumps({"hookSpecificOutput": {"additionalContext": "from json"}})
        out = adapter.translate("SessionStart", 0, stdout, "")
        self.assertEqual(out["injectSteps"][0]["systemMessage"]["systemMessage"], "from json")

    def test_json_without_context_adds_nothing(self):
        self.assertEqual(adapter.translate("SessionStart", 0, '{"continue": true}', ""), {})

    def test_prompt_hook_context_is_a_one_turn_message(self):
        out = adapter.translate("UserPromptSubmit", 0, '{"additionalContext": "note"}', "")
        self.assertEqual(out, {"injectSteps": [{"ephemeralMessage": "note"}]})

    def test_prompt_hook_exit_2_stops_the_turn_and_shows_the_user_why(self):
        out = adapter.translate("UserPromptSubmit", 2, "", "contains a secret")
        self.assertEqual(out["terminationBehavior"], "terminate")
        self.assertEqual(out["injectSteps"], [{"errorMessage": {"userMessage": "contains a secret"}}])

    def test_stop_exit_2_keeps_the_agent_going(self):
        out = adapter.translate("Stop", 2, "", "tests still failing")
        self.assertEqual(out, {"decision": "continue", "reason": "tests still failing"})

    def test_stop_exit_0_lets_the_agent_stop(self):
        self.assertEqual(adapter.translate("Stop", 0, "", ""), {})


class PayloadTests(unittest.TestCase):
    def test_run_command_becomes_a_bash_call(self):
        p = {"conversationId": "c", "toolCall": {"name": "run_command", "args": {"CommandLine": "ls -la"}}}
        c = adapter.claude_payload("PreToolUse", p, "/ws")
        self.assertEqual((c["tool_name"], c["tool_input"], c["cwd"]), ("Bash", {"command": "ls -la"}, "/ws"))
        self.assertEqual(c["hook_event_name"], "PreToolUse")

    def test_other_tools_keep_their_name_and_args(self):
        p = {"toolCall": {"name": "browser_click", "args": {"x": 1}}}
        c = adapter.claude_payload("PostToolUse", p, "/ws")
        self.assertEqual((c["tool_name"], c["tool_input"]), ("browser_click", {"x": 1}))

    def test_last_user_input_becomes_the_prompt(self):
        c = adapter.claude_payload("UserPromptSubmit", {"lastUserInput": "fix it"}, "/ws")
        self.assertEqual(c["prompt"], "fix it")

    def test_stop_hook_active_tracks_the_execution_number(self):
        self.assertFalse(adapter.claude_payload("Stop", {"executionNum": 1}, "/w")["stop_hook_active"])
        self.assertTrue(adapter.claude_payload("Stop", {"executionNum": 2}, "/w")["stop_hook_active"])


class EndToEndTests(unittest.TestCase):
    """Run the adapter as agy does: a process, JSON on stdin, JSON on stdout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "workspace"
        (self.ws / ".harness").mkdir(parents=True)
        # A plugin dir laid out like the emitted one: hooks/<name>/<script> beside the adapter.
        self.plugin = Path(self.tmp.name) / "plugin"
        (self.plugin / "hooks").mkdir(parents=True)
        (self.plugin / "hooks" / "_agy_hook_adapter.py").write_text(_ADAPTER.read_text(encoding="utf-8"))
        for name in ("kill-switch", "steer"):
            src = _ROOT / "src" / "developer-safety" / "hooks" / name
            dst = self.plugin / "hooks" / name
            dst.mkdir()
            for f in src.glob("*.sh"):
                (dst / f.name).write_text(f.read_text(encoding="utf-8"))
        self.env = dict(os.environ, TMPDIR=self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, event, payload, *cmd):
        """The adapter's JSON answer, or None when it printed nothing."""
        proc = subprocess.run(
            [sys.executable, "./hooks/_agy_hook_adapter.py", event, *cmd],
            input=json.dumps(payload), capture_output=True, text=True,
            cwd=self.plugin, env=self.env, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def _tool_payload(self):
        return {"conversationId": "c1", "workspacePaths": [str(self.ws)],
                "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}}

    def test_kill_switch_passes_through_without_a_stop_file(self):
        out = self._run("PreToolUse", self._tool_payload(), "bash", "./hooks/kill-switch/kill-switch.sh")
        self.assertIsNone(out)  # printed nothing; {} would have been a deny

    def test_kill_switch_denies_when_stop_file_exists(self):
        (self.ws / ".harness" / "STOP").write_text("", encoding="utf-8")
        out = self._run("PreToolUse", self._tool_payload(), "bash", "./hooks/kill-switch/kill-switch.sh")
        self.assertEqual(out["decision"], "deny")
        self.assertIn(".harness/STOP", out["reason"])

    def test_steer_note_reaches_the_model_once_per_message(self):
        (self.ws / ".harness" / "STEER.md").write_text("use approach B\n", encoding="utf-8")
        payload = {"conversationId": "c-steer", "workspacePaths": [str(self.ws)],
                   "lastUserInput": "go", "invocationNum": 1}
        first = self._run("UserPromptSubmit", payload, "bash", "./hooks/steer/steer.sh")
        self.assertEqual(first, {"injectSteps": [{"ephemeralMessage": "use approach B\n"}]})
        # The same message again (agy's next model call in the turn) is let through untouched.
        self.assertEqual(self._run("UserPromptSubmit", payload, "bash", "./hooks/steer/steer.sh"), {})

    def test_a_new_message_in_the_same_conversation_runs_the_hook_again(self):
        script = self.plugin / "hooks" / "echo.sh"
        script.write_text("#!/usr/bin/env bash\necho ran\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        base = {"conversationId": "c-two", "workspacePaths": [str(self.ws)]}
        a = self._run("UserPromptSubmit", {**base, "lastUserInput": "one"}, "bash", "./hooks/echo.sh")
        b = self._run("UserPromptSubmit", {**base, "lastUserInput": "one"}, "bash", "./hooks/echo.sh")
        c = self._run("UserPromptSubmit", {**base, "lastUserInput": "two"}, "bash", "./hooks/echo.sh")
        self.assertEqual(a, {"injectSteps": [{"ephemeralMessage": "ran"}]})
        self.assertEqual(b, {})
        self.assertEqual(c, {"injectSteps": [{"ephemeralMessage": "ran"}]})

    def test_the_script_runs_from_the_workspace_with_claude_env(self):
        script = self.plugin / "hooks" / "where.sh"
        script.write_text('#!/usr/bin/env bash\necho "$PWD|$CLAUDE_PROJECT_DIR"\n', encoding="utf-8")
        out = self._run("SessionStart", {"workspacePaths": [str(self.ws)]}, "bash", "./hooks/where.sh")
        said = out["injectSteps"][0]["systemMessage"]["systemMessage"]
        real = os.path.realpath(self.ws)
        self.assertEqual(said, f"{real}|{self.ws}")

    def test_a_crashing_adapter_fails_open_the_way_each_event_expects(self):
        def run(event):
            return subprocess.run([sys.executable, "./hooks/_agy_hook_adapter.py", event,
                                   "bash", "./hooks/does-not-exist.sh"],
                                  input="not json at all", capture_output=True, text=True,
                                  cwd=self.plugin, env=self.env, timeout=30)
        tool = run("PreToolUse")
        self.assertEqual((tool.returncode, tool.stdout), (0, ""))  # NOT {} — that denies the call
        stop = run("Stop")
        self.assertEqual((stop.returncode, json.loads(stop.stdout)), (0, {}))


if __name__ == "__main__":
    unittest.main()
