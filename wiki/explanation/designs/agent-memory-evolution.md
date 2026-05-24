# Agent M: Agent Memory on every Surface

> [!NOTE]
> **Status:** Evolving — includes V1 through V3 history + V4 look-ahead
> **Date:** 2026-05-23
> **Author:** Alex Herrero
> **Packaged as:** `agentic-harness` v3.0.0 + `agent-toolkit` v1.0.0

This document is the high-level design for Agent M — An agentic memory impementation that combines a persistent knowledge layer with personally curated content (i.e. your own notes in markdown format) through a combination of skills, sidecars and vectorized indexing. Imagine those workflows you saw in the movies. You're talking to your agent, "Lets open a new file for project M" and off you go. It remembers your projects and files together, can talk to you about them, and it learns and grows with you as you work. The context it builds is self-maintaining and it improves automatically as you go. No need to spend time maintaining your own knowledge graphs, and it can help you with your personal notes too, when **you** want it to. Agent M has grown over time, for more on what it is and how it's grown, keep reading.

## Goals

1. Discuss how Agent M evolved from a static local notes directory into a vault auto-loaded into every harness phase — and why each version solved a different problem.
2. Document the current (V3) architecture for posterity.
3. Frame where we are going with V4.

We don't get into the 'how' as part of this design, for that, and the gory details of how we decided to do things a certain way, read our wiki(should be linked here).

## Background

### Why memory and notes matter — together

LLM sessions are stateless. Every new session starts cold. Whatever your agent learned about your conventions, your codebase, your fixes, your preferences last session is gone unless something on disk preserves it. You can re-explain every time, but that scales linearly and quietly erodes trust ("you should already know this by now"). Persistent state on disk, auto-loaded at session start, is the only fix that holds.

Your own notes are the other half. You already capture knowledge — Obsidian vaults, scratch markdown, READMEs, half-finished ideas in a folder. That content is yours, it's how you think, and it's where the durable context already lives. An agent that ignores it works in the dark. An agent that tries to *replace* it is hostile to how you already work.

Agent M sits in the middle. It runs on top of your existing notes — Obsidian-flavored markdown in a folder you already sync — and adds a structured layer the agent reads at every session start and writes to under controlled conditions. You curate the content; the agent maintains the index, surfaces what's relevant, and captures new durable knowledge as it goes. Neither side does the other's job. Both sides have the full picture, and the collaboration gets sharper because of it.

### Why this evolution

Each version solved something the previous one exposed:

- **V1** showed **static local notes work for you but not for your agent** — you could grep your ContextVault; the agent started blank every session.
- **V2** showed **per-project workflow state is necessary but not sufficient** — `.harness/PLAN.md` and `progress.md` gave the agent project memory, but cross-project conventions ("we always use `LC_ALL=C sort` for cross-platform checksums") had nowhere to live.
- **V3** added the **shared vault**: structured entries, per-phase auto-recall, controlled writes. It exposed two new problems: the vault is local to one machine, and recall is reactive rather than proactive.
- **V4** sets out to solve those. Deferred to a dedicated roadmap because the design space is large enough that scoping it as one plan would either rush it or block V3 from shipping.

### Evolutionary path V1 → V4

- **V1 — ContextVault (local, manual).** `~/ContextVault/` of hand-written markdown. No agent integration; you pasted relevant excerpts into prompts. Limit: every session required your action.
- **V2 — Harness workflow state.** `.harness/PLAN.md` + `progress.md` + `features.json` per project; the agent reads at phase entry and writes at phase exit. Limit: per-project only; cross-project knowledge had no home.
- **V3 — Vault + auto-recall + controlled write (current).** A folder at `<your-Obsidian-vault>/AgentMemory/` (Google Drive synced across your machines). The `/memory` skill writes; `harness_memory.py` reads; every harness phase recalls relevant entries at start and offers to save at end. **Ships with `agentic-harness` v3.0.0 + `agent-toolkit` v1.0.0.**
- **V4 — Vault as true knowledge database (deferred).** V3's markdown-and-frontmatter layout is the *durable input* — your content stays human-readable. On top of that, V4 builds a fully indexed and vectorized recall layer so the agent pulls just the right context dynamically during conversation — not too much, not too little. The surface gets conversational: *"open a project file for M"*, *"list my active projects"*, *"pull everything we've discussed about the home server"*. Think filing cabinet you can talk to — a competent assistant who already knows where everything lives. The roles sharpen too: **raw inputs are yours** (brain dumps, fetched articles, conversation excerpts), **the compiled wiki is the agent's** (summaries, cross-references, synthesis it maintains for you), **the schema is jointly maintained** (your AGENTS.md is the contract both sides operate against). V4 is also when Agent M stops being just a coding tool — same vault, same backlinks, same recall, but the projects in it span coding, research, vacation planning, sourdough notebooks, workshop builds, learning a new subject. What varies is the content density per bucket, not the bucket vocabulary. Folder structure and storage patterns evolve to support this; the agent gains tighter guardrails around touching your personal docs (only when **you** ask). Detail in [`agentic-harness/.harness/ROADMAP-AgentMemoryV4.md`](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP-AgentMemoryV4.md).

## Architecture

### V1 — Directory plus grep

One directory, your filesystem tools. No schema, no integration, no automation. The architecture diagram is one box.

### V2 — Harness workflow state

Three files per project under `.harness/`:

- `PLAN.md` — current plan with goals, tasks, verification criteria, locked design calls.
- `progress.md` — append-only log of completed work.
- `features.json` — structured feature ledger.

Harness phase commands (`/setup`, `/plan`, `/work`, `/review`, `/release`, `/bugfix`) read at phase entry and write at phase exit. Memory was project-local; nothing crossed.

### V3 — Vault + auto-recall + controlled write

Three coordinated systems on top of an Obsidian markdown folder synced via Google Drive.

**Vault layout** at `<your-Obsidian-vault>/AgentMemory/`:

```
<vault>/
├── personal-private/
│   ├── _always-load/              # session-boot injection
│   ├── _inbox/                    # low-confidence candidates pending triage
│   ├── _archive/                  # status: superseded entries
│   ├── _idea-incubator/<slug>/    # deep-research dirs for captured ideas
│   ├── _skill-watchlist/          # adapt-skills output
│   ├── <kind>/<slug>.md           # default group for /memory save
│   ├── skill-discovery-sources.md # editable URL whitelist
│   └── trusted-sources.md         # editable trusted-org whitelist
├── personal-skills/<repo>/<skill-name>.md  # auto-indexed skill pointers
├── personal-projects/<slug>/
│   ├── _index.md
│   ├── decisions/
│   ├── open-questions/
│   ├── known-issues/
│   └── conventions.md
└── _meta/
    ├── vec-index.db                          # sqlite-vec embedding index
    ├── transcript-reflection-state.json      # corpus-mode resume state
    └── skill-discovery-cache/
```

**Recall layer.** `scripts/harness_memory.py recall` runs at the start of every harness phase. It loads `_always-load/*` unconditionally (the global signal) plus per-project entries scoped to the phase. Budgets tunable via `HARNESS_RECALL_BUDGET_<PHASE>`:

| Phase | Tokens | Per-project sub-paths |
|---|---|---|
| `setup` | 4000 | `_index.md` |
| `plan` | 6000 | `_index.md`, `decisions/`, `open-questions/` |
| `work` | 6000 | `decisions/`, `known-issues/` |
| `review` | 4000 | (none — global only; reviewer shouldn't bias toward prior decisions) |
| `release` | 6000 | `decisions/` |
| `bugfix` | 6000 | `known-issues/` |

Detail: [harness ADR 0007](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0007-auto-context-into-harness-phases.md).

**Write layer.** `/memory save` is the primary write surface; saves are collision-checked, no overwrite. `/memory evolve` archives the old and writes the new with a `supersedes:` cross-link. `harness_memory.py offer-save` is the harness-side dispatcher at phase exit, routed by confidence (see [Constitutional Schema](#constitutional-schema)).

**Cross-project resolution.** `scripts/vault_project.py` resolves your project's vault slug via a 3-tier chain: explicit `vault_project` field in `.harness/project.json` → `github.repo` basename → `git remote get-url origin`. If none resolve, project-scoped recall graceful-skips; always-load still applies.

### V4 — Vectorized + dynamic recall on top of your notes

V3's flat-file frontmatter is the *durable substrate* — your markdown stays the source of truth. V4 layers a true knowledge database on top: vectorized indexing of every entry plus your broader notes, dynamic recall during conversation (just enough context, just in time, no cargo-loading), and a conversational surface that lets you ask for *projects* and *topics* rather than navigate paths.

A three-stage pipeline replaces V3's single wiki tree. **Raw** holds your immutable inputs — brain dumps, fetched articles, conversation excerpts, anything the agent might want to draw from but should never edit. **Inbox** is the triage state where raw content gets structured into candidate entries. **Wiki** is the compiled knowledge layer the agent maintains for you. Backlinks become first-class infrastructure: dense bidirectional links are the substrate vectorized recall traverses, not a nice-to-have.

The loop runs continuously: every useful synthesis from a conversation can get filed back as a new wiki entry, so the vault grows from work you were already doing. A single ingest can touch many existing entries — the agent updates cross-references as it goes.

The folder structure and storage patterns evolve to make this work — V3's `personal-private/_always-load/` + per-project tree becomes one input to a richer schema, not the schema itself. The frontmatter contract gets more expressive (relationships, last-touched, project-membership beyond a single dir). The agent gains tighter guardrails around touching your personal docs — read freely, write only when you ask, and even then only with you confirming the diff.

Per-project structure becomes universal. Every project gets `_index.md`, `decisions/`, `open-questions/`, `notes/`, `references/`, `assets/`, and `log.md` — same buckets for a vacation as for an API. The content density per bucket varies by domain; the bucket vocabulary doesn't. The project's `_index.md` declares its domain (`vacation` | `cooking` | `dev` | `research` | `crafting` | `learning` | …) as a tag, not a folder — projects sit peer-to-peer under `personal-projects/`. Binary assets — diagrams, photos, PDFs, spreadsheets — are first-class, referenced from entry frontmatter so recall can surface them alongside markdown. Cross-project layers (`people/`, `tools/`, `patterns/`) hold what spans projects: your framing carpenter and your senior eng peer are both `people`; your Festool router and your IDE are both `tools`.

The design space lives in [`agentic-harness/.harness/ROADMAP-AgentMemoryV4.md`](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP-AgentMemoryV4.md). Migration from V3 is a first-class deliverable: your existing entries move forward, not get rewritten by hand. The harness itself stays dev-coded in V4 — its phase commands (`/setup` `/plan` `/work` …) are software lifecycle vocabulary, and Agent M serves both harness-driven dev work and vault-only non-dev work in parallel. A future **V4.5** revisits the harness so it handles any kind of work the same way — that's a separate design once V4 ships.

## Constitutional Schema

Every vault entry carries YAML frontmatter. Field order is locked for deterministic diffs:

```yaml
---
kind: <kind>                 # preference | workflow | fix | domain-reference | idea | skill-pointer | ...
status: active               # active | superseded | promoted | dismissed | deferred
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []                     # kebab-case; inline flow
group: <group>               # personal-private | personal-skills/<repo> | personal-projects/<slug>
slug: <slug>                 # kebab-case; ^[a-z0-9-]+$
always_load: true|false      # always present so recall can grep unambiguously
supersedes: <relative-path>  # only on evolved entries
---
```

**Kinds.** Open-ended; conventionally `preference` / `workflow` / `fix` / `domain-reference` / `idea` / `skill-pointer`. Default group is `personal-private/<kind>/`; your locked conventions live in `personal-private/_always-load/`.

**Entry content rule.** Entries are about **your engagement** with a thing, not generic descriptions of the thing itself. Why you cared, what problem it solved, what tradeoffs you hit, how it shaped your decisions. Encyclopedia-style summaries are wrong — that content already exists on the open web and adds nothing your future self or your agent can act on. V3 treats this as convention; V4 enforces it as the content contract.

**Supersession, not deletion.** Updates never overwrite. `/memory evolve <slug>` archives the old entry with `status: superseded` and links the new one back. Your audit trail is permanent; the agent ignores superseded entries at recall time.

**Permeable write boundary.** Agent reads anywhere in your vault; writes default to `<vault>/AgentMemory/` only. Writes outside (e.g. your general `Ideas.md`) need explicit instruction from you or agent-initiated + you-confirmed. Non-interactive contexts default to deny. Read is universal; write is constrained-by-default. This keeps the agent from contaminating your broader notes. V4 tightens this further — touching anything in your personal docs becomes opt-in per request, with the diff shown back to you before the write lands.

Detail: [toolkit ADR 0007](0007-memoryvault-discovery).

## Autonomous Workflows

The `/memory` skill exposes these sub-commands; full bodies in [`memory/SKILL.md`](Use-The-Memory-Skill).

**Capture**
- `/memory save` — write one entry to the vault (collision-checked).
- `/memory evolve` — atomic archive-then-replace.
- `/memory promote idea <slug>` — graduate an incubator dir to `personal-projects/`.

**Recall**
- `/memory recall` — programmatic; called by hooks. Top-K=5 via sqlite-vec + grep merge (0.7 semantic + 0.3 keyword).
- `/memory search` — operator-facing manual query (engine live; surface stubbed; lands in V4).

**Reflect**
- `/memory reflect` — mine the current session's transcript for save candidates (workflows / preferences / fixes + idea candidates). Tri-modal routing: HIGH → auto-save, MEDIUM → review or `_inbox/`, LOW → `_inbox/`.
- `/memory reflect corpus` — batched walk over all historical transcripts; dry-run by default.

**Discover + adapt**
- `/memory index-skills` — walk `SKILL.md` paths; write `kind: skill-pointer` entries.
- `/memory discover-skills` — cadence-checked scan over a 4-URL whitelist; dated snapshots + diffs cached.
- `/memory adapt-skills` — two-pass adapt-don't-import. Python rubric (6 rules) → enriched JSON → `adapt-evaluator` sub-agent writes a watchlist entry. The sub-agent's write tool is allowlisted to `_skill-watchlist/` only; it **cannot** fork into `agent-toolkit/skills/`. Promotion is your call, in a separate session.
- `/memory watchlist` — review queued entries with `list` / `review` / `promote` / `dismiss` / `defer`.

## Background Automations

Six coordinated hook surfaces on Claude Code (other hosts integrate as their hook surfaces grow):

| Hook | Event | What it does |
|---|---|---|
| `memory-recall-session-start` | `SessionStart` | Globs `_always-load/*.md`, filters `status: superseded`, injects bodies. 500ms budget. |
| `memory-recall-prompt-submit` | `UserPromptSubmit` | Treats each prompt as a recall query; top-K=5; dedup vs. always-load; inject remainder. 300ms budget. |
| `memory-reflect-stop` | `Stop` | Mines the just-ended transcript; tri-modal routing places candidates. |
| `memory-reflect-idle` | `SessionStart` | Crash recovery — picks up `.harness/session-id-*.start` markers older than `MEMORY_IDLE_THRESHOLD_SEC` (default 3600s), reflects retroactively, renames `.start` → `.reflected`. GC sweeps `.reflected` >30d old. Also cron-able. |
| `commit-on-stop` | `Stop` | Auto-commits open work as a safety branch (separate quality-gate hook; bundled with `/memory` for crash resilience). |
| Dual-trigger plan-done promotion | (harness dispatch) | When `/work` flips a task `[ ] → [x]` OR `/release` cuts, the harness invokes `harness_memory.py plan-done-promotion`. A cursor at `.harness/.promoted-progress-cursor` tracks how much of `progress.md` has been processed; both triggers share it. Idempotent. |

**Offer-save confidence routing.** `harness_memory.py offer-save` is dispatched explicitly from harness phase commands (not from a hook). `HARNESS_AUTO_SAVE_MODE` is `ask` (default) | `silent` | `off`; `HARNESS_AUTO_SAVE_CONFIDENCE_THRESHOLD` is 0.8 default. In `ask` mode, confidence ≥ threshold silent-saves with a stderr notice; below threshold previews and prompts. Non-TTY stdin defaults to skip — never silent-acts unattended. V4 flips the default: most reflections auto-save; you only get asked when confidence is genuinely low. The agent earns the auto-save default by proving (in V3) that what it captures is what you'd have captured yourself.

**Synthesis (V4).** V3 reflection mines what you said. V4 adds a synthesis layer that reads graph topology — finds concepts in distant corners of the vault that share tradeoffs, drafts a new entry that bridges them, and surfaces it for your review. The point is the agent finding connections you didn't know to look for, not just transcribing the ones you named.

## Commands Reference

| Command | What it does | Status |
|---|---|---|
| `/memory save` | Write one entry to the vault (collision-checked). | ✅ V3 |
| `/memory evolve` | Atomic archive-then-replace; preserves audit trail. | ✅ V3 |
| `/memory reflect` | Mine the current session's transcript for save candidates. | ✅ V3 |
| `/memory reflect corpus` | Batched walk over all historical transcripts. | ✅ V3 |
| `/memory search` | Manual semantic + keyword query (engine live, surface stubbed). | ⏸️ V4 |
| `/memory index-skills` | Walk `SKILL.md` paths; write `skill-pointer` entries. | ✅ V3 |
| `/memory discover-skills` | Cadence-checked scan over the discovery URL whitelist. | ✅ V3 |
| `/memory adapt-skills` | Two-pass adapt-don't-import with sub-agent write allowlist. | ✅ V3 |
| `/memory watchlist <action>` | Review queued adapted skills. | ✅ V3 |
| `/memory promote idea <slug>` | Promote `_idea-incubator/<slug>/` to `personal-projects/<slug>/`. | ✅ V3 |
| `/memory promote gc` | Sweep 6-month-idle incubator dirs. | ✅ V3 |
| Vectorized + dynamic recall | Just-enough context pulled on demand during conversation. | ⏸️ V4 |
| Conversational surface | *"Open a project file for M"* / *"list my active projects"* / *"pull everything on the home server"*. | ⏸️ V4 — roadmap #28 |
| Vault-backed harness state | Move `.harness/PLAN.md` + `progress.md` into the vault. | ⏸️ V4 — roadmap #26 |
| Cross-surface protocol | Native vault read from Claude.ai / Gemini / Antigravity. | ⏸️ V4 — roadmap #22 |
| Auto-orchestration | Chain `/memory` sub-commands into background routines. | ⏸️ V4 — roadmap #23 |
| Memory-line audit | Review external memory architectures; adopt / adapt / reject. | ⏸️ V4 — roadmap #25 |

V4 commands are deliberately under-specified here. Each gets its own design doc when picked up.

---

**See also**

- [`v3-retrospective`](v3-retrospective) — what the V3 arc shipped, learned, and left for V4
- [`memoryvault`](memoryvault) — the parent design doc that drove V3 implementation
- [Use the memory skill](Use-The-Memory-Skill) — operator-facing how-to for `/memory`
- [harness ADR 0007](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0007-auto-context-into-harness-phases.md) — per-phase recall integration
- [toolkit ADR 0007](0007-memoryvault-discovery) — discovery + mining + adapt-don't-import
- [`agentic-harness/.harness/ROADMAP-AgentMemoryV4.md`](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP-AgentMemoryV4.md) — V4 roadmap (lands in plan #14 task 3)
