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
| `/plan --name <slug>` | `PLAN-<slug>.md` (authored, **active**) | `progress-<slug>.md` | named pair, active tier |
| `/plan --stage <slug>` | `queued-plans/PLAN-<slug>.md` (authored, **staged/inert**) | — | staging tier ([Two-tier staging](#two-tier-named-plan-staging)) |
| `/plan --activate <slug>` | `queued-plans/PLAN-<slug>.md` → `PLAN-<slug>.md` (promoted) | — | promotes staged → active |
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

## Two-tier named-plan staging

> [!NOTE]
> Shipped in `developer-workflows` 0.5.0. The active-tier `--name` write and the singleton write above are **unchanged** — staging is purely additive.

`/plan` gains a second tier. Alongside writing the **active** named plan directly (`--name`), a coordinator can **stage** a plan into an inactive tier and **activate** it later when a worker picks it up. Staged plans are **inert** — invisible to `/work` and `/queue-status-lite` until activated.

### The four `/plan` modes

| Mode | Writes | Tier | Seen by `/work` & `/queue-status-lite`? |
|---|---|---|---|
| `/plan <brief>` | `PLAN.md` | singleton | yes |
| `/plan --name <slug> <brief>` | `PLAN-<slug>.md` | active | yes |
| `/plan --stage <slug> <brief>` | `queued-plans/PLAN-<slug>.md` | **staging (inert)** | **no** — until activated |
| `/plan --activate <slug>` | promotes `queued-plans/PLAN-<slug>.md` → `PLAN-<slug>.md` | staging → active | yes, after promotion |

### Staging tier

| Property | Value |
|---|---|
| Staging dir | `<harness>/queued-plans/` — **flat** (crickets flat-vault convention) |
| Staged plan file | `queued-plans/PLAN-<slug>.md` |
| Visibility | inert — not resolved by `/work --name`, not listed by `/queue-status-lite`, until activated |
| Active path it activates into | `<harness>/PLAN-<slug>.md` (the path `/work --name <slug>` reads) |
| Harness dir | whatever the resolver returns — vault-backed `_harness/` when a memory layer is present, `.harness/` standalone (see [Resolution](#resolution)) |

### `--activate` guard

`/plan --activate <slug>` is a **guarded copy** — it hard-stops (non-zero exit, no silent fallback) when promotion would be unsafe:

| Condition | Behavior |
|---|---|
| Active `PLAN-<slug>.md` already exists | refuse — would clobber an active plan |
| Staged `queued-plans/PLAN-<slug>.md` missing | refuse — nothing to promote |
| Both clear | copy `queued-plans/PLAN-<slug>.md` → `PLAN-<slug>.md` |

### Implementation

A new `scripts/stage_plan.py` (stdlib-only, pure-core + injectable resolver, mirroring `resolve_plan.py`) owns both verbs. It is **composed onto** `resolve_plan.resolve` — it never re-derives the `_harness/` location or the vault redirect; it takes the resolved *active* `PLAN-<slug>.md` and composes `queued-plans/` onto its parent.

| Component | Location | Role |
|---|---|---|
| `staging_path()` | [`stage_plan.py:87`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L87) | Composes `queued-plans/` onto the active path the resolver returns → `<_harness>/queued-plans/PLAN-<slug>.md`. Read-only; emits the path. |
| `activate()` | [`stage_plan.py:101`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L101) | The guarded copy. Refuses (exit 2, writes nothing) on missing staged file ([`:115`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L115)) or active-plan collision ([`:116`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L116), "refusing to clobber"). Copies bytes verbatim; leaves the staged file in place (copy, not move). |
| `_active_plan_path()` | [`stage_plan.py:70`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L70) | Named-only guard — refuses an empty/singleton name (exit 2, "staging requires a named plan") at [`:79`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L79) *before* the resolver is consulted. The singleton `PLAN.md` is the active default; there is nothing to stage for it. |
| `_QUEUED_DIR = "queued-plans"` | [`stage_plan.py:65`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L65) | The flat staging-dir name (crickets flat-vault convention). |
| CLI verbs `path` / `activate` | [`stage_plan.py:127`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/stage_plan.py#L127) (`_build_parser`) | Invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/stage_plan.py" path <slug>` and `... activate <slug>`. Exit codes align with `resolve_plan.py`: `0` ok, `1` graceful-skip propagated from the resolver, `2` loud refusal. |

The `--stage` / `--activate` modes are wired in [`commands/plan.md:35`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/plan.md#L35) (the four-mode block; `--stage` bullet at [`:39`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/plan.md#L39), `--activate` bullet at [`:40`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/plan.md#L40)) with an updated `argument-hint` at [`:8`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/commands/plan.md#L8).

The **staged = inert** invariant is free, not a new change: `queue_status._list_plan_files` root-globs `PLAN-*.md` **non-recursively** ([`queue_status.py:138`](https://github.com/alexherrero/crickets/blob/main/src/developer-workflows/scripts/queue_status.py#L138)), so the `queued-plans/` subdir is naturally skipped — that is the load-bearing reason staged plans are invisible to `/queue-status-lite`. `queue_status.py` was **not** modified for staging.

Locked by `scripts/test_stage_plan.py` — 14 hermetic tests over both resolver backends (standalone `.harness/` fallback + a stub proving the vault redirect is honored, not `<root>/.harness`), the three `activate` guards (happy-path bytes-verbatim, collision-refuses-leaving-active-untouched, missing-staged-refuses), copy-not-move, the negative invariant that a staged plan is not returned by `queue_status._list_plan_files`, and the `main()` CLI.

> [!NOTE]
> **Not in scope of this plan:** surfacing staged plans in `/queue-status-lite` (staged = inactive *by design*). The queue glance continues to list only the active tier — see [Reading the queue](#reading-the-queue--queue-status-lite).

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
