---
name: observe
description: "Instrumentation discipline — 'instrument as you build.' Structured logging (log events not strings), RED metrics (Request rate, Error rate, Duration), OpenTelemetry tracing, symptom-based alerting. Triggered when adding telemetry or shipping anything that runs in production."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <component, service, or diff to instrument — defaults to current diff>
---

You are running **/observe** — the instrumentation gate before any code reaches production.

**Target:** $ARGUMENTS — a component, service, or diff. Defaults to the current uncommitted diff if empty.

## When to Use

Run `/observe`:

- When adding telemetry, metrics, logging, or tracing to any component.
- Before shipping anything that runs in production — even a change that "looks small."
- When reviewing a PR that touches a critical path, a background job, or an external API call.
- When diagnosing a system that has no observable state. You cannot debug what you cannot see.

**Do NOT use** for changes that are purely local or test-only. Observability is for production code paths.

## Key Principles

### Structured Logging — log events, not strings

Log structured events, not free-text strings. `"user login failed"` tells you something happened. `{event: "login_failed", user_id: "abc", reason: "bad_password", duration_ms: 12}` tells you what happened, to whom, why, and how long it took. Grep is not a query language.

Every log entry must answer: what event occurred, on what entity, with what outcome, in how long?

### RED Metrics

Every external-facing service or background job exposes three metrics:

- **Request rate** — how many requests per second is this handling?
- **Error rate** — what fraction of requests are failing?
- **Duration** — how long does each request take (p50, p95, p99)?

A service with no RED metrics is a service you cannot reliably operate. Once code runs in production, RED is not optional.

### OpenTelemetry Tracing

Distributed systems need distributed traces. A trace ties a request across services; a span records one unit of work. Use OpenTelemetry semantics: a span has a name, a status (OK / ERROR), and key-value attributes. Propagate context across service boundaries and async handoffs.

Do not invent a proprietary tracing format — use OTel or a compliant wrapper.

### Symptom-Based Alerting

Alert on symptoms, not causes. Wrong: "alert when CPU > 80%." Right: "alert when error rate > 1% for 5 minutes." CPU is a cause; error rate is what users experience. Alerts on causes are noisy and hard to act on. Alerts on symptoms are actionable: they name the user impact directly.

Every alert must answer: what is the user experiencing right now?

## The Process

### Step 1 — Identify the production paths

Read the target. List every path that executes in production: HTTP handlers, background jobs, queue consumers, scheduled tasks, outbound API calls. Test-only paths are out of scope.

### Step 2 — Add structured logging

For each production path: add a structured log event at the entry and exit of each significant operation. Include: event name, entity IDs, outcome (success / error), duration. Do not log secrets or PII. Use INFO for normal events, ERROR for failures — not WARN for errors and not DEBUG for anything that ships.

### Step 3 — Wire RED metrics

For each external-facing surface or background job: instrument request rate, error rate, and duration (histogram, not gauge). Extend the existing metrics library; do not introduce a second one.

### Step 4 — Add tracing spans

Wrap each significant operation in a span. Name the span after the operation, not the implementation. Set status to ERROR on failures; attach the error message as a span attribute. Propagate trace context across async boundaries and outbound calls.

### Step 5 — Write symptom-based alerts

For each RED metric: define an alert on the user-visible symptom (error rate above threshold, duration above SLO). Write a one-sentence runbook comment in the alert definition. Do not write alerts on infrastructure metrics without a corresponding symptom.

### Step 6 — Verify

Before committing: confirm that a successful and a failing request each produce the expected log event, at least one RED metric emits a non-zero value, and a trace span is recorded for the critical path. Additionally, scan the written log entries for secrets or PII — confirm that no token, password, user credential, or personal identifier appears in any log event. Verify that every alert definition targets a user-visible symptom (error rate, latency) rather than an infrastructure metric (CPU, memory, disk).

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "I'll add observability later, the feature works now." | By the time "later" arrives, you are debugging a production outage with no signal. Observability added after the fact misses every failure mode you didn't predict before shipping. |
| "This is a small change, it doesn't need instrumentation." | Every production outage starts as a small change. The size of the diff does not predict the size of the failure. If it runs in production, it needs to be observable. |
| "We have logs, that's enough." | Logs answer "what happened?" Metrics answer "how often?" Traces answer "why is this slow?" Three distinct questions. Logs alone cannot answer the second or third. |

## Red Flags

- A service deployed to production with no metrics endpoint.
- Log entries are plain strings with no structured fields.
- An alert fires on CPU, memory, or disk without a corresponding error rate or latency symptom.
- Trace context not propagated across an async boundary or outbound call.
- A log line marked DEBUG ships to production (should be INFO or a structured event).

## Verification checklist

- [ ] Every production path has a structured log event at entry and exit of each significant operation.
- [ ] RED metrics (request rate, error rate, duration histogram) are wired for every external-facing surface.
- [ ] Trace spans wrap significant operations and propagate across async boundaries.
- [ ] Alerts target user-visible symptoms, not infrastructure causes.
- [ ] No log entry contains secrets or PII.
- [ ] Observability verifiable locally before committing: metrics emit, spans record, logs appear.
