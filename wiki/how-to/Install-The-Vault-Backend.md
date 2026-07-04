# How to install the vault backing plugin

> [!NOTE]
> **Goal:** Install the `obsidian-vault` plugin and point the engine at your MemoryVault so `storage.backend=vault` resolves to it. `obsidian-vault` has been the only live vault backend since agentm v5.5.0 (the V5-3 cutover, 2026-06-17) — the kernel's built-in vault backend was deleted at that release, so there is no parallel-run step and nothing to fall back to.
> **Prereqs:** an agentm engine present (the backend only runs under it); an existing MemoryVault directory (a plain folder, optionally Drive-synced — see [Back the vault with Drive](https://github.com/alexherrero/agentm/wiki/Back-The-Vault-With-Drive)); the crickets plugin marketplace registered (`claude plugin marketplace add alexherrero/crickets`).

## Steps

1. Install the `obsidian-vault` plugin.

   ```bash
   claude plugin install obsidian-vault@crickets
   ```

   Dogfooding a sibling checkout instead of the installed plugin cache? Point `$OBSIDIAN_VAULT_SCRIPTS` at `<crickets-checkout>/src/obsidian-vault/scripts` — discovery checks that env override first, then a sibling `crickets/src/obsidian-vault/scripts` checkout next to your agentm checkout, then the installed plugin cache last.

2. Point the engine at your vault and select the `vault` backend — one command does both:

   ```bash
   python3 scripts/agentm_config.py --vault-path "/path/to/your/MemoryVault"
   ```

   (run from your agentm checkout, or wherever `agentm_config.py` is installed). This writes `plugins.obsidian-vault.vault_path` and sets `storage.backend=vault` in `~/.claude/.agentm-config.json`.

3. Confirm the engine discovers the plugin and resolves to it — run the verify step below; a `[OK]` on the `backend` row means selection resolved to `obsidian-vault`.

## Verify

Run the `vault-doctor` skill (or its read-only probe directly) for a one-pass health check — it confirms the configured `vault_path` is a real MemoryVault, that selection resolves `vault` to this plugin, and that no GDrive/DriveFS sync-conflict files remain:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/doctor_vault.py"
# three [OK]/[WARN]/[FAIL] rows: vault-path / backend / conflicts; exit 1 only on a FAIL
```

The probe is read-only (constructs no backend, writes neither the vault nor `~/.claude/.agentm-config.json`). Three `[OK]` rows and exit 0 mean the plugin is wired up.

## Troubleshooting

- **Engine refuses loudly on `storage.backend=vault`**: the plugin isn't discoverable — not installed at the native plugin cache, not found via `$OBSIDIAN_VAULT_SCRIPTS`, and no sibling checkout. Install it (step 1) or point `$OBSIDIAN_VAULT_SCRIPTS` at its `scripts/` dir. The engine never silently demotes to `device-local` — a loud refusal is by design.
- **Vault path unreachable (e.g. GDrive unmounted)**: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/doctor_vault.py"` reports the `vault-path` row as `[FAIL]` rather than the engine silently falling back — remount the drive and re-run.
- **No session-start nudge on Antigravity**: expected — Antigravity has no `SessionStart` event, so the conflict-merger nudge is Claude-Code-only. The detector stays reachable on demand via the `vault-doctor` skill and `doctor_vault.py`'s `conflicts` check (run it at session start). See [Antigravity limitations → Hooks](Antigravity-Limitations#2--hooks).

## See also

- [Obsidian vault backend](Obsidian-Vault-Backend) — the reference for the seam verbs, capability descriptor, and discovery/lock contract.
- [Install crickets plugins](Install-Into-Project) — the general plugin install paths.
- [CI gates](CI-Gates) — the gate battery the conformance-suite proof joins.
