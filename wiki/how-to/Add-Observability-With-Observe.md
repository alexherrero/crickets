# How to instrument code with /observe

> [!IMPORTANT]
> **Status: implemented** — shipped in `src/developer-workflows/commands/observe.md` (v0.1.0).

> [!NOTE]
> **Goal:** Wire structured telemetry (logging, RED metrics, distributed tracing, symptom-based alerts) into a feature or service as you build it, using the `/observe` command to enforce the "instrument as you build" discipline before any code ships to production.
> **Prereqs:** the `developer-workflows` plugin installed at a version that ships `/observe` ([Install crickets plugins](Install-Into-Project)); a working tree with code that runs in production (test-only changes are out of scope for `/observe`).

`/observe` enforces four disciplines in order: structured logging (log events not strings), RED metrics (Request rate, Error rate, Duration), OpenTelemetry tracing, and symptom-based alerting (alert on symptoms, not causes). It is triggered whenever you are adding telemetry or shipping anything to production.

## Steps

1. Invoke the command at the point you are about to add telemetry or ship to production. Pass a component name, service name, or leave it empty to default to the current uncommitted diff:

   ```text
   /observe <component-or-service>
   ```

   The command identifies every production path in scope (HTTP handlers, background jobs, queue consumers, scheduled tasks, outbound API calls). Test-only paths are excluded ([`observe.md` lines 59–61](../src/developer-workflows/commands/observe.md)).

2. Add structured log events at the entry and exit of each significant operation. The command enforces the rule "log events, not strings": every entry must carry event name, entity IDs, outcome, and duration. Secrets and PII are prohibited. Use `INFO` for normal events and `ERROR` for failures — no `WARN` for errors, no `DEBUG` in production ([`observe.md` lines 63–66](../src/developer-workflows/commands/observe.md)).

3. Wire RED metrics for every external-facing surface or background job — request rate, error rate, and duration as a histogram (not a gauge). The command flags introduction of a second metrics library as a red flag; extend the existing one ([`observe.md` lines 68–70](../src/developer-workflows/commands/observe.md)).

4. Wrap each significant operation in an OpenTelemetry span. Name the span after the operation, set `ERROR` status on failures, attach the error message as a span attribute, and propagate trace context across async boundaries and outbound calls ([`observe.md` lines 72–75](../src/developer-workflows/commands/observe.md)).

5. Define symptom-based alerts for each RED metric: alert on user-visible symptoms (error rate above threshold, duration above SLO), not on infrastructure causes (CPU, memory, disk). Include a one-sentence runbook comment in each alert definition ([`observe.md` lines 77–80](../src/developer-workflows/commands/observe.md)).

## Verify

Before committing, confirm the six-item checklist from [`observe.md` lines 100–105](../src/developer-workflows/commands/observe.md):

- Every production path has a structured log event at entry and exit of each significant operation.
- RED metrics (request rate, error rate, duration histogram) are wired for every external-facing surface.
- Trace spans wrap significant operations and propagate across async boundaries.
- Alerts target user-visible symptoms, not infrastructure causes.
- No log entry contains secrets or PII.
- Observability is verifiable locally before committing: metrics emit, spans record, logs appear.

## Troubleshooting

The command surfaces common rationalizations as red flags ([`observe.md` lines 84–96](../src/developer-workflows/commands/observe.md)):

| Symptom | Cause | Fix |
|---|---|---|
| `/observe` flags the diff even though "the feature works" | Observability is missing — "works" and "observable" are separate properties | Add structured logging, RED metrics, and trace spans before committing |
| Alert fires on CPU / memory / disk | Alert targets an infrastructure cause, not a user symptom | Rewrite alert to target error rate or latency SLO |
| Trace context lost across an async boundary or outbound call | Context not propagated | Propagate OTel context through the async handoff or outbound call |

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/observe`.
- [How to run a pre-launch readiness gate with /launch](Add-Launch-Readiness-Gate) — the companion gate that confirms observability is wired before first production rollout.
