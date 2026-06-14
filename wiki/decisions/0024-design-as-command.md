# ADR 0024 — Package `/design` as a command (tested Python helper + thin prompt), not a skill

> [!NOTE]
> Status: accepted
> Date: 2026-06-13 (accepted 2026-06-14 at the `/design` v3.10.0 release)

> [!IMPORTANT]
> **Accepted** (V5-10 sibling #5, `design-command`, shipped `developer-workflows` 0.10.0). The command is built and released; the decision below held through the build. Implementation: `src/developer-workflows/commands/design.md` (the three-verb prompt), `src/developer-workflows/scripts/design_doc.py` (the `Status:`/frontmatter + detailed-design gates), and `src/developer-workflows/scripts/design_sequence.py` (the Kahn topological sort the `sequence` verb composes onto `stage_plan.py`).

## Context

The phase loop is now an **all-commands** surface: `/plan`, `/work`, `/review`, `/release`, `/bugfix`, `/spawn-worker`, `/integrate-worker` all ship as commands in the `developer-workflows` plugin. The one authoring step still missing from the front of that loop is `/design` — the upstream step that takes an ambiguous, multi-stakeholder, or cross-cutting problem from a brief to a settled design before `/plan` ever runs.

A canonical `/design` already exists in agentm as a **SKILL** with a no-Bash tool allowlist (`[Read, Write, Edit, Glob, Grep]`), recorded in [ADR 0004](0004-design-skill.md). This plan ports that authoring step into crickets, but the packaging choices that made sense for the agentm skill do not all carry over: the rest of the crickets phase loop is commands, the named-plan staging machinery (`stage_plan.py`) is a tested Python helper, and the `sequence` step needs to wire onto that helper rather than re-deriving harness paths in prompt prose.

**Open questions this decision resolves:**

- Skill or command? The agentm original is a skill; the crickets phase loop is all commands. Which packaging does the crickets port take?
- How does `/design sequence` emit plans without colliding with the singleton `PLAN.md` or re-implementing harness-path resolution?
- No-Bash prompt-only (agentm idiom) or tested Python helper + thin prompt (crickets idiom)?
- What is in scope for this plan, and what is explicitly deferred?
- Does [ADR 0004](0004-design-skill.md) get a `superseded-by-0024` note, or is "divergent port" the right relationship? **Resolved: divergent port — 0004 stays `accepted`, no supersession.** 0004 is the historical origin of the conventions 0024 *inherits* (the 10-section template §2, the Status lifecycle §4, the visibility routing §5); a supersession flip would wrongly void them. And the skill 0004 records already left crickets for agentm in v2.0.0, so there is no live crickets decision for 0024 to supersede — only a port to record. See *Related* below.

## Decision

_Skeleton — full rationale filled at `/release` from the shipped implementation._

### 1. Package `/design` as a command, not a skill

`/design` ships at `src/developer-workflows/commands/design.md` with three sub-verbs (`author`, `translate`, `sequence`), consistent with the rest of the all-commands phase loop.

**Why not a skill (the agentm idiom)?** _Filled at `/release`. Framing: the crickets phase loop is uniformly commands; shipping `/design` as a skill would split the authoring step off the surface every other phase shares, and operators would have to remember a different invocation shape for the one upstream step._

### 2. `/design sequence` wires onto `stage_plan.py`; never touches the singleton

`/design sequence` emits one named plan per part via the already-shipped `stage_plan.py` writer (sibling #1) — first part **activated** (`PLAN-<doc-slug>-<part-slug>.md`), the rest **staged** into `queued-plans/`. It never writes the singleton `PLAN.md`.

**Why not re-derive harness paths in the command prompt?** _Filled at `/release`. Framing: `stage_plan.py` already owns harness-path resolution (composed onto `resolve_plan.resolve`) and the staged-vs-active tier guards; re-implementing that in prompt prose would fork the path logic and risk singleton collisions the helper already prevents._

### 3. Crickets idiom — tested Python helper + thin command prompt (vs agentm's no-Bash skill)

The deterministic work (path resolution, topo-sort, part-file IO, plan emission) lives in tested Python; the command prompt stays thin and orchestrates.

**Why not no-Bash prompt-only (the agentm idiom)?** _Filled at `/release`. Framing: crickets phase commands lean on tested Python helpers (`resolve_plan.py`, `stage_plan.py`, `queue_status.py`, `integrate_worker.py`) so the deterministic core is gate-locked by hermetic tests rather than re-derived in prose on every run. ADR 0004's no-Bash allowlist was an agentm-skill constraint, not a crickets one._

### 4. External-review handoff is deferred

The Antigravity / Gemini transfer-context external-review flow (ADR 0004 Amendment 2026-05-16) is **not** ported in this plan. The inline review pass (`author` approve / revise / skip) is the only review mode.

**Why defer?** _Filled at `/release`. Framing: the inline pass is the load-bearing review surface; the external handoff adds cross-host artifacts and lifecycle that can land in a later plan once the command core is proven._

> [!NOTE]
> Also deferred (not a decision here, just out of scope): the `final → launched` auto-transition + queued-plan auto-promotion on `/release`.

## Consequences

_Skeleton — filled at `/release`._

**Positive**

- The phase loop's upstream authoring step joins the same all-commands surface as every other phase — one invocation idiom.
- `/design sequence` reuses the tested `stage_plan.py` writer, so it inherits the named-plan staging guards (no singleton clobber, staged = inert) for free.
- The deterministic core is gate-locked by tests, not re-derived in prompt prose.

**Negative / accepted debt**

- The crickets `/design` packaging now diverges from agentm's skill packaging — two ports of the same authoring step with different shapes. _Re-audit framing filled at `/release`._
- External-review handoff and `final → launched` auto-promotion are deferred — operators who want the Antigravity comment flow stay on the agentm skill until a later plan ports it.

**Load-bearing assumptions + re-audit triggers**

- _The named-plan-per-part model (`PLAN-<doc-slug>-<part-slug>.md`) composes cleanly onto `stage_plan.py` without singleton collisions._ **Re-audit if** sequencing ever writes or mutates the singleton `PLAN.md`, or if the per-part naming collides with a hand-authored named plan.
- _Filled at `/release`._

## Related

- [ADR 0004 — design skill](0004-design-skill.md) — the agentm-side `/design` skill this command ports; the no-Bash allowlist (§8), the 10-section template (§2), the Status lifecycle (§4), and the visibility routing (§5) originate there. The skill moved to agentm in v2.0.0; this ADR records the crickets *command* port's packaging divergence. **This is a divergent port, not a supersession:** 0004 stays `accepted` and is **not** flagged `superseded-by-0024`, because 0024 *inherits* its template / Status-lifecycle / visibility conventions rather than replacing them — and there is no live crickets decision left to supersede once the skill itself moved to agentm. The two ADRs coexist: 0004 owns the agentm skill, 0024 owns the crickets command port.
- [Author a design](Author-A-Design) — the how-to recipe for the three sub-verbs.
- [Named plans](Named-Plans) — the reference for the phase-loop command surface and the `stage_plan.py` writer `/design sequence` rides on.
- The agentm V5-10 design — the source of the sibling build order; sibling #1 (`multi-plan-behavioral`) shipped `stage_plan.py`, which this command composes onto.
