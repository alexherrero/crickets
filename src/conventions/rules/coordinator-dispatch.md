---
name: coordinator-dispatch
description: Any multi-session job is authored as one coordinator dispatch — a dispatch-only coordinator, verbatim per-agent briefs, a completion log, and an escalate ledger — not a hand-pasted sequence of prompts. Hand-paste survives only where a step is genuinely operator-interactive.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: coordinator-dispatch

Migrated in (Consolidation arc, CONS-8) from the Consolidation-arc verdict's ruling 8. The verdict's own diagnosis (rubric 10): the orchestration machinery shipped — named plans, worktree-native spawn, `/queue-status-lite`, the coordinator role roster (see [Coordinator roles](https://github.com/alexherrero/crickets/wiki/Coordinator-Roles)) — and the operator still hand-pasted prompts between sessions anyway. The gap wasn't a missing capability; it was a missing **default**. This rule names the default: a multi-session job is a coordinator dispatch, not a string of separately-typed prompts.

### The shape

A coordinator dispatch (the shape this Consolidation arc itself ran, `CONS-COORD`) has four parts:

1. **A dispatch-only coordinator.** One session reads the plan (or verdict, or brief) that names the work, and does nothing else but dispatch, track, and report — it does not implement. Coding stays single-threaded per session ([`agentic-engineering`](../skills/agentic-engineering/SKILL.md)'s "single-threaded for coherence" principle); the coordinator's job is sequencing sessions, not writing code itself.
2. **Verbatim per-agent briefs.** Each dispatched session gets a self-contained brief — what to do, why, the acceptance criteria, and enough context to make judgment calls without re-deriving the plan from scratch. A brief that says "go do task 4" without restating scope forces the dispatched session to either guess or re-read everything the coordinator already read.
3. **A completion log.** The coordinator keeps a running, append-only log (a `<slug>-COORD-LOG.md`-shaped file) of what was dispatched, in what mode (worktree vs. direct), and its outcome — merged, done, or stalled. This is the on-disk state a coordinator's own context can't durably hold across a long arc.
4. **An escalate ledger.** Anything outside a brief's scope, or a lane that fails, is escalated — recorded in a ledger, not improvised around. The coordinator executes the plan; it does not re-litigate it.

**Re-dispatch-once-then-escalate.** If a dispatched lane stalls or fails, the coordinator retries it once (optionally with a simplified or chunked prompt, per whatever bisection the failure suggests) before escalating. A twice-failed lane escalates — it does not get a third silent retry, and it does not get improvised around.

### When hand-paste survives

Hand-paste (the operator directly running a step themselves, or a session prompted turn-by-turn without a coordinator) is legitimate only where a step is **genuinely operator-interactive** — ratification of a decision, a design conversation, or any step whose actual content is the operator's own judgment rather than execution of an already-made call. A multi-session **execution** job — the kind where every step's content is already decided and the only open question is who does the work and in what order — is a coordinator dispatch by default, not a candidate for case-by-case judgment.

### The fleet pre-flight: `fanout_cost_gate.py`

`src/tokens/scripts/fanout_cost_gate.py` (the crickets-token-audit design's pre-flight cost gate) is named as the fleet pre-flight this convention wires in: before a coordinator dispatches a fan-out (parallel lanes, or a wave of independent lanes), it estimates `agent_count × per_agent_cost` against a configured budget share and returns a proceed/confirm-or-block result with the cost stated explicitly — the direct fix for a fleet dispatch that exhausts a session budget mid-run with no pre-flight estimate in front of the operator.

**Status (updated by the fanout-cost-gate-wiring plan, Consolidation arc Wave 4 proving window): wired and live.** `fanout_cost_gate.py` is now called from `src/development-lifecycle/scripts/fanout_announcement.py`'s `announce_dispatch()` — the one chokepoint every dispatch group already passes through (every phase command's own "Mandatory fan-out announcement" step), not a bespoke coordinator-only call site. At `agent_count >= 4`, `announce_dispatch()` runs the gate against its own `DEFAULT_BUDGET_SHARE_USD` and folds a block into the same `pause_required` flag the silent-inheritance guard already used, so a dispatch site checks one flag regardless of which mechanism fired. This is broader than the coordinator-only wiring this rule originally anticipated when it was authored — it covers every dispatch, coordinator-authored or not — and closes the follow-up named at this rule's authoring; no further wiring work is open here.

### What is NOT an acceptable substitute

| Stated substitute | Why it is not acceptable |
|---|---|
| "I'll just paste the prompts myself, it's faster to set up" | Setup speed is not the point — a hand-pasted sequence has no completion log, no escalate ledger, and no re-dispatch discipline, so a stalled lane fails silently instead of surfacing. |
| "This job only has two steps, it doesn't need a coordinator" | The rule of three for *building a dedicated skill* is a separate question (below) — the convention itself (dispatch-only coordinator + brief + log + ledger) applies to any multi-session job, two steps or twenty. |
| "The step is interactive-ish, so I'll hand-paste the whole job" | Only the genuinely interactive step (ratification, a design conversation) is exempt. A job with one interactive step and five execution steps still runs the five as a coordinator dispatch. |

### Why this stays a convention, not a skill (for now)

A dedicated coordinator-dispatch skill was considered and deferred: only two real uses exist so far (`CONS-COORD`, the earlier `N1` overnight-run coordinator) against the rule of three, and a consolidation arc's own prime directive is fewer subsystems, not new ones. This lands as a **documented default** now; a skill is warranted once a third independent use exists.

### Enforcement

Before starting a multi-session job, check:

1. Is every step's content already decided (execution), or does a step's content depend on the operator's own judgment (interactive)? Execution steps route through a coordinator dispatch; interactive steps hand-paste.
2. Does the coordinator have a written brief per lane (not just a role name) and a place to log completion + escalations?
3. Did a stalled lane get exactly one retry before escalating — not zero (silently giving up) and not three-plus (silently improvising around a real problem)?

If all three are satisfied, the dispatch is compliant. If any is missing, that is the gap this rule exists to close.

## See also

- [Coordinator roles](https://github.com/alexherrero/crickets/wiki/Coordinator-Roles) — the four thin-skin roles (`researcher`, `tech-lead`, `worker`, `project-manager`) a coordinator dispatches against.
- [`coalescence-gate`](coalescence-gate.md) — the arc-exit checklist; a coordinator-dispatched arc runs this checklist against itself at close.
- `src/tokens/scripts/fanout_cost_gate.py` — the fleet pre-flight named above.
