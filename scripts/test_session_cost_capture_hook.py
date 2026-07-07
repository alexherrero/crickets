#!/usr/bin/env python3
"""Hook-firing tests for src/tokens/hooks/session-cost-capture (PLAN-wave-d-
tokens-and-privacy task 1).

Drives the bash Stop hook as a subprocess with a synthetic Stop event JSON on
stdin -- the same "prove it actually fires" discipline agentm's
test_memory_reflect_stop_hook.py established for this exact class of hook
(not a live session-stop, which this suite deliberately avoids disrupting;
see that file's own precedent for the pattern this mirrors). Proves the hook
resolves the transcript path, invokes session_cost_writer.py, and writes a
real `kind: session-cost` entry when a vault + agentm sibling checkout are
both present -- and gracefully no-ops (exit 0, never blocks session close) on
every absent-input path.

Hermetic: a fake HOME whose .claude/projects/<cwd-slug>/<sid>.jsonl doubles as
the transcript root the hook computes, and whose .agentm-config.json points
AGENTM_INSTALL_PREFIX-style resolution isn't needed here since
session_cost_writer.py's own vault-path resolution reads MEMORY_VAULT_PATH
directly (simpler chain than the reflect hook's, no source_clones indirection
needed for the writer script itself -- CLAUDE_PLUGIN_ROOT points straight at
this repo's own src/tokens/scripts/ in dev-checkout mode).

Run: python3 -m unittest test_session_cost_capture_hook
Skipped on non-POSIX (bash hook) and when no agentm sibling checkout resolves.
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
_WRITER_SCRIPTS_DIR = _REPO / "src" / "tokens" / "scripts"

_TRANSCRIPT = (
    '{"type":"assistant","timestamp":"2026-07-06T10:00:00Z","message":'
    '{"model":"claude-sonnet-5","usage":{"input_tokens":100,'
    '"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":50}}}\n'
)


def _agentm_sibling_available() -> bool:
    # Conventional clone location (Path.home()/"Antigravity"/"agentm") -- the
    # same resolution session_cost_writer.py's own _candidate_dirs() uses.
    # NOT _REPO.parent: this repo may be checked out as a worktree (e.g.
    # .claude/worktrees/<slug>/), whose parent is the worktrees dir, not the
    # sibling-repos root -- test_find_capability.py / test_queue_status.py /
    # etc. all anchor on Path.home() for exactly this reason.
    sibling = Path.home() / "Antigravity" / "agentm"
    return (sibling / "harness" / "skills" / "memory" / "scripts" / "save.py").is_file()


@unittest.skipIf(os.name == "nt", "bash hook — POSIX only")
@unittest.skipUnless(_HOOK.is_file(), f"{_HOOK} not present")
class TestSessionCostCaptureHook(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = __import__("tempfile").TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(parents=True)
        self.proj = self.root / "proj" / "crickets"
        self.proj.mkdir(parents=True)
        self.fake_home = self.root / "home"
        self.fake_home.mkdir()
        # session_cost_writer.py resolves agentm via Path.home()/"Antigravity"/
        # "agentm" -- symlink the fake HOME to the real conventional clone so
        # the subprocess-under-test finds it (mirrors test_conflict_merger_hook.py).
        if _agentm_sibling_available():
            real_agentm = Path.home() / "Antigravity" / "agentm"
            (self.fake_home / "Antigravity").mkdir(parents=True, exist_ok=True)
            os.symlink(real_agentm, self.fake_home / "Antigravity" / "agentm")

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

    def _env(self, with_vault: bool = True, **over) -> dict:
        env = {**os.environ, "HOME": str(self.fake_home), "CLAUDE_PLUGIN_ROOT": str(_REPO / "src" / "tokens")}
        env.pop("AGENTM_INSTALL_PREFIX", None)
        if with_vault:
            env["MEMORY_VAULT_PATH"] = str(self.vault)
        else:
            env.pop("MEMORY_VAULT_PATH", None)
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

    # ── graceful-skip / non-blocking (no agentm sibling needed) ────────────

    def test_graceful_skip_no_stdin(self) -> None:
        r = self._run_hook(self._env(), raw_payload="")
        self.assertEqual(r.returncode, 0)

    def test_graceful_skip_no_session_id(self) -> None:
        r = self._run_hook(self._env(), raw_payload=json.dumps({"cwd": str(self.proj)}))
        self.assertEqual(r.returncode, 0)

    def test_graceful_skip_transcript_missing(self) -> None:
        r = self._run_hook(self._env(), sid="ghost")
        self.assertEqual(r.returncode, 0)

    def test_graceful_skip_no_vault(self) -> None:
        self._place_transcript("s-novault", self.proj)
        r = self._run_hook(self._env(with_vault=False), sid="s-novault")
        self.assertEqual(r.returncode, 0)

    # ── fires (requires a real agentm sibling checkout) ─────────────────────

    @unittest.skipUnless(_agentm_sibling_available(), "agentm sibling checkout unavailable")
    def test_fires_and_writes_session_cost_entry(self) -> None:
        self._place_transcript("s-fire", self.proj)
        r = self._run_hook(self._env(), sid="s-fire")
        self.assertEqual(r.returncode, 0, r.stderr)
        # save_entry() target = vault/<group>/<kind>/<slug>.md; group is
        # "projects/<project>/session-cost" (mirrors agentm_bridge.py's
        # write_failure_incident group convention), so kind repeats as the
        # final path segment before the vault -- same shape as diagnostics'
        # own failure-incident writes.
        written = list((self.vault / "projects" / "crickets" / "session-cost" / "session-cost").glob("*.md"))
        self.assertEqual(len(written), 1, f"stderr: {r.stderr}")
        content = written[0].read_text(encoding="utf-8")
        self.assertIn("kind: session-cost", content)
        self.assertIn("model: claude-sonnet-5", content)


if __name__ == "__main__":
    unittest.main()
