# ADR 0008: diataxis-author skill

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-22
> **Related:** [Parent design — diataxis-author](../designs/diataxis-author.md) · [agentic-harness ADR 0004 — Diátaxis Documentation Spec](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0004-diataxis-documentation-spec.md) · [ADR 0001 — agent-toolkit purpose](0001-agent-toolkit-purpose) · [ADR 0007 — MemoryVault Discovery + Mining](0007-memoryvault-discovery) (the sub-agent dispatch pattern this ADR reuses) · [ROADMAP item #13](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md)

## Context

ROADMAP item #13 shipped as the natural follow-on to the MemoryVault parent design (#7a + #7b closed 2026-05-20 + 2026-05-22). The operator maintains three Diátaxis-shaped wikis (`agentic-harness`, `agent-toolkit`, `dev-setup`) plus the just-shipped MemoryVault parent design documents — Diátaxis discipline is real, ongoing, and previously supported only by:

- **`scripts/check-wiki.py`** (harness-side) — strict validator; catches violations at commit time + in CI.
- **`documenter` sub-agent** (harness-side) — fires at `/release` boundaries; periodic sweep, not live authoring guidance.
- **`migrate-to-diataxis` predecessor skill** (harness-side) — one-shot legacy migration; never fires again after a project is migrated.

The gap: **proactive authoring guidance** (template selection at write time, mode classification on ambiguous pages, filename style enforcement) + **ongoing drift detection + repair** (mode-mixed pages that emerge from edits, stale cross-references, template-shape drift) was unsupported. Operators wrote pages by hand + relied on `check-wiki.py --strict` to catch problems after the fact + manually triggered `documenter` at `/release` for sweep-style updates.

The locked execution-order ROADMAP note explicitly placed this as #13: "natural fit after MemoryVault (wiki-style preferences can be stored there); designed via design skill". This ADR captures the locked design calls + load-bearing assumptions for the resulting `diataxis-author` skill.

## Decision

**Ship `diataxis-author` as a single agent-toolkit skill with five sub-commands**, mirroring `/memory`'s shape: one `SKILL.md` with multi-sub-command bodies, deterministic Python pipelines under `skills/diataxis-author/scripts/`, one read-only sub-agent (`diataxis-evaluator`) for ambiguous mode-classification. The skill **subsumes** the harness's `migrate-to-diataxis` predecessor (ships deprecation notice in v1; predecessor file removed in follow-up harness PATCH after dogfood). The harness-side `documenter` sub-agent is **repurposed as the skill's mechanical-write worker** (same orchestration-vs-worker split as `/memory adapt-skills` + `adapt-evaluator` from ADR 0007 / plan #7b). **AgentMemory integration is read + write** (per-repo overrides at `<repo>/wiki/.diataxis-conventions.md`; global vault entries at `<vault>/personal-private/_always-load/diataxis-*.md`).

Four locked design calls Q1-Q4 (operator answers to AskUserQuestion at design-author time):

### Q1 — Scope: author + maintain + migrate (subsume predecessor)

One unified skill covers the full lifecycle: live authoring (`/diataxis author`) + drift detection (`/diataxis check`) + repair (`/diataxis repair`) + one-shot migration (`/diataxis migrate`) + classification debug (`/diataxis classify`). Subsumes `migrate-to-diataxis` predecessor.

**Why not author-only**: operators write pages once + maintain them continuously; supporting only the write phase leaves the maintenance gap unaddressed (`check-wiki.py` is the gate, not the workflow).

**Why not keep predecessor coexistent**: mental-model burden of "which Diátaxis skill do I use?" outweighs the lifecycle-split rationale. Operators answered: "one Diátaxis skill, not two".

**Why not separate `diataxis-doctor` + `diataxis-migrate` + `diataxis-author`**: matches the rejection above; multi-skill split adds install surface without justification.

### Q2 — AgentMemory: read + write conventions (per-repo overrides via .diataxis-conventions.md)

Skill reads operator conventions at every invocation. **Write-back** is operator-confirmed via `permeable_boundary` helper from plan #7a part 4 — when operator makes a non-trivial judgment call (e.g. "use kebab-case in this repo, not the global CamelCase-With-Dashes default"), skill offers to capture as new `_always-load/diataxis-*.md` entry. Per-repo overrides at `<repo>/wiki/.diataxis-conventions.md` take precedence over vault entries.

**Why not read-only**: skill becomes consistent across the operator's three Diátaxis wikis only when learned conventions write back to AgentMemory. Read-only forces operator to manually `/memory save --always-load` every judgment call — operator-tax violates the recall-loop goal.

**Why not skip AgentMemory entirely**: locked execution-order note ("wiki-style preferences can be stored there") + the MemoryVault parent design's own promise to be the durable convention store both required this integration. Skipping it duplicates the convention-store function elsewhere.

### Q3 — `documenter` relationship: skill calls documenter as worker

`documenter` sub-agent (harness-side, mode-aware writer per ADR 0004 §4) becomes the mechanical-write worker for `/diataxis repair`'s mode-mixed splits. Same dispatch pattern as `/memory adapt-skills` → `adapt-evaluator` from ADR 0007: orchestration skill (operator-facing surface) dispatches sub-agent (mechanical work). `documenter` still fires from harness `/release` (existing direct dispatch); after v1 ships, harness `/release` phase spec gets graceful-skip amendment that prefers `/diataxis check` invocation when `diataxis-author` is installed.

**Why not subsume documenter entirely** (skill owns all wiki writes): coordination cost — harness's `/release` flow already dispatches documenter; tearing that out and replacing with the new skill is invasive + risky. Keep documenter; let the new skill dispatch it for the new use case.

**Why not let them coexist independently** (both writing to wiki): convention drift between the two writers is a real risk. Clear ownership: skill orchestrates; documenter does mechanical writes only when dispatched.

### Q4 — Sub-command shape: single skill with 5 sub-commands

Matches `/memory`'s established pattern (save / evolve / reflect / promote / search / index-skills / discover-skills / adapt-skills / watchlist). One install surface, one mental model.

**Why not multiple discrete skills**: install surface bloat + cognitive load. Operator can still invoke individual sub-commands directly via their canonical Python script paths.

**Why not hybrid (multi-sub-command + dedicated sub-agent)**: chose single skill + single sub-agent (`diataxis-evaluator`) — matches `/memory adapt-skills` + `adapt-evaluator` precedent exactly.

## Consequences

### Positive

- **Five sub-commands ship with consistent shape** — same CLI flag conventions (`--wiki-root` / `--dry-run` / `--stub` / `--limit` / etc.), same atomic state-file pattern (no state in v1 — pure-Python invocations), same graceful-skip contracts (check-wiki.py absent / AgentMemory absent / per-repo overrides absent → defaults apply).
- **Mode classification is deterministic + testable** — heuristic Tier 1 (`classify.py`) catches the clear majority of cases without LLM. Sub-agent Tier 2 (`diataxis-evaluator`) handles the ambiguous tail with semantic judgment but bounded write scope.
- **Adapt-don't-import-style architectural enforcement** for the classifier — sub-agent has **zero filesystem write scope** (stricter than `adapt-evaluator` which has scoped-write-to-`_skill-watchlist/`). All classification decisions return to caller for preview-first action.
- **Subsume predecessor cleanly** — `/diataxis migrate` ports predecessor's contract (preview-first, deterministic classification, `git mv` for blame, mode-mixed-flag) + adds net-new (single-commit safety net, `.diataxis-conventions.md` auto-seed, delegation to `/diataxis repair` for splits).
- **Operator-editable conventions everywhere** — both vault-side (global) and per-repo override (specific). Operators tune from real use without code changes; ship-instrumented + tune-from-real-use pattern proves out (precedent from `recall.py` rank-merge weights post-#7a part 5 task 6 + `adapt_skills.py` 6-rule rubric tuning post-#7b task 4).
- **First skill to integrate with AgentMemory's write-side** beyond the reflection sidecar — proves the operator-confirmed write-back pattern generalizes beyond idea-capture (existing `/memory reflect` use case) to convention-capture.

### Negative

- **Five sub-commands × five parts × cross-platform smoke tests** = ~150 sub-tests landed across the plan; CI runtime grew accordingly (per-OS smoke install now ~40s on Linux, ~45s on Mac, ~2m on Windows). Acceptable for solo dev pace; will need optimization if multi-developer use grows.
- **Cross-repo coordination overhead** — Part 4 ships toolkit + harness commits in sequence. Each cross-repo plan has a coordination tax; managed via clear sequencing in the plan part files + `[[coordinated-release-order]]` convention.
- **Heuristic-only Tier 1 will have false positives + negatives** that the sub-agent Tier 2 needs to clean up. Ship-instrumented + tune-from-real-use is the only honest path; first watchlist review iteration after live use will surface what to adjust.
- **`documenter` dispatch transition** in harness `/release` phase spec needs both-paths-tested (with + without `diataxis-author` installed). Smoke tests verify both; possible failure mode if operator partially-installs.

### Load-bearing assumptions (re-audit triggers)

1. **Operator runs Claude Code + Antigravity** (not a different host suite). The skill's tool allowlist + sub-agent dispatch pattern assumes Claude Code's task delegation works. Re-audit triggers: ROADMAP item #17 (Antigravity 2.0 + CLI host support) lands + we verify the new CLI's dispatch surface is equivalent.

2. **Operator maintains ≤5 Diátaxis-shaped wikis** that share a convention vault. Skill assumes per-repo `.diataxis-conventions.md` is the right granularity for per-project overrides. Re-audit triggers: operator-managed wiki count grows to ~10+ AND convention-divergence-per-wiki becomes painful; could split AgentMemory entries into per-project-tagged conventions instead of global with per-repo override.

3. **Diátaxis four-mode taxonomy stays the canonical convention** for operator-managed wikis. Re-audit triggers: industry shift to a different documentation framework OR operator chooses to deprecate Diátaxis for some/all projects. ADR 0004 (canonical Diátaxis spec, harness-side) is the upstream of this assumption.

4. **Mode-classification heuristic + sub-agent split stays valuable** as the wiki content evolves. Could be wrong: operator's content evolves toward pages that are all clearly mode-pure, making the sub-agent surface unused; OR operator's content evolves toward many ambiguous pages, making the heuristic surface unused. Re-audit triggers: 6+ months of real watchlist+repair use without sub-agent dispatches firing (heuristic enough); OR every classify call dispatches sub-agent (heuristic useless).

## Related

- [Parent design — diataxis-author](../designs/diataxis-author.md) — full architectural context including all 8 Detailed Design subsections + Tech Debt + Quality Attributes + Migrations.
- [agentic-harness ADR 0004 — Diátaxis Documentation Spec](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0004-diataxis-documentation-spec.md) — canonical Diátaxis spec this skill enforces (upstream).
- [ADR 0007 — MemoryVault Discovery + Mining](0007-memoryvault-discovery) — precedent for the orchestration-skill + worker-sub-agent + scoped-write-allowlist architectural pattern this skill mirrors.
- [ADR 0001 — agent-toolkit purpose](0001-agent-toolkit-purpose) — upstream for the stdlib-only / no-new-third-party-deps convention all skill scripts follow.
- [Use Diataxis Author how-to](../../how-to/Use-Diataxis-Author.md) — operator-facing how-to with worked scenarios for all 5 sub-commands + AgentMemory integration walkthrough.
- [`diataxis-evaluator` sub-agent](../../../agents/diataxis-evaluator.md) — read-only Tier-2 worker; zero-write-scope architectural enforcement.
- [ROADMAP item #13](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md) — the roadmap entry that triggered this design.
- [Predecessor `migrate-to-diataxis`](https://github.com/alexherrero/agentic-harness/blob/main/harness/skills/migrate-to-diataxis.md) — deprecated 2026-05-22; subsumed by `/diataxis migrate` (Migrations §1 in parent design).
