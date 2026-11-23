# Developer-Workflows token efficiency

> [!NOTE]
> Status: implemented
> Shipped: crickets v3.14.0, developer-workflows v0.13.0–v0.17.0, 2026-06-14
> Last updated: 2026-11-22 (crickets plan 105: model ids)

> [!NOTE]
> **Routed dispatch came and went (2026-07-04 → 2026-11-22).** The forward pointer that stood here said the phase commands would read [token-audit](crickets-token-audit)'s versioned routing table at each dispatch and print a mandatory fan-out announcement before every sub-agent launch. That layer was built, then taken back out of the phase commands in `development-lifecycle` 1.3.0: the `explorer` dispatch in `/work` and `/bugfix` now names `sonnet` directly, no phase command prints the announcement, and `/plan`'s step template has no `Work-type` or `Tier hint` field (an old plan that carries them still parses). The build-it / create-it loop names a model for each of its passes. token-audit's routing table and its routing-conformance report remain, outside the phase commands.

## Intent

A fresh `developer-workflows` install is token-frugal by default. The goal driving that is a simple one: all-day-autonomous coding on a smaller Claude plan, where the token budget is a hard daily constraint. When tokens are scarce, every session either respects the discipline or burns the day early — so the plugin has to make frugality the path of least resistance, not a thing you remember to do.

The trick is that this discipline is structural, not a matter of willpower. Routing the right model to each phase, staying quiet between tool calls, preferring `Edit` over `Write`, clearing at phase boundaries — these are steady habits, stable enough to bake into the plugin instead of leaving you to remember them. So they ship as built-in defaults, and you get the savings without hand-writing your own token-discipline rules.

The honest limit is that a plugin can only nudge — it cannot pull the levers for you. A hook can notice a session's context is large and suggest `/compact`, but it cannot actuate the command; model routing sets a sensible default per phase, but you can always override it with `--model`. Nudge-only is the ceiling, by design: the primitives lower the friction and keep the reminder in front of you, and the last step stays yours.

The four levers, each mapped to the primitive kind that carries it:

| Lever | Primitive kind | Effect |
|---|---|---|
| Phase-aware model routing | `model:` frontmatter in agent defs + a recommended-model line in command prompts | `/plan`, `/spec`, `/design`, `/build-it`, `/create-it` recommend Sonnet 5.5; `/work`, `/bugfix` recommend `opusplan` |
| Terse output style | `output-style` at `output-styles/terse.md` | Silence between tool calls; preserves the end-of-task status report |
| Edit-over-Write rule | `rule` at `rules/edit-over-write.md` | Prefer `Edit` to `Write` for existing files; `/clear` over `/compact` at phase boundaries |
| Compact-nudge-on-resume hook | `hook` at `hooks/compact-nudge-resume/` | On resumed sessions with large context, emits an `additionalContext` nudge; nudge-only |

## Design

### Model routing: two coverage paths

Agent defs honor `model:` frontmatter: they spawn sub-processes and the host applies the field. `worker.md` and `evaluator.md` pin the `sonnet` alias, so they follow the current Sonnet without a bump when a new generation ships. Slash commands carry a **recommended-model line** at the top of the prompt; you apply it with `/model`.

Routing defaults, as shipped (crickets plan 105, `development-lifecycle` 2.2.0):

- **`/work` and `/bugfix` recommend `opusplan`**: Opus 5.5 plans, Sonnet 5.5 executes the long autonomous stretch.
- **`/plan`, `/spec`, `/design`, `/build-it` and `/create-it` recommend Sonnet 5.5 (`claude-sonnet-5-5`)** for planning, authoring and making. `/build-it` and `/create-it`'s reviewers pick their own models.
- **`worker` and `evaluator` pin `sonnet`.** Plan 105 retired the `researcher` and `tech-lead` agents that this list used to name.

Defaults are operator-overridable via `claude --model` or the `/model` command. The full model × effort tier scale (T0–T4 + the persona→tier map) lives in the [model + effort routing design](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing). The concrete model ids the tier scale draws from live in [token-audit](crickets-token-audit)'s versioned routing table (`src/tokens/scripts/routing_table.py`): its rows name `claude-opus-5-5`, `claude-sonnet-5-5` and `opusplan`, and it recognizes `claude-fable-5-2` without routing to it.

### Terse output style

The terse style is scoped to inter-tool chatter only. The end-of-task status report is explicitly carved out — it must remain detailed. This mirrors the carve-out in the global CLAUDE.md block and is regression-tested by `tests/test_dw_terse_style.py`.

### Edit-over-Write rule

`Write` re-emits the whole file as output tokens (~5x billed), while `Edit` emits only the changed strings. The rule covers the `Edit`-vs-`Write` call and adds a `/clear`-not-`/compact` reminder to `plan.md` and `release.md`'s close-out section — the two commands that mark clean phase boundaries where state is on disk.

### Compact-nudge hook

The hook fires on `UserPromptSubmit` and stays silent below 60% context (read via `CLAUDE_CONTEXT_USAGE_PERCENTAGE` if present, or a JSONL assistant-line count over 400 as a proxy). Above the threshold it emits an `additionalContext` nudge explaining the compact-vs-clear trade-off, including a rough numeric estimate when Part B's `pricing.py` is installed. Nudge-only is the permanent ceiling — hooks cannot actuate `/compact`.

## Implementation

Source locations (`src/development-lifecycle/` unless noted):

- `agents/worker.md`, `agents/evaluator.md` — `model: sonnet`
- `commands/plan.md`, `commands/spec.md`, `commands/build-it.md`, `commands/create-it.md`, `src/design/commands/design.md` — recommended model Sonnet 5.5 (`claude-sonnet-5-5`)
- `commands/work.md`, `commands/bugfix.md` — recommended model `opusplan` (Opus 5.5 plans, Sonnet 5.5 executes)
- `output-styles/terse.md` — the terse output style
- `rules/edit-over-write.md` — the Edit-over-Write rule
- `hooks/compact-nudge-resume/hook.md` — the compact nudge

## Notes

- **Parity with the global directive is the spec.** The operator's `~/.claude/CLAUDE.md` token-discipline block (2026-06-13) is authoritative; any divergence in these primitives is a defect.
- **`output-styles/` and `rules/` are new subdirs within the `developer-workflows` plugin group** — `generate.py` and `lint_src.py` may need generator patches to discover them (task 2 audits first). See the [Composition design](crickets-composition) for the discovery-path decision.
- **Compact-nudge context signal:** `CLAUDE_CONTEXT_USAGE_PERCENTAGE` availability is confirmed at build; JSONL line-count proxy is the documented fallback.

## Related

- [Development lifecycle design](crickets-development-lifecycle) — the routing-defaults design decision, and the history of the routed-dispatch layer noted above
- [Composition design](crickets-composition) — the `output-style`/`rule` discovery-path decision
- [Model + effort routing design](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing) — the T0–T4 tier + effort policy this page's static defaults are a hardcoded instance of
- [Token-audit design](crickets-token-audit) — the measurement + budget-gate capability this efficiency protocol is being automated into, and the **single home of current model ids** (the versioned routing table, seeded and rendered there) plus the `classify_work_type` classifier that resolves a dispatch to one of its rows
- [Customization types](../reference/Customization-Types) — what each primitive kind is
- [Manifest Schema](../reference/Manifest-Schema) — frontmatter contract including `model:` and the discovery table
- [Hooks](../reference/Hooks) — the hook catalog and how `UserPromptSubmit` events work
