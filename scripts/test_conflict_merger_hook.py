#!/usr/bin/env python3
"""End-to-end regression tests for the re-homed conflict-merger SessionStart hook
(`src/obsidian-vault/hooks/conflict-merger-session-start/conflict-merger-session-start.sh`).

Port of the kernel hook test (agentm `test_conflict_merger_hook.py`), re-pointed
at this plugin's hook after the V5-2 task-2 re-home. The load-bearing assertions
that travel with it:

  - `test_resolves_vault_from_config_when_env_unset` — Claude Code does NOT inject
    `MEMORY_VAULT_PATH` into the hook env on user-scope installs, so the hook must
    fall back to the present engine's `.agentm-config.json::vault_path` (LC-4 —
    read in place). Fails against a hook that only checks the env var.
  - The broadened sweep (bracket / copy-of / numbered families + the DriveFS
    lost_and_found/ dump) reaches the operator end-to-end through the hook, not
    just at the function level.

The rewired hook loads this plugin's `scripts/vault_conflicts.py` via
`$CLAUDE_PLUGIN_ROOT` and imports `_conflict_family` from the present engine
(LC-3). So the harness sets `CLAUDE_PLUGIN_ROOT` to the plugin source dir and a
fake `HOME` whose `Antigravity/agentm` symlink points at the located agentm clone
(so the hook's `$HOME/Antigravity/agentm/scripts/harness_memory.py` candidate
resolves). When no clone is reachable (crickets CI in isolation) the whole case
**graceful-skips** to keep the gate deterministic. POSIX-only (bash hook; the
pwsh twin mirrors the behavior but has no test harness, matching the repo posture).
"""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
_PLUGIN_ROOT = REPO_ROOT / "src" / "obsidian-vault"
_HOOK = _PLUGIN_ROOT / "hooks" / "conflict-merger-session-start" / "conflict-merger-session-start.sh"

_CONFLICT_NAME = "PLAN (conflicted copy 2026-05-27) - Mac.md"


def _locate_agentm_repo() -> Path | None:
    """The agentm repo root, or None when no clone is reachable.

    Order: an explicit `AGENTM_SCRIPTS` override (→ its parent), then the
    conventional sibling checkout (`../agentm`). The hook needs the kernel's
    `scripts/harness_memory.py` so `vault_conflicts.py`'s `_conflict_family`
    import resolves.
    """
    override = os.environ.get("AGENTM_SCRIPTS")
    if override:
        p = Path(override).expanduser()
        return p.parent if (p / "harness_memory.py").is_file() else None
    sibling = REPO_ROOT.parent / "agentm"
    return sibling if (sibling / "scripts" / "harness_memory.py").is_file() else None


@unittest.skipIf(os.name == "nt", "bash hook — POSIX only")
@unittest.skipUnless(_HOOK.is_file(), f"{_HOOK} not present")
class TestConflictMergerHook(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.agentm_repo = _locate_agentm_repo()
        if cls.agentm_repo is None:
            raise unittest.SkipTest(
                "agentm kernel clone not found (set AGENTM_SCRIPTS or check out "
                "../agentm) — hook subprocess test skipped to keep CI deterministic"
            )

    def setUp(self) -> None:
        self._tmp = __import__("tempfile").TemporaryDirectory()
        self.root = Path(self._tmp.name)

        # Fixture vault with a Google Drive conflict file in it.
        self.vault = self.root / "vault"
        (self.vault / "projects" / "demo" / "_harness").mkdir(parents=True)
        self.conflict = self.vault / "projects" / "demo" / "_harness" / _CONFLICT_NAME
        self.conflict.write_text("# conflicted copy\n", encoding="utf-8")

        # Neutral cwd for the hook subprocess (keeps the hook's relative
        # harness_memory.py candidates — ../agentm, ../../agentm — from
        # accidentally resolving against the real machine layout).
        self.cwd = self.root / "cwd"
        self.cwd.mkdir()

        # Fake HOME: config carries vault_path (the fallback under test) and a
        # symlink so the hook's "$HOME/Antigravity/agentm/scripts/harness_memory.py"
        # candidate resolves to the located clone regardless of the host machine.
        self.fake_home = self.root / "home"
        (self.fake_home / ".claude").mkdir(parents=True)
        (self.fake_home / "Antigravity").mkdir(parents=True)
        os.symlink(self.agentm_repo, self.fake_home / "Antigravity" / "agentm")
        self._write_config(vault_path=str(self.vault))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_config(self, *, vault_path: str | None) -> None:
        cfg = {"schema_version": 2}
        if vault_path is not None:
            cfg["vault_path"] = vault_path
        (self.fake_home / ".claude" / ".agentm-config.json").write_text(
            json.dumps(cfg), encoding="utf-8",
        )

    def _env(self, **over) -> dict:
        env = {
            **os.environ,
            "HOME": str(self.fake_home),
            # The rewired hook loads vault_conflicts.py from here.
            "CLAUDE_PLUGIN_ROOT": str(_PLUGIN_ROOT),
        }
        # Clean slate: env var must be UNSET to exercise the config fallback.
        env.pop("MEMORY_VAULT_PATH", None)
        env.pop("AGENTM_INSTALL_PREFIX", None)
        env.update(over)
        return env

    def _run(self, env: dict):
        payload = json.dumps({"session_id": "doctor-probe", "cwd": str(self.cwd)})
        return subprocess.run(
            ["bash", str(_HOOK)], input=payload, env=env,
            cwd=str(self.cwd), capture_output=True, text=True,
        )

    # ── The regression ─────────────────────────────────────────────────────
    def test_resolves_vault_from_config_when_env_unset(self) -> None:
        """MEMORY_VAULT_PATH unset → resolve vault_path from .agentm-config.json
        and still detect the conflict file."""
        r = self._run(self._env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[conflict-merger]", r.stderr,
                      f"expected conflict notice on stderr; got: {r.stderr!r}")
        self.assertIn(_CONFLICT_NAME, r.stderr)

    # ── Companion behaviors (must keep passing) ────────────────────────────
    def test_env_var_still_wins_when_set(self) -> None:
        r = self._run(self._env(MEMORY_VAULT_PATH=str(self.vault)))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[conflict-merger]", r.stderr)
        self.assertIn(_CONFLICT_NAME, r.stderr)

    def test_graceful_skip_when_no_vault_anywhere(self) -> None:
        self._write_config(vault_path=None)
        r = self._run(self._env())
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("[conflict-merger]", r.stderr)

    def test_graceful_skip_when_plugin_root_unset(self) -> None:
        """No CLAUDE_PLUGIN_ROOT (not running as an installed plugin) → silent
        exit 0, even with a resolvable vault holding a conflict."""
        env = self._env()
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        r = self._run(env)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("[conflict-merger]", r.stderr)

    def test_no_notice_when_vault_clean(self) -> None:
        self.conflict.unlink()
        r = self._run(self._env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("[conflict-merger]", r.stderr)

    def test_mode_off_short_circuits(self) -> None:
        r = self._run(self._env(HARNESS_CONFLICT_MERGER_MODE="off"))
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("[conflict-merger]", r.stderr)

    # ── the broadened sweep surfaces through the hook ──────────────────────
    def _harness_dir(self) -> Path:
        return self.vault / "projects" / "demo" / "_harness"

    def test_detects_bracket_conflict_family(self) -> None:
        name = "FOLLOWUPS [Conflict].md"
        (self._harness_dir() / name).write_text("x", encoding="utf-8")
        r = self._run(self._env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[conflict-merger]", r.stderr)
        self.assertIn(name, r.stderr)

    def test_detects_copy_of_family(self) -> None:
        name = "Copy of FOLLOWUPS.md"
        (self._harness_dir() / name).write_text("x", encoding="utf-8")
        r = self._run(self._env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(name, r.stderr)
        self.assertIn("FOLLOWUPS.md", r.stderr)  # "Copy of " stripped to canonical

    def test_detects_numbered_duplicate_family(self) -> None:
        d = self._harness_dir()
        (d / "FOLLOWUPS.md").write_text("base", encoding="utf-8")  # base co-exists
        (d / "FOLLOWUPS (1).md").write_text("dup", encoding="utf-8")
        r = self._run(self._env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("FOLLOWUPS (1).md", r.stderr)

    def test_detects_lost_and_found_orphan(self) -> None:
        """The DriveFS lost_and_found/ dump — resolved via the fake HOME, so the
        scan is hermetic against the real machine — is swept and labeled."""
        laf = (self.fake_home / "Library" / "Application Support"
               / "Google" / "DriveFS" / "lost_and_found")
        laf.mkdir(parents=True)
        (laf / "orphaned-note.md").write_text("orphan", encoding="utf-8")
        r = self._run(self._env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[conflict-merger]", r.stderr)
        self.assertIn("orphaned-note.md", r.stderr)
        self.assertIn("lost", r.stderr.lower())  # labeled lost+found / lost_and_found


if __name__ == "__main__":
    unittest.main()
