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
        slug = "-" + str(cwd).replace("/", "-")
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


if __name__ == "__main__":
    unittest.main()
