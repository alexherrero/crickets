#!/usr/bin/env python3
"""Structural spec for the developer-workflows compact-nudge-resume hook.

Locks the load-bearing facts using synthesized fixtures (no real transcripts):

  * hook.md has valid frontmatter (kind: hook, supported_hosts: [claude-code],
    version, name, trigger description).
  * The hook script emits {"additionalContext": ...} on stdout when a
    synthesized large-session JSONL (> 400 assistant turns) is provided.
  * The hook script emits nothing when a small-session JSONL (< 400 turns)
    is provided.
  * The hook script emits nothing when no JSONL exists.
  * COMPACT_NUDGE_JSONL_PATH override wires correctly in all cases.

All tests use subprocess so the script runs as it would in production —
no mocking of internal functions.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_HOOK_DIR = _ROOT / "src" / "developer-workflows" / "hooks" / "compact-nudge-resume"
_HOOK_SCRIPT = _HOOK_DIR / "compact-nudge-resume.py"
_HOOK_MD = _HOOK_DIR / "hook.md"

sys.path.insert(0, str(_HERE))
from src_model import read_frontmatter  # noqa: E402

_EVENT_JSON = json.dumps({"cwd": "/tmp/fake-project", "prompt": "hello"})


def _make_large_jsonl(path: Path, n: int = 450) -> None:
    """Write a JSONL with n assistant-type lines (> 400 threshold)."""
    with path.open("w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"type": "assistant", "message": f"response {i}"}) + "\n")


def _make_small_jsonl(path: Path, n: int = 50) -> None:
    """Write a JSONL with n assistant-type lines (< 400 threshold)."""
    with path.open("w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(json.dumps({"type": "assistant", "message": f"response {i}"}) + "\n")


def _run_hook(jsonl_path: str | None, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook script with controlled env and return the result."""
    env = {**os.environ}
    # Strip any real session vars that could interfere
    env.pop("CLAUDE_SESSION_ID", None)
    env.pop("CLAUDE_CONTEXT_USAGE_PERCENTAGE", None)
    env.pop("COMPACT_NUDGE_JSONL_PATH", None)
    if jsonl_path is not None:
        env["COMPACT_NUDGE_JSONL_PATH"] = jsonl_path
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
        input=_EVENT_JSON,
        text=True,
        capture_output=True,
        env=env,
    )


class TestCompactNudgeHookFrontmatter(unittest.TestCase):
    """hook.md satisfies the hook manifest contract."""

    @classmethod
    def setUpClass(cls):
        cls.fm = read_frontmatter(_HOOK_MD) or {}

    def test_hook_md_exists(self):
        self.assertTrue(_HOOK_MD.exists(), f"Missing: {_HOOK_MD}")

    def test_kind_is_hook(self):
        self.assertEqual(self.fm.get("kind"), "hook")

    def test_name_is_compact_nudge_resume(self):
        self.assertEqual(self.fm.get("name"), "compact-nudge-resume")

    def test_supported_hosts_is_claude_code_only(self):
        hosts = self.fm.get("supported_hosts") or []
        self.assertIn("claude-code", hosts)

    def test_has_version(self):
        self.assertIn("version", self.fm)

    def test_has_description(self):
        self.assertTrue(str(self.fm.get("description", "")).strip())

    def test_settings_fragment_exists(self):
        frag = _HOOK_DIR / "settings-fragment-bash.json"
        self.assertTrue(frag.exists(), f"Missing: {frag}")

    def test_settings_fragment_registers_user_prompt_submit(self):
        frag = json.loads((_HOOK_DIR / "settings-fragment-bash.json").read_text())
        self.assertIn("UserPromptSubmit", frag.get("hooks", {}))


class TestCompactNudgeLargeSession(unittest.TestCase):
    """Hook emits additionalContext when the session JSONL has > 400 assistant turns."""

    def test_large_jsonl_triggers_nudge(self):
        with tempfile.TemporaryDirectory() as tmp:
            large = Path(tmp) / "large.jsonl"
            _make_large_jsonl(large, n=450)
            result = _run_hook(str(large))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.strip(), "Expected nudge output for large session; got nothing")
        payload = json.loads(result.stdout)
        self.assertIn("additionalContext", payload)
        nudge = payload["additionalContext"]
        self.assertIn("/clear", nudge)
        self.assertIn("/compact", nudge)

    def test_large_jsonl_nudge_mentions_state_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            large = Path(tmp) / "large.jsonl"
            _make_large_jsonl(large, n=450)
            result = _run_hook(str(large))
        payload = json.loads(result.stdout)
        self.assertIn("on disk", payload["additionalContext"])

    def test_context_pct_env_triggers_nudge_with_resumed_session(self):
        """CLAUDE_CONTEXT_USAGE_PERCENTAGE ≥ 60 with a resumed session triggers nudge."""
        with tempfile.TemporaryDirectory() as tmp:
            # Need at least 1 assistant line so session "appears resumed"
            small_with_history = Path(tmp) / "history.jsonl"
            _make_small_jsonl(small_with_history, n=5)
            result = _run_hook(
                str(small_with_history),
                extra_env={"CLAUDE_CONTEXT_USAGE_PERCENTAGE": "75.0"},
            )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.strip())
        self.assertIn("additionalContext", json.loads(result.stdout))


class TestCompactNudgeSmallOrNoSession(unittest.TestCase):
    """Hook is silent when context is small or the session is brand-new."""

    def test_small_jsonl_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            small = Path(tmp) / "small.jsonl"
            _make_small_jsonl(small, n=50)
            result = _run_hook(str(small))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "", "Expected silence for small session; got output")

    def test_no_jsonl_is_silent(self):
        result = _run_hook(None)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "", "Expected silence when no JSONL; got output")

    def test_empty_jsonl_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.jsonl"
            empty.write_text("")
            result = _run_hook(str(empty))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_context_pct_below_threshold_is_silent(self):
        """CLAUDE_CONTEXT_USAGE_PERCENTAGE < 60 with a resumed session stays silent."""
        with tempfile.TemporaryDirectory() as tmp:
            small = Path(tmp) / "small.jsonl"
            _make_small_jsonl(small, n=5)
            result = _run_hook(
                str(small),
                extra_env={"CLAUDE_CONTEXT_USAGE_PERCENTAGE": "30.0"},
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_nonexistent_jsonl_path_is_silent(self):
        result = _run_hook("/tmp/nonexistent-does-not-exist-12345.jsonl")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
