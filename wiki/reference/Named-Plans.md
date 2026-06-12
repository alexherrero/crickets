<!-- Status: pending — declares the state of the developer-workflows multi-plan-writers plan (PLAN.md "Multi-plan writers — teach the developer-workflows phase loop to target named plans"). Partially landed: the resolve_plan.py bridge + the /work wiring have shipped (the `/work` rows and the Resolver-bridge section are real today); the `/plan` and `/review` rows remain reserved for the next task. Flip to `implemented` at /release once the whole work/plan/review surface ships and the diff proves it. -->
# Named plans

> [!IMPORTANT]
> **Status: pending — partially landed.** The resolver bridge (`resolve_plan.py`) and the `/work` wiring have shipped: the `/work` rows in the tables below and the [Resolver bridge](#resolver-bridge) section are accurate today. The `/plan` and `/review` rows still declare *future* state reserved by the plan **Multi-plan writers** (`.harness/PLAN.md`) — they flip to live at the next task. The page-level status flips to `implemented` once that whole surface ships.

The `developer-workflows` phase commands `/work`, `/plan`, and `/review` accept an **optional plan name**. With a name they operate on a **named plan pair** — `PLAN-<name>.md` + `progress-<name>.md` — instead of the singleton `PLAN.md` / `progress.md`. This is what lets one shared harness state dir hold several concurrent plans at once. Bare invocations are unchanged: they resolve to the singleton, byte-for-byte as today. Consult this page to look up what a name maps to, how the name is resolved, and the standalone-fallback paths. The task recipe is in [Run a named plan](Run-A-Named-Plan); the *why* is in [Why phase-gating](Why-Phase-Gating).

## ⚡ Quick Reference

| Invocation | Plan file read/written | Progress file appended | Notes |
|---|---|---|---|
| `/work` | `PLAN.md` | `progress.md` | singleton — byte-identical to today |
| `/work <name>` | `PLAN-<name>.md` | `progress-<name>.md` | named pair |
| `/work task N` | `PLAN.md` | `progress.md` | singleton, task selector — unchanged |
| `/work <name> task N` | `PLAN-<name>.md` | `progress-<name>.md` | named pair + task selector |
| `/plan` | `PLAN.md` | `progress.md` | singleton — unchanged |
| `/plan <name>` | `PLAN-<name>.md` (authored) | `progress-<name>.md` | named pair |
| `/review` | `PLAN.md` | — | singleton — unchanged |
| `/review <name>` | `PLAN-<name>.md` | — | named pair |

> [!NOTE]
> Paths above are shown by basename. The actual directory is whatever the resolver returns — `.harness/` in standalone mode, or a hosting memory layer's state dir when one is present (see [Resolution](#resolution)).

## Commands that accept a name

| Command | Argument | Effect with a name |
|---|---|---|
| `/work` | optional leading `<name>` | reads the named PLAN, appends the scoped progress, marks `[x]` in the named PLAN |
| `/plan` | optional leading `<name>` | authors `PLAN-<name>.md`, appends the scoped `progress-<name>.md` line |
| `/review` | optional leading `<name>` | resolves + reads the named pair for adversarial critique |

`/setup`, `/release`, and `/bugfix` do **not** take a plan name in this plan — they remain singleton-only.

## `/work` argument parse rule

`/work` already accepts a `task N` selector, so the leading token is disambiguated as follows:

| Argument | Parsed as |
|---|---|
| _(none)_ | singleton, next unchecked task |
| `task N` | singleton, task N |
| `<name>` | named plan `<name>`, next unchecked task |
| `<name> task N` | named plan `<name>`, task N |

> [!WARNING]
> The literal token `task` is reserved by the selector — a plan named exactly `task` would collide. No such plan exists; slug-safety + naming convention keep it that way. _(Noted, not handled.)_

## Resolution

Named-plan resolution is **not** reimplemented in `developer-workflows`. The commands call a thin bridge script that delegates to the hosting memory layer (agentm) when present, and falls back to plain files otherwise.

| Concern | Owner |
|---|---|
| Precedence: explicit `<name>` → `.harness/active-plan` marker → singleton | agentm `resolve_active_plan` |
| Slug-safety (reject traversal / unsafe names) | agentm `resolve_active_plan`; mirrored in the standalone fallback |
| Dangling-marker loud error (present-but-unresolvable `active-plan`) | agentm `resolve_active_plan`, propagated through the bridge |
| Standalone fallback to plain `.harness/` | the `developer-workflows` bridge |

> [!IMPORTANT]
> This plan **reads** the `.harness/active-plan` marker (via the resolver) but writes none. The explicit `<name>` argument is the binding mechanism. A present-but-unresolvable marker surfaces a **loud error + non-zero exit** through the whole bridge — it never silently falls back to whatever `PLAN.md` happens to be there (the worker→plan mis-binding foot-gun). The sticky per-worktree marker *writer* is a separate, out-of-scope plan.

### Resolver bridge

| Property | Value |
|---|---|
| Script | `${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py` |
| Args | optional positional `name`; `--project-root PATH` (default cwd) |
| Output | one line, tab-separated: `<plan_path>\t<progress_path>` |
| On dangling marker / unsafe slug | non-zero exit + stderr message (never a singleton fallback) |
| Delegate target | agentm `harness_memory.py resolve-active-plan` when locatable; else the standalone fallback |

The bridge locates agentm the same way the session-start hook does: `~/.claude/.agentm-config.json` → `source_clones.agentm`, falling back to `~/Antigravity/agentm/scripts/harness_memory.py`.

## Standalone fallback (no agentm installed)

When no hosting memory layer is locatable, the bridge degrades to plain `.harness/` files — flat, no vault redirect, no marker, no CAS:

| Invocation | Resolves to |
|---|---|
| bare | `.harness/PLAN.md` + `.harness/progress.md` |
| `<name>` | `.harness/PLAN-<name>.md` + `.harness/progress-<name>.md` |
| unsafe slug | rejected locally — non-zero exit, no path printed |

The bare paths are **byte-identical** to today's literals; this is locked by an executable test, not a promise.

## Related

- [Run a named plan](Run-A-Named-Plan) — the task recipe for driving `/work <name>` and friends.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin these commands belong to.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
- [Compatibility](Compatibility) — host support for the phase commands.
