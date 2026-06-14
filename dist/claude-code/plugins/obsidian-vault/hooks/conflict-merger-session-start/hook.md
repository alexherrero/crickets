---
name: conflict-merger-session-start
description: SessionStart hook that detects GDrive/DriveFS-induced conflict + duplicate files (`<file> (conflicted copy YYYY-MM-DD).md`, `[Conflict]`, `Copy of …`, ` (N)`) anywhere under the Obsidian vault, plus the DriveFS `lost_and_found/` dump, and surfaces an operator-facing notice per pair. Detection is heuristic; safe to graceful-skip when no vault resolves or the present engine is absent (nothing to scan).
kind: hook
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
---

# conflict-merger-session-start — GDrive conflict-file detection at SessionStart

When the operator works against the Obsidian vault from multiple devices (desktop + phone via Obsidian, multiple workstations, etc.), GDrive/DriveFS sync occasionally produces conflict files: `PLAN (conflicted copy 2026-05-27) - Mac.md` alongside the canonical `PLAN.md`, plus bracketed `[Conflict]`, `Copy of …`, and numbered ` (N)` duplicates. DriveFS additionally dumps files it could not re-home into a `lost_and_found/` folder with no notification. Without explicit detection, these accumulate silently — the operator discovers them weeks later in Obsidian's file browser, by which time merging is painful.

This hook walks the vault (and the DriveFS `lost_and_found/`) at SessionStart and surfaces an operator-facing notice per pair found, so the operator can decide right then whether to merge or defer.

## Where this lives (re-homed out of the kernel — V5-2)

This hook ships in the **obsidian-vault** plugin, beside the backend it serves — not in the storage-agnostic agentm kernel. The conflict-sweep machinery it walks (`detect_conflict_files`, `default_lost_and_found_root`, `_infer_conflict_base_path`) is re-homed into this plugin's `scripts/vault_conflicts.py`. The one piece that stays kernel-side is the pure filename classifier `_conflict_family` — the kernel's own named-plan dashboard (`queue_status_lite.py`) still consumes it, so `vault_conflicts.py` **imports** it from the present engine rather than vendoring a copy (LC-3).

## What it does

1. Resolves the vault path: `MEMORY_VAULT_PATH` env → the present engine's `.agentm-config.json` `vault_path` (read in place, never written — LC-4) → none. Graceful-skip if nothing resolves or the directory is missing.
2. Locates this plugin's `scripts/vault_conflicts.py` via `$CLAUDE_PLUGIN_ROOT`, and locates the present engine's `scripts/` dir (where `harness_memory.py` lives) to put on `sys.path` so `vault_conflicts.py`'s `from harness_memory import _conflict_family` resolves. Graceful-skip if either is absent — no engine present means nothing to import.
3. Calls `vault_conflicts.default_lost_and_found_root()` + `vault_conflicts.detect_conflict_files(vault_root, lost_and_found_root=laf)`, which walk the vault for the four marker families plus the DriveFS dump.
4. For each entry, prints a one-line operator-facing summary on stderr:
   ```
   [conflict-merger] N conflict/duplicate file(s) detected (M in vault, K in DriveFS lost_and_found):
       [vault]      conflict: projects/agentm/_harness/PLAN (conflicted copy 2026-05-27) - Mac.md
                    base:     projects/agentm/_harness/PLAN.md
       [lost+found] conflict: <orphan>
   ```
5. The hook itself is non-blocking — it surfaces information; the actual merge happens via `/work` or operator-direct in Obsidian. SessionStart never freezes on operator input.

## Why SessionStart (not idle)

Conflict-file accumulation correlates with operator-active multi-device work. SessionStart fires at the moment the operator is about to start a session — they can decide right then whether to deal with conflicts or defer.

## Graceful-skip conditions (silent)

- No vault resolves (`MEMORY_VAULT_PATH` unset and no engine config `vault_path`).
- Vault directory missing.
- `$CLAUDE_PLUGIN_ROOT/scripts/vault_conflicts.py` not found (plugin not installed as a plugin).
- The present engine's `scripts/harness_memory.py` not importable on this device — no engine, nothing to scan.
- No conflict files found (output empty; no operator notice).

## Configuration

- `HARNESS_CONFLICT_MERGER_MODE` env var:
  - `interactive` (default) — surface the notice + merge guidance at SessionStart.
  - `silent` — log findings to stderr but skip the guidance block (CI / scripted-session use).
  - `off` — full no-op.

## Host support

**Claude-only.** `SessionStart` has no Antigravity equivalent, so this hook is declared `supported_hosts: [claude-code]` — the Antigravity plugin carries the vault backend scripts but not this hook. (This mirrors the documented SessionStart gap: hooks bound to events Antigravity lacks don't ship to that host.)

## Settings fragment

Registered the same way as the other crickets SessionStart hooks; the emitted command resolves to `bash ${CLAUDE_PLUGIN_ROOT}/hooks/conflict-merger-session-start/conflict-merger-session-start.sh` (timeout 5).

## Related

- `scripts/vault_conflicts.py` — `detect_conflict_files()` / `default_lost_and_found_root()` / `_infer_conflict_base_path()`, the re-homed helpers this hook walks.
- The kernel's `_conflict_family` classifier (imported, not vendored — LC-3) and `queue_status_lite.py`, its other consumer.
- V5-2 task 2 — the re-home of the vault-specific conflict-merger machinery out of the kernel into this plugin.
