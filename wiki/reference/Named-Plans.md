# Named plans

The `developer-workflows` phase commands `/work`, `/plan`, and `/review` accept an **optional `--name <slug>` flag**. With a name they operate on a **named plan pair** — `PLAN-<slug>.md` + `progress-<slug>.md` — instead of the singleton `PLAN.md` / `progress.md`. This is what lets one shared harness state dir hold several concurrent plans at once. Bare invocations are unchanged: they resolve to the singleton, byte-for-byte as today. Consult this page to look up what a name maps to, how the name is resolved, the standalone-fallback paths, and the read-only `/queue-status-lite` command that lists the whole queue. The task recipes are in [Run a named plan](Run-A-Named-Plan) and [See every active plan](See-Every-Active-Plan); the *why* is in [Why phase-gating](Why-Phase-Gating).

## ⚡ Quick Reference

| Invocation | Plan file read/written | Progress file appended | Notes |
|---|---|---|---|
| `/work` | `PLAN.md` | `progress.md` | singleton — byte-identical to today |
| `/work --name <slug>` | `PLAN-<slug>.md` | `progress-<slug>.md` | named pair |
| `/work task N` | `PLAN.md` | `progress.md` | singleton, task selector — unchanged |
| `/work --name <slug> task N` | `PLAN-<slug>.md` | `progress-<slug>.md` | named pair + task selector |
| `/plan` | `PLAN.md` | `progress.md` | singleton — unchanged |
| `/plan --name <slug>` | `PLAN-<slug>.md` (authored) | `progress-<slug>.md` | named pair |
| `/review` | `PLAN.md` | — | singleton — unchanged |
| `/review --name <slug>` | `PLAN-<slug>.md` | — | named pair |

> [!NOTE]
> Paths above are shown by basename. The actual directory is whatever the resolver returns — `.harness/` in standalone mode, or a hosting memory layer's state dir when one is present (see [Resolution](#resolution)).

## Commands that accept a name

| Command | Argument | Effect with a name |
|---|---|---|
| `/work` | optional `--name <slug>` (anywhere in args) | reads the named PLAN, appends the scoped progress, marks `[x]` in the named PLAN |
| `/plan` | optional `--name <slug>` (anywhere in args) | authors `PLAN-<slug>.md`, appends the scoped `progress-<slug>.md` line |
| `/review` | optional `--name <slug>` (anywhere in args) | resolves + reads the named pair for adversarial critique |

`/setup`, `/release`, and `/bugfix` do **not** take a plan name in this plan — they remain singleton-only.

## Reading the queue — `/queue-status-lite`

The read complement to the `--name` writers above. `/queue-status-lite` lists **every** active plan in the harness dir — for each, its name, its `Status:` line, and the most-recent entry of the matching `progress*.md` — and prints that dashboard. It takes **no** `--name` flag: it enumerates the whole queue, not one pair. It is the coordinator's *glance* — **read-only by contract**: no claim, no lease, no arbitration, no writes. It surfaces the queue and decides nothing; the human stays the arbiter of who works which plan. It is **not a gate**. The task recipe is in [See every active plan](See-Every-Active-Plan).

| Property | Value |
|---|---|
| Command | `/queue-status-lite` |
| Argument | optional `--harness-dir <path>` (default: resolve from cwd) |
| Active plans listed | `PLAN.md` plus every `PLAN-<slug>.md` (archives + GDrive conflict copies skipped) |
| Per-plan output | name · `Status:` line · last `progress*.md` line |
| Mutates | nothing — reads and prints only |
| Exit | `0` in normal use (a status read, never a gate) — `0` even when there is no harness dir to read |

### Read bridge

`/queue-status-lite` calls a bridge script that mirrors the resolver bridge's **two backends, one contract** shape (see [Resolution](#resolution) above):

| Property | Value |
|---|---|
| Script | `${CLAUDE_PLUGIN_ROOT}/scripts/queue_status.py` |
| Args | optional `--harness-dir PATH` (default: resolve from cwd) |
| Output | a deterministic, human-scannable dashboard block on stdout |
| Delegate target | agentm's shipped `queue_status_lite.py` reader when an agentm clone is locatable |
| Standalone fallback | a minimal local `.harness/` dashboard mirroring the reader's format |

When an agentm clone is installed the bridge **delegates** to agentm's `queue_status_lite.py` and re-emits its stdout verbatim — that reader is the single owner of the enumeration + render (naming contract, GDrive-conflict skipping, vault redirection). With no clone the bridge renders the minimal local dashboard itself, so the glance degrades rather than vanishing — a clean graceful-skip, never an error. It imports the agentm-clone lookup and the PLAN→progress naming helpers from the resolver bridge (`resolve_plan.py`), so that logic has one owner and is never copied.

> [!NOTE]
> `/queue-status-lite` adds **zero** agentm changes: it direct-shells to the *already-shipped* standalone reader — no new agentm verb. It is the read side of the multi-plan surface whose writers are the `--name`-aware `/work` / `/plan` / `/review` above.

## `/work` argument parse rule

The `--name <slug>` flag selects the plan; it can appear anywhere in the arguments and **cannot collide** with the `task N` selector, a brief, a branch, or a commit range. Positional slots keep their meaning — for `/work` that's the `task N` selector. The two are independent:

| Argument | Parsed as |
|---|---|
| _(none)_ | singleton, next unchecked task |
| `task N` | singleton, task N |
| `--name <slug>` | named plan `<slug>`, next unchecked task |
| `--name <slug> task N` | named plan `<slug>`, task N |

> [!NOTE]
> Slugs are slug-safe — the resolver rejects path traversal and unsafe names (non-zero exit, no path printed). A plan whose slug is a reserved positional word (e.g. `task`) is still reachable unambiguously via `--name task`, because the flag never competes with positional slots.

## Resolution

Named-plan resolution is **not** reimplemented in `developer-workflows`. The commands call a thin bridge script that delegates to the hosting memory layer (agentm) when present, and falls back to plain files otherwise.

| Concern | Owner |
|---|---|
| Precedence: explicit name → `.harness/active-plan` marker → singleton | agentm `resolve_active_plan` |
| Slug-safety (reject traversal / unsafe names) | agentm `resolve_active_plan`; mirrored in the standalone fallback |
| Dangling-marker loud error (present-but-unresolvable `active-plan`) | agentm `resolve_active_plan`, propagated through the bridge |
| Standalone fallback to plain `.harness/` | the `developer-workflows` bridge |

> [!IMPORTANT]
> The commands **read** the `.harness/active-plan` marker (via the resolver) but write none. The explicit `--name <slug>` flag is the binding mechanism. A present-but-unresolvable marker surfaces a **loud error + non-zero exit** through the whole bridge — it never silently falls back to whatever `PLAN.md` happens to be there (the worker→plan mis-binding foot-gun). The sticky per-worktree marker *writer* is a separate, out-of-scope plan.

### Resolver bridge

| Property | Value |
|---|---|
| Script | `${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py` |
| Args | optional positional `name`; `--project-root PATH` (default cwd) |
| Output | one line, tab-separated: `<plan_path>\t<progress_path>` |
| On dangling marker / unsafe slug | non-zero exit + stderr message (never a singleton fallback) |
| Delegate target | agentm `harness_memory.py resolve-active-plan` when locatable; else the standalone fallback |

The `--name <slug>` flag is a **command-level** convention: `/work`, `/plan`, and `/review` parse it out of their arguments and pass the extracted slug **positionally** to this bridge — the bridge's own CLI takes the name as a positional argument, not a flag. The bridge locates agentm the same way the session-start hook does: `~/.claude/.agentm-config.json` → `source_clones.agentm`, falling back to `~/Antigravity/agentm/scripts/harness_memory.py`.

## Standalone fallback (no agentm installed)

When no hosting memory layer is locatable, the bridge degrades to plain `.harness/` files — flat, no vault redirect, no marker, no CAS:

| Resolver input (positional) | Resolves to |
|---|---|
| bare (no slug) | `.harness/PLAN.md` + `.harness/progress.md` |
| `<slug>` | `.harness/PLAN-<slug>.md` + `.harness/progress-<slug>.md` |
| unsafe slug | rejected locally — non-zero exit, no path printed |

The bare paths are **byte-identical** to today's literals; this is locked by an executable test, not a promise.

## Related

- [Run a named plan](Run-A-Named-Plan) — the task recipe for driving `/work --name <slug>` and friends.
- [See every active plan](See-Every-Active-Plan) — the read-side recipe: `/queue-status-lite` for a one-glance view of the queue.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin these commands belong to.
- [Why phase-gating](Why-Phase-Gating) — why the loop is gated and state lives on disk.
- [Compatibility](Compatibility) — host support for the phase commands.
