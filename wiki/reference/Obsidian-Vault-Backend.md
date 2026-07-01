<!-- mode: reference -->
# Obsidian vault backend

## Architecture

Obsidian Vault lets your agent keep its memory inside your own Obsidian vault instead of a store buried in a device-local folder. Everything the agent learns lands as plain Markdown you can open, read, and edit in Obsidian — and because the vault lives on Google Drive, that memory follows you from one device to the next. It also knows how to cope with the mess cloud sync leaves behind, spotting the conflict and duplicate files Drive scatters around so your memory stays clean. This is a storage backend the memory engine picks up and runs on its own, so nothing in your normal workflow calls it directly. It stands alone — it needs no other plugin, only a vault to point at.

> [!IMPORTANT]
> **Status: pending** (V5-2). This page is a forward-declared skeleton — the `obsidian-vault` plugin is built but **not yet the live backend** (V5-2 parallel-run, pre-V5-3-cutover). A later `/work` task flips it to a documented surface only once the diff proves each row. Do not treat any reserved value below as shipped; the descriptor, seam-verb, and acceptance rows are reserved, not yet verified. (The `vault-doctor` skill and `doctor_vault.py`, shipped in V5-2 task 6, are the exception — they are reachable today.)

### Diagram

How memory reaches the vault — the engine hands each save to the backend, which writes plain Markdown into the Drive-synced folder while watching for the conflict files sync leaves behind:

![The obsidian-vault storage flow: the memory engine hands each save to the vault backend, which guards concurrent writers and writes plain Markdown into your Drive-synced Obsidian vault, while conflict detection spots the stray copies cloud sync leaves behind](diagrams/obsidian-vault-storage.svg)

How it composes — obsidian-vault requires and enhances nothing, standing alone on the AgentM memory engine that discovers and loads it:

![obsidian-vault composition: the plugin has no couplings to other plugins — it stands alone, running one-way on the AgentM memory engine that discovers, selects, and loads it](diagrams/obsidian-vault-composition.svg)

### How it works

The heart of the plugin is a storage backend — the piece the memory engine writes to and reads from. When you point the engine at your vault, it hands every save to this backend, which writes the memory out as Markdown into the folder Drive keeps in sync. Because that folder can be open on more than one machine at once, the backend takes care to let two sessions write to the same vault without clobbering each other's work. It leans on the engine's own building blocks to do that rather than carrying its own copies, so it always runs as part of the engine, never on its own.

Cloud sync has a habit of leaving litter behind — a duplicate here, a "conflicted copy" there — whenever two devices touch the same file. The plugin knows what those stray files look like and can point them out so you can clean them up. On Claude Code it does this for you at the start of a session; everywhere else, a small health check surfaces the same thing on demand and confirms your vault is wired up and conflict-free.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | — | None. The plugin is standalone (`requires: []`); it depends on the agentm memory engine at runtime, not on another crickets plugin. |
| Required by (hard) | — | None. |

### Why not

Obsidian vault backend is opinionated about where memory lives, and it will not fit everyone. Reach for something else if:

- You don't keep an Obsidian vault, or you don't sync one through Google Drive — the device-local backend the engine ships with needs no plugin and no setup.
- You want a store with server-side encryption or true multi-writer transactions; this backend stores plain Markdown and reconciles concurrent writes with a content-hash CAS, not a database.
- You'd rather not deal with sync-conflict files at all. Cross-device Drive sync produces them, and while the plugin detects and surfaces them, resolving each pair is still your call.

## Reference

### Commands & skills

No host-facing commands — the plugin ships mainly a `scripts/` backend payload that the agentm engine loads. The operator-facing surface is the `vault-doctor` skill and its Claude-only session-start hook; the rest of the table is the backend and its vault machinery. Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`vault-doctor`](https://github.com/alexherrero/crickets/blob/main/src/obsidian-vault/skills/vault-doctor/SKILL.md) | skill | Read-only health check over `doctor_vault.py` — vault path, backend selection, conflict sweep; reachable on **both** hosts (`supported_hosts: [claude-code, antigravity]`). |
| [`conflict-merger-session-start`](https://github.com/alexherrero/crickets/blob/main/src/obsidian-vault/hooks/conflict-merger-session-start/hook.md) | hook | Surfaces GDrive/DriveFS conflict + duplicate files at session start (Claude Code only). |
| [`storage_vault.py`](https://github.com/alexherrero/crickets/blob/main/src/obsidian-vault/scripts/storage_vault.py) | script | The `vault` backend — implements the storage seam, composing the V5-0 write stack (mutex + CAS + atomic-write). |
| [`doctor_vault.py`](https://github.com/alexherrero/crickets/blob/main/src/obsidian-vault/scripts/doctor_vault.py) | script | Read-only probe backing `vault-doctor` — three rows (`vault-path` / `backend` / `conflicts`), exit 1 only on a `FAIL`; constructs no backend, writes neither the vault nor the engine config. |
| [`vault_conflicts.py`](https://github.com/alexherrero/crickets/blob/main/src/obsidian-vault/scripts/vault_conflicts.py) | script | GDrive/DriveFS sync-conflict detection; imports the kernel's filename classifier rather than vendoring it. |

### Seam verbs

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

### Capability descriptor

The backend declares a capability descriptor plus a named conflict strategy that the engine reads.

| Capability | Value |
|---|---|
| concurrent-writers | yes |
| conflict-files | yes |
| encryption | no |
| sync | yes |
| conflict strategy | "GDrive whole-file merger" (named) |

_Descriptor semantics pending — filled by `/work` once the task ships._

### Vault-specific machinery

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

### Discovery + lock contract

| Contract | Behaviour |
|---|---|
| Discovery | the engine locates the installed plugin by a convention path off the plugin-install root |
| Fail-loud | if `storage.backend=vault` is selected but the plugin is absent, the engine refuses loudly — it never silently demotes to device-local |
| Write-lock | the backend **imports** the agentm kernel's canonical write-lock module; it never vendors a copy |
| Runtime precondition | the backend only ever runs under a present engine |

_Contract details pending — filled by `/work` once the task ships._

### First-run adoption

| Behaviour | Value |
|---|---|
| On install | reads the existing `vault_path` from `~/.claude/.agentm-config.json` **in place** (never writes it) |
| Registration | registers as the `vault` backend |
| Data movement | none — zero re-setup, zero data movement |

_Adoption details pending — filled by `/work` once the task ships._

### Acceptance proof

The backend must pass its checks before the later V5-3 cutover is triggered.

| Proof | What it asserts |
|---|---|
| Conformance suite | GREEN on the V5-1-authored suite — verb battery + byte-identical LF-exact markdown round-trip |
| Parallel-run | byte-identical resolution against the still-present built-in backend |
| Behavioral contract | `write` **bites** on a concurrent modification (raises `ConcurrentModificationError` via the content-hash CAS) + the plugin advertises the built-in's exact `capabilities` / `conflict_strategy` — asserted against both backends for parity |

_Proof harness pending — filled by `/work` once the task ships._

> [!WARNING]
> **Conformance-suite green proves byte-faithfulness, not the concurrency contract.** The V5-1 suite's `UNIVERSAL_CHECKS` are single-writer / byte-round-trip only — they never exercise the `vault_mutex` / content-hash CAS / `ConcurrentModificationError`. A backend degraded to `atomic_write`-only (dropping the load-bearing CAS) passes every conformance + parallel-run case GREEN. Because V5-3 deletes the built-in backend on the strength of this gate, the cutover gate must **also** assert the behavioral contract — the CAS bite + capability parity in the row above. The universal suite can't carry the CAS check itself: the frozen seam's `write(locator, content)` exposes no CAS precondition (DC-7), so crickets adds it as a backend-specific check, not a kernel-suite extension.

### Host coverage

| Host | Conflict-merger nudge | Detector reachability |
|---|---|---|
| Claude Code | automatic session-start nudge fires (`conflict-merger-session-start` hook) | reachable — automatic + on-demand |
| Antigravity | no automatic nudge (no `SessionStart` event) | reachable on demand via the `vault-doctor` skill + `doctor_vault.py`'s `conflicts` check |

> [!NOTE]
> On Antigravity, detection is **not** lost — only the automatic nudge. The detector stays reachable through the `vault-doctor` skill (`supported_hosts: [claude-code, antigravity]`) and `doctor_vault.py`'s read-only `conflicts` check. Both shipped in V5-2 task 6. See the [Antigravity limitations register → Hooks](Antigravity-Limitations#2--hooks) for the host-gap context.

## Configuration

The vault location is resolved at runtime, not baked into the plugin. The engine reads `plugins.obsidian-vault.vault_path` from its config (set via `agentm_config --vault-path`), and `$MEMORY_VAULT_PATH` is the per-invocation override. The plugin itself reads that path in place and never writes it. No other configuration — it works out of the box once a vault is configured.

## See also

- [Install the vault backend](Install-The-Vault-Backend) — install the plugin and prove parallel-run identical before the cutover.
- [CI gates](CI-Gates) — the gate battery the conformance-suite + parallel-run proofs will join.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin's `scripts/` payload is.
- [Antigravity limitations](Antigravity-Limitations) — why the automatic session-start nudge is Claude-only, and the host-gap register it belongs to.
- [obsidian-vault design](crickets-obsidian-vault) · [vault-git design](crickets-vault-git) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)
