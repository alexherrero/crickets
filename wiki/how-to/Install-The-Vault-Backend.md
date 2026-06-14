# How to install the vault backing plugin and verify parallel-run

> [!IMPORTANT]
> **Status: pending** (V5-2). This is a forward-declared skeleton — the `obsidian-vault` plugin is not yet built. Step bodies are reserved, not written; a later `/work` task fills them from the shipped diff. Do not follow these steps yet.

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

_Verification commands filled by `/work` once the task ships — the green parallel-run is what triggers the later V5-3 cutover._

## Troubleshooting

- **Engine refuses loudly on `storage.backend=vault`**: the plugin is absent or not discovered off the plugin-install root. _Fix filled by `/work` once the task ships._ The engine never silently demotes to device-local — a loud refusal is by design.
- **No session-start nudge on Antigravity**: expected — Antigravity has no `SessionStart` event, so the conflict-merger nudge is Claude-Code-only. The detector stays reachable via the operator skill and the doctor check.

## See also

- [Obsidian vault backend](Obsidian-Vault-Backend) — the reference for the seam verbs, capability descriptor, and discovery/lock contract.
- [Install crickets plugins](Install-Into-Project) — the general plugin install paths.
- [CI gates](CI-Gates) — the gate battery the conformance-suite + parallel-run proofs join.
