# How to author or modify a CI/CD pipeline with /ci-cd

> [!IMPORTANT]
> **Status: pending** (developer-workflows Ship phase). This is a forward-declared skeleton — `/ci-cd` does not yet exist. Step bodies are reserved, not written; a later `/work` task fills them from the shipped diff. Do not follow these steps yet.

> [!NOTE]
> **Goal:** Author or modify a CI/CD pipeline that moves quality gates as early as possible (Shift Left), makes the pipeline fast enough that smaller-diff deploys become the natural cadence (Faster is Safer), and eliminates any "ship anyway" bypass path.
> **Prereqs:** the `developer-workflows` plugin installed at a version that ships `/ci-cd` ([Install crickets plugins](Install-Into-Project)); a CI/CD config file to create or modify (e.g., `.github/workflows/`, `.gitlab-ci.yml`). _Exact prereqs filled by `/work` once the task ships._

`/ci-cd` enforces four principles:

- **Shift Left** — move quality gates earlier in the pipeline; a defect caught in lint costs less than one caught in deploy.
- **Faster is Safer** — a faster pipeline lowers the blast radius of each deploy by keeping diffs small; speed is a safety property.
- **Quality gate pipeline order** — lint → typecheck → test → build → deploy. Stages run in this order; no skipping.
- **No bypass** — failure feedback loops must be real; no `--skip`, no `|| true`, no bypass flags on any quality gate stage.

## Steps

1. Invoke the command when authoring or modifying a CI/CD config:

   ```text
   /ci-cd
   ```

   _Filled by `/work` once the task ships._

2. Structure the pipeline in canonical gate order: lint → typecheck → test → build → deploy.

   _Filled by `/work` once the task ships._

3. Move each quality gate as early as possible (Shift Left): confirm no gate runs later than it must.

   _Filled by `/work` once the task ships._

4. Audit the pipeline for speed: identify and address the slowest stage so faster iteration is the natural cadence.

   _Filled by `/work` once the task ships._

5. Confirm no bypass paths exist — no `--skip` flags, no `|| true` on any quality-gate step, no optional-failure markers.

   _Filled by `/work` once the task ships._

## Verify

_Filled by `/work` once the task ships._

## Troubleshooting

_Filled by `/work` once the task ships._

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/ci-cd`.
- [CI gates](CI-Gates) — the reference for the crickets project's own gate battery.
- [How to run a pre-launch readiness gate with /launch](Add-Launch-Readiness-Gate) — the pre-production companion gate.
