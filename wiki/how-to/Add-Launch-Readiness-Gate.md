# How to run a pre-launch readiness gate with /launch

> [!IMPORTANT]
> **Status: pending** (developer-workflows Ship phase). This is a forward-declared skeleton — `/launch` does not yet exist. Step bodies are reserved, not written; a later `/work` task fills them from the shipped diff. Do not follow these steps yet.

> [!NOTE]
> **Goal:** Gate a first production rollout with a structured readiness checklist — observability wired, rollback tested, feature flag off-switch confirmed, staged rollout plan written — using the `/launch` command before any production users see the feature.
> **Prereqs:** the `developer-workflows` plugin installed at a version that ships `/launch` ([Install crickets plugins](Install-Into-Project)); a feature ready for first production exposure; observability instrumented (see [/observe](Add-Observability-With-Observe)). _Exact prereqs filled by `/work` once the task ships._

`/launch` is the **first-production-rollout gate**; it is distinct from `/release` (which is the pre-merge code gate). `/launch` enforces:

1. Observability is wired (logs, metrics, alerts live).
2. Rollback has been tested and is confirmed to work.
3. A feature flag off-switch is confirmed (the kill switch is real, not hypothetical).
4. A staged rollout plan is written (dark launch → staged rollout → full rollout → flag removed).

## Steps

1. Invoke the command before the first production exposure:

   ```text
   /launch
   ```

   _Filled by `/work` once the task ships._

2. Confirm observability is wired — logs structured, RED metrics live, alerts defined.

   _Filled by `/work` once the task ships._

3. Confirm rollback has been tested and works end-to-end.

   _Filled by `/work` once the task ships._

4. Confirm the feature flag off-switch exists and has been validated (not just coded).

   _Filled by `/work` once the task ships._

5. Write and confirm the staged rollout plan: dark launch → staged rollout percentage → full rollout → flag removal schedule.

   _Filled by `/work` once the task ships._

## Verify

_Filled by `/work` once the task ships._

## Troubleshooting

_Filled by `/work` once the task ships._

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/launch`.
- [How to instrument code with /observe](Add-Observability-With-Observe) — observability must be wired before `/launch` passes.
- [How to author CI/CD pipelines with /ci-cd](Author-A-CICD-Pipeline) — the pipeline authoring companion.
