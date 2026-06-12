<!-- Status: pending — declares the future how-to for the developer-workflows multi-plan-writers plan (.harness/PLAN.md "Multi-plan writers"). Partially landed: the resolve_plan.py bridge + the /work wiring (Step 2 + the Step 4 resolver call) have shipped; the /plan and /review steps (Steps 1 and 3) are still placeholders until that task lands. Flip to implemented at /release once the full /work + /plan + /review surface ships and the diff proves it. -->
# How to run a named plan

> [!NOTE]
> **Goal:** Drive a `developer-workflows` phase (`/work`, `/plan`, `/review`) against a **named** plan pair — `PLAN-<name>.md` + `progress-<name>.md` — so several concurrent plans can share one harness state dir, instead of being limited to the singleton `PLAN.md` / `progress.md`.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); a chosen, slug-safe plan name. Optional: a hosting memory layer (agentm) — when present, resolution is delegated to it; when absent, plans degrade to plain `.harness/PLAN-<name>.md` + `.harness/progress-<name>.md` (see [Named plans](Named-Plans)).

> [!IMPORTANT]
> **Status: pending — partially landed.** The `resolve_plan.py` bridge and the `/work` wiring have shipped: **Step 2 (work the named plan)** and the **Step 4 resolver check** are live today. **Step 1 (`/plan`)** and **Step 3 (`/review`)** are still placeholders, reserved by the plan **Multi-plan writers** (`.harness/PLAN.md`) for the next task. This page flips to `implemented` once that whole surface ships.

Use a named plan when you want more than one plan in flight at once — the wedge behind the coordinator-directed agent team. Bare `/work` / `/plan` / `/review` keep operating on the singleton, unchanged; adding a `<name>` is purely additive. For the full mapping of invocation → files, see [Named plans](Named-Plans).

## Prerequisites

- The `developer-workflows` plugin installed on your host ([Install crickets plugins](Install-Into-Project)).
- A slug-safe plan name (no path traversal; the resolver rejects unsafe names).
- _Optional:_ agentm installed as the hosting memory layer, for vault-backed state + the precedence chain. Without it, named plans live flat in `.harness/`.

## Steps

1. **Author the named plan.** Run `/plan <name> <brief>` to write `PLAN-<name>.md` (and seed its `progress-<name>.md`).

   _Filled by /work once the task ships._

2. **Work the named plan.** Run `/work <name>` to work `PLAN-<name>.md`'s task list, appending to `progress-<name>.md`. Add a `task N` selector after the name (`/work <name> task N`) to pick a specific task.

   `/work`'s "Read state" step resolves the pair by calling `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<name>]` — the leading token is parsed as `<name>` / `task N` / `<name> task N` (or none → singleton, next unchecked task). A non-zero exit from the resolver is a **hard stop**: `/work` never falls back to the singleton on a dangling marker or unsafe slug. The task-mark (`[x]`) and the progress append at the end of the run both target the **resolved** pair, so `/work <name>` writes `PLAN-<name>.md` + `progress-<name>.md` and bare `/work` stays byte-identical to the singleton.

3. **Review the named plan.** Run `/review <name>` to run the adversarial pass against the named pair.

   _Filled by /work once the task ships._

4. **Confirm what a name resolves to** (when in doubt about which files a name maps to):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <name>
   ```

   It prints one tab-separated line — `<plan_path>\t<progress_path>` — or exits non-zero with a stderr message on a dangling marker or unsafe slug (never a silent singleton fallback).

## Troubleshooting

- **A bare `/work` picked up the wrong plan.** A present-but-unresolvable `.harness/active-plan` marker surfaces a loud error + non-zero exit rather than silently running the singleton. Resolve or remove the marker — never assume the singleton ran. See [Named plans § Resolution](Named-Plans#resolution).
- **The name was rejected.** Names are slug-safe; traversal or unsafe characters are refused. Pick a plain name.

## Related

- [Named plans](Named-Plans) — the lookup: invocation → files, the parse rule, the resolver + standalone-fallback paths.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin these commands belong to.
- [Install crickets plugins](Install-Into-Project) — get `developer-workflows` onto your host.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
