---
title: vault-git — design
status: proposed
kind: design
scope: feature
area: crickets/obsidian-vault   # nearest vault-domain capability area; may warrant its own — see Risks
parent: crickets-hld.md
---

> [!NOTE]
> **Proposed** (lifted to tracked `wiki/designs/` 2026-06-28). The git-transport plugin under the agentm [Vault Storage & Presentation Design](https://github.com/alexherrero/agentm/wiki/agentm-vault-storage-presentation) — the plugin is forthcoming, so this governs no code yet. A vault-domain crickets capability alongside [obsidian-vault](crickets-obsidian-vault).

## Objective

`vault-git` is a crickets plugin that makes a private GitHub repo the vault's transport and keeps it healthy. It does for git-backing what `install.sh` does for the harness: makes the correct setup the easy default, so the operator never has to remember the one critical rule or hand-maintain `.gitignore`. It is the parent design's recommended primary transport — it serves history, off-device backup, and the chat propose-via-PR path. It is a plugin that uses the storage seam, and manages the *transport* under the existing `vault` backend's `SOURCE` tier.

## Overview

The plugin ships **deterministic scripts** for the git work, an **autosync hook that runs at session end (on by default)**, and a **thin skill** that invokes them and reads back results. Git operations are deterministic, so they live in scripts — cheaper and firmer than routing routine `add`/`commit`/`push` through an LLM. The skill earns its place where judgment helps: explaining a `doctor` result and guiding the fix. Setup offers two modes — **git-only** (recommended; every device a clone) or **hybrid** (Drive kept for mobile, with `.git` held outside the synced tree). Both commit only `SOURCE`-tier markdown; the `.gitignore` the init script writes keeps the derived, machine-local tier out, following the seam's `LOCAL_INDEX` rule.

**Per-root by design (forward-compat).** Each script targets a named vault root, so one machine can back several git vaults at once — a personal vault and a shared team repo, for instance — and the autosync hook syncs each configured root. This keeps vault-git a single-repo transport *primitive* that the future team-vault design composes per-root (see Risks).

## Design

The git work lives in deterministic scripts; the skill is a thin layer over them.

| Primitive | Kind | Contract (entry → exit · invocation) |
|---|---|---|
| `vault_git_init` | script | Operator runs once per vault. Creates or points at a private repo, writes the `.gitignore`, makes the first commit, sets the remote, pushes. Idempotent — re-running verifies the setup. Halts before the first commit if it finds `.env` or secret patterns. |
| `vault_git_sync` | script | `add -A` → scan for secrets → timestamped commit → `pull --rebase` → push. The autosync hook calls it; the operator can also run it directly. A conflict exits as a clear "resolve these N files" report. If the remote is unreachable, it commits locally and reports the skipped push. |
| `vault_git_status` | script | Read-only. One line: ahead/behind, dirty count, last-snapshot age. |
| `vault-git doctor` | script + thin skill | The script runs the checks (derived tier ignored, remote reachable, no tracked secrets, `.git` placement in hybrid mode); the skill reads the result and guides any fix. Folds into the agentm `doctor` surface. |
| `vault-git-autosync` hook | **on by default** | A `Stop`-event hook (the commit-on-stop pattern) runs `vault_git_sync` for each configured git-backed root at session end, so agent writes reach every remote automatically. |

**Setup recipe** (what `init` plus the hook give the operator): run `vault_git_init` once. From then on, autosync commits and pushes at every session end, so the vault stays current on its own. For edits made outside a session, Obsidian Git keeps the clone synced on desktop and Android (auto-pull on open, commit-and-push on an interval), and Working Copy + Obsidian does the same on iOS. Chat surfaces read through the GitHub connector and propose changes as PRs.

**Safety rules (the scripts enforce these deterministically, which is firmer than a skill remembering them):**
- **Commit only `SOURCE`-tier markdown** — the `.gitignore` excludes the derived tier (`*.sqlite*`, `.obsidian/workspace*`) and conflict copies.
- **Push only fast-forwards** — `sync` rebases and pushes, leaving history intact.
- **Scan for secrets before every commit** — `init` gates the first commit and `sync` gates each one. This gate matters more now that autosync commits automatically: it stands between an accidental `.env` and an automatic push.
- **Keep chat surfaces to read + propose-via-PR** — they reach the repo through a connector, and the scripts run where a real shell and filesystem exist (Claude Code, Antigravity).

### Opinions it consumes

This is a transport/setup capability, so it consumes none of the four workflow Opinions (`done` / `good` / `efficient` / `how-we-engineer`) by name; its safety rules are engineering-standard hygiene. **Open:** whether infrastructure plugins join the Opinion model or stand outside it — flagged for the parent design.

## Dependencies

- **Composes under** the seam's `vault` backend (`SOURCE` tier), reusing `Capabilities.sync` / `conflict_files` and the `LOCAL_INDEX` rule. See [Memory↔Storage Seam](https://github.com/alexherrero/agentm/wiki/memory-storage-seam).
- **Points up at** [Vault Storage & Presentation Design](https://github.com/alexherrero/agentm/wiki/agentm-vault-storage-presentation) (the transport-vs-presentation split and the pick-one decision).
- **Mutually exclusive with** [Back the vault with Google Drive](https://github.com/alexherrero/agentm/wiki/Back-The-Vault-With-Drive) — one transport per folder.
- **Pairs with** [Set up Obsidian on the vault](https://github.com/alexherrero/agentm/wiki/Use-Obsidian-With-The-Vault) when the operator uses Obsidian (the Obsidian Git settings live there).
- **Depended on by** the team-vault extension (forward-ref) — it composes vault-git per-root, then adds multi-root recall at the engine.

## Risks & open questions

- **Built vs designed:** nothing built — proposal only. The setup recipe is verified operator knowledge (2026-06-27); the scripts and hook are unbuilt.
- **Autosync-on captures whatever is in the vault at session end.** Two consequences, both handled: a secret could be auto-committed → the per-commit secret-scan gate stops it; a half-finished edit could be committed → harmless, because the vault is markdown and any session-end snapshot is a valid state, reversible through git history.
- **Offline at session end** → `sync` commits locally and reports the skipped push; the next online sync catches up.
- **Team vault is a separate item — and composes this plugin per-root.** A shared team vault inverts the layers and needs one real agentm *engine* change — multi-root recall (`vault_roots` + union + provenance) — tracked as an agentm-substrate item (the team-vault / multi-root-recall item sub-idea 2; likely a late-V7/V8 slot). vault-git stays the single-repo transport: a member runs it on their personal vault *and* the shared team repo at once (per-root, above), and multi-root recall unions them at the engine. The two-root split and PR-gated governance belong to that design.
- **Open:** `git-lfs` policy for media-heavy vaults (own it here or as a parent-design cross-cutting rule) · `doctor` severity — which checks warn vs fail · its own `area:` (`crickets/vault-transport`) vs folding under `crickets/obsidian-vault`, decided at lift.

## References

- [Vault Storage & Presentation Design](https://github.com/alexherrero/agentm/wiki/agentm-vault-storage-presentation) — the parent design; the pick-one-transport decision.
- [Back the vault with Google Drive](https://github.com/alexherrero/agentm/wiki/Back-The-Vault-With-Drive) — the mutually-exclusive sibling. [Set up Obsidian on the vault](https://github.com/alexherrero/agentm/wiki/Use-Obsidian-With-The-Vault) — the presentation layer it pairs with.
- [Memory↔Storage Seam](https://github.com/alexherrero/agentm/wiki/memory-storage-seam) — why this stays a transport plugin over the existing backend; the tiers and capabilities it reuses.
- the team-vault / multi-root-recall item — origin record + the team-vault sub-idea.

## Amendment log

**2026-06-28 — scripts + autosync-on.** Recast the git work as **deterministic scripts** (`vault_git_init`, `vault_git_sync`, `vault_git_status`, the `doctor` checks) with a thin skill over them, and set the **autosync hook on by default**. *Why scripts:* git operations are deterministic, so scripts are cheaper and firmer than an LLM skill, which earns its place only where judgment helps (reading `doctor` output). *Why autosync-on:* agent writes reach the remote without manual steps. The safety rules move from skill-discipline to **script-enforcement** (firmer), and the secret-scan becomes a **per-commit gate** because autosync now commits automatically. Resolved the commit-cadence open question (autosync-on); added the autosync-capture and offline-at-session-end risks. Applied positive-framing prose throughout (Tonal lesson 2). **Per-root forward-compat:** made explicit that each script targets a named root and the autosync hook syncs each configured root, so one machine can back several git vaults (a personal vault and a shared team repo) — keeping vault-git a single-repo transport *primitive* the future team-vault design composes per-root (no new scope; multi-root recall, the two-root split, and PR governance stay in that design). Swapped "load-bearing" → "critical" in the Objective per the operator's word ban.

**2026-06-27 — authored (draft).** Specified the `vault-git` crickets plugin as the parent design's recommended primary transport. Conformed to the abbreviated-design template. *Why a plugin, not a seam backend:* git here is transport over the existing `vault` backend; a backend would buy nothing and cost a conformance pass. **Re-audit triggers:** confirm the crickets `area:` at lift; revisit the LFS/doctor open questions at build; split out team-vault as its own agentm-substrate design when picked up.
