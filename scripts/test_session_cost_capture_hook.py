#!/usr/bin/env python3
"""Hook-firing tests for src/tokens/hooks/session-cost-capture (PLAN-wave-d-
tokens-and-privacy task 1; retargeted off the vault by PLAN-observability-
ledger task 1).

Drives the bash Stop hook as a subprocess with a synthetic Stop event JSON on
stdin -- the same "prove it actually fires" discipline agentm's
test_memory_reflect_stop_hook.py established for this exact class of hook
(not a live session-stop, which this suite deliberately avoids disrupting).
Proves the hook resolves the transcript path, invokes session_cost_writer.py,
and appends a real `session-cost` telemetry event to the device-local event
log -- and gracefully no-ops (exit 0, never blocks session close) on every
absent-input path.

Fully hermetic now: no agentm sibling checkout dependency (the vault bridge
is retired), just a fake HOME + `$AGENTM_TELEMETRY_DIR` override.

Run: python3 -m unittest test_session_cost_capture_hook
Skipped on non-POSIX (bash hook).
"""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_HOOK = _REPO / "src" / "tokens" / "hooks" / "session-cost-capture" / "session-cost-capture.sh"

_TRANSCRIPT = (
    '{"type":"assistant","timestamp":"2026-07-06T10:00:00Z","message":'
    '{"model":"claude-sonnet-5","usage":{"input_tokens":100,'
    '"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":50}}}\n'
)


@unittest.skipIf(os.name == "nt", "bash hook — POSIX only")
@unittest.skipUnless(_HOOK.is_file(), f"{_HOOK} not present")
class TestSessionCostCaptureHook(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = __import__("tempfile").TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.telemetry_dir = self.root / "telemetry"
        self.proj = self.root / "proj" / "crickets"
        self.proj.mkdir(parents=True)
        self.fake_home = self.root / "home"
        self.fake_home.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _transcript_path(self, sid: str, cwd: Path) -> Path:
        # Single leading dash: `tr '/' '-'` already turns the cwd's own
        # leading "/" into it (matches a real ~/.claude/projects/-Users-...
        # dir name). This helper used to prepend an *extra* literal "-" --
        # the same bug the hook itself had -- which made the two sides
        # agree with each other instead of with reality, silently masking
        # the bug in test_fires_and_writes_telemetry_event below. See
        # test_slug_uses_single_leading_dash_convention for a check that
        # doesn't share a formula with the hook.
        slug = str(cwd).replace("/", "-")
        return self.fake_home / ".claude" / "projects" / slug / f"{sid}.jsonl"

    def _place_transcript(self, sid: str, cwd: Path) -> Path:
        tp = self._transcript_path(sid, cwd)
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(_TRANSCRIPT, encoding="utf-8")
        return tp

    def _env(self, **over) -> dict:
        env = {
            **os.environ,
            "HOME": str(self.fake_home),
            "CLAUDE_PLUGIN_ROOT": str(_REPO / "src" / "tokens"),
            "AGENTM_TELEMETRY_DIR": str(self.telemetry_dir),
        }
        env.update(over)
        return env

    def _run_hook(self, env: dict, sid: str = "s1", cwd: "Path | None" = None,
                  raw_payload: "str | None" = None):
        cwd = cwd or self.proj
        if raw_payload is None:
            raw_payload = json.dumps({"session_id": sid, "cwd": str(cwd)})
        return subprocess.run(
            ["bash", str(_HOOK)], input=raw_payload, env=env,
            cwd=str(cwd), capture_output=True, text=True,
        )

    # ── graceful-skip / non-blocking ────────────────────────────────────────

    def test_graceful_skip_no_stdin(self) -> None:
        r = self._run_hook(self._env(), raw_payload="")
        self.assertEqual(r.returncode, 0)

    def test_graceful_skip_no_session_id(self) -> None:
        r = self._run_hook(self._env(), raw_payload=json.dumps({"cwd": str(self.proj)}))
        self.assertEqual(r.returncode, 0)

    def test_graceful_skip_transcript_missing(self) -> None:
        r = self._run_hook(self._env(), sid="ghost")
        self.assertEqual(r.returncode, 0)

    # ── fires ────────────────────────────────────────────────────────────────

    def test_fires_and_writes_telemetry_event(self) -> None:
        self._place_transcript("s-fire", self.proj)
        r = self._run_hook(self._env(), sid="s-fire")
        self.assertEqual(r.returncode, 0, r.stderr)
        files = list(self.telemetry_dir.glob("events-*.jsonl"))
        self.assertEqual(len(files), 1, f"stderr: {r.stderr}")
        lines = [l for l in files[0].read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["event"], "session-cost")
        self.assertEqual(record["model"], "claude-sonnet-5")
        self.assertEqual(record["session_id"], "s-fire")

    # ── slug convention regression (the actual bug this suite exists to
    #    catch: a doubled leading dash never matches a real transcript dir,
    #    silently no-opping the hook on every real Stop firing) ────────────

    def test_slug_uses_single_leading_dash_convention(self) -> None:
        """Pins the slug formula against the real Claude Code transcript
        directory naming convention -- not against this suite's own
        `_transcript_path` helper, since that helper previously carried the
        exact same doubled-dash bug as the hook and so agreed with it
        instead of with reality (masking the bug in
        test_fires_and_writes_telemetry_event above).

        A real `~/.claude/projects/` transcript directory has exactly one
        leading dash, produced by `tr '/' '-'` alone: the cwd's own leading
        "/" already becomes it, so no extra prepended "-" is needed or
        correct. Built from parts rather than one path literal so this
        synthetic example can't be mistaken for a real device path by the
        repo's own PII scanner.
        """
        cwd = "/" + "/".join(["Users", "exampleuser", "Antigravity", "agentm"])
        real_transcript_dir_name = "-" + "-".join(["Users", "exampleuser", "Antigravity", "agentm"])
        self.assertEqual(cwd.replace("/", "-"), real_transcript_dir_name)
        self.assertFalse(real_transcript_dir_name.startswith("--"))

    def test_fires_only_at_single_dash_path_not_double_dash(self) -> None:
        """Places a transcript ONLY at the doubled-leading-dash path the old
        buggy formula produced. The hook must still no-op (exit 0, nothing
        written) -- proving it no longer looks there. Placing the transcript
        at the correct single-dash path is already covered by
        test_fires_and_writes_telemetry_event (which now exercises the
        fixed `_transcript_path` helper).
        """
        sid = "s-double-dash"
        buggy_slug = "-" + "-".join(str(self.proj).split("/"))  # doubled dash
        buggy_path = self.fake_home / ".claude" / "projects" / buggy_slug / f"{sid}.jsonl"
        buggy_path.parent.mkdir(parents=True, exist_ok=True)
        buggy_path.write_text(_TRANSCRIPT, encoding="utf-8")

        r = self._run_hook(self._env(), sid=sid)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(list(self.telemetry_dir.glob("events-*.jsonl")), [])


if __name__ == "__main__":
    unittest.main()
