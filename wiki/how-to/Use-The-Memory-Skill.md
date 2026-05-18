# How to use the memory skill

> [!NOTE]
> **Goal:** capture durable preferences / workflows / fixes to MemoryVault so the agent's behavior compounds across sessions. Evolve entries when preferences change without losing the audit trail.
> **Prereqs:** `agent-toolkit` installed (skill lands at `.claude/skills/memory/` + `.agent/skills/memory/`); an Obsidian vault folder set up as your `MemoryVault/` root + the path exported as `MEMORY_VAULT_PATH` (or passed via `--vault-path` on each invocation). Optional: `pip install sqlite-vec sentence-transformers` for full vec-index + offline embedding; `VOYAGE_API_KEY` or `ANTHROPIC_API_KEY` env var for online embedding. Without these the skill still works (file writes always succeed; embedding work queues for later).

The `memory` skill ships as plan #7a part 1 of [MemoryVault — Permanent agent memory via Obsidian-vault-folder + reflection sidecar](../explanation/designs/memoryvault.md). This page covers the **two write primitives** available today (`/memory save` + `/memory evolve`) — recall (auto-injection at SessionStart + UserPromptSubmit), reflection sidecar (Stop + idle hooks), idea ledger, and discovery come in subsequent parts.

## ⚡ At-a-glance

| Sub-command | Input | Output | Backed by |
|---|---|---|---|
| `/memory save` | `<kind> <slug>` + body (stdin or interactive) | Entry at `<vault>/<group>/<kind>/<slug>.md` (or `_always-load/<slug>.md`); queued embedding | `skills/memory/scripts/save.py` |
| `/memory evolve` | `<old-path> <reason>` + new body | Archive at `_archive/<original>.YYYYMMDD.md` + new entry replacing old | `skills/memory/scripts/evolve.py` |
| `/memory reflect` | — | (stub; lands in plan #7a part 3) | — |
| `/memory search` | — | (stub; lands in plan #7a part 2) | — |

## When to use which sub-command

| You want to... | Reach for |
|---|---|
| Save a new preference / workflow / fix you want the agent to remember | `/memory save` |
| Mark an entry as "always loaded" — injected at SessionStart for every session | `/memory save --always-load` |
| Replace an existing entry with a corrected version, preserving the old one as audit trail | `/memory evolve` |
| Rename an entry's slug while evolving content | `/memory evolve --new-slug <new>` |
| Search the vault for prior entries (or auto-recall via hooks) | (deferred to plan #7a part 2 — `/memory search`; auto-recall via SessionStart / UserPromptSubmit hooks) |
| Run reflection over the current session to mine durable entries | (deferred to plan #7a part 3 — `/memory reflect`) |

## Scenario 1 — Save a new preference

Capture a dev-flow convention you want the agent to follow forever:

```bash
echo "Status:[x] task closeouts in PLAN.md must be paragraph-long narratives,
not just checkmarks. The next session's context is whatever the closeout
captures — so capture everything that matters: files changed, design calls,
scope adjustments, CI per-OS times, manual verification scenarios, negative
test results when relevant." \
| python3 ~/Antigravity/agent-toolkit/skills/memory/scripts/save.py \
  preferences paragraph-long-status-narratives \
  --vault-path ~/Library/CloudStorage/GoogleDrive-<account>/My\ Drive/Obsidian/MemoryVault \
  --tags dev-flow,status-reports,locked-design-call \
  --always-load
```

Or via Claude Code (the agent invokes the skill's documented flow using `Read` / `Write` / `Edit` tools — byte-identical output):

```
/memory save preferences paragraph-long-status-narratives \
  --always-load \
  --tags dev-flow,status-reports,locked-design-call
```

The file lands at `MemoryVault/personal-private/_always-load/paragraph-long-status-narratives.md` with YAML frontmatter:

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

Followed by the body content.

The `--always-load` flag routes the entry to `_always-load/` (regardless of `--group`) and sets `always_load: true` so future recall hooks inject it at SessionStart.

## Scenario 2 — Evolve a preference when you change your mind

Three months later you decide bulleted lists work better than paragraphs for status reports. Use `/memory evolve` to preserve the audit trail:

```bash
echo "Status:[x] task closeouts in PLAN.md use bulleted lists per task:
- files changed (count + key paths)
- design calls (locked decisions only)
- CI per-OS times (Linux / Mac / Windows)
- manual verification scenarios (if applicable)
- negative-test results (if applicable)
Each bullet 1-2 sentences max." \
| python3 ~/Antigravity/agent-toolkit/skills/memory/scripts/evolve.py \
  personal-private/_always-load/paragraph-long-status-narratives.md \
  "Switched preference: bulleted lists scale better; paragraph format was hard to scan when reviewing PLAN archives" \
  --vault-path ~/Library/CloudStorage/GoogleDrive-<account>/My\ Drive/Obsidian/MemoryVault
```

After:

- **Active entry** at the original path now contains the new bulleted preference. Its frontmatter gains `supersedes: personal-private/_archive/personal-private/_always-load/paragraph-long-status-narratives.md.20260817.md`.
- **Archive entry** at `personal-private/_archive/personal-private/_always-load/paragraph-long-status-narratives.md.20260817.md` contains the original body (unchanged) plus updated frontmatter: `status: superseded`, `superseded_by: <new-path>`, `superseded_at: 2026-08-17T...Z`, `superseded_reason: "Switched preference: bulleted lists scale better..."`.

The recall engine (lands in plan #7a part 2) skips `status: superseded` entries by default, so the agent picks up the new preference automatically. The archive stays for human-review of the supersession history.

## Scenario 3 — Rename an entry while evolving

The slug `paragraph-long-status-narratives` no longer fits the new preference. Use `--new-slug` to rename:

```bash
echo "New content for renamed entry..." \
| python3 ~/Antigravity/agent-toolkit/skills/memory/scripts/evolve.py \
  personal-private/preferences/paragraph-long-status-narratives.md \
  "Renamed to reflect new bulleted format" \
  --new-slug bulleted-status-narratives \
  --vault-path ~/Library/CloudStorage/GoogleDrive-<account>/My\ Drive/Obsidian/MemoryVault
```

The old entry is unlinked from its original path; a new entry appears at `<old-parent>/bulleted-status-narratives.md` with `supersedes:` cross-link to the archive. The archive contains the old body + slug, frozen at the evolution moment.

**Note**: `--new-slug` is rejected for `_always-load/` entries — those evolve in place only (the directory structure under `_always-load/` is flat by convention).

## Vault path resolution

The skill resolves the MemoryVault root in this order:

1. **`--vault-path <path>`** CLI arg (highest priority; overrides everything)
2. **`MEMORY_VAULT_PATH`** environment variable
3. **Config file** at `~/.config/agent-toolkit/memory.yml` (`vault_path:` key) — **documented but not yet implemented as of v0.9.0**; tracked for a future task

If none resolve, both `save.py` and `evolve.py` error out with a clear next-step message. No implicit fallback to `cwd` or `~` (prevents accidental writes to wrong directories).

## Embedding modes

By default the skill embeds entries via the Voyage AI endpoint (Anthropic's recommended embedding provider). Set `MEMORY_USE_API_EMBEDDINGS=false` to use the local `sentence-transformers` fallback (offline-capable; ~80MB model; `pip install sentence-transformers` required).

The embedding step is **async** — it queues to `<vault>/_meta/embedding-queue.jsonl` synchronously (fast; never blocks the file write) and a separate drain step (`python3 vec_index.py --vault-path <vault> drain` or future idle-time hook) processes the queue + writes to the vec-index. This means:

- Save / evolve always succeed even if no embedding mode is available (no API key, no local model, sqlite-vec missing). The queue accumulates pending work.
- Drain processes the queue when deps become available — graceful-skip pattern across multiple layers (sqlite-vec / embedding mode / enable_load_extension).
- The queue file is operator-debuggable (`cat <vault>/_meta/embedding-queue.jsonl`) and the drain function is idempotent (re-runs on a stable queue produce the same final state).

The full happy path requires: `pip install sqlite-vec sentence-transformers` + a Python build with `enable_load_extension` enabled (Homebrew Python or pyenv; not Apple's macOS system Python).

## Troubleshooting

**`save.py` exits with `No vault path resolved`**
Set `--vault-path` or `export MEMORY_VAULT_PATH=...` before invoking. The skill refuses to guess.

**`save.py` exits with `entry already exists at <path>`**
The collision check is non-negotiable — `/memory save` never overwrites. Either use a different slug, or use `/memory evolve` to supersede the existing entry (preserves it as audit trail).

**`evolve.py` exits with `old entry status is 'superseded', not 'active'`**
You can't evolve an already-superseded entry. The supersession graph traverses outward from active state. Manual escape hatch: edit the entry's `status:` frontmatter to `active` if you really need to evolve it.

**Drain reports `skipped: N, processed: 0` with `errors: 0`**
This is the graceful-skip path: sqlite-vec is missing OR the Python build doesn't support `enable_load_extension` (Apple system Python). Workaround: install Homebrew Python (`brew install python`) or use pyenv, then `pip install sqlite-vec`. Until then, save + evolve still work; embeddings queue stays pending.

**Drain reports embedding skipped for some entries**
The configured embedding mode wasn't available for those entries (no API key for api mode, or `sentence-transformers` missing for local mode). The entries stay in the queue; re-running drain after configuring the mode will process them.

## See also

- [MemoryVault design doc](memoryvault) — the canonical "Why we built this" entry point per the locked design call from plan #6. Covers the full architecture across all 6 parts.
- [Customization Types](Customization-Types) — `kind: skill` row covers the memory skill.
- [Manifest Schema](Manifest-Schema) — frontmatter contract for skill manifests.
- [Per-Host Paths](Per-Host-Paths) — destination paths per kind per host.
- [Use the design skill](Use-The-Design-Skill) — the skill that authored MemoryVault's design doc (first real dogfood).
