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

Live authoring guidance — operator invokes when starting a new wiki page. Skill resolves the mode (explicit `--mode` flag, or inferred from `--intent <sentence>` via `classify.py`, or operator prompt), loads the right Diátaxis template from `templates/<mode>.md`, applies the operator's filename style, computes target path `<wiki-root>/<mode-dir>/<filename>.md`, refuses if target exists (operator picks a different slug), and writes the skeleton. Operator edits in their editor; skill doesn't write further content after the skeleton.

#### Invocation shape

```
/diataxis author <slug> [--mode <tutorial|how-to|reference|explanation>]
                        [--intent "<one sentence>"]
                        [--filename-style <CamelCase-With-Dashes|kebab-case|snake_case>]
                        [--wiki-root <path>]
                        [--overwrite]
```

| Arg | Required | Default | Meaning |
|---|---|---|---|
| `<slug>` | yes | — | Page slug (e.g. "Install foo into a project"). Words extracted via alphanumeric splitting; filename style applied. |
| `--mode <m>` | yes¹ | — | Diátaxis mode. ¹Required unless `--intent` provided (then `classify.py` infers); halts with operator-prompt if neither given. |
| `--intent "<text>"` | no | — | One-sentence intent statement. Passed to `classify.py` as classification input; mode inferred if heuristic confidence ≥0.7. Sub-agent dispatch triggered if below threshold. |
| `--filename-style <s>` | no | `CamelCase-With-Dashes` | Filename style. Three options: `CamelCase-With-Dashes` (default) / `kebab-case` / `snake_case`. AgentMemory always-load entry override planned for part 5. |
| `--wiki-root <path>` | no | `./wiki` | Wiki root directory. Auto-detected as `<cwd>/wiki`; override for cross-repo invocations. |
| `--overwrite` | no | off | Allow overwriting an existing target. Default: refuse + ask operator to pick a different slug. |

#### Step-by-step flow

**Step 1 — Resolve mode.** If `--mode` set, use it directly. If `--intent` set, call `classify.py` on the intent text + check `needs_subagent` flag; halt + prompt operator for explicit `--mode` if classifier confidence is below threshold. Otherwise halt with "ERROR: --mode or --intent required".

**Step 2 — Validate inputs.** Mode in `{tutorial, how-to, reference, explanation}`; filename style in valid set; wiki root exists + is a directory.

**Step 3 — Compute target path.** Apply filename style to slug → base name. Mode-to-directory mapping: `tutorial → tutorials/` (plural per Diátaxis convention; only this mode is pluralized), `how-to → how-to/`, `reference → reference/`, `explanation → explanation/`. Target = `<wiki-root>/<mode-dir>/<base>.md`.

**Step 4 — Collision check.** If target exists + `--overwrite` not set, halt with `"target already exists: <path>; pick a different slug or pass --overwrite"`.

**Step 5 — Load template.** Read `templates/<mode>.md` (ships in this part). Halt if missing (shouldn't happen post-install; indicates broken install).

**Step 6 — Create parent dirs + write.** `mkdir -p` for the mode-dir; write template content via `write_bytes` (LF-only line endings — Windows portability per `save.py` + `adapt_skills.py` convention).

**Step 7 — Return confirmation.** JSON: `{action: "authored", target: <path>, mode: <mode>, template: <path>, filename_style: <style>, filename: <base.md>}`. Operator opens the target file in their editor + fills in placeholders.

#### Examples

```bash
# Explicit mode
python3 ~/Antigravity/agent-toolkit/skills/diataxis-author/scripts/author.py \
  "Install agent-toolkit into a project" --mode how-to
# → wiki/how-to/Install-Agent-Toolkit-Into-A-Project.md

# Infer mode from intent
python3 ~/Antigravity/agent-toolkit/skills/diataxis-author/scripts/author.py \
  "CLI reference for the installer" --intent "lookup table for all install.sh flags"
# → wiki/reference/Cli-Reference-For-The-Installer.md  (inferred: reference)

# Kebab-case filename style
python3 ~/Antigravity/agent-toolkit/skills/diataxis-author/scripts/author.py \
  "Tutorial 3 — Advanced things" --mode tutorial --filename-style kebab-case
# → wiki/tutorials/tutorial-3-advanced-things.md
```

#### Failure modes (graceful)

- **Missing wiki root** → exit 1 with `"wiki root not found: <path>; pass --wiki-root or cd into a project with a wiki/ dir"`.
- **Target collision** (page exists) → exit 1 with operator next-step.
- **Mode + intent both missing** → exit 1 with `"--mode or --intent required"`.
- **Intent classification ambiguous** (confidence < threshold) → exit 1 with classifier output + prompt to disambiguate via explicit `--mode`.
- **Template missing** → exit 1 with broken-install indication.
- **Invalid mode** → exit 1 with valid options listed.

#### Anti-patterns

- **Don't pass `--overwrite` casually.** The collision refusal is intentional — re-using a slug across modes (e.g. how-to + explanation with the same name) is usually a sign you meant to split a mode-mixed page. Use `/diataxis classify` to verify.
- **Don't write skill body content beyond the skeleton.** The skill emits the template + lets the operator fill in. Auto-writing body content would defeat the "live authoring guidance" promise.
- **Don't bypass `--filename-style`.** The default `CamelCase-With-Dashes` matches the operator's convention from the canonical wikis (agentic-harness + agent-toolkit + dev-setup). AgentMemory override (planned part 5) lets you tune per-repo.

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

Single-page mode classification — operator-debug surface + the `diataxis-evaluator` sub-agent's primary invocation surface for ambiguous cases. Takes a file path; returns mode + confidence + per-mode scores + rationale + `needs_subagent` flag. Tier-1 (deterministic Python heuristic in `classify.py`) handles clear cases via regex + heading-shape rules from ADR 0004. Tier-2 (`diataxis-evaluator` sub-agent — operational from this part) handles ambiguous mode-mixed pages where heuristic scoring is tight (default confidence threshold 0.7).

#### Invocation shape

```
/diataxis classify <file> [--threshold N] [--no-subagent] [--stub]
```

| Arg | Required | Default | Meaning |
|---|---|---|---|
| `<file>` | yes | — | Path to the wiki page to classify. |
| `--threshold N` | no | `0.7` | Confidence threshold below which Tier-1 emits `needs_subagent: true`. |
| `--no-subagent` | no | off | Never set `needs_subagent: true`; return Tier-1 result even if ambiguous. Operator-debug + scripting. |
| `--stub` | no | off | When sub-agent dispatch would fire, emit `needs_subagent: true` marker without actually invoking sub-agent. Used by CI smoke tests to avoid live LLM calls. |

#### Step-by-step flow

**Step 1 — Read file.** Halt with `"ERROR: page not found"` if missing.

**Step 2 — Strip frontmatter.** If file starts with `---`, parse YAML frontmatter (best-effort tolerant); else treat whole file as body.

**Step 3 — Score 4 modes** via the heuristic engine in `classify.py`:

- **Tutorial**: `## Step N — ...` heading + `## What you learned` + `## Next` → 0.95; partial signals 0.5-0.75.
- **How-to**: `## Steps` section → 0.85; ≥3 numbered imperative steps in first 40 lines → 0.65; penalty 50% if `## Rationale|Why|Background|Context` sections detected (mode-mixed signal).
- **Reference**: `## ⚡ Quick Reference` heading near top → 0.8; ≥60% table lines → 0.9.
- **Explanation**: default mode; `1.0 - max(other 3)`; bumped to 0.85 if ADR-shape (`> [!NOTE]` block with `Status:` line) detected.

**Step 4 — Pick winning mode** (highest score). Mode-mixed flag = true if ≥1 other mode within 0.2 of winner AND above 0.5.

**Step 5 — Decide on sub-agent dispatch.** `needs_subagent: true` when (a) winning score < `--threshold`, OR (b) `mode_mixed: true`. Default threshold 0.7.

**Step 6 — Return classification.** JSON: `{mode, confidence, rationale, mode_mixed, needs_subagent, scores: {tutorial, how-to, reference, explanation}}` + (when caller dispatches) `suggested_split: [{mode, body_section_ranges}]`.

#### Sub-agent dispatch (Tier 2)

When `needs_subagent: true`, the caller (typically `/diataxis author --intent` or future `/diataxis check` / `/diataxis repair` from part 3) dispatches the `diataxis-evaluator` sub-agent with the caller-supplies-inline-rubric pattern documented in [`agents/diataxis-evaluator.md`](../../agents/diataxis-evaluator.md). Sub-agent has **zero filesystem write scope** (allowlist Read/Glob/Grep/WebFetch only) — returns classification decision; caller acts on it.

The CLI itself doesn't dispatch sub-agents directly — it returns the marker + lets the calling skill body handle dispatch. Same pattern as `adapt_skills.py` from plan #7b task 4.

#### Examples

```bash
# Clear tutorial page → mode: tutorial, confidence: 0.95
python3 ~/Antigravity/agent-toolkit/skills/diataxis-author/scripts/classify.py \
  wiki/tutorials/01-Getting-Started.md

# Ambiguous mode-mixed page → needs_subagent: true
python3 ~/Antigravity/agent-toolkit/skills/diataxis-author/scripts/classify.py \
  wiki/some/ambiguous.md
# → {mode: "explanation", confidence: 0.575, mode_mixed: true, needs_subagent: true, ...}

# Force Tier-1-only via --no-subagent (operator-debug)
python3 ~/Antigravity/agent-toolkit/skills/diataxis-author/scripts/classify.py \
  wiki/some/ambiguous.md --no-subagent
# → {needs_subagent: false, ...} (Tier-1 verdict regardless of confidence)

# CI smoke-safe: --stub avoids actual sub-agent dispatch
python3 ~/Antigravity/agent-toolkit/skills/diataxis-author/scripts/classify.py \
  wiki/some/ambiguous.md --stub
# → {needs_subagent: true, dispatched_subagent: false, ...}
```

#### Failure modes (graceful)

- **File not found** → exit 1 with the actual path checked.
- **File empty** → emit `{mode: "explanation", confidence: 0.3, rationale: "empty page; default to explanation"}` (stub-style page; reasonable default).
- **Frontmatter malformed** → ignore frontmatter; classify body only.
- **All 4 modes score 0** → emit `explanation` with confidence based on `1.0 - max(others) = 1.0` (perfect default — no positive signal for any other mode).

#### Anti-patterns

- **Don't use `--no-subagent` in automation.** The `needs_subagent` flag is the signal to escalate; bypassing it loses information. `--no-subagent` is operator-debug only.
- **Don't tune `--threshold` per-invocation.** The default 0.7 is tuned to v1 fixtures; operator-level threshold should be set globally via AgentMemory always-load entry (part 5 wires this).
- **Don't dispatch the sub-agent without passing classify.py's Tier-1 output as rubric context.** The sub-agent's caller-supplies-inline-rubric contract expects the heuristic verdict + per-mode scores so it can validate or override. Bare dispatch wastes the deterministic signal.

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
