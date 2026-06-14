# How to install the vault backing plugin and verify parallel-run

> [!IMPORTANT]
> **Status: pending** (V5-2). This is a forward-declared skeleton — the `obsidian-vault` plugin is built but **not yet the live backend** (V5-2 parallel-run, pre-V5-3-cutover). Step bodies are reserved, not written; a later `/work` task fills them from the shipped diff. Do not follow these steps yet.

> [!NOTE]
> **Goal:** Install the `obsidian-vault` plugin alongside the still-present built-in backend, then prove the two resolve byte-identically before the V5-3 cutover.
> **Prereqs:** an agentm engine present (the backend only runs under it); an existing `vault` set up via `~/.claude/.agentm-config.json`; the crickets marketplace/plugin install path. _Exact prereqs filled by `/work` once the task ships._

## Steps

1. Install the `obsidian-vault` plugin.

   _Filled by `/work` once the task ships._

2. Confirm first-run adoption picked up the existing `vault_path` in place (no re-setup, no data movement).

   _Filled by `/work` once the task ships._

3. Confirm the engine discovered the plugin and registered it as the `vault` backend.

   _Filled by `/work` once the task ships._

4. Run the V5-1 conformance suite against the plugin backend (verb battery + LF-exact markdown round-trip) and confirm GREEN.

   _Filled by `/work` once the task ships._

5. Run the parallel-run check against the still-present built-in backend and confirm byte-identical resolution.

   _Filled by `/work` once the task ships._

## Verify

Run the `vault-doctor` skill (or its read-only probe directly) for a one-pass health check — it confirms the configured `vault_path` is a real MemoryVault, that selection resolves `vault` to this plugin, and that no GDrive/DriveFS sync-conflict files remain:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/doctor_vault.py"
# three [OK]/[WARN]/[FAIL] rows: vault-path / backend / conflicts; exit 1 only on a FAIL
```

The probe is read-only (constructs no backend, writes neither the vault nor `~/.claude/.agentm-config.json`). Three `[OK]` rows and exit 0 mean the plugin is wired up.

> [!NOTE]
> The remaining verification — the green **parallel-run** against the still-present built-in backend that triggers the later V5-3 cutover — is _filled by `/work` once that step ships._ `vault-doctor` checks wiring + health; it does not itself prove parallel-run identity.

## Troubleshooting

- **Engine refuses loudly on `storage.backend=vault`**: the plugin is absent or not discovered off the plugin-install root. _Fix filled by `/work` once the task ships._ The engine never silently demotes to device-local — a loud refusal is by design.
- **No session-start nudge on Antigravity**: expected — Antigravity has no `SessionStart` event, so the conflict-merger nudge is Claude-Code-only. The detector stays reachable on demand via the `vault-doctor` skill and `doctor_vault.py`'s `conflicts` check (run it at session start). See [Antigravity limitations → Hooks](Antigravity-Limitations#2--hooks).

## See also

- [Obsidian vault backend](Obsidian-Vault-Backend) — the reference for the seam verbs, capability descriptor, and discovery/lock contract.
- [Install crickets plugins](Install-Into-Project) — the general plugin install paths.
- [CI gates](CI-Gates) — the gate battery the conformance-suite + parallel-run proofs join.
