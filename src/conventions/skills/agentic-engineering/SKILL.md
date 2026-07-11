---
name: agentic-engineering
description: The harness discipline every phase workflow and every persona operates under — phase-gated sessions, state-on-disk-not-conversation, single-threaded implementation with read-only sub-agent fan-out, the PLAN.md shape, wake-on-CI, no parallel implementers, and the single-cycle shape for background primitives. A re-home of standards that previously lived only in agentm's AGENTS.md / harness/principles.md and the operator's global ~/.claude/CLAUDE.md — this domain owns the standard now; those files keep a pointer.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

# agentic-engineering

The base standards a phase workflow or persona consumes directly, before any opinion weighs in. Migrated in (crickets-conventions.md's Migrations spec) from agentm's `AGENTS.md` / `harness/principles.md` and the operator's global `~/.claude/CLAUDE.md` — a re-home, not a rewrite; wording below is preserved from those sources.

## Phase-gated workflow over free-form conversation

A single session should do exactly one of: scaffold, plan, implement, review, release. The boundaries exist because:

- Each phase has a different success criterion. Mixing them makes all of them worse.
- Fresh context at each boundary is cheaper and more reliable than trying to compact across roles.
- When something goes wrong, you can see *which phase* broke.

## State lives on disk, not in context

Context is ephemeral. Files are durable, diffable, resumable. Four on-disk artifacts per project:

- `.harness/PLAN.md` (or a named `PLAN-<name>.md`) — an active goal and its task decomposition with verification criteria. A solo session uses the unnamed `PLAN.md`; concurrent workers each own a distinct named plan.
- `.harness/features.json` — structured feature list with `{ description, steps, passes: bool }` per feature.
- `.harness/progress.md` — append-only log of completed work. Starts every new session by reading this.
- `.harness/init.sh` — pre-written script to boot the dev environment.

**Rule:** every phase ends with an on-disk update. A session that leaves no trace is a session the next agent cannot pick up.

**Assume the full task list; safety-gate each task.** A `/work` session works the plan's tasks autonomously, in sequence — no per-task approval. Before each task, run a safety pre-check and stop to ask only when it fails (hard-to-reverse / ambiguous / scope-drifting / unverifiable) or a clarification is needed; otherwise run to the end of the plan.

## Single-threaded for coherence, fan-out only for read-only breadth

Coding is coherence-critical. Parallel implementers produce mutually-inconsistent decisions no orchestrator can reconcile. Parallel *read-only* sub-agents are fine, and often strictly better than sequential reads — they compress independent regions of the codebase before the main agent synthesizes.

**Rule:** sub-agents gather context; they never write code. One implementer per `/work` session. **No parallel implementers** — this is a non-negotiable, not a preference.

This is about fan-out *inside* a single session. Coordinating *across* several sessions on one multi-session job is a distinct convention — see [`coordinator-dispatch`](../../rules/coordinator-dispatch.md).

## Deterministic verification before LLM judgment

LLM judges are sycophantic under pressure. Typecheckers and tests are neither sycophantic nor expensive.

**Ordering for the review phase:** typecheck → lint → unit tests → integration tests (if they exist) → build → *then* the adversarial LLM reviewer, for things the above can't see (API design, spec adherence, subtle logic, security issues without a lint rule). A review that skips the deterministic steps is not a review.

## Adversarial review with "assume bugs" framing

Neutral-prompted reviewers rubber-stamp. The reviewer must be told the code likely contains bugs, find them:

- Reviewer gets artifact + spec only, not the implementer's reasoning trace — otherwise it anchors on the implementer's justifications.
- Reviewer must produce an executable artifact — a failing test, a specific line-number defect, a reproducible counter-example input. Prose critiques fluff; executable ones don't.
- Log the rejection rate. A reviewer with <10% rejections over a sample is broken (or the implementer is superhuman — far less likely).

## Re-audit the harness on every model bump

Scaffolding essential for one model generation is often just overhead on the next. The harness should get *simpler* over time, not more elaborate.

**Rule:** every time you adopt a new default model, spend 30 minutes running a "what's still load-bearing?" pass. Delete anything that isn't.

## Simplicity first

Find the simplest solution possible, and only increase complexity when needed. When tempted to add a seventh phase, a third sub-agent, a new template — ask: "what specific failure am I trying to prevent, and have I seen it happen?" If the answer is hypothetical, don't add it.

## Non-principles (explicitly rejected)

- **Multi-agent dev-team role-play** (PM / Architect / Dev / QA as separate agents). Coordination cost without matching benefit outside benchmarks.
- **Parallel implementer fan-out.** Merge hell. Use a single implementer and iterate.
- **LLM-as-judge as a final gate.** Always backed by deterministic checks.
- **100+ subagent libraries.** Pick the two or three you actually use.
- **Elaborate message buses / event streams.** A plan file and git history are the coordination primitive.

## The `.harness/PLAN.md` shape

- **Locked design calls section** at the bottom of every plan — capture the resolutions to open design questions so they don't drift mid-plan.
- **Task `Status: [x]` annotations** include a paragraph-long narrative of what shipped, not just the checkmark. The next session's context is whatever this captures.
- **When a plan completes** (last task `[x]`): flip plan-level `Status: done`, append an end-of-plan summary to `progress.md`, move the corresponding roadmap item to Completed with a full narrative, and archive the active `PLAN.md` to `archive/PLAN.archive.YYYYMMDD-<slug>.md` as the final close-out step — not when the next plan starts. **The archive step writes into an `archive/` subdirectory, not a flat path directly under `.harness/`** (Consolidation arc ruling 6) — a working directory's eyeline stays a small, current set of active files; done work moves one level deeper rather than accumulating flat alongside it.

## The wake-on-CI pattern

Don't mark tasks `[x]` speculatively. Push (or open/update a PR, whichever actually triggers the project's CI) → schedule a wake → close out with `[x]` + `progress.md` append only when the relevant check-suite confirms green across the OS matrix. Where a project's full CI matrix triggers on `pull_request` rather than a bare push to main, wake on the PR's check-suite there, not the push.

## The single-cycle shape

A background primitive built to run often and cheaply when there's nothing to do:

- **Cooldown-gated** — a cursor + a per-item marker decide what's due, so a repeat call this soon is a cheap no-op.
- **Cursor-backed** — progress lives in a local, non-synced marker, never in memory, never re-derived.
- **Idempotent** — a crashed or re-fired cycle re-runs whole safely, because the cursor and the dispatched-set make repetition harmless.
- **Opt-in** — nothing runs until an operator or a job manifest turns it on.
- **Surface, don't adopt** — the primitive reports what it did; a caller decides what to do with the report; the primitive never acts unilaterally beyond its own scope.

Two independent implementations converged on this shape without citing each other — named here so it reads as one documented pattern, not two coincidentally-similar mechanisms invented twice.

## Sources

Migrated from (crickets-conventions.md's Migrations spec, "the objective base standards that live only in `AGENTS.md` / `principles.md` / `~/.claude/CLAUDE.md`"):

- agentm `AGENTS.md` § Non-negotiable rules (rules 1, 2, 4, 6)
- agentm `harness/principles.md` (all seven principles + the non-principles list)
- the operator's global `~/.claude/CLAUDE.md` § Development flow conventions (the `.harness/PLAN.md` shape and Wake-on-CI pattern subsections)

Content this domain does **not** own (cite, don't duplicate): the recoverability/push/worktree doctrine stays [developer-safety](https://github.com/alexherrero/crickets/wiki/crickets-developer-safety)'s; the gate-battery mechanics stay the `ci-battery` rule's, not this skill's.
