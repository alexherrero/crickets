---
name: diataxis-author
description: Author + maintain a Diátaxis-style wiki for any repo. Live authoring guidance (mode selection + template-fill + filename style), ongoing drift detection + repair, one-shot migration of legacy audience-based wikis to the four-mode (tutorials / how-to / reference / explanation) discipline, and single-page mode classification with sub-agent fallback on ambiguous cases. Reads operator conventions from AgentMemory `_always-load/diataxis-*.md`; offers to capture judgment calls back as new conventions (operator-confirmed via permeable-boundary helper). Dispatches the existing `documenter` sub-agent for mechanical-write work; never auto-forks into wiki/ without preview. Subsumes the predecessor `migrate-to-diataxis` skill (harness-side) per ROADMAP #13. Hosts: Claude Code + Antigravity (`gemini-cli` removed in v0.9.0 per ADR 0006).
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# diataxis-author — author + maintain a Diátaxis wiki for any repo

The second major skill in `agent-toolkit` (after `memory`). Encodes the operator's Diátaxis discipline from [agentic-harness ADR 0004 — Diátaxis Documentation Spec](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0004-diataxis-documentation-spec.md) into proactive authoring guidance + ongoing drift detection + repair + one-shot migration, with per-repo overrides via `wiki/.diataxis-conventions.md` and global conventions stored in AgentMemory (`_always-load/diataxis-*.md`). Designed via [agent-toolkit's design skill](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/diataxis-author.md) — second real dogfood of plan #6's `/design author` after MemoryVault closed.

**Position vs. `check-wiki.py` strict validator**: validators catch violations after-the-fact; diataxis-author provides **proactive** guidance at write time (template selection, mode classification, filename style). Both layers complement: skill prevents drift at write time; `check-wiki.py` catches drift at commit time + during `/diataxis check`.

**Position vs. harness's `documenter` sub-agent**: documenter is the **mechanical write worker** (Diátaxis-aware writes per ADR 0004 §4); diataxis-author is the **operator-facing orchestration + guidance surface**. Skill dispatches documenter for splits + heavy writes — same separation as `/memory adapt-skills` (orchestration) vs. `adapt-evaluator` (sub-agent worker) from plan #7b task 4.

**Position vs. predecessor `migrate-to-diataxis` (harness-side)**: subsumed (plan #13 part 4). v1 ships the predecessor with a deprecation notice; follow-up harness release removes the file entirely after dogfood confirms diataxis-author is the better surface.

## When to reach for which sub-command

| You want to... | Reach for |
|---|---|
| Author a new wiki page with template + mode selection + filename style | `/diataxis author <slug>` |
| Detect drift across the wiki (mode-mixed pages, stale cross-refs, template-shape drift, convention drift) | `/diataxis check [--strict]` |
| Apply suggested fixes for detected drift, interactively | `/diataxis repair` |
| One-shot migrate a legacy audience-based wiki to the four-mode Diátaxis layout | `/diataxis migrate` |
| Classify a single page's mode (operator-debug; sub-agent dispatches here for ambiguous cases) | `/diataxis classify <file>` |

## Sub-commands

### `/diataxis author <slug>`

> [!NOTE]
> **Status**: stub. Full body lands in plan #13 **part 2** (`author-classify`) where the mode-classification engine + 4 templates + invocation flow ship. See the [author-classify part](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/diataxis-author/parts/author-classify.md) for the locked design.

Live authoring guidance — operator invokes when starting a new wiki page. Skill prompts for mode (tutorial / how-to / reference / explanation; sub-agent classifies from one-sentence intent if uncertain), picks the right Diátaxis template from the 4 ADR 0004 templates, applies the operator's filename style (default `CamelCase-With-Dashes` per AgentMemory always-load entry), and emits a pre-filled skeleton at `wiki/<mode>/<filename>.md`. Operator edits in their editor; skill doesn't write further.

**Planned invocation shape** (subject to refinement in plan #13 part 2):

```
/diataxis author <slug> [--mode <tutorial|how-to|reference|explanation>]
                        [--filename-style <CamelCase-With-Dashes|snake_case|kebab-case>]
                        [--intent "<one sentence>"]
```

### `/diataxis check [--strict]`

> [!NOTE]
> **Status**: stub. Full body lands in plan #13 **part 3** (`check-repair`). See the [check-repair part](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/diataxis-author/parts/check-repair.md) for the locked design.

Drift detection — wraps `scripts/check-wiki.py` (harness-side) as a subprocess + adds 4 skill-side heuristics (mode-mixed page detection / stale cross-references / template-shape drift / convention drift against AgentMemory conventions). Outputs a structured report grouped by mode. `--strict` mirrors check-wiki.py's strict mode. Non-zero exit on findings. Graceful-skip when check-wiki.py absent → in-skill heuristic-only mode + clear stderr warning.

**Planned invocation shape** (subject to refinement in plan #13 part 3):

```
/diataxis check [--strict] [--mode <tutorial|how-to|reference|explanation>] [--wiki-root <path>]
```

### `/diataxis repair`

> [!NOTE]
> **Status**: stub. Full body lands in plan #13 **part 3** (`check-repair`). See the [check-repair part](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/diataxis-author/parts/check-repair.md) for the locked design.

Interactive fix-application for drift detected by `/diataxis check`. Per finding: present suggested fix (cross-ref rewrite / mode reclassification / template realignment / split-mode-mixed-into-N-pages) + operator approves / edits / rejects. Pattern matches `/memory watchlist review`'s interactive flow. Mode-mixed splits dispatch `documenter` sub-agent (the mechanical-write worker). All file modifications preview-first; never silent.

**Planned invocation shape** (subject to refinement in plan #13 part 3):

```
/diataxis repair [--mode <m>] [--limit N] [--stub]
```

### `/diataxis migrate`

> [!NOTE]
> **Status**: stub. Full body lands in plan #13 **part 4** (`migrate-subsume`). See the [migrate-subsume part](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/diataxis-author/parts/migrate-subsume.md) for the locked design.

One-shot migration of legacy audience-based wikis (`development/` + `operational/` + `design/` + `architecture/`) to the four-mode Diátaxis layout. Subsumes the harness's predecessor `migrate-to-diataxis` skill — same contract: preview-first, deterministic classification by heading shape per ADR 0004's machine-enforceable rules, `git mv` for blame preservation, mode-mixed pages flagged for human split (delegates to `/diataxis repair` for the actual split work), link rewrites across all `wiki/**/*.md`. Single-commit safety net (entire migration is one git commit; revert is one `git revert <SHA>`).

**Planned invocation shape** (subject to refinement in plan #13 part 4):

```
/diataxis migrate [--preview | --execute] [--yes]
```

### `/diataxis classify <file>`

> [!NOTE]
> **Status**: stub. Full body lands in plan #13 **part 2** (`author-classify`). See the [author-classify part](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/diataxis-author/parts/author-classify.md) for the locked design.

Single-page mode classification — operator-debug surface + the `diataxis-evaluator` sub-agent's primary invocation surface for ambiguous cases. Takes a file path; returns mode classification + confidence + rationale + (if ambiguous) suggested splits. Pure-Python heuristic for clear cases (heading shape + frontmatter signals from ADR 0004's machine-enforceable rules); dispatches `diataxis-evaluator` sub-agent for ambiguous mode-mixed pages where heuristic scoring is tight.

**Planned invocation shape** (subject to refinement in plan #13 part 2):

```
/diataxis classify <file> [--no-subagent] [--limit N]
```

## Tool allowlist

**`Read, Write, Edit, Glob, Grep, Bash`** — `Bash` is required for the `check-wiki.py` subprocess invocation in `/diataxis check` (part 3) + `git mv` invocations in `/diataxis migrate` (part 4). Python scripts under `skills/diataxis-author/scripts/` (added in parts 2-5) handle the deterministic heavy lifting (mode classification heuristics, link rewriting, template loading). Sub-agent dispatch happens via the agent's standard task delegation; the skill body itself doesn't shell out to other agents.

Python-side scripts can use whatever they need (network for ADR 0004 cross-reference via WebFetch if any; subprocess for git + check-wiki.py; filesystem for everything else) — the allowlist restriction is on the SKILL.md body itself, not the dispatched scripts.

## Host scope

`supported_hosts: [claude-code, antigravity]` — `gemini-cli` excluded per [ROADMAP item #15](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md) (Gemini-CLI host removal, shipped in toolkit v0.9.0 / ADR 0006). Same scope as the sibling `memory` skill.

## Cross-references

- **Parent design**: [diataxis-author](https://github.com/alexherrero/agent-toolkit/blob/main/wiki/explanation/designs/diataxis-author.md) — the canonical "Why we built this" entry point per the locked design call from plan #6.
- **Diátaxis spec source**: [agentic-harness ADR 0004 — Diátaxis Documentation Spec](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0004-diataxis-documentation-spec.md) — the canonical convention this skill enforces.
- **Predecessor (being subsumed)**: [agentic-harness `migrate-to-diataxis` skill](https://github.com/alexherrero/agentic-harness/blob/main/harness/skills/migrate-to-diataxis.md) — one-shot migration skill that `/diataxis migrate` ports + extends. Ships deprecation notice in plan #13 part 4.
- **Sibling sub-agent**: [`diataxis-evaluator`](https://github.com/alexherrero/agent-toolkit/blob/main/agents/diataxis-evaluator.md) — read-only sub-agent for ambiguous mode classification. Dispatched from `/diataxis classify` (operational from part 2) + `/diataxis repair` mode-mixed splits (operational from part 3).
- **Sibling skill (orchestration pattern)**: [`memory`](https://github.com/alexherrero/agent-toolkit/blob/main/skills/memory/SKILL.md) — `/memory adapt-skills` + `adapt-evaluator` is the orchestration-skill + worker-sub-agent pattern this skill mirrors.
- **External worker**: [`documenter` sub-agent (harness-side)](https://github.com/alexherrero/agentic-harness/blob/main/harness/agents/documenter.md) — Diátaxis-aware mechanical-write worker. Repurposed: dispatched from `/diataxis repair` mode-mixed splits (part 3) + existing harness `/release` direct dispatch (part 5 transitions via skill-presence check).
- **Validator complement**: [`scripts/check-wiki.py`](https://github.com/alexherrero/agentic-harness/blob/main/scripts/check-wiki.py) — strict-mode validator the skill wraps for `/diataxis check`.

## Status

This skill is **stub-shipped** as of v0.11.0-pre (plan #13 part 1). All 5 sub-commands have documented shape + planned invocation but no functional implementation yet. The 5 sub-commands fill in across plan #13 parts 2-5:

- **Part 2** (`author-classify`): `/diataxis author` + `/diataxis classify` + `diataxis-evaluator` operational flow + 4 templates.
- **Part 3** (`check-repair`): `/diataxis check` + `/diataxis repair` + `documenter` dispatch as worker.
- **Part 4** (`migrate-subsume`): `/diataxis migrate` + harness predecessor deprecation notice.
- **Part 5** (`agentmemory-docs-release`): AgentMemory read + write integration + new how-to + new ADR 0008 + paired release v0.11.0 + v2.4.3 + plan close-out.

Re-audit triggers (per design doc Tech Debt + Risks): mode-classification false-positive rate (parent §1); convention drift across operator's three Diátaxis wikis (parent §2); `documenter` dispatch transition correctness (parent §3); AgentMemory write-back fatigue (parent §4).
