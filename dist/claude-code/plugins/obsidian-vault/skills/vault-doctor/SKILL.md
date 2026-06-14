---
name: vault-doctor
description: Diagnose the Obsidian/Google-Drive vault storage backend (the obsidian-vault plugin). Confirms the configured vault_path is a real MemoryVault, the plugin is the backend selection resolves to, and no unresolved GDrive/DriveFS sync-conflict files remain. Read-only — never writes the vault or the engine config. Invoke when the vault backend misbehaves, after installing the plugin, or on Antigravity (which has no session-start conflict nudge).
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: user
---

# vault-doctor

Operator-facing health check for the **obsidian-vault** backing plugin — the
re-homed `vault` storage backend the agentm memory engine discovers and loads.
This skill is the thin interactive surface over the read-only probe
`scripts/doctor_vault.py`; it never mutates the vault or the engine config (LC-4 —
`vault_path` is read in place).

## When to invoke

- **After installing the obsidian-vault plugin** — confirm selection now resolves
  `vault` to the plugin (the parallel-run precondition) and the configured
  `vault_path` is the real MemoryVault.
- **When memory recall/save misbehaves** under `storage.backend=vault` — is the
  backend even the one the engine selected, or did it refuse / fall through?
- **When you suspect GDrive/DriveFS sync conflicts** — `(conflicted copy …)`,
  `[Conflict]`, `Copy of …`, numbered `(N)` duplicates, or files dumped into the
  DriveFS `lost_and_found/`.
- **On Antigravity, at session start (by hand).** Antigravity has no `SessionStart`
  event, so the `conflict-merger-session-start` hook does not fire there — see
  [Antigravity coverage](#antigravity-coverage) below. Running this skill is the
  reachable substitute: same detector, on demand.

## What it checks

`doctor_vault.py` runs three read-only checks and prints one
`[OK]`/`[WARN]`/`[FAIL]` row each:

| Check | Asserts | FAIL when |
|---|---|---|
| `vault-path` | the configured `vault_path` resolves to a real MemoryVault (the `vault_probe` shape: `_meta/repos.json` or `personal-private/`), recovering a nested `Obsidian/AgentMemory` via its parent | no `vault_path` configured, or the path does not exist |
| `backend` | selection resolves the `vault` protocol to **this plugin** — not the kernel built-in, not a silent demotion to device-local — routed through the engine's own `storage_preview`, so the row can't drift from runtime | the engine would refuse at runtime (plugin absent/unloadable; `vault` selected with no `vault_path`) |
| `conflicts` | the conflict-merger detector finds **no** unresolved GDrive/DriveFS conflict files in the vault (and the `lost_and_found/` dump) | — (conflict files are a `WARN` to triage, never a hard install FAIL) |

`WARN` rows are advisory (a conflict file to merge by hand, or "no agentm engine
reachable to verify" on a crickets-only checkout). `main` exits **1 only on a
`FAIL`**; `OK`/`WARN` exit 0.

## How to run

The probe ships beside the backend in this plugin's `scripts/`. Locate and run it:

1. **Locate `doctor_vault.py`.** As an installed plugin it lives at
   `$CLAUDE_PLUGIN_ROOT/scripts/doctor_vault.py` (Claude Code) or the equivalent
   plugin root on Antigravity. In a dogfood checkout:
   `<crickets>/src/obsidian-vault/scripts/doctor_vault.py`.
2. **Run it** (it resolves `vault_path` from `$MEMORY_VAULT_PATH` → the on-device
   `~/.claude/.agentm-config.json` automatically; pass `--vault-path <dir>` to
   override):

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/doctor_vault.py"
   # or scan only the vault tree (skip the DriveFS lost_and_found/ sweep):
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/doctor_vault.py" --no-lost-and-found
   ```

3. **Read the rows** and act:
   - `vault-path [FAIL]` → set `vault_path` (`agentm_config --vault-path <dir>`) or
     point `MEMORY_VAULT_PATH` at the real MemoryVault.
   - `backend [FAIL]` → the message carries the exact remediation (install
     `obsidian-vault@crickets`, set `$OBSIDIAN_VAULT_SCRIPTS`, or change
     `storage.backend`). It mirrors what the engine prints on refusal.
   - `conflicts [WARN]` → review each pair in Obsidian or via `diff <base>
     <conflict>` and merge by hand. The detector **surfaces**, it does not
     auto-merge.

The kernel-side storage doctor (`backend_selection.py --doctor`) is the
complementary check for *which* backend is selected and whether its plugin is
installed; this skill adds the vault-specific shape + conflict checks.

## Antigravity coverage

On **Claude Code**, the `conflict-merger-session-start` hook walks the vault for
conflict files automatically at session boot. **Antigravity has no `SessionStart`
event**, so that nudge never fires there ([Antigravity limitations
register](https://github.com/alexherrero/crickets/wiki/Antigravity-Limitations)).

Detection is **not lost** on Antigravity — only the automatic nudge. The detector
is fully reachable through this skill and `doctor_vault.py`'s `conflicts` check.
Run vault-doctor at the start of an Antigravity session (or whenever you suspect a
sync conflict) to get the same surfacing the Claude Code hook gives for free.

## Read-only contract

`doctor_vault.py` constructs no backend (construction would `mkdir` the vault
root), writes neither the vault nor `~/.claude/.agentm-config.json`, and mutates
nothing. It is safe to run against the operator's live vault at any time. The
checks that need the agentm engine (the `vault_probe` shape test, `storage_preview`,
the conflict classifier) **locate** the engine and import from it (LC-3 — never a
vendored copy); when no engine is reachable they degrade to a `WARN`, never a
crash.
