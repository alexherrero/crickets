# Agent M: Agent Memory on every Surface

> [!NOTE]
> **Status:** Evolving — includes V1 through V3 history + V4 look-ahead
> **Date:** 2026-05-23
> **Author:** Alex Herrero
> **Packaged as:** `agentm` v3.0.0 + `crickets` v1.0.0

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

### Evolutionary path V1 → V6

- **V1 — ContextVault (local, manual).** `~/ContextVault/` of hand-written markdown. No agent integration; you pasted relevant excerpts into prompts. Limit: every session required your action.
- **V2 — Harness workflow state.** `.harness/PLAN.md` + `progress.md` + `features.json` per project; the agent reads at phase entry and writes at phase exit. Limit: per-project only; cross-project knowledge had no home.
- **V3 — Vault + auto-recall + controlled write.** A folder at `<your-Obsidian-vault>/AgentMemory/` (Google Drive synced across your machines). The `/memory` skill writes; `harness_memory.py` reads; every harness phase recalls relevant entries at start and offers to save at end. **Shipped with `agentm` v3.0.0 + `crickets` v1.0.0.**
- **V4 — Device-wide harness + vault as true knowledge database (in progress).** V3's markdown-and-frontmatter layout becomes the *durable substrate* across all projects + a device-wide install. The harness stops being per-repo: skills + hooks + phase commands install once to `~/.claude/`, state moves from `<project>/.harness/` to `<vault>/projects/<slug>/_harness/`, project resolution defaults to cwd (with a future-ready resolver chain). First-time auto-detect handles per-project configuration on first conversation in an unconfigured repo — no separate setup script. Compound skills + agentic memory canonically live in agentm; crickets keeps base primitives. The vault becomes universally accessible across desktop + phone (read-only on phone via Obsidian). Surface gets conversational: *"open a project file for M"*, *"what was I working on yesterday."* Detail in `agentm/.harness/ROADMAP-AgentMemoryV4.md`.
- **V5 — Indexed, graph-linked, tiered retrieval.** As the vault grows past where "load it all into context" works well, V5 makes retrieval relevance-ranked. A queryable index over the vault: vector embeddings + BM25 + reciprocal rank fusion for hybrid retrieval; an entity graph with typed relationships (`refines`, `supersedes`, `uses`, `related-to`) for traversal; consolidation tiers (a small "constitutional" tier always loads; everything else is indexed-recall on demand). The agent stops loading 30+ always-load entries on every session — it loads ~5-10 constitutional entries + queries the index for the ~5 most relevant per task. Lifecycle layer marks entries draft → ratified → deprecated. Self-healing lint flags stale entries; crystallization auto-promotes high-confidence ephemeral entries. Project type taxonomy (`coding | build | vacation | research | ...`) with per-type templates + promotion paths lands here. Detail in `agentm/.harness/ROADMAP-AgentMemoryV5.md`.
- **V6 — Dreaming, multi-surface, self-improving.** The vault becomes self-improving via offline consolidation cycles ("dreaming") that run on a schedule (every few days) while the operator is away. Dream-mode reads the indexed vault, finds patterns invisible to in-session reflection, proposes consolidations (merge duplicates, promote candidates, archive stale), and produces a dream report for operator review. Built on an extensible scheduled-sidecar framework — dreaming is the first consumer; doctor health-check is the second (runs `/doctor --live` against all projects during dream cycles, appends health report to dream report). Multi-surface adaptation enables web-hosted agents (claude.ai, gemini web, Cowork) to access the same vault via a read-only API layer. FRIDAY-style natural-extension feels truly cross-device + cross-surface. Detail in `agentm/.harness/ROADMAP-AgentMemoryV6.md`.

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

Detail: [harness ADR 0007](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0007-auto-context-into-harness-phases.md).

**Write layer.** `/memory save` is the primary write surface; saves are collision-checked, no overwrite. `/memory evolve` archives the old and writes the new with a `supersedes:` cross-link. `harness_memory.py offer-save` is the harness-side dispatcher at phase exit, routed by confidence (see [Constitutional Schema](#constitutional-schema)).

**Cross-project resolution.** `scripts/vault_project.py` resolves your project's vault slug via a 3-tier chain: explicit `vault_project` field in `.harness/project.json` → `github.repo` basename → `git remote get-url origin`. If none resolve, project-scoped recall graceful-skips; always-load still applies.

### V4 — Vectorized + dynamic recall on top of your notes

V3's flat-file frontmatter is the *durable substrate* — your markdown stays the source of truth. V4 layers a true knowledge database on top: vectorized indexing of every entry plus your broader notes, dynamic recall during conversation (just enough context, just in time, no cargo-loading), and a conversational surface that lets you ask for *projects* and *topics* rather than navigate paths.

A three-stage pipeline replaces V3's single wiki tree. **Raw** holds your immutable inputs — brain dumps, fetched articles, conversation excerpts, anything the agent might want to draw from but should never edit. **Inbox** is the triage state where raw content gets structured into candidate entries. **Wiki** is the compiled knowledge layer the agent maintains for you. Backlinks become first-class infrastructure: dense bidirectional links are the substrate vectorized recall traverses, not a nice-to-have.

The loop runs continuously: every useful synthesis from a conversation can get filed back as a new wiki entry, so the vault grows from work you were already doing. A single ingest can touch many existing entries — the agent updates cross-references as it goes.

The folder structure and storage patterns evolve to make this work — V3's `personal-private/_always-load/` + per-project tree becomes one input to a richer schema, not the schema itself. The frontmatter contract gets more expressive (relationships, last-touched, project-membership beyond a single dir). The agent gains tighter guardrails around touching your personal docs — read freely, write only when you ask, and even then only with you confirming the diff.

Per-project structure becomes universal. Every project gets `_index.md`, `decisions/`, `open-questions/`, `notes/`, `references/`, `assets/`, and `log.md` — same buckets for a vacation as for an API. The content density per bucket varies by domain; the bucket vocabulary doesn't. The project's `_index.md` declares its domain (`vacation` | `cooking` | `dev` | `research` | `crafting` | `learning` | …) as a tag, not a folder — projects sit peer-to-peer under `personal-projects/`. Binary assets — diagrams, photos, PDFs, spreadsheets — are first-class, referenced from entry frontmatter so recall can surface them alongside markdown. Cross-project layers (`people/`, `tools/`, `patterns/`) hold what spans projects: your framing carpenter and your senior eng peer are both `people`; your Festool router and your IDE are both `tools`.

The design space lives in `agentm/.harness/ROADMAP-AgentMemoryV4.md`. Migration from V3 is a first-class deliverable: your existing entries move forward, not get rewritten by hand. The harness itself stays dev-coded in V4 — its phase commands (`/setup` `/plan` `/work` …) are software lifecycle vocabulary, and Agent M serves both harness-driven dev work and vault-only non-dev work in parallel. A future **V4.5** revisits the harness so it handles any kind of work the same way — that's a separate design once V4 ships.

#### V4 release milestones

V4 ships incrementally. Each MAJOR release on either side of the agentm + crickets pair adds a subsection here per the `hld-evolution-update-on-major-release` convention. Order is reverse-chronological (newest first).

- **V4.3 — agentm v4.1.0 (2026-05-27) — Vault-backed harness state + folder rename `personal-projects/` → `projects/`.** ROADMAP-V4 item #26. The foundational state-migration build. Per-project harness state (`PLAN.md`, `progress.md`, `ROADMAP-*.md`, `FOLLOWUPS.md`, `features.json`, archived plans, designs/) relocates from `<project>/.harness/` to `<vault>/projects/<slug>/_harness/`. The vault top-level folder renames in the same release. Backward-compat preserved: legacy `<project>/.harness/<file>` reads still work via fallback in the resolver chain with a one-warn-per-session-per-file deprecation notice; writes go only to the vault path unless `.project-mode=local` (operator opt-out for the reversibility escape hatch). New primitives in `harness_memory.py`: `resolve_project()` returns `{slug, vault_path, project_root, layout}`; `vault_state_path(resolution, filename)`; `read_state_file()` + `write_state_file()` dispatchers; `safe_write_replace_style()` with mtime-based concurrent-modification check; `detect_conflict_files()` walker for GDrive `(conflicted copy …)` files; `warn_once()` session-scoped helper. New `conflict-merger-session-start` hook surfaces conflict-file detection at SessionStart non-blockingly. Two new operator-invoked scripts: `rename-vault-personal-projects.{sh,ps1}` (vault-side `mv` + cross-file sed sweep across `_always-load/` + `_idea-incubator/` + `personal-private/` + project-tree `_index.md` + wikilinks; `_meta/` deliberately excluded as historical narrative) and `migrate-harness-to-vault.{sh,ps1}` (per-project copy + marker + `.project-mode` flag; idempotent; reversible via `--rollback`; opt-in `--cleanup`). `scripts/list-plans.{sh,ps1}` ships the cross-repo "show me all in-flight plans" surface that becomes meaningful once state is centralized. The reorg deliberately ships state migration *as backward-compat* — the hard-cut deprecation of legacy `.harness/` paths is deferred to a later v4.x release. Single-repo release (no paired crickets bump). Single dogfood pass during plan #20 task 9 surfaced 3 bugs (preview-mode sweep gap; `_idea-incubator/` wikilinks not swept; stale `github.repo` in project.json causing wrong slug resolution) — all fixed mid-session.

- **V4.2 — crickets v2.0.0 + agentm v4.0.0 (2026-05-27, paired pair #11) — Reorganization: device-wide era opens.** ROADMAP-V4 item #36. Compound skills (`memory`, `design`, `diataxis-author`, `ship-release`), the four memory hooks (`memory-recall-session-start`, `memory-recall-prompt-submit`, `memory-reflect-stop`, `memory-reflect-idle`), the `evidence-tracker` hook, the `memory-idea-researcher` sub-agent, the `plugins/` tree (with `install-plugin.sh`), and the `bundles/` namespace (with `quality-gates`) all moved from crickets to Agent M, matching the device-wide-by-default decision locked in ADR 0012. Crickets v2.0.0 narrows to base primitives only (2 skills + 3 sub-agents + 3 hooks); Agent M v4.0.0 absorbs the compound surface + memory stack and dispatches it via a new manifest-walking installer block. The reorg is the *foundational* V4 work — every subsequent V4.x build (state migration in #26, global install scope in #30, auto-detect in #32, vault-context resolution in #35, etc.) operates against this cleanly-bounded repo layout. v4.0.0 keeps the legacy `<project>/.harness/` paths with deprecation warning; the hard-cut moves to whichever v4.x release ships state migration. No vault-side migration required — operators run `agentm/install.sh` after `crickets/install.sh` and the compound skills + memory hooks land at the same destination paths (`.claude/skills/`, `.claude/hooks/`, `.agents/skills/`) crickets v1.x delivered to.

- **V4.1 — crickets v1.2.0 + agentm v3.2.0 (2026-05-25, paired pair #10) — Antigravity 2.0 + Antigravity CLI (`agy`) host support.** ROADMAP-V4 item #34. Google launched Antigravity 2.0 (desktop) + Antigravity CLI on 2026-05-19; the toolkit absorbed both as the canonical `antigravity` host. Dispatch path migrated from `.agent/` singular to `.agents/` plural (agy v1.0.2+ scans `{workspace}/.agents/skills/<name>/SKILL.md`). New `kind: plugin` customization type added (Antigravity 2.0 plugin format with JSON `plugin.json` manifest). Agent M's `doctor` skill gained probes for the new primitives. Gemini CLI (which Antigravity CLI replaces) removed in v0.9.0; consumer Gemini CLI sunsets 2026-06-18.

### V5 — Indexed, graph-linked, tiered

The V5 architectural leap closes the gap V4 leaves open: as the vault grows, "load all always-load + truncate at budget" becomes lossy. V5 makes retrieval relevance-ranked, graph-aware, and tiered.

**Hybrid retrieval.** Three signal sources combine via reciprocal rank fusion: dense vector embeddings, BM25 keyword scoring, and an optional cross-encoder reranker on the top results. The recall API shifts from "load all always-load up to budget" to "given query Q, return top-K relevant entries." Always-load becomes a small "constitutional" tier (~5-10 entries — only the truly load-bearing-every-session conventions); everything else is indexed-recall on demand.

**Chunking + parent-child mapping.** Per-entry vector embeddings (V4's pattern — one vector per `.md` file) work well at vault-size ~100s of short preferences/workflows but dilute semantic signal as entries lengthen. V5 splits markdown by header boundaries (with paragraph-boundary fallback), embeds each chunk independently, and stores `parent_path` + `chunk_index` + `chunk_anchor` alongside each vec row. Retrieval returns chunk-grain hits; the caller decides per-query whether to load the matching chunk alone (tight context) or the parent entry with anchor-highlight (broader context). See ROADMAP-V5 item **V5-10** for the build plan.

**SQL+vector hybrid queries.** Frontmatter (kind, status, tags, group, slug, project, dates) materializes into a standard SQLite table alongside the `vec_entries` virtual table. Enables single-query `WHERE tag='security' AND project='sherwood' AND vec_entries MATCH :emb ORDER BY distance` instead of vec-search-then-Python-filter. Treats SQLite as the runtime cache (hydratable from markdown source-of-truth via `vec_index.py rebuild` + V4 #37's drift-detect) — markdown stays canonical, SQLite stays queryable. See ROADMAP-V5 item **V5-11**.

**Time-weighted retrieval.** Recall blends RRF relevance with recency-decay: `final_score = α × rrf_score + β × exp(-age_days / half_life)`. Constitutional-tier entries skip decay (always-load is timeless by definition); episodic tier applies full decay; semantic + procedural apply moderate decay. Per-phase α/β tuning lets `/work` weight recency over `/release` (which favors stable convention recall). See ROADMAP-V5 item **V5-12**.

**Knowledge graph.** Entries gain typed relationships extracted via regex-inference (when wikilinks have explicit type markers) + LLM extraction during reflection or dream cycles. Relationships include `refines`, `supersedes`, `uses`, `related-to`, `constrains`, `applies-to-project`. Graph-walk supplements vector retrieval: load one relevant entry, traverse its outbound edges to find adjacent context the vector search missed.

**Lifecycle + consolidation tiers.** Every entry has a state: `draft`, `ratified`, `superseded-by:<other>`, `deprecated`. Retrieval skips deprecated unless explicitly requested. Three retrieval tiers: **constitutional** (~5-10 entries always loaded — vault-as-canonical-context, commit conventions, the truly universal rules); **indexed-recall** (everything else, queried per-task); **crystallized** (auto-promoted from indexed-recall when retrieval frequency crosses a threshold; graduates to constitutional automatically).

**Self-healing + crystallization.** Periodic lint flags stale references, low-retrieval entries, frontmatter drift, broken wikilinks. Lint produces a candidate-fixes report for operator confirm. Crystallization auto-promotes high-confidence ephemeral entries.

**Project type taxonomy.** `type: coding | build | vacation | research | ...` becomes a first-class frontmatter field on project `_index.md`. Per-type internal-structure templates: coding has `decisions/`; build has `materials.md` + `phases/`; vacation has `itinerary.md` + `packing.md`; research has `questions.md` + `sources/`. Promotion paths — `research → coding-project`, `_idea-incubator/<slug> → research-project` — let projects evolve types.

**What V5 enables:** the context-bloat problem solves itself. V4 had ~30 always-load × ~1000 words ≈ ~40K tokens of memory context every session. V5 cuts that to ~5-10 constitutional entries + top-K per query — typically 5-15K tokens. Coverage goes UP because retrieval is relevance-ranked, not blind truncation.

### V6 — Dreaming, multi-surface, self-improving

V6 makes the vault self-improving (via dreaming) + cross-surface (web agents) + extensible (scheduled-sidecar framework). All three depend on V4's device-wide foundation + V5's indexed retrieval.

**Scheduled-sidecar framework.** V6 ships an extensible primitive: long-running agent processes that run on a schedule (cron-style) when the operator is away. Sidecars get their own context window (don't burn live-session quota), report results into the vault, and consolidate at next operator session. First consumers: dreaming, doctor health-check.

**Dreaming.** Periodic offline consolidation — typically every 3-7 days; configurable; can fire on extended operator inactivity. Dream-mode reads the indexed vault (V5 retrieval narrows scope per dream-cycle goal), runs LLM passes to: identify duplicate or near-duplicate entries → propose merges; spot patterns across many entries that no single entry captures → propose new synthesis entry; flag stale entries → propose archival; check internal links + supersede chains for consistency → propose fixes. Operator reviews the dream report at next session; approves or rejects each proposal. Dreams don't auto-commit — operator gate per V4 A3 permeable-boundary.

**Doctor health-check sidecar.** Runs `/doctor --live` (alias `health-check`) against every registered project during the dream cycle. Output rolled into the dream report under a "Project health" section. Operator sees vault-side AND project-install-side health in one place. Detects: stale installs (project hasn't been opened in N days); install drift (skills/hooks out-of-date vs current crickets); state-vs-vault drift (legacy `.harness/` files still present post-V4 #26 deprecation).

**Multi-surface adaptation.** Web-hosted agents (claude.ai, gemini web, Cowork, others) gain read-only vault access via a small API layer. Different from V4 #22 (which covers desktop-hosted Claude Code + Antigravity where the vault is directly mountable). Full iCloud Drive vault support also finalizes here (V4 stubs detection; V6 handles iCloud's sync semantics + conflict-file naming + offline-sync behavior).

**FRIDAY-style natural-extension matures.** *"Open a project file for X"*, *"what was I working on last Tuesday"*, *"remind me what we decided about Y"* — all become single-query interactions backed by V5 retrieval + V6 multi-surface. The operator-as-AI-extension vision from V4 #28 gets its full payoff here.

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
- `/memory adapt-skills` — two-pass adapt-don't-import. Python rubric (6 rules) → enriched JSON → `adapt-evaluator` sub-agent writes a watchlist entry. The sub-agent's write tool is allowlisted to `_skill-watchlist/` only; it **cannot** fork into `crickets/skills/`. Promotion is your call, in a separate session.
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
- [harness ADR 0007](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0007-auto-context-into-harness-phases.md) — per-phase recall integration
- [toolkit ADR 0007](0007-memoryvault-discovery) — discovery + mining + adapt-don't-import
- `agentm/.harness/ROADMAP-AgentMemoryV4.md` — V4 roadmap (operator-local; `.harness/` is gitignored)
- `agentm/.harness/ROADMAP.archive.20260523-v3-complete.md` — full V3-era ROADMAP snapshot (operator-local; preserved for eventual vault migration)
