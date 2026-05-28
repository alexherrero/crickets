# Device-wide architecture for the Agent M harness

> [!NOTE]
> **Status:** initial publication (v0.1) — 2026-05-26. Paired with plan #18 close.
> **Position in arc:** companion to [`agent-memory-evolution.md`](agent-memory-evolution.md). That doc covers the V1 → V6 evolution of Agent Memory; this doc covers the V4 architectural shift — from per-repo harness to **device-wide agentic OS**.
> **Lifecycle:** updated on every qualifying release per the operator's HLD-update convention. See **Lifecycle** at the bottom.

## Goals

Agent M started as a phase-gated workflow for a single repo. It outgrew that frame. The harness is now a device-wide agentic development environment + learning assistant — installed once per machine, present in every conversation by default, with state living in the operator's vault rather than scattered across project directories.

This design locks the V4 shape:

1. Customizations install device-wide to `~/.claude/` (skills, sub-agents, hooks, slash commands). One install per machine; available in every project.
2. Harness state moves from `<project>/.harness/` to `<vault>/projects/<slug>/_harness/`. Repos stay clean — no gitignored harness clutter; multi-device access via Obsidian sync.
3. Project resolution defaults to cwd → vault slug, with a future-ready resolver chain so V5/V6 can add non-coding anchors (house projects, vacation planning, research) without breaking V4 code.
4. First conversation in a new project auto-detects what the project is + proposes a configuration. No separate `setup-project.sh` script.
5. Vault is canonical for context, state, drafts; only final published outputs leave the vault.
6. The vault holds context for **any subject the operator cares about** — not just projects. Cross-cutting content (people, conversations, ad-hoc captures, web snippets, correspondence) gets a first-class home alongside `projects/`. V4 sets the device-wide foundation + vault-as-canonical-context principle; V5 builds the explicit content shapes (project type taxonomy + non-project content layers).

Build work for #1–#5 falls out into V4 #26 (vault-backed state), V4 #30 (global-install + first-run vault detection), V4 #32 (auto-detect + auto-configure), V4 #35 (documenter vault-context resolution), and V4 #36 (agentm/crickets reorganization) — all sequenced after this design pass (V4 #31) locks. Goal #6 lands in V5 (non-project content shapes + project type taxonomy together).

## Background

The V3 model had a clear shape: per-project install via `bash install.sh <target>` drops files into `<project>/.claude/`; the harness keeps a gitignored `.harness/` next to your code; state moves with the repo. That works for one developer with one project. It strains everywhere else:

- **Cross-project queries** (*"what did I ship last Tuesday across all my projects?"*) require opening each project individually.
- **Cross-device continuity** doesn't exist — your phone can read the vault but not the per-project `.harness/PLAN.md`.
- **Onboarding new repos** means re-running `install.sh` for every project; easy to forget.
- **Repo clutter** — every project has `.harness/`, `.claude/`, and (post-Antigravity-2.0) `.agents/` directories cluttering the project root.
- **The agent's tools are scattered** — your skills + hooks + commands belong to YOU, not to each project. Today's per-project install model says otherwise.

V4 reframes the harness as the operator's agentic OS — installed device-wide, with project-specific state living in the vault. Each repo on disk stays minimal: source code + AGENTS.md + CLAUDE.md + optional `.project-slug` override file. Everything else is device-wide or vault-backed.

The architectural principle that makes this work is **vault-as-canonical-context** — the vault holds everything the agent needs; only final published outputs leave.

## Architectural Principles

### Vault-as-canonical-context

Per [[vault-as-canonical-context]] (an always-load convention as of 2026-05-26):

The Agent Memory vault is the canonical home for all context, state, drafts, knowledge, and working artifacts. Outputs leave the vault only for final published consumption — repository READMEs, wiki published pages, GitHub release notes, source code in repos. The act of publishing is **promote from vault → repo**, not "create directly in repo." The vault retains the context + a copy/reference of its outputs for later retrieval.

This principle drives the rest of the architecture:

- State migration (V4 #26) moves harness state INTO the vault because state is context the agent needs.
- Documenter vault-context resolution (V4 #35) reads context from the vault when generating outputs.
- V5 indexed retrieval relies on EVERYTHING being in one canonical place — without that, no useful index.
- V6 dreaming consolidates over the vault contents; same prerequisite.

### Operator-in-the-loop preserved

Device-wide ≠ autonomous. The A3 permeable boundary — operator confirms vault writes that affect personal content — stays. Auto-detect on first session **proposes**; operator approves or edits. Dreaming proposes consolidations; operator gates each. Cross-device sync surfaces conflicts to the operator; no silent overwrites.

### Markdown-canonical + filesystem-only

State in vault is markdown files in directories. No database (V5 adds an index ON TOP of markdown, never replacing it). The vault stays human-readable, scriptable, GDrive-syncable, Obsidian-browsable.

### Per-cwd runtime ephemeral stays per-cwd

A small carve-out: `.evidence-reads` (the evidence-tracker hook's session-state cache) stays at `<project>/.harness/.evidence-reads` even post-V4 #26. It's per-session runtime cache, regenerated each session; vault-syncing it would create write storms via GDrive. Everything else moves.

## Architecture

The target layout — what lives where after V4 builds land:

```
DEVICE-WIDE (one install per machine)              VAULT-BACKED (per-project state)
~/.claude/                                          <AgentMemory>/projects/<slug>/
├── CLAUDE.md                                       ├── _index.md
├── commands/                                       ├── _harness/                              ← NEW v4 home for state
│   ├── plan.md     ← from agentm                   │   ├── PLAN.md
│   ├── work.md                                     │   ├── progress.md
│   ├── review.md                                   │   ├── ROADMAP*.md
│   ├── release.md                                  │   ├── FOLLOWUPS.md
│   ├── bugfix.md                                   │   ├── features.json    ← auto-detect output
│   └── setup.md                                    │   ├── designs/
├── skills/                                         │   ├── init.sh
│   ├── memory/        ← from agentm post-V4 #36    │   └── PLAN.archive.*.md
│   ├── design/        ← from agentm post-V4 #36    ├── decisions/
│   ├── diataxis-author/  ← from agentm post-V4 #36 ├── conventions[.md]/
│   ├── ship-release/  ← from agentm post-V4 #36    ├── pattern/
│   ├── pii-scrubber/  ← from crickets              ├── gap/
│   ├── dependabot-fixer/  ← from crickets          └── drafts/                                ← NEW v4 surface
│   └── doctor/        ← from agentm
├── agents/                                         <AgentMemory>/personal-private/
│   ├── documenter.md                               ├── _always-load/    ← operator conventions
│   ├── adversarial-reviewer.md                     ├── _inbox/          ← reflection candidates
│   ├── explorer.md                                 └── domains/         ← domain knowledge
│   ├── evaluator.md   ← from crickets
│   ├── adapt-evaluator.md  ← from crickets         <project on disk>/                         ← STAYS MINIMAL
│   ├── diataxis-evaluator.md  ← from crickets      ├── AGENTS.md         (project agent instructions)
│   └── memory-idea-researcher.md  ← from agentm    ├── CLAUDE.md         (Claude Code reference)
├── hooks/                                          ├── .project-slug     (optional vault slug override)
│   ├── kill-switch.sh   ← from crickets            ├── (source code)
│   ├── steer.sh         ← from crickets            ├── (tests, docs, infra)
│   ├── commit-on-stop.sh  ← from crickets          └── .harness/.evidence-reads  (runtime-only)
│   ├── evidence-tracker.sh  ← from agentm
│   ├── memory-recall-session-start.sh  ← from agentm
│   ├── memory-recall-prompt-submit.sh  ← from agentm
│   ├── memory-reflect-idle.sh          ← from agentm
│   └── memory-reflect-stop.sh          ← from agentm
└── settings.json     ← hooks registered here

~/.gemini/config/plugins/                          (existing; agy plugin paths)
├── google-antigravity-sdk/                        (pre-installed)
├── ... other Google-shipped plugins ...
└── example-plugin/   ← from agentm post-V4 #36

VAULT NON-PROJECT CONTENT — V4 has hints; V5 designs concretely
<AgentMemory>/personal-private/
├── _always-load/        ← operator conventions
├── _inbox/              ← reflection candidates today; V5+ extends to web-clips, email, ad-hoc captures
├── domains/             ← domain knowledge (current: homelab/)
└── (V5+ additions:)
    ├── people/          ← per-person context: notes, correspondence refs, conversation archives
    ├── conversations/   ← cross-project conversation archives (chat exports, meeting notes)
    └── topics/          ← cross-cutting themes (alternative or complement to domains/)

(optional operator-private sibling repo — adds shell-env wiring if present;
 agentm install is self-sufficient otherwise. See ADR 0012 § 6 for the
 invisibility policy.)
```

The repo on disk is intentionally minimal. Repo-side `AGENTS.md` + `CLAUDE.md` continue to carry project-specific agent instructions. The optional `.project-slug` file is a per-repo override for vault-slug resolution; usually not needed since AGENTS.md frontmatter or cwd-basename inference handles it.

## Project resolution

Per design call #7 + the resolver-chain abstraction in task 4 prep:

`resolve_project(context) → Optional[Resolution]` returns `{slug, type, vault_path}`. v1 uses only `cwd`; future versions add Obsidian-file-anchored, conversation-anchored, and explicit-operator-selected resolvers without breaking the v1 contract.

**v1 resolution chain (fallback order):**

1. `explicit_slug` — caller provides it; always-available override.
2. `AGENTS.md` frontmatter `vault_slug:` field — preferred declared override (AGENTS.md is already a checked-in convention file).
3. `.project-slug` plain-text file — fallback for projects that don't use AGENTS.md.
4. Legacy `<project>/.harness/project.json` `vault_project` field — preserved for transition.
5. cwd basename inference against `<vault>/projects/<slug>/_index.md`.
6. `git remote get-url origin` → basename → same vault lookup.
7. `None` — no signal. Callers either graceful-skip OR trigger auto-detect bootstrap (V4 #32).

**v1 always returns `type: "coding"`.** V5 reads `type:` from `_index.md` frontmatter and supports `build | vacation | research | ...` per the project type taxonomy (a V5 ROADMAP item).

When resolution returns `None`, the agent in a session triggers auto-detect bootstrap (next section). When it succeeds, every downstream skill/hook/command gets a stable `{slug, type, vault_path}` to operate against.

## State migration

`<project>/.harness/<file>` → `<vault>/projects/<slug>/_harness/<file>`.

Coupled with a one-time vault folder rename: `<vault>/personal-projects/` → `<vault>/projects/` (operator preference 2026-05-26 — shorter; extensible naming for future project types).

**Order of operations in V4 #26 build:**

1. Vault folder rename FIRST (so state lands at the new path; no intermediate). Single `mv` + sed sweep across scripts + always-load entries + wikilinks. Operator runs once.
2. State migration per project: `bash agentm/scripts/migrate-harness-to-vault.sh <target-project>` walks each `<target>/.harness/<file>` and writes to `<vault>/projects/<slug>/_harness/<file>`. Idempotent.
3. Phase specs + dispatcher scripts updated to read/write vault paths.
4. Backward-compat: dispatchers check `.harness/<file>` as graceful fallback during transition (with deprecation warning).

**The `_harness/` naming locks** — matches vault prefix-underscore convention (`_always-load/`, `_meta/`, `_idea-incubator/`). Self-documenting: anyone scanning a project dir sees `_harness/` = harness-managed state.

**Hard-cut at agentm v4.0.0** — legacy `<project>/.harness/` reads removed entirely. v3.x MINOR releases warn; v3.9.x ships a strong banner; v4.0.0 removes the fallback.

## Dispatcher contracts

Per task 6 prep: every customization now has TWO lookup types.

**State lookup** — for customizations reading/writing PLAN.md / progress.md / FOLLOWUPS.md / features.json / etc. Uses `vault_state_path(resolution, "PLAN.md")` → `<vault>/projects/<slug>/_harness/PLAN.md`.

**Context lookup** — for doc-touching customizations (writing READMEs, wiki, ADRs, CHANGELOG, designs). Uses `vault_context(resolution, writing_target="adr")` returning a dict of project entries (decisions, conventions) + operator-personal entries (`docs-prose-style`, `silent-source-influences`, `adr-shape`, etc.) relevant to that writing target.

A small table maps `writing_target` → relevant always-load entries:

| Target | Always-load entries pulled |
|---|---|
| `adr` | adr-shape, docs-prose-style, silent-source-influences |
| `wiki-page` | docs-prose-style, docs-cover-ours-link-theirs, wiki-url-not-file-path-for-readme-crossrefs |
| `readme` | docs-prose-style, personal-comms-style, brand-consistency-end-to-end-cascade |
| `changelog` | changelog-shape, coordinated-release-order, hld-evolution-update-on-major-release |
| `design` (HLD) | adr-shape, vault-as-canonical-context, no-internal-google-refs-in-design-docs |
| `commit-message` | commit-no-coauthor-trailer |

V4 #35 ships the helper. Doc-touching customizations call it before generating output. Operator-personal entries **influence** the output (style, voice, constraints) but don't appear literally in the published doc.

## Installer redesign + first-run vault detection + auto-detect bootstrap

### `bash install.sh --scope user` — new default

Installs device-wide. Detects the operator-private shell-env sibling repo if present; defers to it; otherwise writes directly to `~/.zshrc` (or detected shell config). Cross-platform parity with `install.ps1`.

Agentm install **bundles crickets** automatically (per operator decision: agentm depends on crickets, crickets is independent). Discovery is via one-liner:

```bash
# agentm one-liner — installs both agentm + crickets
curl -fsSL https://raw.githubusercontent.com/alexherrero/agentm/main/install.sh | bash

# crickets standalone one-liner
curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/install.sh | bash
```

Pre-pipe notes in each repo's README make the asymmetric dependency clear without requiring the operator's optional shell-env sibling.

### `bash install.sh --scope project <target>` — retained as opt-in

For OSS contributors, testing, or per-project install needs. Minor warning at install that `--scope user` is now recommended.

### First-run vault detection

When `MEMORY_VAULT_PATH` is unset OR points at a non-existent path, the installer (or a SessionStart hook on first session post-install) probes common paths in order:

1. `$MEMORY_VAULT_PATH` env (if set).
2. `~/.config/crickets/memory.yml` `vault_path:` key.
3. Mac: `~/Library/CloudStorage/GoogleDrive-*/My Drive/Obsidian/AgentMemory/`, `~/Library/CloudStorage/iCloudDrive*/Obsidian/AgentMemory/`.
4. Cross-platform: `~/Obsidian/AgentMemory/`, `~/Documents/Obsidian/AgentMemory/`, `~/AgentMemory/`.

If found, propose to operator. If not found, prompt: *"Where's your vault? Or do you not have one yet?"* If no vault, suggest a recommended path + link to `Set-Up-AgentMemory-Vault.md`. Operator can also defer with graceful-skip mode (memory-coupled features dormant until vault is configured later).

Full iCloud Drive sync semantics (conflict-file naming, offline behavior) finalize in V6; v1 stubs detection.

### Auto-detect bootstrap on first session in unconfigured project

Replaces a separate `setup-project.sh` script (per operator decision: no separate setup script).

Flow on SessionStart:

1. Hook runs `resolve_project({cwd})`. If resolution succeeds (project registered), exit silently.
2. If `None`, run auto-detect: scan cwd for project signals (wiki/, CHANGELOG.md, .env files, tests/, etc.).
3. Propose to operator: *"This looks like a new project I haven't seen. Detected: [list]. Default: register with all skills + hooks enabled. (a) all-enabled (b) custom selection (c) skip (one-time scratch session)."*
4. On approve: write `<vault>/projects/<slug>/_index.md` + `_harness/features.json` + offer to add `vault_slug:` line to AGENTS.md.
5. Subsequent sessions resolve via the new registration.

**Default-all-enabled** per operator preference. Detection rules surface RATIONALE for why each skill is on; operator opts out per skill if desired.

10 initial detection rules ship: `R-wiki` (enables diataxis-author), `R-changelog`+`R-pkg-manifest` (enables ship-release), `R-dependabot` (enables dependabot-fixer), `R-pii` (enables pii-scrubber), `R-tests` (ensures evidence-tracker), `R-harness` (bypass), `R-pkg-scripts` (informs kill-switch + steer), `R-vault-content` (memory-* hooks), `R-design` (enables design skill), `R-non-coding` (V5 type-aware enablement).

Detection rules extensible — operator can drop custom rules at `~/.config/agentm/detection-rules.d/<name>.py`.

## agentm/crickets reorganization (V4 #36)

The harness has evolved into the operator's agentic environment. Compound skills and agentic memory belong canonically in agentm; crickets keeps base/primitive customizations.

**Classification rubric:**

- **Base/primitive** (stays in crickets) — atomic in purpose; universally useful across coding projects regardless of harness use; self-contained.
- **Compound** (moves to agentm) — multi-step workflow; tightly coupled to harness flow or vault.

**Move list — to agentm post-V4 #36:**

- Skills: `memory`, `design`, `diataxis-author`, `ship-release`.
- Sub-agents: `memory-idea-researcher`.
- Hooks: `memory-recall-session-start`, `memory-recall-prompt-submit`, `memory-reflect-idle`, `memory-reflect-stop`, `evidence-tracker`.
- Plugins layer: `plugins/example-plugin/` + `scripts/install-plugin.sh`.

**Stays in crickets — base primitives:**

- Skills: `pii-scrubber`, `dependabot-fixer`.
- Sub-agents: `evaluator`, `adapt-evaluator`, `diataxis-evaluator`.
- Hooks: `kill-switch`, `steer`, `commit-on-stop`.
- Schema: `Manifest-Schema.md` + `validate-manifests.py` — the contract for ALL kinds; validator invocable against any repo's manifests.

**Removed entirely:**

- `bundles/quality-gates/` — dissolved. Operator gets the 5 customizations (evaluator + 3 base hooks + evidence-tracker) via `--all` default install or individual flags. A new how-to page `Quality-Gates-Recipe.md` documents the recipe.
- `bundles/example-bundle/` — removed.
- `kind: bundle` stays in schema as reserved-future (no bundles ship).
- ADR 0010 (quality-gates bundle) — deleted entirely (no supersession marker; clean removal).

**Release shape:** paired pair #11 — crickets v2.0.0 (MAJOR; primitives-removed = breaking) + agentm v4.0.0 (MAJOR; compound-skills-added + hard-cut deprecation).

## Concurrency + multi-device sync

The vault syncs across devices via Obsidian + GDrive. Two sessions on different devices may write the same project's state concurrently.

**File classes by write pattern:**

- **Append-only** (progress.md, _inbox/, archives) — natural merge via timestamps. GDrive sync handles concurrent appends. A SessionStart hook scans for `(conflicted copy ...)` files + surfaces resolution UX.
- **Replace-style** (PLAN.md, _index.md, features.json) — cursor + last-modified pre-write check. If file changed between read + write, agent surfaces conflict: (a) re-read + re-apply, (b) force-write, (c) save as `.local` for manual merge.
- **Cursor-tracked** (`.promoted-progress-cursor`) — existing V4 #8 primitive, generalized for ROADMAP + FOLLOWUPS promotion.
- **Per-cwd runtime** (`.evidence-reads`) — stays in `<project>/.harness/`; not synced; per-cwd cache.
- **Advisory locks** (`.session-lock`) — long-running phases announce themselves; informational, not enforced.

Multi-device concurrent operation is supported with graceful degradation. Hard-merge conflicts surface to operator with clear UX paths.

## Migration plan

Single entry point: `bash agentm/install.sh --scope user --migrate-existing`. Steps:

1. Install agentm + crickets device-wide (clones crickets if absent).
2. Detect vault (or run first-run vault detection if absent).
3. Per registered project in vault: run `migrate-harness-to-vault.sh` (moves `.harness/<files>` to `<vault>/projects/<slug>/_harness/`).
4. Per repo NOT yet in vault but with `.harness/` populated: prompt auto-detect bootstrap.
5. Print summary.

Idempotent. Tracks completion via `<vault>/projects/<slug>/_harness/.migrated-from-v3` marker.

Backward-compat: dispatchers check both vault + legacy paths during transition (writes vault-only; reads check both with deprecation warning). v4.0.0 hard-cut removes legacy fallback.

## Cross-impacts

This design unlocks the rest of the V4 line:

- **V4 #36** ships first (reorg) so subsequent builds reference the new repo boundaries.
- **V4 #26** ships state migration + folder rename.
- **V4 #30** ships global install + first-run vault detection + one-liner installers.
- **V4 #35** ships documenter vault-context resolution.
- **V4 #32** auto-detect builds on #30 (skills available device-wide) + #35 (documenter generates propose-config text).
- **V4 #33** (cleanup) + **V4 #34** (operator aesthetic pass) follow once foundations are solid.
- **V4 #25** audit reframes as post-build — audits external sources against the new model, not the per-repo predecessor.
- **V4 #28** (FRIDAY-style) gets its full payoff after V5 retrieval + V6 multi-surface land.

V5 prepares for indexed retrieval — vault-as-canonical-context (this design's principle) is what makes V5 work. V6 prepares for dreaming + multi-surface — same dependency chain.

**Non-project vault content (V5 item).** Project content lives in `<vault>/projects/<slug>/` per V4. Non-project content — people, conversations, web-clips, email correspondence, ad-hoc captures — lands in `<vault>/personal-private/` under sub-folders to be designed in a new V5 ROADMAP item (*Non-project vault content shapes*). The V4 architecture supports this without modification: vault-as-canonical-context covers ALL content; the V5 retrieval index works over the whole vault, not just projects; V6 dreaming consolidates across everything; V6 multi-surface enables ingestion via web-hosted agents (send a snippet from a browser → vault inbox → agent triages). V4 builds the foundation; V5 builds the explicit content shapes (project type taxonomy + non-project layers); V6 enables cross-surface access + ingestion.

## Open questions

Tracked in [`agentm/.harness/designs/v4-device-wide/12-open-questions.md`](https://github.com/alexherrero/agentm/blob/main/.harness/designs/v4-device-wide/12-open-questions.md) (operator-local). Each question has an explicit deferral target — V4 build plan, V5 plan time, V6 plan time, or operator preference. The list is not load-bearing for this HLD; build plans inherit it.

## Lifecycle

Per the operator's [[hld-evolution-update-on-major-release]] convention, this HLD gets a new dated subsection added whenever a release introduces, changes, or locks a relevant design call.

**Update history:**

- **v0.3 — 2026-05-27 — V4.3 — agentm v4.1.0 — Vault-backed harness state + folder rename.** ROADMAP-V4 item #26. The first BUILD on top of the V4.2 reorganization. Implements the locked design from this HLD's "State migration" section + plan #18's `.harness/designs/v4-device-wide/05-state-migration.md` + `06-dispatcher-contracts.md` + `08-concurrency.md` + `09-backward-compat.md`. Per-project state files (PLAN.md, progress.md, ROADMAP-*.md, FOLLOWUPS.md, features.json, init.sh, designs/, archived plans, cursor files) relocate from `<project>/.harness/` to `<vault>/projects/<slug>/_harness/`. Vault top-level folder `personal-projects/` renames to `projects/` in the same release. Backward-compat preserved: legacy `<project>/.harness/<file>` reads still work via the resolver's tier-2 fallback with a one-warn-per-session-per-file deprecation notice; writes go only to vault unless `.project-mode=local` (the operator-opt-out escape hatch). Concurrency primitives ship per the §08-concurrency design: `safe_write_replace_style()` with mtime-based concurrent-modification check; `detect_conflict_files()` for GDrive `(conflicted copy …)` files; new `conflict-merger-session-start` hook (claude-code-only, non-blocking, surfaces detections on stderr at SessionStart). Cross-repo `list-plans.{sh,ps1}` ships the "show me all in-flight plans" surface that becomes meaningful once state is centralized. Single-repo release (no paired crickets bump); crickets stays at v2.0.0. The reorg is *additive* — no breaking changes for v4.0.0 operators. Operator-paced migration: `migrate-harness-to-vault.sh <project>` per project; `--rollback` flips back; `--cleanup` removes legacy after byte-identical verification. Hard-cut deprecation of legacy paths deferred to a later v4.x release. **Dogfood discoveries from plan #20 task 9** (mid-build operator-vault migration of multiple repos): three bugs caught + fixed pre-release (preview-mode sweep gap; `_idea-incubator/` wikilinks excluded from sweep; stale `github.repo` in agentm's `project.json` from pre-v3.1.0 rename caused wrong slug resolution). Six watchlist items deferred to operator's real-use sessions (multi-device cursor concurrency stress test; mobile-readable `progress.md` formatting at 723+ lines; GDrive conflict-file naming edge cases; recall-noise from vault-resident PLAN narratives; backward-compat warning behavior in real-use; cross-repo list-plans UX iteration).

- **v0.2 — 2026-05-27 — V4.2 — crickets v2.0.0 + agentm v4.0.0 (paired pair #11) — Reorganization.** ROADMAP-V4 item #36 — the first BUILD plan after #31 (this HLD's design pass) locked the architecture. Compound skills (`memory`, `design`, `diataxis-author`, `ship-release`), the four memory hooks, the `evidence-tracker` hook, the `memory-idea-researcher` sub-agent, the `plugins/` tree (with `install-plugin.sh`), and the `bundles/` namespace (with `quality-gates`) all moved from crickets to Agent M. The split now reflects the device-wide-by-default rationale: crickets owns universal base primitives; Agent M owns the agentic memory + compound flows that turn the harness into a learning environment. crickets v2.0.0 narrows to base primitives only (2 skills + 3 sub-agents + 3 hooks); Agent M v4.0.0 absorbs the compound surface + memory stack and dispatches it via a new manifest-walking installer block. The reorg deliberately does NOT ship state migration (the `<vault>/projects/<slug>/_harness/` move) — that's V4 #26, next on the queue. v4.0.0 keeps the legacy `<project>/.harness/` paths intact with deprecation warning until #26 lands. No vault-side migration required; operators run `agentm/install.sh` after `crickets/install.sh` and the compound skills + memory hooks land at the same `.claude/skills/`, `.claude/hooks/`, `.agents/skills/` destinations crickets v1.x used.

- **v0.1 — 2026-05-26**: initial publication, paired with plan #18 close.

Future updates land here as the V4 build phases (#26, #30, #35, #32) ship + as V5/V6 work touches the architecture. A heavy operator-edit + reflection pass on the broader Agent Memory HLD set is scheduled for post-V5 close.

## See also

- [`agent-memory-evolution.md`](agent-memory-evolution.md) — the V1 → V6 evolution of Agent Memory (Agent M)
- [`agentm/.harness/ROADMAP-AgentMemoryV4.md`](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP-AgentMemoryV4.md) — V4 build sequencing
- [`agentm/.harness/ROADMAP-AgentMemoryV5.md`](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP-AgentMemoryV5.md) — V5 indexed retrieval + lifecycle + types
- [`agentm/.harness/ROADMAP-AgentMemoryV6.md`](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP-AgentMemoryV6.md) — V6 dreaming + multi-surface + extensible sidecars
- crickets ADR 0012 (lands with plan #18 close) — locks the device-wide-by-default decision
