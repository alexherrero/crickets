# Developer-Workflows token efficiency

> [!NOTE]
> Status: implemented
> Shipped: crickets v3.14.0, developer-workflows v0.13.0–v0.17.0, 2026-06-14
> Last updated: 2026-07-04

> [!NOTE]
> **Forward pointer (2026-07-04, designed, not built).** The static per-command routing described below (Sonnet/Opus by phase) is the *interim* state. [token-audit](crickets-token-audit) is gaining a **versioned routing table** (work-type → model+effort tier, the single home of current model ids — colocated with `pricing.py`'s per-model rates), and [development-lifecycle](crickets-development-lifecycle) is being amended so this plugin's dispatch points read that table at dispatch time instead of the hardcoded frontmatter below — with a **mandatory fan-out announcement** at every sub-agent launch (covering built-in-agent inheritance, e.g. Explore ≥2.1.198) and a hard prohibition on silent session-model inheritance. [model-effort-routing](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing) keeps the tier + effort policy only; it no longer carries the concrete model ids itself. Until this lands (`PLAN-efficiency-automation` + `PLAN-efficiency-dispatch`), this page accurately describes what ships today; it will need a follow-up pass once the routed-dispatch layer is built, at which point the table below the routing defaults becomes a rendering of token-audit's versioned data rather than the source of truth itself.

## Intent

A fresh `developer-workflows` install is token-frugal by default. The goal driving that is a simple one: all-day-autonomous coding on a smaller Claude plan, where the token budget is a hard daily constraint. When tokens are scarce, every session either respects the discipline or burns the day early — so the plugin has to make frugality the path of least resistance, not a thing you remember to do.

The trick is that this discipline is structural, not a matter of willpower. Routing the right model to each phase, staying quiet between tool calls, preferring `Edit` over `Write`, clearing at phase boundaries — these are steady habits, stable enough to bake into the plugin instead of leaving you to remember them. So they ship as built-in defaults, and you get the savings without hand-writing your own token-discipline rules.

The honest limit is that a plugin can only nudge — it cannot pull the levers for you. A hook can notice a session's context is large and suggest `/compact`, but it cannot actuate the command; model routing sets a sensible default per phase, but you can always override it with `--model`. Nudge-only is the ceiling, by design: the primitives lower the friction and keep the reminder in front of you, and the last step stays yours.

The four levers, each mapped to the primitive kind that carries it:

| Lever | Primitive kind | Effect |
|---|---|---|
| Phase-aware model routing | `model:` frontmatter in agent defs + routing nudge in command prompts | `/plan`, `/review`, `/design` default to Sonnet; `/work`, `/bugfix` default to Opus |
| Terse output style | `output-style` at `output-styles/terse.md` | Silence between tool calls; preserves the end-of-task status report |
| Edit-over-Write rule | `rule` at `rules/edit-over-write.md` | Prefer `Edit` to `Write` for existing files; `/clear` over `/compact` at phase boundaries |
| Compact-nudge-on-resume hook | `hook` at `hooks/compact-nudge-resume/` | On resumed sessions with large context, emits an `additionalContext` nudge; nudge-only |

## Design

### Model routing: two coverage paths

Agent defs (`worker.md`, `researcher.md`, `tech-lead.md`) honor `model:` frontmatter — they spawn sub-processes and the host applies the field. Slash commands (`/plan`, `/work`, etc.) carry a `model:` + `effort:` frontmatter pin applied for the turn the command runs (turn-scoped host enforcement, not the advisory-only nudge this page originally shipped with — see the [model-effort-routing design](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing)'s 2026-07-04 P14c amendment).

Routing defaults, as designed:

- **`/work` and `/bugfix` run under `opusplan`** — the T1 · Execute build default (Opus plans, then Sonnet executes), not flat Opus. The global session default (`~/.claude/settings.json`, `"model": "opusplan"`) already carries this; each command's own nudge text has not caught up (see the correction below).
- **Sonnet — the current generation, `claude-sonnet-5`:** `worker.md` (the spawned executor, **T1**), `researcher.md`, `tech-lead.md`, `/plan`, `/review`, `/design` — planning, authoring, read-only research, and execution.

Defaults are operator-overridable via `claude --model` or the `/model` command. The full model × effort tier scale (T0–T4 + the persona→tier map) lives in the [model + effort routing design](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing); `worker.md` is realigned to **T1** there. The concrete model ids the tier scale currently draws from — including the T1/T0 seed rows and where a work-type resolves to `opusplan` vs. flat Sonnet — live in [token-audit](crickets-token-audit)'s versioned routing table, resolved per dispatch by its `classify_work_type` classifier (see both links below).

**Two corrections, live and already-fired, not hypothetical:**

- **The agent-def frontmatter and every command's nudge text still name `claude-sonnet-4-6` (and `claude-opus-4-8` for `/work`/`/bugfix`), not `claude-sonnet-5`.** `pricing.py` added the `claude-sonnet-5` row on 2026-07-03 (the same R0.7 repair pass); the roster hasn't been bumped to match. This is the content-refresh trigger the model-effort-routing design already names, caught live — see the Implementation table below for exactly which files.
- **No command's nudge text mentions `opusplan` at all** — `work.md` and `bugfix.md` both recommend flat "Opus 4.8," which understates what actually runs: the global default is `opusplan` (Opus plans, Sonnet executes), a two-model split, not a single strong model straight through.

### Terse output style

The terse style is scoped to inter-tool chatter only. The end-of-task status report is explicitly carved out — it must remain detailed. This mirrors the carve-out in the global CLAUDE.md block and is regression-tested by `tests/test_dw_terse_style.py`.

### Edit-over-Write rule

`Write` re-emits the whole file as output tokens (~5x billed), while `Edit` emits only the changed strings. The rule covers the `Edit`-vs-`Write` call and adds a `/clear`-not-`/compact` reminder to `plan.md` and `release.md`'s close-out section — the two commands that mark clean phase boundaries where state is on disk.

### Compact-nudge hook

The hook fires on `UserPromptSubmit` and stays silent below 60% context (read via `CLAUDE_CONTEXT_USAGE_PERCENTAGE` if present, or a JSONL assistant-line count over 400 as a proxy). Above the threshold it emits an `additionalContext` nudge explaining the compact-vs-clear trade-off, including a rough numeric estimate when Part B's `pricing.py` is installed. Nudge-only is the permanent ceiling — hooks cannot actuate `/compact`.

## Implementation

Source locations, with each roster string's **current** (stale) vs. **target** value — the bump itself is `[PENDING-IMPL]`, tracked as a `PLAN-efficiency-automation` task, not yet applied:

- `src/developer-workflows/agents/worker.md` — `model: claude-sonnet-4-6` → target `claude-sonnet-5`
- `src/developer-workflows/agents/researcher.md` — `model: claude-sonnet-4-6` → target `claude-sonnet-5`
- `src/developer-workflows/agents/tech-lead.md` — `model: claude-sonnet-4-6` → target `claude-sonnet-5`
- `src/developer-workflows/commands/plan.md` — nudge text names `claude-sonnet-4-6` → target `claude-sonnet-5`; gains a `model:`/`effort:` frontmatter pin (turn-scoped, replacing the nudge) + keeps the `/clear` reminder
- `src/developer-workflows/commands/work.md` — nudge text names flat `claude-opus-4-8` → target: name `opusplan` explicitly (not a single model); gains a `model:`/`effort:` frontmatter pin
- `src/developer-workflows/commands/review.md` — nudge text names `claude-sonnet-4-6` → target `claude-sonnet-5`; gains a `model:`/`effort:` frontmatter pin
- `src/developer-workflows/commands/design.md` — nudge text names `claude-sonnet-4-6` → target `claude-sonnet-5`; gains a `model:`/`effort:` frontmatter pin
- `src/developer-workflows/commands/bugfix.md` — nudge text names flat `claude-opus-4-8` → target: name `opusplan` explicitly; gains a `model:`/`effort:` frontmatter pin + keeps the `/clear` reminder
- `src/developer-workflows/commands/spec.md`, `commands/interview-me.md` — nudge text names `claude-sonnet-4-6` → target `claude-sonnet-5`
- `src/developer-workflows/output-styles/terse.md` — new primitive
- `src/developer-workflows/rules/edit-over-write.md` — new primitive
- `src/developer-workflows/hooks/compact-nudge-resume/hook.md` — new primitive

## Notes

- **Parity with the global directive is the spec.** The operator's `~/.claude/CLAUDE.md` token-discipline block (2026-06-13) is authoritative; any divergence in these primitives is a defect.
- **`output-styles/` and `rules/` are new subdirs within the `developer-workflows` plugin group** — `generate.py` and `lint_src.py` may need generator patches to discover them (task 2 audits first). See the [Composition design](crickets-composition) for the discovery-path decision.
- **Compact-nudge context signal:** `CLAUDE_CONTEXT_USAGE_PERCENTAGE` availability is confirmed at build; JSONL line-count proxy is the documented fallback.

## Related

- [Development lifecycle design](crickets-development-lifecycle) — the routing-defaults design decision *(gaining the routed-dispatch + mandatory-announcement layer — see the forward pointer above)*
- [Composition design](crickets-composition) — the `output-style`/`rule` discovery-path decision
- [Model + effort routing design](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing) — the T0–T4 tier + effort policy this page's static defaults are a hardcoded instance of
- [Token-audit design](crickets-token-audit) — the measurement + budget-gate capability this efficiency protocol is being automated into, and the **single home of current model ids** (the versioned routing table, seeded and rendered there) plus the `classify_work_type` classifier that resolves a dispatch to one of its rows
- [Customization types](../reference/Customization-Types) — what each primitive kind is
- [Manifest Schema](../reference/Manifest-Schema) — frontmatter contract including `model:` and the discovery table
- [Hooks](../reference/Hooks) — the hook catalog and how `UserPromptSubmit` events work
