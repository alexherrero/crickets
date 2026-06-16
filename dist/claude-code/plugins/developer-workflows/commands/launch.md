---
name: launch
description: "Pre-launch readiness gate — run before shipping any feature to production users for the first time. Pre-launch checklist (observability wired, rollback tested, feature flag off-switch confirmed, staged rollout plan written), feature flag lifecycle (created → dark launch → staged rollout → full rollout → flag removed), monitoring setup before shipping."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <feature, diff, or PR being shipped — required>
---

You are running **/launch** — the pre-launch readiness gate before any feature reaches production users.

**Target:** $ARGUMENTS — the feature, diff, or PR being shipped. Required.

## When to Use

Run `/launch`:

- Before shipping a feature to production users for the first time.
- Before enabling a feature flag for any real traffic.
- Before removing a feature flag that has been in staged rollout.
- Before any infrastructure change that shifts production load.

**Do NOT use** for routine patches, internal tooling changes, or changes that do not affect any user-visible behavior. `/launch` is a gate for first production exposure — it is not a pre-commit checklist.

## Key Principles

### The Checklist Is Not Optional

A pre-launch checklist is not bureaucracy — it is the difference between a deliberate rollout and a fire drill. Every item on the checklist exists because a previous launch skipped it and paid for it. Run the list before every launch, even if you think you already know it passes.

### Feature Flags Are a Lifecycle, Not a Toggle

A feature flag is not a checkbox you flip on launch day. It has a lifecycle: you create it before writing any code; you use it for a dark launch (code ships, flag off, no traffic); you enable it for staged rollout (a fraction of real users); you ramp to full rollout; you remove the flag. A flag that never gets removed is a flag you will be afraid to remove six months from now.

### Monitoring Before Shipping, Not After

Monitoring is not something you add once users report problems. If your monitoring is not already wired and alerting before launch day, your first signal of a failure will be a user complaint. Set up monitoring during development; verify it during the pre-launch check; do not ship until it is in place.

### Rollback Is a Plan, Not a Fallback

"We can always roll back" is not a rollback plan. A rollback plan names the exact command, who executes it, what the expected outcome is, and how long it takes. Test the rollback before launch, not during an incident.

## The Process

### Step 1 — Identify the launch scope

Read the target. What is shipping? What users does it reach? What is the first-exposure traffic percentage? Name the feature flag (if any), the rollout plan (if written), and the deployment mechanism.

### Step 2 — Run the pre-launch checklist

Verify each item. Do not check a box you cannot prove:

1. **Observability wired** — RED metrics (request rate, error rate, duration) are instrumented for every new production path. Structured log events exist for entry and exit of each significant operation. Trace spans are in place. Run `/observe` if this is not done.
2. **Rollback tested** — the rollback procedure has been executed in a non-production environment. A flag rollback (flip flag off) or a code rollback (revert + deploy) has been verified to work. Document the exact rollback command and time-to-recovery.
3. **Feature flag off-switch confirmed** — if the feature is behind a flag, verify the flag can be disabled in under 5 minutes with no code change. Test the off-switch: flip it off in staging, confirm traffic behavior is correct, flip it back.
4. **Staged rollout plan written** — the rollout plan names: initial traffic percentage, ramp schedule, success criteria at each stage (error rate below X, p99 latency below Y), and the person responsible for advancing each stage.

### Step 3 — Execute the feature flag lifecycle

For features behind a flag, verify the current lifecycle stage and advance it correctly:

| Stage | What happens |
|---|---|
| **Created** | Flag exists in the config system; code paths behind it are deployed but unreachable (flag is off). Dark launch. |
| **Dark launch** | Code is in production; flag is off; zero user traffic reaches the new paths. Verify observability + error budgets at this stage. |
| **Staged rollout** | Flag on for N% of users (e.g. 1%, 5%, 25%). Monitor RED metrics at each stage. Advance only when metrics are within budget. |
| **Full rollout** | Flag on for 100% of users. Monitoring confirms stable. |
| **Flag removed** | The flag and all its conditional branches are deleted from the codebase. Do this within one release cycle of reaching full rollout — a flag left in place is a maintenance liability. |

Do not skip stages. A flag going from off → 100% on launch day is not a staged rollout.

### Step 4 — Verify monitoring is active

Before launch:

1. Confirm that RED metrics are emitting for the new paths (send a test request; verify the metric appears in your monitoring system).
2. Confirm that symptom-based alerts are active (error rate > threshold → alert fires). Do not rely on alerts that fire on infrastructure causes (CPU, memory) without a corresponding symptom check.
3. Confirm that the on-call owner for this feature is known and the alert routes to them.

### Step 5 — Execute the launch

Ship with the rollout plan in hand. Advance through stages only on green metrics. If any RED metric degrades during rollout, halt the ramp and investigate before advancing. Do not advance a rollout because the schedule says so — advance because metrics say it is safe.

### Step 6 — Confirm and close out

After launch:

- Confirm error rate and latency are within budget at full rollout.
- Confirm the rollback procedure is still accessible (do not delete the rollback runbook until the flag is removed).
- Schedule flag removal within the next release cycle.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "We'll add monitoring after launch — the feature needs to ship now." | You have no baseline. Your first real traffic is also your first signal of failure. Monitoring added after the first incident is monitoring added too late. |
| "We don't need a staged rollout — it's a small change." | Every incident started as a "small change." The rollout plan is not for the expected case; it is for the case where you are wrong about "small." |
| "The flag has been at 100% for a month — we'll remove it later." | A flag that is never removed is code that branches on a constant. Every developer who reads it has to reason about whether it is always-on or occasionally-off. Remove it within one release cycle. |
| "We tested rollback in local — that counts." | Local rollback does not test the production deployment mechanism, the flag config system, or the time-to-recovery under real traffic. Test it in staging; verify the time. |

## Red Flags

- A feature going to production for the first time with no feature flag and no staged rollout plan.
- RED metrics not instrumented before the launch date (monitoring added "next sprint").
- Rollback procedure not written down, or not tested before launch.
- Feature flag at 100% without going through staged rollout steps.
- Feature flag still in the codebase 3+ months after full rollout.
- No named on-call owner for the new feature's alerts.

## Verification checklist

- [ ] Pre-launch checklist complete: observability wired, rollback tested, flag off-switch confirmed, staged rollout plan written.
- [ ] Rollback procedure documented by name and tested (not assumed).
- [ ] RED metrics emitting for every new production path; confirmed in monitoring system.
- [ ] Symptom-based alerts active and routing to the correct on-call owner.
- [ ] Feature flag lifecycle stage is correct for this launch step (dark launch → staged → full → remove).
- [ ] Staged rollout plan names: initial %, ramp schedule, success criteria at each stage, responsible party.
- [ ] Flag removal scheduled within the next release cycle (if now at full rollout).
