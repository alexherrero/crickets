---
title: vault-git — design
status: launched
kind: design
scope: feature
area: crickets/obsidian-vault
governs: []
parent: crickets-hld.md
---

> [!NOTE]
> **Recast 2026-11-03 to describe what runs; the `vault-git` plugin is closed, not needed.** This page used to propose a crickets plugin that made a private GitHub repo the vault's transport. That plugin was never built, and the operator closed it on 2026-11-03 because the setup below already gives the vault history, an off-device backup and reach from other devices. The page now records that setup and why the plugin isn't coming. It governs no crickets code. The agentm side is the [Vault Storage & Presentation Design](https://github.com/alexherrero/agentm/wiki/agentm-vault-storage-presentation).

## Objective

Say how the vault at `~/Vault` keeps its history, gets backed up off the machine, and reaches other devices, so a session that wonders whether to build vault sync or backup finds the answer here: it already runs, and none of it lives in crickets.

## What runs

Three pieces each do one job. None of them is a crickets plugin, and none needs the operator day to day.

| Piece | Job | Where it lives |
|---|---|---|
| AgentM memory daemon | Commits the vault to its own local git repository as notes change. It never pushes. | agentm (the resident daemon) |
| `vault-backup-push` | Pushes that history to a private Gitea remote on the home NAS every four hours and at login, then checks the remote now holds what it sent. | The operator's private machine-setup repo, run by the launchd job `com.agentm.vault-backup` |
| Google Drive | Mirrors the `~/Vault` folder in place as plain files, for the phone and the chat assistants' Drive connectors. | Drive for Desktop |

**History.** The vault is a git repository whose git directory sits outside the vault folder, so Drive never syncs the object database. The daemon is the only committer.

**Backup.** The push only ever fast-forwards. If local and remote have diverged it refuses and logs why, because a timer has no business settling that. The remote is reached over SSH with a deploy key that can write only to the vault repository. Off the home network the run skips and the next one catches up.

**Reach.** Drive carries files, not git. An edit made on another device arrives as an ordinary file change and the daemon commits it like any other. Two devices editing one note between syncs leave a Drive conflicted copy, which the [obsidian-vault](crickets-obsidian-vault) backend tolerates and its `vault-doctor` skill reports.

**What crickets owns here.** Only the [obsidian-vault](crickets-obsidian-vault) storage backend: safe writes into the synced folder, and conflict-copy detection. Commit cadence, backup and the git remote are outside crickets.

## Why the plugin is closed

The proposal (June 2026) was a `vault-git` plugin making a private GitHub repo the vault's only transport, with every device a clone: deterministic init, sync, status and doctor scripts, a session-end autosync hook, a secret scan on every commit, and chat assistants proposing edits as pull requests. Drive was to be the discouraged fallback.

Every outcome it promised already runs: per-change history from the daemon, an off-device backup the operator controls from the Gitea push, and mobile and chat reach from the Drive mirror. The plugin would have added a second sync engine over the same folder and a second remote, and put a personal vault's full history on a third-party host. So it was closed as not needed rather than deferred.

The team-vault idea it pointed at (several people sharing one vault, with multi-root recall in the engine) was never part of what runs and is not picked up here.

## How to check it

All read-only. Leave commits in the vault to the daemon.

- `launchctl list | grep agentm` lists `com.agentm.daemon` and `com.agentm.vault-backup`.
- `git -C ~/Vault log -3` shows recent daemon commits.
- `git -C ~/Vault remote -v` shows the single backup remote.
- The backup log, `~/Library/Logs/vault-backup.log`, shows each run as pushed-and-verified, already current, or skipped.
- The `obsidian-vault:vault-doctor` skill checks the vault path and reports unresolved Drive conflict files.

## Rules that hold

- The git directory stays outside the Drive-mirrored folder.
- The backup never forces and never rewrites the remote.
- Any git remote for the vault stays private and on hardware the operator owns. The vault holds personal details by assumption, and a published history can't be unpublished.

## Dependencies

- **Points up at** the [crickets HLD](crickets-hld.md) and across to the agentm [Vault Storage & Presentation Design](https://github.com/alexherrero/agentm/wiki/agentm-vault-storage-presentation), which owns the same facts on the engine side. The two stay consistent.
- **Sibling:** [obsidian-vault](crickets-obsidian-vault), the storage backend crickets does ship.
- **Outside crickets:** the daemon (agentm), the backup script and its launchd job (the operator's machine setup), Gitea (the NAS), Drive for Desktop.

## Amendment log

**2026-11-03 — recast to what runs; the `vault-git` plugin closed as not needed.** The body now describes the setup in use: the AgentM daemon commits `~/Vault` to a local git repository, `vault-backup-push` (launchd `com.agentm.vault-backup`) pushes a verified fast-forward to a private Gitea remote on the home NAS every four hours, and Google Drive mirrors the folder as files. The proposed plugin (GitHub transport, init/sync/status/doctor scripts, session-end autosync) was never built and is closed. `status: proposed` → `launched` with `governs: []`: the page is now a tracked record of what runs, and governs no crickets code. *Why not keep the proposal open:* every outcome it promised is delivered by pieces that already run, and a GitHub transport would add a second sync engine and a third-party copy of a personal vault's history. **Re-audit trigger:** a second machine starts writing the vault through its own git clone, the backup remote moves off the NAS, or the vault leaves Drive.

**2026-06-28 — scripts + autosync-on.** Recast the git work as **deterministic scripts** (`vault_git_init`, `vault_git_sync`, `vault_git_status`, the `doctor` checks) with a thin skill over them, and set the **autosync hook on by default**. *Why scripts:* git operations are deterministic, so scripts are cheaper and firmer than an LLM skill, which earns its place only where judgment helps (reading `doctor` output). *Why autosync-on:* agent writes reach the remote without manual steps. The safety rules move from skill-discipline to **script-enforcement** (firmer), and the secret-scan becomes a **per-commit gate** because autosync now commits automatically. Resolved the commit-cadence open question (autosync-on); added the autosync-capture and offline-at-session-end risks. Applied positive-framing prose throughout (Tonal lesson 2). **Per-root forward-compat:** made explicit that each script targets a named root and the autosync hook syncs each configured root, so one machine can back several git vaults (a personal vault and a shared team repo) — keeping vault-git a single-repo transport *primitive* the future team-vault design composes per-root (no new scope; multi-root recall, the two-root split, and PR governance stay in that design). Swapped "load-bearing" → "critical" in the Objective per the operator's word ban.

**2026-06-27 — authored (draft).** Specified the `vault-git` crickets plugin as the parent design's recommended primary transport. Conformed to the abbreviated-design template. *Why a plugin, not a seam backend:* git here is transport over the existing `vault` backend; a backend would buy nothing and cost a conformance pass. **Re-audit triggers:** confirm the crickets `area:` at lift; revisit the LFS/doctor open questions at build; split out team-vault as its own agentm-substrate design when picked up.
