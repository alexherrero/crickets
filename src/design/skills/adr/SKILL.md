---
name: adr
description: ADR authoring via the adr-shape convention — when to write, the 5-section shape with re-audit triggers, and the "why not the alternative" requirement per decision call.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

You are applying the `adr` skill. An Architecture Decision Record (ADR) captures a load-bearing
design choice so a future reader — including the author six months later — can understand what was
decided, why, and under what assumptions.

> **Authoritative source:** the `adr-shape` always-load entry in `~/.claude/CLAUDE.md` (section
> "CHANGELOG + ADR shapes") is the canonical reference. This skill packages it for per-project
> installation and adds the re-audit-triggers discipline. If CLAUDE.md is updated, re-audit this
> skill against it — see **Re-audit trigger for this skill** at the bottom.

> [!IMPORTANT]
> **In crickets and agentm the ADR model is retired.** A decision in those repos amends the relevant living design's `## Amendment log` under `wiki/designs/`, not a standalone ADR file — see [How to record a design decision](Record-An-Architectural-Decision). The ADR shape below still governs other repos that use the ADR model.

## When to write an ADR

Write an ADR for any of the following:

- A **technology or library choice** where the rationale would otherwise live only in one person's head (e.g. "why not the obvious library?").
- A **structural or architectural pattern** that other contributors need to know to work in the area (e.g. "why does the storage layer use CAS instead of locks?").
- A **cross-cutting constraint** that governs many future decisions (e.g. "no mutable shared state across agent calls").
- Any **public API or behavior change** that can't be understood from the code alone.
- Any decision a future reader would reasonably ask *"why did they do it this way?"* — if the answer is non-trivial, it belongs in an ADR.

Do not write an ADR for pure implementation details (variable names, internal helper refactors, obvious dependency choices with no real alternatives). ADRs are for load-bearing calls, not every call.

## The 5-section shape

This shape is the canonical format. Use it verbatim — no section renames, no omissions.

### Opening block

```
> [!NOTE]
> **Status:** accepted | superseded | rejected
> **Date:** YYYY-MM-DD
```

Status values:
- `accepted` — current, governing decision.
- `superseded` — replaced by a later ADR (link the superseding ADR in Related).
- `rejected` — considered and rejected; kept for future reference so the rationale isn't rediscovered.

### 1. Context

What situation prompted this decision? Include:
- The open question the ADR resolves.
- Relevant constraints (technical, organizational, timeline).
- Any prior art or earlier ADRs this builds on.

The Context section is what makes the Decision legible. A thin Context forces readers to reconstruct the problem from scratch.

### 2. Decision

State the decision in one sentence, then justify it. **Required per call: "why not the alternative."**

For every load-bearing choice in this section, include an explicit rejection note:

```
We chose X over Y because <reason>. We did not choose Y because <specific technical or
organizational reason — not "Y was worse", but the concrete constraint that ruled it out>.
```

This is the most commonly skipped requirement and the most valuable part of the ADR. "We picked X" tells a reader what you chose; "why not Y" tells them whether the decision still makes sense under changed conditions.

### 3. Consequences

Three sub-lists, all required (use "None." if genuinely empty):

**Positive** — what this decision enables or improves.

**Negative** — what this decision costs or constrains; what you gave up; what makes future work harder.

**Load-bearing assumptions with re-audit triggers** — the facts that must remain true for this decision to stay correct. For each assumption, name the condition under which it becomes wrong:

```
- Assumption: Claude Code hooks fire on every tool call in the current session.
  Re-audit if: Claude Code ships a hook v2 shape that changes the execution model.
```

The re-audit trigger is what separates a living record from a tombstone. Without it, an ADR whose premise eroded silently stays in force until someone breaks something.

### 4. Related

Cross-references to:
- Other ADRs this builds on or supersedes.
- Design docs, plans, or external specs this implements.
- Tracking issues or PRs where the decision was discussed.

### 5. Document History

A table tracking the ADR's lifecycle:

```
| Date | Change | Status |
|---|---|---|
| YYYY-MM-DD | Initial draft. | accepted |
| YYYY-MM-DD | Superseded by ADR 0042 — <one-sentence reason>. | superseded |
```

## Re-audit triggers

Every assumption in an ADR's Consequences section must have a re-audit trigger. Common triggers:

- A third-party API changes its contract.
- A framework ships a major version with breaking changes.
- A team or organizational constraint that drove the decision is lifted.
- A new standard emerges that wasn't available at decision time.

When a trigger fires, open a new ADR (or update the original's Status to `superseded`) — never silently edit the accepted ADR to paper over the changed premise.

## Anti-patterns

| Anti-pattern | Why it fails |
|---|---|
| ADR written after the fact as a tombstone | Missing the decision context: you can record what was decided but not *why*, because the reasoning is gone. |
| "Why not the alternative" omitted | The ADR captures the outcome but not the reasoning. A future reader can't tell if the rejected option is still off the table or just overlooked. |
| No re-audit triggers | The ADR becomes a dead record when its premise erodes. Nobody knows when to revisit it. |
| Status never updated | An ADR that says `accepted` but governs a system that was replaced is worse than no ADR — it actively misleads. |
| Consequences section skipped | Missing the negative bullets means the next person inheriting this decision doesn't know the trade-offs they're working within. |

## Re-audit trigger for this skill

This skill packages the `adr-shape` convention from `~/.claude/CLAUDE.md`. If the canonical
`adr-shape` always-load entry changes its section names, required fields, or re-audit-trigger
conventions, re-audit this skill against the updated CLAUDE.md and issue a patch bump.

## Cross-reference

For **design docs** (10-section template, full author/translate/sequence workflow), see the
`/design` command — install `developer-workflows` or the `design-docs` plugin.
