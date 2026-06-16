# How to author or modify a CI/CD pipeline with /ci-cd

> [!IMPORTANT]
> **Status: implemented** — `/ci-cd` shipped in `src/developer-workflows/commands/ci-cd.md`.

> [!NOTE]
> **Goal:** Author or modify a CI/CD pipeline that moves quality gates as early as possible (Shift Left), makes the pipeline fast enough that smaller-diff deploys become the natural cadence (Faster is Safer), and eliminates any "ship anyway" bypass path.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); a CI/CD config file to create or modify (e.g., `.github/workflows/`, `.gitlab-ci.yml`).

`/ci-cd` enforces four principles:

- **Shift Left** — move quality gates earlier in the pipeline; a defect caught in lint costs less than one caught in deploy.
- **Faster is Safer** — a faster pipeline lowers the blast radius of each deploy by keeping diffs small; speed is a safety property.
- **Quality gate pipeline order** — lint → typecheck → test → build → deploy. Stages run in this order; no skipping.
- **No bypass** — failure feedback loops must be real; no `--skip`, no `|| true`, no bypass flags on any quality gate stage.

## Steps

1. Invoke the command, passing the pipeline file, workflow, or CI config being authored or modified:

   ```text
   /ci-cd <pipeline file or CI config>
   ```

   The argument is required. `/ci-cd` is for changes **to pipeline structure** — what gates exist, what they check, what order they run. Do not use it for app code changes that happen to touch a test file or build script. See `src/developer-workflows/commands/ci-cd.md` (`When to Use`) for the boundary.

2. Read the full pipeline config before changing any part of it. Understand: what gates currently exist, what order they run, what each gate does, and what currently blocks the deploy.

3. Map the current gate order. The canonical order is **lint → typecheck → test → build → deploy** — each stage costs more than the one before it. Any gate that runs later than this order requires a Shift Left finding.

4. Apply Shift Left for each out-of-order gate:
   - Identify the gate's approximate run time.
   - Identify the cheaper gate that should precede it.
   - Move it earlier, confirming the earlier stage does not require artifacts that only the later stage produces.
   - If two gates cannot be ordered by cost because they are independent, parallelize them (same stage, parallel jobs).

5. Wire blocking on every gate. Audit any use of `continue-on-error` or `--no-fail-fast`. A gate with `continue-on-error: true` is a reporting step, not a quality gate. Remove it from quality gates unless you have an explicit documented reason.

6. Wire the failure feedback loop. Confirm the pipeline notifies the committer on failure with: the failing gate name, a link to the full log (not just the summary), and a delivery path that actually reaches the committer — not a shared channel with no owner.

7. Measure pipeline speed. If wall-clock time exceeds 10 minutes, identify the slowest gate. Speed targets (soft ceilings, not hard rules): lint + typecheck under 2 minutes; unit tests under 5 minutes; full build + integration under 15 minutes. Treat significant overrun as a Shift Left issue.

8. After any change, verify the pipeline on both a failing and a passing input: confirm the modified gate fails as expected; confirm the pipeline completes end-to-end on green; confirm failure notification reaches the right destination; confirm no gate has `continue-on-error: true` that should block.

## Verify

Work through the verification checklist from `src/developer-workflows/commands/ci-cd.md`:

- [ ] Gates run in order: lint → typecheck → test → build → deploy.
- [ ] Every gate blocks the next stage on failure — no `continue-on-error` on quality gates.
- [ ] CI failure notification reaches the committer (name + log link, not just a summary).
- [ ] Pipeline wall-clock time measured; gates parallelized where independent.
- [ ] No "ship anyway" bypass exists for a red gate.
- [ ] Failure feedback loop verified: triggered a failure, confirmed notification, confirmed re-run unblocked merge.
- [ ] Each gate verified on both a failing and a passing input.

## Troubleshooting

Common rationalizations that signal a pipeline design problem (from `src/developer-workflows/commands/ci-cd.md` "Common Rationalizations"):

| Excuse | What it signals |
|---|---|
| "We'll speed up the pipeline later — it works now." | Slowness compounds as the team grows: long pipelines cause batching, batching causes larger diffs, larger diffs cause more failures. Treat slowness as a correctness issue now. |
| "`continue-on-error` is there because the gate is flaky." | A flaky gate is a broken gate. Fix the flakiness; do not route around it indefinitely. |
| "The failing test doesn't block merge because it's a separate job." | Separate jobs are not exempt from the blocking rule. Decide: does this job's output block merge? If yes, wire it to block. If no, remove it from the quality gate pipeline. |
| "We can't shift left — the expensive test is the first signal we have." | That means no cheaper signal exists yet. Add one: a fast unit test, a type check, a lint pass. The expensive test is a first gate by default, not by design. |

## See also

- [Developer Workflows plugin](Developer-Workflows) — the plugin that ships `/ci-cd`.
- [CI gates](CI-Gates) — the reference for the crickets project's own gate battery.
- [How to run a pre-launch readiness gate with /launch](Add-Launch-Readiness-Gate) — the pre-production companion gate.
