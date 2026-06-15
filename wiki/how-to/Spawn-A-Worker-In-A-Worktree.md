# How to spawn a worker in a worktree

> [!NOTE]
> **Goal:** Give a named plan its own isolated workspace — a `git worktree` on a fresh `worker/<name>` branch, pre-bound to that plan — so a `/work` session run inside it resolves *its* plan without re-passing `--name`, and several workers can run concurrently without colliding in one checkout.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); an **activated** named plan to bind the worker to (author + activate it first — see [Run a named plan](Run-A-Named-Plan)); a clean working tree (no in-flight changes the new worktree would inherit).

There are two operator-authority paths to a worker worktree:

| Path | When to use |
|---|---|
| **`/spawn-worker <name>`** (explicit command) | Coordinator flow: stage + activate a named plan, then hand it to a worker in its own checkout. The command invocation itself is the operator authority. |
| **Config-gated auto-spawn** (`isolation.mode: worktree-per-plan` in `.harness/project.json`) | Set once; every subsequent `/work` or `/bugfix` run auto-spawns a `worker/<slug>` worktree at step 1.5 and finalizes it (push + PR) at the plan's end. The config field is the operator authority — see [ADR 0028](0028-worktree-authority-config-opt-in). |

Both paths are operator authority. Silent authority-free spawn (no command, no config opt-in) stays forbidden per [ADR 0028](0028-worktree-authority-config-opt-in).

This page covers the **explicit-command path**. For the config-gated path, set `isolation.mode: worktree-per-plan` in `.harness/project.json` and run `/work` normally — the isolation check and auto-spawn run automatically. For the full command surface (arguments, the per-worktree plan marker, the guards), see [Named plans](Named-Plans#spawning-a-worker-worktree).

## Steps

1. **Spawn the worker's worktree.** Run `/spawn-worker <name>`, where `<name>` is the activated named-plan slug (`foo`, `PLAN-foo`, and `PLAN-foo.md` all normalize to `foo`). The command runs the helper, which creates a `git worktree` on a fresh `worker/<name>` branch and prints the new worktree path on stdout. By default the worktree lands at `<repo>.worktrees/<name>` beside the repo (so it never shows up in the repo's own `git status`); pass `--worktree-path <path>` to override the location, or `--project-root <path>` if you are not invoking from the repo root.

2. **Confirm the worktree is bound to its plan.** The helper writes the worktree-local `.harness/active-plan` marker holding the **bare slug** `<name>` (plus a trailing newline) — the exact case-preserving form agentm's resolver reads back. Inside the worktree that marker is the per-worktree precedence tier between an explicit `--name` and the singleton, so a `/work` run there resolves `PLAN-<name>.md` with **no `--name` argument and no singleton ambiguity**. (If the repo carries a `vault_project` override that diverges from the `origin` remote basename, the helper also reproduces `.harness/project.json` into the worktree as a fallback; when they match, the copy is skipped.)

3. **Launch a `/work` session in the new worktree.** `cd <worktree-path>` (the path the helper printed), then run `/work` bare — the worktree-local marker binds it to `PLAN-<name>.md`. You do not re-pass `--name`; the marker is the binding.

## Verify

- The worktree exists on its own branch: `git worktree list` shows `<worktree-path>` on branch `worker/<name>`.
- The marker holds the bare slug: `cat <worktree-path>/.harness/active-plan` prints `<name>`.
- A bare `/work` inside the worktree picks up `PLAN-<name>.md` (not the singleton `PLAN.md`).

## Troubleshooting

- **`/spawn-worker` refused (exit 2) and created nothing.** Every guard runs *before* any mutation, so a refusal leaves the repo untouched — there is no partial spawn to clean up. The command refuses when:
  - the target **worktree path already exists** — even a dangling symlink at that path counts (no-clobber);
  - the **`worker/<name>` branch already exists** (no reuse);
  - the **name is empty or the singleton** — `<name>` must be a real named-plan slug; the singleton plan cannot be handed to a worker;
  - the **named plan does not resolve** — an unsafe slug, a dangling `active-plan` marker, or a missing/empty `PLAN-<name>.md`. The resolver's refusal is authoritative and propagated verbatim.

  Do not work around a refusal by mutating the name or path to dodge the guard. Remove the conflicting worktree/branch, or pick a different plan name, then re-run.

- **`/spawn-worker` failed *after* creating the worktree (exit 2) and the message names a survivor.** A failure on the post-create setup path (or a checkout-phase failure inside `git worktree add`) rolls the worktree + branch back automatically — so the normal case is still "nothing left behind." In the rare case the rollback itself can't finish (a git hang, a non-zero `git`), the exit-2 message names **exactly what survived** — the worktree dir, the `worker/<name>` branch, or both. Remove only what it names: `git worktree remove <path>` (or `git worktree remove --force <path>`) for the dir, then `git branch -D worker/<name>` for the branch, then re-run. The message never makes a false clean-rollback claim, so trust it over a guess.

## Related

- [Named plans](Named-Plans) — the lookup: `/spawn-worker`'s arguments, the per-worktree plan marker, and the spawn guards.
- [Run a named plan](Run-A-Named-Plan) — author + stage + activate the plan this worker binds to, then drive `/work --name <slug>` (or bare `/work` inside the bound worktree).
- [See every active plan](See-Every-Active-Plan) — the read-side glance over the plan queue a coordinator reads before spawning a worker.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin this command belongs to.
