# How to run a named plan

> [!NOTE]
> **Goal:** Drive a `developer-workflows` phase (`/work`, `/plan`, `/review`) against a **named** plan pair — `PLAN-<slug>.md` + `progress-<slug>.md` — so several concurrent plans can share one harness state dir, instead of being limited to the singleton `PLAN.md` / `progress.md`.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); a chosen, slug-safe plan name. Optional: a hosting memory layer (agentm) — when present, resolution is delegated to it; when absent, plans degrade to plain `.harness/PLAN-<slug>.md` + `.harness/progress-<slug>.md` (see [Named plans](Named-Plans)).

Use a named plan when you want more than one plan in flight at once — the wedge behind the coordinator-directed agent team. Bare `/work` / `/plan` / `/review` keep operating on the singleton, unchanged; adding `--name <slug>` is purely additive. For the full mapping of invocation → files, see [Named plans](Named-Plans).

## Prerequisites

- The `developer-workflows` plugin installed on your host ([Install crickets plugins](Install-Into-Project)).
- A slug-safe plan name (no path traversal; the resolver rejects unsafe names).
- _Optional:_ agentm installed as the hosting memory layer, for vault-backed state + the precedence chain. Without it, named plans live flat in `.harness/`.

## Steps

1. **Author the named plan.** Run `/plan --name <slug> <brief>` to write `PLAN-<slug>.md` (and seed its `progress-<slug>.md`). The `--name <slug>` flag selects the named pair; everything else in the arguments is the brief. Bare `/plan <brief>` (no `--name`) authors the singleton `PLAN.md`, unchanged.

2. **Work the named plan.** Run `/work --name <slug>` to work `PLAN-<slug>.md`'s task list, appending to `progress-<slug>.md`. The `--name <slug>` flag and the `task N` selector are independent — combine them (`/work --name <slug> task N`) to work a specific task of a named plan.

   `/work`'s "Read state" step resolves the pair by passing the slug positionally to `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" [<slug>]` (omit it for the singleton). A non-zero exit from the resolver is a **hard stop**: `/work` never falls back to the singleton on a dangling marker or unsafe slug. The task-mark (`[x]`) and the progress append at the end of the run both target the **resolved** pair, so `/work --name <slug>` writes `PLAN-<slug>.md` + `progress-<slug>.md` and bare `/work` stays byte-identical to the singleton.

3. **Review the named plan.** Run `/review --name <slug>` to run the adversarial pass against the named pair — it reads `PLAN-<slug>.md` for the task context and logs the outcome to `progress-<slug>.md`. Any remaining argument (a commit range, branch, or `task N`) still scopes *what* is reviewed, independent of `--name`. Bare `/review` (no `--name`) reviews against the singleton, unchanged.

4. **Confirm what a name resolves to** (when in doubt about which files a name maps to). The bridge takes the slug **positionally** — this is a direct call to the resolver, not a slash command, so there's no `--name` flag here:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py" <slug>
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
