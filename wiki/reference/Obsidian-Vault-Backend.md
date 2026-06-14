<!-- mode: reference -->
# Obsidian vault backend

> [!IMPORTANT]
> **Status: pending** (V5-2). This page is a forward-declared skeleton — the `obsidian-vault` plugin is built but **not yet the live backend** (V5-2 parallel-run, pre-V5-3-cutover). A later `/work` task flips it to a documented surface only once the diff proves each row. Do not treat any value below as shipped; rows are reserved, not verified.

The `obsidian-vault` plugin is a crickets plugin (group version 0.1.0) that re-homes the agentm memory engine's `vault` storage backend out of the agentm kernel and into a crickets plugin. The backend is **agentm-facing**: it ships as the plugin's `scripts/` payload, the agentm engine discovers and loads it, and the host (Claude Code / Antigravity) never calls it directly. This page indexes what the backend implements, the descriptor it declares, and the discovery/lock contract it lives under.

## ⚡ Quick Reference

| Aspect | Value |
|---|---|
| Plugin slug | `obsidian-vault` |
| Group version | 0.2.0 (V5-2 task 6 — added the `vault-doctor` skill + `doctor_vault.py`) |
| Audience | agentm engine (agentm-facing, not host-facing) |
| Packaging | plugin `scripts/` payload — **not** a new manifest `kind:` |
| Protocol name | `vault` |
| Implements | the V5-1 storage seam |
| Return type | the seam's locator type |

_All rows pending — filled by `/work` once the task ships._

## Seam verbs

The backend implements the V5-1 storage seam: five core verbs plus two ergonomic verbs, registered under the protocol name `vault`.

| Verb | Class |
|---|---|
| `resolve` | core |
| `read` | core |
| `write` | core |
| `list` | core |
| `exists` | core |
| `info` | ergonomic |
| `mkdir` | ergonomic |

_Per-verb contracts pending — filled by `/work` once the task ships._

## Capability descriptor

The backend declares a capability descriptor plus a named conflict strategy that the engine reads.

| Capability | Value |
|---|---|
| concurrent-writers | yes |
| conflict-files | yes |
| encryption | no |
| sync | yes |
| conflict strategy | "GDrive whole-file merger" (named) |

_Descriptor semantics pending — filled by `/work` once the task ships._

## Vault-specific machinery

The plugin carries the vault-specific machinery beside the backend.

| Component | Role |
|---|---|
| vault probe | detection / ranking of a present vault |
| GDrive conflict-merger | sync-conflict detection family + the whole-file merge strategy |
| `conflict-merger-session-start` hook | session-start nudge (Claude Code only — see Host coverage) |
| `vault-doctor` skill | operator-facing health check over `doctor_vault.py`; reachable on **both** hosts (`supported_hosts: [claude-code, antigravity]`) |
| `doctor_vault.py` | read-only `doctor` check — three rows (`vault-path` / `backend` / `conflicts`), exit 1 only on a `FAIL`; constructs no backend, writes neither the vault nor the engine config |
| state migration script | per-project state migration |

> [!NOTE]
> The `vault-doctor` skill and `doctor_vault.py` shipped in V5-2 task 6 and are reachable today; the remaining rows in this table stay pending until the diff proves each. The skill + doctor are the Antigravity-reachable substitute for the Claude-only session-start nudge — see [Host coverage](#host-coverage).

_Remaining component contracts pending — filled by `/work` once the task ships._

## Discovery + lock contract

| Contract | Behaviour |
|---|---|
| Discovery | the engine locates the installed plugin by a convention path off the plugin-install root |
| Fail-loud | if `storage.backend=vault` is selected but the plugin is absent, the engine refuses loudly — it never silently demotes to device-local |
| Write-lock | the backend **imports** the agentm kernel's canonical write-lock module; it never vendors a copy |
| Runtime precondition | the backend only ever runs under a present engine |

_Contract details pending — filled by `/work` once the task ships._

## First-run adoption

| Behaviour | Value |
|---|---|
| On install | reads the existing `vault_path` from `~/.claude/.agentm-config.json` **in place** (never writes it) |
| Registration | registers as the `vault` backend |
| Data movement | none — zero re-setup, zero data movement |

_Adoption details pending — filled by `/work` once the task ships._

## Acceptance proof

The backend must pass two checks before the later V5-3 cutover is triggered.

| Proof | What it asserts |
|---|---|
| Conformance suite | GREEN on the V5-1-authored suite — verb battery + byte-identical LF-exact markdown round-trip |
| Parallel-run | byte-identical resolution against the still-present built-in backend |
| Behavioral contract | `write` **bites** on a concurrent modification (raises `ConcurrentModificationError` via the content-hash CAS) + the plugin advertises the built-in's exact `capabilities` / `conflict_strategy` — asserted against both backends for parity |

_Proof harness pending — filled by `/work` once the task ships._

> [!WARNING]
> **Conformance-suite green proves byte-faithfulness, not the concurrency contract.** The V5-1 suite's `UNIVERSAL_CHECKS` are single-writer / byte-round-trip only — they never exercise the `vault_mutex` / content-hash CAS / `ConcurrentModificationError`. A backend degraded to `atomic_write`-only (dropping the load-bearing CAS) passes every conformance + parallel-run case GREEN. Because V5-3 deletes the built-in backend on the strength of this gate, the cutover gate must **also** assert the behavioral contract — the CAS bite + capability parity in the row above. The universal suite can't carry the CAS check itself: the frozen seam's `write(locator, content)` exposes no CAS precondition (DC-7), so crickets adds it as a backend-specific check, not a kernel-suite extension.

## Host coverage

| Host | Conflict-merger nudge | Detector reachability |
|---|---|---|
| Claude Code | automatic session-start nudge fires (`conflict-merger-session-start` hook) | reachable — automatic + on-demand |
| Antigravity | no automatic nudge (no `SessionStart` event) | reachable on demand via the `vault-doctor` skill + `doctor_vault.py`'s `conflicts` check |

> [!NOTE]
> On Antigravity, detection is **not** lost — only the automatic nudge. The detector stays reachable through the `vault-doctor` skill (`supported_hosts: [claude-code, antigravity]`) and `doctor_vault.py`'s read-only `conflicts` check. Both shipped in V5-2 task 6. See the [Antigravity limitations register → Hooks](Antigravity-Limitations#2--hooks) for the host-gap context.

## See also

- [Install the vault backend](Install-The-Vault-Backend) — install the plugin and prove parallel-run identical before the cutover.
- [CI gates](CI-Gates) — the gate battery the conformance-suite + parallel-run proofs will join.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin's `scripts/` payload is.
- [Antigravity limitations](Antigravity-Limitations) — the host-gap register the missing `SessionStart` nudge belongs to.
