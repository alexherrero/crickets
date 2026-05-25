# How to use the diataxis-author skill

> [!NOTE]
> **Goal:** Author + maintain a Diátaxis-style wiki for any repo via the 5-sub-command `/diataxis` skill — live authoring (`author`), drift detection (`check`), interactive repair (`repair`), one-shot legacy migration (`migrate`), and mode classification (`classify`).
> **Prereqs:** `crickets` installed (see [Manifest-Schema](Manifest-Schema) for the `kind: skill` shape); for `check`/`repair`: `scripts/check-wiki.py` from `agentm` available via sibling clone (graceful-skip if absent); for `migrate`: clean working tree + a legacy audience-based wiki layout to migrate from.

The `diataxis-author` skill encodes the operator's preferred conventions from [agentm ADR 0004](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0004-diataxis-documentation-spec.md) into proactive authoring guidance + ongoing drift detection + repair + one-shot migration. One skill, five sub-commands (matches `/memory`'s shape).

## Prerequisites

- crickets installed in your project (per [Tutorial 1](../tutorials/01-First-Customization.md)).
- For drift detection: `scripts/check-wiki.py` from the harness (auto-detected at sibling-clone locations; graceful-skip if absent).
- For migration: working tree must be clean (`git status --porcelain` empty); legacy audience-based wiki layout (`development/`, `operational/`, `design/`, `architecture/`) for `/diataxis migrate` to have anything to do.

## ⚡ At-a-glance

| Sub-command | Input | Output | Backed by |
|---|---|---|---|
| `/diataxis author <slug>` | `<slug>` + `--mode` OR `--intent` | Pre-filled template skeleton at `wiki/<mode-dir>/<filename>.md` | `skills/diataxis-author/scripts/author.py` |
| `/diataxis classify <file>` | path to wiki page | JSON: mode + confidence + per-mode scores + `needs_subagent` flag | `skills/diataxis-author/scripts/classify.py` |
| `/diataxis check [--strict]` | (walks `wiki/`) | Structured JSON report — drift findings by rule | `skills/diataxis-author/scripts/check.py` |
| `/diataxis repair` | (consumes check output) | Interactive fix-application; preview-first per finding | `skills/diataxis-author/scripts/repair.py` |
| `/diataxis migrate` | (one-shot, requires legacy layout) | git mv operations + `.diataxis` marker + `.diataxis-conventions.md` | `skills/diataxis-author/scripts/migrate.py` |

## When to use which sub-command

| You want to... | Reach for |
|---|---|
| Start a new wiki page with the right template + filename style | `/diataxis author <slug>` |
| Verify a single page's Diátaxis mode + see if it's ambiguous | `/diataxis classify <file>` |
| Audit the entire wiki for mode-mixed pages / stale links / template drift | `/diataxis check [--strict]` |
| Walk through detected drift and apply fixes interactively | `/diataxis repair` |
| One-shot migrate a legacy audience-based wiki to Diátaxis (subsumes harness predecessor) | `/diataxis migrate` |

## Scenario 1 — Author a new how-to

You want to write a new how-to page. Let the skill pick the template + apply filename style + drop a pre-filled skeleton you edit in your editor.

```bash
python3 ~/Antigravity/crickets/skills/diataxis-author/scripts/author.py \
  "Install crickets into a project" --mode how-to
```

Output:

```
{
  "action": "authored",
  "target": "/path/to/wiki/how-to/Install-Agent-Toolkit-Into-A-Project.md",
  "mode": "how-to",
  "template": "/path/to/skills/diataxis-author/templates/how-to.md",
  "filename_style": "CamelCase-With-Dashes",
  "filename": "Install-Agent-Toolkit-Into-A-Project.md"
}
```

Skill writes the how-to template skeleton (mode-appropriate sections per ADR 0004); you open the file in your editor + fill in the placeholders.

## Scenario 2 — Author with mode inference from intent

Don't know whether your page should be a tutorial / how-to / reference / explanation? Describe the intent + let the classifier pick.

```bash
python3 ~/Antigravity/crickets/skills/diataxis-author/scripts/author.py \
  "MCP server lookup tables" --intent "quick-reference page listing every MCP server we use with their default ports + configs"
```

Skill calls `classify.py` against the intent text, picks `reference`, writes the reference template.

If the intent is ambiguous (heuristic confidence below threshold, default 0.7), the skill halts + prompts you to disambiguate via `--mode`.

## Scenario 3 — Audit the wiki for drift

You've been editing the wiki for a while; want to see what's drifted.

```bash
python3 ~/Antigravity/crickets/skills/diataxis-author/scripts/check.py --wiki-root wiki/
```

Outputs structured JSON listing all findings — mode-mixed pages, stale cross-references, template-shape drift, and (when check-wiki.py is available) the strict validator's rules too.

For each finding, a one-line suggested fix is included so you can grep for "needs human split" or "move to <mode>-mode dir" patterns to triage at a glance.

## Scenario 4 — Repair detected drift interactively

After running `check`, walk through each finding interactively.

```bash
python3 ~/Antigravity/crickets/skills/diataxis-author/scripts/repair.py
```

For each finding, the skill displays the file + rule + msg + suggested fix in a `──`-separated card and prompts:

```
Action: [a]pply / [e]dit / [r]eject / (default: skip)
```

- **apply** — apply the suggested fix (e.g. preview a `git mv` for template-drift; dispatch `documenter` sub-agent for mode-mixed splits).
- **edit** — record the finding as needing manual operator edit (you handle outside the skill).
- **reject** — drop the finding.
- **skip** (default + non-TTY) — leave it; surfaces again next `check` run.

Mode-mixed splits route through the `documenter` sub-agent (mechanical-write worker) — but only in real interactive runs. Use `--stub` to test the dispatch flow without invoking the sub-agent (CI-safe).

## Scenario 5 — Migrate a legacy audience-based wiki

Your project has the old harness layout (`development/`, `operational/`, `design/`, `architecture/`) and you want to bring it onto Diátaxis. One-shot migration, preview-first, blame-preserving:

```bash
# Preview only — see what would happen, no filesystem changes
python3 ~/Antigravity/crickets/skills/diataxis-author/scripts/migrate.py --preview
# Apply
python3 ~/Antigravity/crickets/skills/diataxis-author/scripts/migrate.py --execute
```

The skill:

1. Verifies preconditions (clean tree + `wiki/` exists + no `.diataxis` marker + ≥1 legacy mode-dir).
2. Walks `wiki/`; classifies every page by heading shape per ADR 0004's deterministic rules.
3. Mode-mixed pages flagged for human split (stay at old path; you handle via `/diataxis repair` after migration).
4. `git mv` each cleanly-classified page to its mode-dir (preserves blame).
5. Creates `wiki/.diataxis` marker + auto-seeds `wiki/.diataxis-conventions.md` with operator-editable conventions.
6. **Does not commit** — operator reviews the diff + commits manually (single-commit safety net).

After migration: `git status` should show ~N moves; spot-check `git log --follow wiki/<mode>/<some-page>.md` to confirm blame; split flagged pages via `/diataxis repair`; commit.

## AgentMemory integration

The skill reads operator conventions from AgentMemory at every invocation via a 3-tier fallback chain:

1. **Per-repo override** at `<repo>/wiki/.diataxis-conventions.md` (highest priority; created on `/diataxis migrate` first run).
2. **Global vault entries** at `<vault>/personal-private/_always-load/diataxis-*.md` (operator-curated via `/memory save --always-load` or skill-offered write-back).
3. **ADR 0004 hardcoded defaults** (fallback when neither operator surface has entries).

Recognized convention keys (case-insensitive; with or without `**bold**` wrapping):

| Key | Default | Example values |
|---|---|---|
| `Filename style:` | `CamelCase-With-Dashes` | `kebab-case`, `snake_case` |
| `Confidence threshold:` | `0.7` | `0.5` (looser), `0.85` (stricter) |
| `Mode-mixed default split:` | `how-to + reference` | `tutorial + how-to`, `how-to + explanation` |

Inspect current effective conventions:

```bash
python3 ~/Antigravity/crickets/skills/diataxis-author/scripts/agentmemory_conventions.py \
  --vault-path "$MEMORY_VAULT_PATH" \
  --wiki-root /path/to/your/project/wiki
```

## Per-repo `.diataxis-conventions.md` overrides

When `/diataxis migrate` runs, it auto-seeds `<repo>/wiki/.diataxis-conventions.md` with a starter template. Edit this file to lock per-repo deviations from your global vault conventions.

Example:

```markdown
# Diátaxis conventions for shrimpi-mono

## Filename style

kebab-case (Shrimpi monorepo convention — divergent from operator's
global CamelCase-With-Dashes default).

## Confidence threshold

0.85 (stricter — this repo has high-stakes ADRs that warrant more
human review on ambiguous classifications).
```

When the skill runs in this repo, kebab-case + 0.85 threshold apply; in your other repos, the global vault entries (or defaults) apply.

## Troubleshooting

**"wiki root not found"** — pass `--wiki-root <path>` or cd into a project with a `wiki/` directory.

**"already migrated"** (`/diataxis migrate`) — `wiki/.diataxis` marker exists. Remove it manually if you really want to re-run migration (rare; usually means migration succeeded and there's nothing more to do).

**"working tree not clean"** (`/diataxis migrate`) — commit or stash uncommitted changes first. The migration's diff is too large to read against unrelated changes.

**`/diataxis classify` keeps flagging pages as `needs_subagent: true`** — confidence threshold may be too high for your wiki's writing style. Tune via `<repo>/wiki/.diataxis-conventions.md` `Confidence threshold:` line OR via a global vault `_always-load/diataxis-threshold.md` entry.

**`/diataxis check` reports `check_wiki_status: skipped-absent`** — `scripts/check-wiki.py` from the harness isn't where the skill auto-detects (sibling clone at `<toolkit>/../agentm/scripts/` or `~/Antigravity/agentm/scripts/`). Pass `--check-wiki-py <path>` explicitly, or skip and use only the in-skill heuristics.

**`/diataxis repair` says all findings skipped** — non-TTY stdin defaults all prompts to skip (never-silent-action contract). Run from an interactive terminal OR use the specific-slug subcommands (`/diataxis repair` flow doesn't support batch — by design).

**Mode-mixed split via `documenter` dispatch doesn't write anything** — `--stub` mode is on (no actual sub-agent invocation), or the calling skill body hasn't dispatched the sub-agent. The CLI emits the dispatch marker; the dispatch itself happens at the agent's task delegation layer.

**Windows: `UnicodeEncodeError: 'charmap' codec can't encode character`** — fixed in v0.11.0 via `sys.stdout.reconfigure(encoding="utf-8")` in `migrate.py`. Upgrade to v0.11.0+ if you hit this.

## See also

- [Parent design — diataxis-author](../explanation/designs/diataxis-author.md) — the canonical "Why we built this" entry point per the locked design call from plan #6 (same convention as MemoryVault parent design).
- [ADR 0008 — diataxis-author](../explanation/decisions/0008-diataxis-author.md) — 4 locked design calls (Q1-Q4) + load-bearing assumptions with re-audit triggers.
- [Sibling sub-agent — diataxis-evaluator](../../agents/diataxis-evaluator.md) — read-only Tier-2 worker for ambiguous mode-classification.
- [agentm ADR 0004 — Diátaxis Documentation Spec](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0004-diataxis-documentation-spec.md) — canonical Diátaxis convention this skill enforces.
- [Predecessor (deprecated 2026-05-22) — migrate-to-diataxis](https://github.com/alexherrero/agentm/blob/main/harness/skills/migrate-to-diataxis.md) — superseded by `/diataxis migrate`.
- [Use the Memory Skill](Use-The-Memory-Skill.md) — sibling skill; same multi-sub-command shape; first AgentMemory consumer.
