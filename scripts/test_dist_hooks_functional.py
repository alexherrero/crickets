#!/usr/bin/env python3
"""Functional harness: every emitted plugin's hooks.json command actually runs
from its real dist location (R2.1 / cricketsBuild — dist functional layer).

Before this test, every hook script was unit-tested from `src/` — never
proven to run with `${CLAUDE_PLUGIN_ROOT}` substituted against the real
emitted tree. This test walks every `dist/claude-code/plugins/*/hooks/hooks.json`
entry, substitutes `${CLAUDE_PLUGIN_ROOT}` with that plugin's real dist path
(exactly how Claude Code invokes it — as an env var expanded by a shell, not
a Python format-string), feeds fixture stdin matching the event's shape, and
asserts a sane exit code / stdout shape. Covers, at minimum: the `steer`
PreToolUse hook, the SessionStart "memory recall" hooks (harness-context +
conflict-merger, which inject harness/vault state into session context), and
the `evidence-tracker` hook — plus every other emitted hook, generically.

A negative-path sanity companion proves the positive test isn't vacuous: with
`CLAUDE_PLUGIN_ROOT` unresolved, the substitution breaks and the hook fails.

Requires a freshly built `dist/` (`python3 scripts/generate.py build`) — skips
gracefully (not a failure) if `dist/claude-code/plugins/` doesn't exist yet.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_DIST_PLUGINS = _REPO / "dist" / "claude-code" / "plugins"

# Minimal fixture stdin per Claude Code hook event shape. `cwd` is filled in
# per-test with the isolated fixture directory.
_FIXTURE_STDIN_TEMPLATES: dict[str, dict] = {
    "PreToolUse": {
        "session_id": "fixture", "hook_event_name": "PreToolUse",
        "tool_name": "Read", "tool_input": {"file_path": "README.md"},
    },
    "PostToolUse": {
        "session_id": "fixture", "hook_event_name": "PostToolUse",
        "tool_name": "Read", "tool_input": {"file_path": "README.md"},
    },
    "Stop": {"session_id": "fixture", "hook_event_name": "Stop"},
    "SessionStart": {"session_id": "fixture", "hook_event_name": "SessionStart"},
    "UserPromptSubmit": {"session_id": "fixture", "hook_event_name": "UserPromptSubmit", "prompt": "hello"},
}

_TRACEBACK_MARKER = "Traceback (most recent call last)"


def _iter_hook_commands():
    """Yield (plugin_name, event, command, timeout) for every hooks.json entry."""
    if not _DIST_PLUGINS.is_dir():
        return
    for plugin_dir in sorted(_DIST_PLUGINS.iterdir()):
        hooks_json = plugin_dir / "hooks" / "hooks.json"
        if not hooks_json.is_file():
            continue
        data = json.loads(hooks_json.read_text(encoding="utf-8"))
        for event, matcher_blocks in data.get("hooks", {}).items():
            for block in matcher_blocks:
                for h in block.get("hooks", []):
                    yield plugin_dir.name, event, h["command"], h.get("timeout", 10)


def _run_hook(command: str, *, event: str, cwd: Path, plugin_root: str | None) -> subprocess.CompletedProcess:
    """Run one hooks.json `command` string through a real shell (so
    `${CLAUDE_PLUGIN_ROOT}` gets shell-expanded exactly as Claude Code does
    it — never a Python-side string substitution)."""
    env = dict(os.environ)
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    else:
        env.pop("CLAUDE_PLUGIN_ROOT", None)
    # Some hooks (harness-context-session-start) import sibling .py modules
    # from ${CLAUDE_PLUGIN_ROOT}/scripts/ — running them from the REAL dist
    # location would otherwise leave __pycache__/*.pyc litter inside the
    # tracked dist/ tree, which generate.py check then flags as unexpected
    # drift. Not reproducible on a macOS interpreter with a redirected
    # sys.pycache_prefix, but real on a stock CPython (e.g. CI's ubuntu-latest)
    # — keep this test's dist/ reads read-only regardless of platform.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    fixture = dict(_FIXTURE_STDIN_TEMPLATES.get(event, {"session_id": "fixture", "hook_event_name": event}))
    fixture["cwd"] = str(cwd)
    # Invoke through bash explicitly (never `shell=True`) — hooks.json commands
    # are POSIX shell syntax (`${CLAUDE_PLUGIN_ROOT}/...`) on every host,
    # including Windows (Claude Code ships Git Bash there too). `shell=True`
    # on Windows spawns cmd.exe, which passes `${CLAUDE_PLUGIN_ROOT}` through
    # literally instead of expanding it — every hook "resolved" to a path
    # containing the literal string `${CLAUDE_PLUGIN_ROOT}` and failed.
    # `bash -c` gives POSIX expansion on all three OSes (windows-latest ships
    # Git Bash; scripts/check-no-pii.sh already relies on it in tests-windows.yml).
    return subprocess.run(
        ["bash", "-c", command], input=json.dumps(fixture), env=env, cwd=str(cwd),
        capture_output=True, text=True, timeout=30,
    )


@unittest.skipUnless(
    _DIST_PLUGINS.is_dir(),
    "dist/claude-code/plugins/ not present — run `python3 scripts/generate.py build` first",
)
class TestDistHooksFunctional(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)
        # commit-on-stop snapshots into a side ref (refs/auto-save/<ts>) — an
        # isolated fixture git repo keeps that write off the real crickets repo.
        subprocess.run(["git", "init", "-q"], cwd=self.cwd, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=self.cwd, check=True)
        subprocess.run(["git", "config", "user.name", "fixture"], cwd=self.cwd, check=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_every_emitted_hook_runs_from_its_dist_location(self) -> None:
        commands = list(_iter_hook_commands())
        self.assertTrue(commands, "no hooks.json entries found under dist/claude-code/plugins/")
        for plugin_name, event, command, _timeout in commands:
            plugin_root = str(_DIST_PLUGINS / plugin_name)
            with self.subTest(plugin=plugin_name, event=event, command=command):
                result = _run_hook(command, event=event, cwd=self.cwd, plugin_root=plugin_root)
                self.assertEqual(
                    result.returncode, 0,
                    f"{plugin_name} {event} hook exited {result.returncode} from its real dist "
                    f"location ({plugin_root})\ncommand: {command}\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}",
                )
                self.assertNotIn(_TRACEBACK_MARKER, result.stdout, f"{plugin_name} {event}: traceback on stdout")
                self.assertNotIn(_TRACEBACK_MARKER, result.stderr, f"{plugin_name} {event}: traceback on stderr")

    def test_broken_plugin_root_substitution_fails(self) -> None:
        """Negative-path sanity: an unresolved `${CLAUDE_PLUGIN_ROOT}` must NOT
        silently succeed. Proves the positive test above is exercising the
        real dist path rather than passing vacuously (e.g. because the
        underlying script graceful-skips regardless of its own location)."""
        commands = list(_iter_hook_commands())
        self.assertTrue(commands, "no hooks.json entries found under dist/claude-code/plugins/")
        broken = [
            (plugin_name, event)
            for plugin_name, event, command, _timeout in commands
            if _run_hook(command, event=event, cwd=self.cwd, plugin_root=None).returncode != 0
        ]
        self.assertTrue(
            broken,
            "expected at least one hook to fail when ${CLAUDE_PLUGIN_ROOT} is unresolved — "
            "if none fail, the positive-path test above isn't proving the dist path matters",
        )


if __name__ == "__main__":
    unittest.main()
