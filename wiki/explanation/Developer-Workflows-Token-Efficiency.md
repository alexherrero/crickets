# Developer-Workflows token efficiency

> [!NOTE]
> Status: pending
> Plan: Part D — Phase-aware model routing + Tier-1 lever codification (agentm #46)
> Last updated: 2026-06-14

> [!IMPORTANT]
> **Pending** — four primitives are under construction: phase-aware model routing (task 1), a Terse output style (task 2), an Edit-over-Write rule (task 3), and a compact-nudge-on-resume hook (task 4). This page will flip to `implemented` once all four ship and `check-all.sh` is green.

## Intent

A fresh `developer-workflows` install is token-frugal by default. The operator should not have to carry a personal `~/.claude/CLAUDE.md` token-discipline block to benefit from these patterns — they are structural enough to ship as durable plugin primitives.

The four levers mirror the operator's global token-discipline block (2026-06-13) for adopters:

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

- **Strong model (Opus):** `worker.md`, `/work`, `/bugfix` — autonomous task execution where quality cliffs are most costly.
- **Lighter model (Sonnet):** `researcher.md`, `tech-lead.md`, `/plan`, `/review`, `/design` — planning, authoring, read-only research.

Defaults are operator-overridable via `claude --model` or the `/model` command.

### Terse output style

Scoped to inter-tool chatter only. The end-of-task status report is explicitly carved out — it must remain detailed. This mirrors the carve-out in the global CLAUDE.md block and is regression-tested by `tests/test_dw_terse_style.py`.

### Edit-over-Write rule

Prose rationale: `Write` re-emits the whole file as output tokens (~5x billed); `Edit` emits only the changed strings. The rule covers the `Edit`-vs-`Write` call and adds a `/clear`-not-`/compact` reminder to `plan.md` and `release.md`'s close-out section — the two commands that mark clean phase boundaries where state is on disk.

### Compact-nudge hook

Trigger: `UserPromptSubmit`. Threshold: context >= 60% (via `CLAUDE_CONTEXT_USAGE_PERCENTAGE` if present, or JSONL assistant-line count > 400 as proxy). Below threshold: silent no-op. Above threshold: emits `additionalContext` nudge explaining the compact-vs-clear trade-off. If Part B's `pricing.py` is installed, includes a rough numeric estimate. Nudge-only is the permanent ceiling — hooks cannot actuate `/compact`.

## Implementation

_Filled once tasks 1–4 ship._

Source locations (pending):

- `src/developer-workflows/agents/worker.md` — `model: claude-opus-4-8` frontmatter
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
- **`output-styles/` and `rules/` are new subdirs within the `developer-workflows` plugin group** — `generate.py` and `lint_src.py` may need generator patches to discover them (task 2 audits first). See [ADR 0027](0027-output-style-rule-discovery-paths) for the discovery-path decision.
- **Compact-nudge context signal:** `CLAUDE_CONTEXT_USAGE_PERCENTAGE` availability is confirmed at build; JSONL line-count proxy is the documented fallback.

## Related

- [ADR 0026](0026-phase-aware-model-routing) — the routing-defaults design decision
- [ADR 0027](0027-output-style-rule-discovery-paths) — the `output-style`/`rule` discovery-path decision
- [Customization types](../reference/Customization-Types) — what each primitive kind is
- [Manifest Schema](../reference/Manifest-Schema) — frontmatter contract including `model:` and the discovery table
- [Hooks](../reference/Hooks) — the hook catalog and how `UserPromptSubmit` events work
