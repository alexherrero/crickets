# How to run a pre-launch readiness gate with /launch

> [!IMPORTANT]
> **Status: implemented** — `/launch` shipped in `src/developer-workflows/commands/launch.md`.

> [!NOTE]
> **Goal:** Gate a first production rollout with a structured readiness checklist — observability wired, rollback tested, feature flag off-switch confirmed, staged rollout plan written — using the `/launch` command before any production users see the feature.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); a feature ready for first production exposure; observability instrumented (see [/observe](Add-Observability-With-Observe)).

`/launch` is the **first-production-rollout gate**; it is distinct from `/release` (which is the pre-merge code gate). `/launch` enforces:

1. Observability is wired (logs, metrics, alerts live).
2. Rollback has been tested and is confirmed to work.
3. A feature flag off-switch is confirmed (the kill switch is real, not hypothetical).
4. A staged rollout plan is written (dark launch → staged rollout → full rollout → flag removed).

## Steps

1. Invoke the command, passing the feature, diff, or PR being shipped:

   ```text
   /launch <feature, diff, or PR>
   ```

   The argument is required. `/launch` is for **first production exposure** — not routine patches or internal tooling changes. See `src/developer-workflows/commands/launch.md` (`When to Use`) for the full boundary.

2. Identify the launch scope: what is shipping, which users it reaches, the initial traffic percentage, the feature flag name (if any), and the deployment mechanism.

3. Run the pre-launch checklist. Verify each item; do not check a box you cannot prove:

   | Checklist item | What to verify |
   |---|---|
   | **Observability wired** | RED metrics (rate, error, duration) instrumented for every new production path; structured log events at entry/exit; trace spans in place. Run `/observe` if not done. |
   | **Rollback tested** | Rollback executed in a non-production environment. Document the exact command and measured time-to-recovery. |
   | **Feature flag off-switch confirmed** | Flag can be disabled in under 5 minutes with no code change. Test it: flip off in staging, confirm behavior, flip back. |
   | **Staged rollout plan written** | Names initial traffic %, ramp schedule, success criteria at each stage (error rate below X, p99 latency below Y), and responsible party per stage. |

4. Verify the feature flag lifecycle stage and advance it correctly:

   | Stage | What happens |
   |---|---|
   | **Created** | Flag exists; code is deployed but unreachable (flag off). Dark launch. |
   | **Dark launch** | Code in production; flag off; zero user traffic. Verify observability and error budgets here. |
   | **Staged rollout** | Flag on for N% of users (e.g. 1%, 5%, 25%). Monitor RED metrics; advance only on green. |
   | **Full rollout** | Flag on for 100%. Monitoring confirms stable. |
   | **Flag removed** | Flag and all conditional branches deleted from the codebase. Do this within one release cycle of full rollout. |

   Do not skip stages. A flag going from off to 100% on launch day is not a staged rollout.

5. Confirm monitoring is active before shipping: send a test request and verify the RED metric appears in your monitoring system; confirm symptom-based alerts are firing-ready and route to the named on-call owner.

6. Ship with the rollout plan in hand. Advance through stages only on green metrics — not because the schedule says so.

7. After reaching full rollout: confirm error rate and latency are within budget; confirm rollback procedure is still accessible; schedule flag removal within the next release cycle.

## Verify

Work through the verification checklist from `src/developer-workflows/commands/launch.md`:

- [ ] Pre-launch checklist complete: observability wired, rollback tested, flag off-switch confirmed, staged rollout plan written.
- [ ] Rollback procedure documented and tested (not assumed); time-to-recovery measured.
- [ ] RED metrics emitting for every new production path; confirmed in monitoring system.
- [ ] Symptom-based alerts active and routing to the correct on-call owner.
- [ ] Feature flag lifecycle stage is correct for this launch step.
- [ ] Staged rollout plan names: initial %, ramp schedule, success criteria, responsible party.
- [ ] Flag removal scheduled within the next release cycle (if now at full rollout).

## Troubleshooting

Common rationalizations that signal something is wrong (from `src/developer-workflows/commands/launch.md` "Common Rationalizations"):

| Excuse | What it signals |
|---|---|
| "We'll add monitoring after launch." | No baseline. First real traffic is also first signal of failure. Do not ship. |
| "It's a small change — no staged rollout needed." | Every incident started as a "small change." The rollout plan exists for the case where you are wrong. |
| "The flag has been at 100% for a month — we'll remove it later." | A flag never removed becomes code that branches on a constant. Remove within one release cycle. |
| "We tested rollback in local." | Local rollback does not test the production deployment mechanism or the config system. Test in staging. |

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/launch`.
- [How to instrument code with /observe](Add-Observability-With-Observe) — observability must be wired before `/launch` passes.
- [How to author CI/CD pipelines with /ci-cd](Author-A-CICD-Pipeline) — the pipeline authoring companion.
- [Manifest schema](Manifest-Schema) — command primitive frontmatter reference
