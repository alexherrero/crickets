---
title: reporting — design
status: launched
kind: design
scope: feature
area: crickets/reporting
governs: []
parent: crickets-hld.md
seeded: 2026-06-26
approved: 2026-06-26
---

> **The `reporting` capability — the operator-facing report surface across the agentm/crickets fleet: the digest now (what ran, what changed, health, alerts), dashboards later.** Child of the [crickets HLD](crickets-hld); the [runner](https://github.com/alexherrero/agentm/wiki/agentm-runner) runs its digest job.

# reporting

## Objective

`reporting` is the capability that tells the operator what happened while they were away. Background jobs run unattended — forward-learning, dreaming, health checks, curated-content edits — and the operator needs one place that says what ran, what changed (and how to undo it), whether anything is unhealthy, and what needs their attention. The first primitive is the **digest**; the capability is built to grow into operator-facing **dashboards**.

## Overview

`reporting` has one primitive today and room for a second:

| Primitive | What it does |
|---|---|
| **`digest`** *(greenfield, first)* | The periodic operator report: what each job ran + when, agentm/crickets health, the changes jobs made (with revert pointers), archive proposals to confirm, and anything else to flag. Delivered by email, or shown on request within a session. |
| **`dashboards`** *(greenfield, later)* | Interactive views over the same data — the digest's pull-mode sibling, for when a report isn't enough. The growth direction, not a v1. |

![How the digest is assembled: the runner's job results + T2-change log, diagnostics' health, token-audit's cost, and the memory revert-log feed the digest, which pushes the routine digest (email weekly, or on request) and immediate urgent alerts; dashboards (dimmed) is the later pull-mode view](diagrams/crickets-reporting.svg)

*The digest aggregates four sources and pushes two notifications — the routine digest (email weekly, or on request) and immediate urgent alerts; dashboards (dimmed) is the later pull view.*

## Design

### `digest` — the operator-facing report *(greenfield, first)*

- *Entry:* a **runner job** on a routine cadence (weekly by default), plus an immediate fire on an urgent event (a job failed, the budget tripped, the watchdog circuit-breaker auto-paused a job).
- *Exit:* a report delivered to the operator — sent by email, or shown on request within a session — and, for urgent events, an immediate alert. A routine cycle with nothing to report still sends a brief heartbeat, so silence means idle, not dead.
- *Automated:* aggregate the cycle's outputs — each job's last-run + result, agentm/crickets health (from the [diagnostics](crickets-diagnostics) watchdog), the T2 (curated) changes the runner made (each with a revert pointer), any archive/prune proposals awaiting confirmation, and cost (from [token-audit](crickets-token-audit)) — render it, and deliver it.
- *Composes:* the [runner](https://github.com/alexherrero/agentm/wiki/agentm-runner) (runs the digest job + supplies the per-job results and the T2-change log), [diagnostics](crickets-diagnostics) (health + liveness), [token-audit](crickets-token-audit) (cost), the agentm memory revert-log (the revert pointers).

**The report has three parts:**
1. **Operational summary** — each scheduled job, when it last ran and whether it succeeded (a finished run isn't always a successful one), and agentm + crickets health.
2. **Per-job insights** — what each job found or changed: the **T2 curated changes** (a design, plan, or roadmap the agent edited), each with a one-step **revert pointer**; surfaced ideas; and any **archive/prune proposals to confirm**.
3. **Anything else** — whatever needs the operator's attention that doesn't fit the first two.

**Two notifications, split by urgency:**
- **The routine digest** — sections 1–3, batched on the routine cadence (weekly by default). The standing report.
- **Urgent alerts** — a job failing, the budget ceiling tripping, the watchdog auto-pausing a job. These fire immediately rather than waiting for the weekly digest — by email today, with a **chat-message channel** (instead of or alongside email) as a designed-for future option.

**Delivery — email, or on request.** Sessions aren't reliable, so email carries the digest: it sends when there's something to report, plus a heartbeat at least weekly even when there isn't. The digest does **not** surface automatically at session start; within a session the operator can ask for the latest one on demand. Urgent alerts go out immediately by email today, with a **chat-message channel** (instead of or alongside email) as a designed-for future option.

**`[PENDING-IMPL]`** — build the aggregator + the renderer + the email channel + the on-request surface (documenter). The **email channel is net-new plumbing** (an SMTP or send-API integration) — the one part `reporting` adds that the harness doesn't already have. A **chat-message alert channel** is a designed-for future addition.

### `dashboards` — interactive views *(greenfield, later)*

The digest is push (a report arrives); dashboards are pull (the operator looks). Same data — job state, health, changes, cost — as live views for when a periodic report isn't enough. It's the capability's growth direction; the digest ships first, dashboards follow once there's a reason. **`[PENDING-IMPL]`** — deferred; the digest's aggregator is the data layer a dashboard would read.

### Opinions it consumes

`reporting` consumes no behavioral opinion — the digest reports what happened; it doesn't make a judgment call. Its prose follows the operator's **communication style** (plain, low-drama, scannable — the voice convention every operator-facing surface follows).

### The boundary

- **vs [github-projects](crickets-github-projects)** — github-projects mirrors vault state to a GitHub Project board (the structured, always-on human mirror). `reporting` is the periodic push report + alerts; it points the operator *at* a change, where the board *holds* the state. Different surfaces, different cadence.
- **vs [diagnostics](crickets-diagnostics)** — diagnostics produces the health + liveness signal; `reporting` presents it. diagnostics diagnoses; reporting reports.
- **vs the agentm Operator persona's `/status`** — `/status` is the operator's live on-demand glance; the digest is the scheduled email push (and shows the latest on request within a session). The `dashboards` primitive is where the two converge later.

## Dependencies

- **composes the [runner](https://github.com/alexherrero/agentm/wiki/agentm-runner)** — the digest is a runner job; the runner supplies each job's result + the T2-change log + the archive proposals.
- **composes [diagnostics](crickets-diagnostics)** — the health + liveness data for the operational summary.
- **composes [token-audit](crickets-token-audit)** — the cost line.
- **leans on the agentm memory revert-log** — the revert pointers for T2 changes (the [memory-system](https://github.com/alexherrero/agentm/wiki/agentm-memory-system) tiers + revert-log).
- **a new delivery channel** — email (SMTP / send API), net-new plumbing.
- Points up at the [crickets HLD](crickets-hld); the requires/enhances mechanics are in [crickets-composition](crickets-composition).

## Migrations

- **A 14th capability.** `reporting` is net-new, so the portfolio count moves from 13 to 14: reconcile the capability list/count in the [crickets HLD](crickets-hld), the design catalog, and the area-taxonomy at the lift.
- **The email channel** is plumbing the harness doesn't have — a deliberate add, the one infrastructure piece `reporting` introduces.

## Risks & open questions

- **Email is net-new infrastructure.** The digest's reliable channel needs an SMTP or send-API integration the harness lacks today — the one genuinely new build here. Until it lands, the digest is available on request within a session only (no push).
- **The digest depends on the runner + the tier model.** It reports what the runner did, routed by the memory-system tiers; it's blocked on the runner + the runner's T2-change log + the revert-log being built.
- **Dashboards are deferred.** The capability is named "reporting" (not "digest") to leave room, but only the digest is specced; dashboards is a direction, not a commitment.
- **Re-audit triggers:** reconcile the 13→14 capability count at the lift; build the email channel; flip `[PENDING-IMPL]` as the digest aggregator/renderer/channels land; specify `dashboards` when there's a reason; confirm the runner's T2-change log + the revert-log shapes when those build.

## References

- **Composes:** the [runner](https://github.com/alexherrero/agentm/wiki/agentm-runner) (the digest job + the job results + T2-change log) · [diagnostics](crickets-diagnostics) (health/liveness) · [token-audit](crickets-token-audit) (cost) · the agentm [memory-system](https://github.com/alexherrero/agentm/wiki/agentm-memory-system) revert-log (revert pointers)
- **Related:** the agentm Operator persona's `/status` (the pull-mode sibling) · [github-projects](crickets-github-projects) (the board mirror)
- **Up:** [crickets HLD](crickets-hld) · [composition](crickets-composition)
- R03 — scheduled / background / autonomous agents (the 2026-06 research; the agent-inbox / digest-as-review-surface finding this realizes)

## Amendment log

*Newest first. Collapses to one ≤2-paragraph entry at finalization; git holds the granular history.*

- **2026-06-28 — lock-down sweep (operator review).** Confirmed the report surface — the digest now (what ran · changed · health · alerts), dashboards later; the [runner](https://github.com/alexherrero/agentm/wiki/agentm-runner) runs its digest job. Standing fixes clean (SVG already sized; no mermaid; newest-first log). Designed-not-built (`governs: []`). Locked as a v5–v8 guidepost.

- **2026-06-26 — authored, reviewed, and finalized.** A new crickets capability, `reporting`, homing the **digest** — the operator-facing report the runner's autonomous work needs (concretizing R03's agent-inbox / review-surface finding). The digest is a runner job with three parts (operational summary · per-job insights with revert pointers + archive proposals · anything-else) and two notifications split by urgency (a routine weekly digest + immediate urgent alerts). Delivery is **email** (send-on-report + ≥weekly heartbeat) **or on request within a session** — it does not surface automatically at session start; urgent alerts go out immediately by email, with a chat-message channel as a designed-for future option. `dashboards` is named as the later pull-mode growth direction. The capability replaces the "review inbox" the runner originally carried — report-after for autonomous changes, propose-confirm only for archive/prune. **Net-new:** the email delivery channel; **a 14th capability** (crickets-hld / catalog / area-taxonomy reconciled at the lift). *Re-audit:* build the email + future chat-alert channels; add `reporting` to the composition map (Bucket-B sweep); flip `[PENDING-IMPL]` as the digest builds; specify `dashboards` later.
