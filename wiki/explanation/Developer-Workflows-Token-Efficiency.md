# Developer-Workflows token efficiency

> [!NOTE]
> Status: implemented
> Shipped: crickets v3.14.0, developer-workflows v0.13.0–v0.17.0, 2026-06-14
> Last updated: 2026-06-29

## Intent

A fresh `developer-workflows` install is token-frugal by default. The goal driving that is a simple one: all-day-autonomous coding on a smaller Claude plan, where the token budget is a hard daily constraint. When tokens are scarce, every session either respects the discipline or burns the day early — so the plugin has to make frugality the path of least resistance, not a thing you remember to do.

The insight is that the discipline is structural, not a matter of per-session willpower. Routing the right model to each phase, staying quiet between tool calls, preferring `Edit` over `Write`, clearing at phase boundaries — these are stable enough to bake into the plugin rather than repeat as reminders. So they ship as durable primitives, and an adopter gets the savings without carrying a personal `~/.claude/CLAUDE.md` token-discipline block. The four levers below mirror that global block (2026-06-13) so the two stay in step.

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

Agent defs (`worker.md`, `researcher.md`, `tech-lead.md`) honor `model:` frontmatter — they spawn sub-processes and the host applies the field. Slash commands (`/plan`, `/work`, etc.) run in-session and cannot enforce a model at the primitive level; they carry a one-line "Recommended model for this phase" nudge in the prompt body instead.

Routing defaults:

- **Strong model (Opus):** the `/work` and `/bugfix` command nudges — autonomous task execution where quality cliffs are most costly (the strong-model planning side of `opusplan`, which executes on Sonnet).
- **Lighter model (Sonnet):** `worker.md` (the spawned executor, **T1**), `researcher.md`, `tech-lead.md`, `/plan`, `/review`, `/design` — planning, authoring, read-only research, and execution.

Defaults are operator-overridable via `claude --model` or the `/model` command. The full model × effort tier scale (T0–T4 + the persona→tier map) lives in the [model + effort routing design](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing); `worker.md` is realigned to **T1** (Sonnet) there.

### Terse output style

Scoped to inter-tool chatter only. The end-of-task status report is explicitly carved out — it must remain detailed. This mirrors the carve-out in the global CLAUDE.md block and is regression-tested by `tests/test_dw_terse_style.py`.

### Edit-over-Write rule

Prose rationale: `Write` re-emits the whole file as output tokens (~5x billed); `Edit` emits only the changed strings. The rule covers the `Edit`-vs-`Write` call and adds a `/clear`-not-`/compact` reminder to `plan.md` and `release.md`'s close-out section — the two commands that mark clean phase boundaries where state is on disk.

### Compact-nudge hook

Trigger: `UserPromptSubmit`. Threshold: context >= 60% (via `CLAUDE_CONTEXT_USAGE_PERCENTAGE` if present, or JSONL assistant-line count > 400 as proxy). Below threshold: silent no-op. Above threshold: emits `additionalContext` nudge explaining the compact-vs-clear trade-off. If Part B's `pricing.py` is installed, includes a rough numeric estimate. Nudge-only is the permanent ceiling — hooks cannot actuate `/compact`.

## Implementation

Source locations:

- `src/developer-workflows/agents/worker.md` — `model: claude-sonnet-4-6` frontmatter
- `src/developer-workflows/agents/researcher.md` — `model: claude-sonnet-4-6` frontmatter
- `src/developer-workflows/agents/tech-lead.md` — `model: claude-sonnet-4-6` frontmatter
- `src/developer-workflows/commands/plan.md` — routing nudge line + `/clear` reminder
- `src/developer-workflows/commands/work.md` — routing nudge line
- `src/developer-workflows/commands/review.md` — routing nudge line
- `src/developer-workflows/commands/design.md` — routing nudge line
- `src/developer-workflows/commands/bugfix.md` — routing nudge line + `/clear` reminder
- `src/developer-workflows/output-styles/terse.md` — new primitive
- `src/developer-workflows/rules/edit-over-write.md` — new primitive
- `src/developer-workflows/hooks/compact-nudge-resume/hook.md` — new primitive

## Notes

- **Parity with the global directive is the spec.** The operator's `~/.claude/CLAUDE.md` token-discipline block (2026-06-13) is authoritative; any divergence in these primitives is a defect.
- **`output-styles/` and `rules/` are new subdirs within the `developer-workflows` plugin group** — `generate.py` and `lint_src.py` may need generator patches to discover them (task 2 audits first). See the [Composition design](crickets-composition) for the discovery-path decision.
- **Compact-nudge context signal:** `CLAUDE_CONTEXT_USAGE_PERCENTAGE` availability is confirmed at build; JSONL line-count proxy is the documented fallback.

## Related

- [Development lifecycle design](crickets-development-lifecycle) — the routing-defaults design decision
- [Composition design](crickets-composition) — the `output-style`/`rule` discovery-path decision
- [Customization types](../reference/Customization-Types) — what each primitive kind is
- [Manifest Schema](../reference/Manifest-Schema) — frontmatter contract including `model:` and the discovery table
- [Hooks](../reference/Hooks) — the hook catalog and how `UserPromptSubmit` events work
