---
name: memory
description: File-based, agent-curated permanent memory layer that lives inside the user's existing Obsidian vault. Captures durable preferences / workflows / fixes via a reflection sidecar; recalls relevant entries automatically into every new prompt via SessionStart + UserPromptSubmit hooks; adapts the agent's behavior over time without explicit configuration. The goal is compound learning — each conversation makes the next one better, because the agent never forgets what already happened.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# memory — permanent agent memory via Obsidian-vault-folder + reflection sidecar

The first toolkit skill that integrates with the user's own personal note-taking surface (Obsidian) rather than maintaining a separate agent-only vault. The skill exposes four sub-commands (`save` / `evolve` / `reflect` / `search`); recall is hook-driven rather than user-invoked (SessionStart + UserPromptSubmit hooks shipped alongside in the [recall-loop part](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/memoryvault/parts/recall-loop.md)).

**Position vs. built-in agent memory** (Claude memories, vendor-specific context features): built-in memory is per-platform, opaque, lossy, and not composable across tools. MemoryVault is file-based + version-control-friendly + human-inspectable. The user can open Obsidian + read or edit any captured entry directly; the agent's memory + the user's notes coexist in the same place.

**Position vs. session transcripts**: Claude Code transcripts capture everything that happened. MemoryVault captures what's worth keeping forever — the durable preferences / workflows / fixes that make Day 2 better than Day 1.

## When to reach for which sub-command

| You want to... | Reach for |
|---|---|
| Capture a specific preference / workflow / fix manually right now | `/memory save` |
| Replace an existing entry with a corrected version (preserving audit trail) | `/memory evolve` |
| Run reflection over the current session transcript on demand (or a specified transcript path) | `/memory reflect` |
| Search the vault for entries matching a query (when auto-recall via UserPromptSubmit hook didn't pull what you wanted) | `/memory search` |

Auto-recall happens via the [SessionStart + UserPromptSubmit hooks](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/memoryvault/parts/recall-loop.md) — operators don't invoke a recall command directly. Reflection happens automatically via Stop + idle hooks too; the manual `/memory reflect` is for one-off runs against arbitrary transcripts.

## Sub-commands

### `/memory save`

Synchronously writes a markdown entry to MemoryVault. File write returns immediately (<50ms target); embedding + vec-index update are async and deferred (the actual embedding integration lands in task 4 of plan #7a part 1; until then the embedding step is a no-op stub that logs `"embedding queued (deferred to task 4)"`).

#### Invocation

```
/memory save <kind> <slug> [--group <group>] [--always-load] [--vault-path <path>]
                            [--tags <tag1,tag2,...>] [--supersedes <old-path>]
```

| Arg | Required | Default | Meaning |
|---|---|---|---|
| `<kind>` | yes | — | Entry kind (preference / workflow / fix / domain-reference / idea / etc.). Subdir name under the chosen group. |
| `<slug>` | yes | — | Kebab-case identifier; filename stem. Validated as `^[a-z0-9-]+$`. |
| `--group <group>` | no | `personal-private` | Memory group: `personal-private` / `personal-skills` / `personal-projects/<project-slug>`. |
| `--always-load` | no | false | Routes to `MemoryVault/personal-private/_always-load/<slug>.md` and sets `always_load: true` frontmatter — entry gets injected at SessionStart per the recall-loop part. Overrides `--group` (always lands in `_always-load`). |
| `--vault-path <path>` | no | from config | Absolute path to the MemoryVault folder. Resolution order: `--vault-path` arg > `MEMORY_VAULT_PATH` env var > `~/.config/agent-toolkit/memory.yml` `vault_path:` key > error. |
| `--tags <tag1,tag2>` | no | empty list | Comma-separated tags; written to `tags:` frontmatter list. |
| `--supersedes <old-path>` | no | empty | Path to an existing entry this new entry supersedes. Sets `supersedes:` frontmatter; **does NOT archive the old entry** — that's `/memory evolve`'s job (task 3). `--supersedes` is for cross-link-without-archive cases. |

The entry body (free-form markdown after the YAML frontmatter) comes from stdin OR an interactive prompt. The agent following the skill body asks for the body content if not piped.

#### Step-by-step flow

**Step 1 — Resolve vault path.** Walk the resolution order: `--vault-path` arg → `MEMORY_VAULT_PATH` env var → `~/.config/agent-toolkit/memory.yml` (`vault_path:` key). If none found, halt with `"No vault path resolved. Set --vault-path, MEMORY_VAULT_PATH, or ~/.config/agent-toolkit/memory.yml vault_path: <path>."`. Verify the resolved path exists and is a directory; halt otherwise with a clear error.

**Step 2 — Validate inputs.** `<kind>` and `<slug>` must match `^[a-z0-9-]+$` (kebab-case). `--group` (if provided) must match `^[a-z0-9-]+(/[a-z0-9-]+)?$` (kebab-case; one optional `/<project-slug>` segment for `personal-projects/<slug>`). Tags (if provided) each must match `^[a-z0-9-]+$`. Halt on any validation failure with a clear error pointing at the offending arg.

**Step 3 — Compute target path.** Two cases:

- `--always-load` set: `<vault-path>/personal-private/_always-load/<slug>.md`
- `--always-load` not set: `<vault-path>/<group>/<kind>/<slug>.md` (with `<group>` defaulting to `personal-private`)

Create parent directories if they don't exist (via Write tool's implicit dir creation, or explicit `Glob` + `Write` for clarity).

**Step 4 — Collision check.** If the target path already exists, halt with `"Entry already exists at <path>. Use /memory evolve to supersede the existing entry, or pick a different slug."`. Never overwrite an existing entry from `/memory save` — that's `/memory evolve`'s job.

**Step 5 — Build frontmatter.** Construct YAML frontmatter with these fields:

```yaml
---
kind: <kind>
status: active
created: <today UTC, YYYY-MM-DD>
updated: <today UTC, YYYY-MM-DD>
tags: [<tag1>, <tag2>, ...]   # empty list [] if no --tags
group: <group-or-personal-private>
slug: <slug>
always_load: <true-if-flag-set-else-false>
supersedes: <old-path-if-flag-set>   # omit field entirely if no --supersedes
---
```

Frontmatter field order is locked above for deterministic diffs. The `always_load` field is always present (true or false) so the recall hooks can grep for it without ambiguity.

**Step 6 — Compose entry content.** Prepend the frontmatter to the body content. Final shape:

```
---
<frontmatter>
---

<body markdown>
```

Trailing newline at EOF.

**Step 7 — Write file.** Use the Write tool to create the file at the computed target path. Verify the write succeeded (Write tool returns success/error). File write is synchronous; on success, the file is on disk before the next step.

**Step 8 — Queue async embedding + vec-index update.** Until task 4 of this plan lands (embedding integration), this step is a no-op stub: log `"embedding queued (deferred to task 4)"` and continue. After task 4 ships, this step kicks off an async embedding call to the configured provider (Anthropic API default; local sentence-transformers fallback per `memory.use_api_embeddings`) and writes the embedding to `MemoryVault/_meta/vec-index.db` via sqlite-vec. The async-ness ensures file write is never blocked by network or vec-index latency.

**Step 9 — Return confirmation.** Report success to the operator with:

```
Saved entry to <relative-path-from-vault-root>/<slug>.md
  kind:  <kind>
  group: <group>
  tags:  <tags-or-(none)>
  flags: <always-load-and-supersedes-if-set>
```

Plus the deferred-embedding note: `"(Embedding deferred to plan #7a part 1 task 4; index will populate on next reindex.)"`.

#### Tool allowlist

**`Read, Write, Edit, Glob, Grep`** — no Bash. The skill body never invokes shell commands directly. The agent following this body uses Write to create the entry file; Read to check config files for vault-path resolution; Glob to discover existing parent directories. Python scripts under `skills/memory/scripts/` (added in this task + tasks 3 + 4) handle the heavy lifting when invoked from Claude Code hooks (which run as standalone scripts, not as skill bodies) — see `Tool allowlist` section below for the skill-vs-script split.

#### Hard gates

- **Collision check is non-negotiable** — `/memory save` never overwrites. Operators wanting to replace an entry use `/memory evolve` (task 3).
- **Vault path must resolve** — no implicit fallback to `cwd` or `~`; explicit error if no resolution path succeeds. Prevents accidental writes to wrong directories.
- **Kind / slug / group validation** is strict — kebab-case only. Catches typos before they create unparseable directory structures.

#### Worked example

Saving a dev-flow convention as an `_always-load` entry:

**Invocation:**

```
/memory save preferences paragraph-long-status-narratives \
  --always-load \
  --tags dev-flow,status-reports,locked-design-call \
  --vault-path ~/Library/CloudStorage/GoogleDrive-<account>/My\ Drive/Obsidian/MemoryVault
```

(With the entry body provided via stdin or the agent prompting interactively.)

**Step 1** — `--vault-path` provided → resolved to the synced Obsidian vault root. Exists + is a directory. ✓

**Step 2** — `kind=preferences` ✓; `slug=paragraph-long-status-narratives` ✓; `--always-load` set → group ignored. Tags `[dev-flow, status-reports, locked-design-call]` each match `^[a-z0-9-]+$` ✓.

**Step 3** — `--always-load` set → target path: `<vault>/personal-private/_always-load/paragraph-long-status-narratives.md`. Parent dir created if absent.

**Step 4** — Collision check: path does not exist → proceed.

**Step 5** — Build frontmatter:

```yaml
---
kind: preferences
status: active
created: 2026-05-17
updated: 2026-05-17
tags: [dev-flow, status-reports, locked-design-call]
group: personal-private
slug: paragraph-long-status-narratives
always_load: true
---
```

**Step 6** — Compose with body:

```
---
<frontmatter>
---

Status:[x] task closeouts in `.harness/PLAN.md` must be paragraph-long narratives,
not just checkmarks. The next session's context is whatever the closeout captures —
so capture everything that matters: files changed, design calls, scope adjustments,
CI per-OS times, manual verification scenarios, negative-test results when relevant.
```

**Step 7** — Write file at the target path. ✓

**Step 8** — Log `"embedding queued (deferred to task 4)"`.

**Step 9** — Report:

```
Saved entry to personal-private/_always-load/paragraph-long-status-narratives.md
  kind:  preferences
  group: personal-private (overridden by --always-load → _always-load)
  tags:  dev-flow, status-reports, locked-design-call
  flags: always_load

(Embedding deferred to plan #7a part 1 task 4; index will populate on next reindex.)
```

#### Failure modes

- **Missing vault path** — all 3 resolution paths fail → halt with clear next-step text pointing at the 3 resolution options.
- **Vault path exists but is not a directory** — halt with `"<path>: not a directory."` and exit; never write to a file path treated as a vault root.
- **Invalid kind / slug / group / tags** — halt with the specific arg + the expected kebab-case shape; never coerce or silently lowercase.
- **Target file exists** — halt with the `/memory evolve` recommendation; never overwrite from `/memory save`.
- **Write tool fails** (disk full, permission denied, etc.) — surface the Write tool's error verbatim + a hint that the entry was NOT saved.

#### Anti-patterns

`/memory save` must NOT:

- **Overwrite an existing entry** — Step 4 collision check is the hard gate.
- **Block on embedding** — Step 8 is async-deferred; file write must complete before any network call.
- **Coerce slugs** — operator provides exact slug; validator rejects, never auto-lowercases or strips characters.
- **Default vault path to `cwd` or `~`** — explicit resolution chain; no implicit defaults that could write to wrong directories.
- **Modify Document History or other special files** in the vault — `/memory save` is a single-file-write primitive; cross-file ops are for `/memory evolve` (task 3) + the reflection sidecar (plan #7a part 3).

#### Python-side script (`scripts/save.py`)

In parallel with the agent-driven skill body, this part also ships a standalone Python script at `agent-toolkit/skills/memory/scripts/save.py` that implements the same save logic for **hooks** (which run as standalone Python scripts, not as skill bodies) + **operator-debug** (manual `python3 ...` invocation) + **testing** (deterministic fixture tests that don't require an agent).

The script exposes:

- **Function**: `save_entry(vault_path, kind, slug, body, *, group="personal-private", always_load=False, tags=None, supersedes=None) -> pathlib.Path` — the canonical save primitive. Returns the absolute path written. Raises `FileExistsError` on collision; `ValueError` on validation failure; `FileNotFoundError` if vault path doesn't exist.
- **CLI entry point**: `python3 save.py <kind> <slug> --vault-path <path> [--group <g>] [--always-load] [--tags <t1,t2>] [--supersedes <p>] [--body-file <path-or-->]` — same flag semantics as the skill body's `/memory save` invocation. `--body-file -` reads from stdin.

Both paths (skill-body Write + script-CLI Python) produce byte-identical entry files for the same inputs. Future hooks (plan #7a part 3's reflection sidecar) import + call `save_entry()` directly. The skill body's documented flow is operator-facing; the script is hook-facing; they don't compete.

### `/memory evolve`

> [!NOTE]
> **Status**: stub. Full body lands in **task 3** of plan #7a part 1 (`write-primitives`). See `.harness/PLAN.md` for the task spec.

Atomic archive-and-replace primitive that prevents memory rot when preferences change. Five-step flow: (1) read the old entry; (2) write new entry with `supersedes: <old-path>` frontmatter pointing back; (3) atomically move old entry to `MemoryVault/personal-private/_archive/<original-path>.YYYYMMDD.md` via filesystem rename (single-syscall atomicity on APFS); (4) update old entry's frontmatter `status: superseded` + `superseded_by: <new-path>` cross-link; (5) trigger vec-index update for both. Recall filters skip `status: superseded` by default.

**Planned invocation shape** (subject to refinement in task 3):

```
/memory evolve <old-path> <new-content> <reason>
```

Integrates with the tri-modal review flow (lands in plan #7a part 3, `reflection-and-recovery`): when a new candidate contradicts an existing entry, "supersede existing entry X?" is one of the four approve / edit / reject / supersede options at review time.

### `/memory reflect`

> [!NOTE]
> **Status**: stub. Full body lands in plan #7a **part 3** (`reflection-and-recovery`). See `.harness/designs/memoryvault/queued-plans/reflection-and-recovery.PLAN.md` for the queued plan.

User-invokable trigger for the reflection sidecar logic. Two parallel mining passes over a session transcript: (a) the **3-category mine** (Successful Workflows / User Preferences / Fixes & Workarounds) writes MemoryVault entries via `/memory save`; (b) the **idea-candidate mine** (follow-ups / project ideas / research candidates) writes to `~/Obsidian/Ideas.md` + `MemoryVault/personal-private/_idea-incubator/<slug>/` via the idea-ledger flow (lands in plan #7a part 4).

Tri-modal confidence routing applies: HIGH-confidence candidates auto-save; MEDIUM go through interactive review; LOW land in `_inbox/` for batch triage. Controlled by `memory.review_mode: interactive (default) | silent`.

The same logic runs automatically via Stop-event hook (after every session) + idle-time hook (after N minutes idle, also recovers crashed sessions). `/memory reflect` is the manual trigger for on-demand runs.

**Planned invocation shape** (subject to refinement in plan #7a part 3):

```
/memory reflect [--session <path>]
```

Defaults to the current Claude Code session transcript.

### `/memory search`

> [!NOTE]
> **Status**: stub. Full body lands in plan #7a **part 2** (`recall-loop`) where the recall engine is built. See `.harness/designs/memoryvault/queued-plans/recall-loop.PLAN.md` for the queued plan.

Manual semantic query against the vault — the read primitive that complements `/memory save`'s write. Useful when the automatic recall (via UserPromptSubmit hook) didn't surface what you wanted, or when you want to inspect what's in the vault without re-loading via a session prompt.

Calls the same recall engine the UserPromptSubmit hook uses: sqlite-vec primary + grep + frontmatter alongside, merge results via the locked rank-merge formula (`sim × 0.7 + keyword × 0.3`), dedup, return top-K (K=5 default).

**Planned invocation shape** (subject to refinement in plan #7a part 2):

```
/memory search <query> [--group <group>] [--include-inbox] [--top-k <N>]
```

Default behavior: query against all groups; exclude `_inbox/`; return top-5 results.

## Tool allowlist

**`Read, Write, Edit, Glob, Grep`** — no Bash. Same restriction as `/design` skill. The skill body never invokes shell commands directly; Python scripts under `skills/memory/scripts/` (added in tasks 2-4) handle the heavy lifting (file ops via Python's `os` / `pathlib`; embedding API calls via Python `requests` or vendor SDK; sqlite-vec via the `sqlite-vec` Python wheel).

Python-side scripts can use whatever they need (network for embedding API, filesystem for vec-index, subprocess for `pip install <pkg>` on first invocation if needed) — the allowlist restriction is on the SKILL.md body itself, not the dispatched scripts.

## Host scope

`supported_hosts: [claude-code, antigravity]` — `gemini-cli` excluded per [ROADMAP item #15](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md) (Gemini-CLI host removal, shipped in toolkit v0.9.0). The memory skill was the first new skill to ship post-#15-decision (in v0.8.x scaffold) with the two-host scope from day 1; v0.9.0 then swept all other customizations to match. See [ADR 0006](../../wiki/explanation/decisions/0006-gemini-cli-host-removal.md) for the host-scope-reduction rationale.

See the [parent design's 2026-05-16 Document History row](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/memoryvault.md#document-history) for the host-scope correction rationale that triggered this.

## Cross-references

- **Parent design**: [MemoryVault — permanent agent memory](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/memoryvault.md) — the canonical "Why we built this" wiki entry point per the locked design call from plan #6
- **Part 1 plan**: `write-primitives` (active at `.harness/PLAN.md`) — ships `save` + `evolve` bodies (tasks 2 + 3) + embedding integration (task 4) + partial how-to (task 5)
- **Queued parts**: `recall-loop` (part 2) / `reflection-and-recovery` (part 3) / `idea-ledger` (part 4) / `seed-pass` (part 5) / `discovery-mining` (part 6 = plan #7b)
- **Conventions**: shipping pattern follows [`design` skill's multi-sub-command body shape](https://github.com/alexherrero/agent-toolkit/blob/main/skills/design/SKILL.md) — the first toolkit skill with multiple sub-commands handing off between each other
- **External-review handoff**: applies to design + plan refinement passes; lands via [agent-toolkit v0.8.1](https://github.com/alexherrero/agent-toolkit/releases/tag/v0.8.1) + [agentic-harness v2.3.1](https://github.com/alexherrero/agentic-harness/releases/tag/v2.3.1) shipped 2026-05-16

## Status

This skill is **stub-shipped** as of v0.9.0 (plan #7a part 1, task 1). All 4 sub-commands have documented shape + planned invocation but no functional implementation yet. The 4 sub-commands fill in across plan #7a tasks 2-5 + the 5 queued parts (recall-loop, reflection-and-recovery, idea-ledger, seed-pass, discovery-mining) which complete the v0.9.0 → v0.10.0 sequence.

Until full bodies land, invoking any of the 4 sub-commands will surface a "Stub — full implementation lands in <task/part X>. See parent design at <link>." message rather than executing the operation.
