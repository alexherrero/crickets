# ADR 0026 — Phase-aware model routing in developer-workflows

> [!NOTE]
> Status: accepted
> Date: 2026-06-14

## Context

The `developer-workflows` plugin ships a phase-gated loop: `/plan` → `/work` → `/review` → `/release`, plus `/bugfix`. Different phases have materially different cost profiles:

- **Planning and reviewing phases** (`/plan`, `/review`, `/design`) are authoring and read-only tasks — they benefit from a capable model but are relatively short and do not execute code or make autonomous multi-step decisions.
- **Execution phases** (`/work`, `/bugfix`) are long-running, autonomous, and multi-step — a quality cliff from a mis-routed cheap model here costs more than the token savings.

Without routing defaults in the plugin, every adopter must set model routing manually, re-deriving the same call. The operator's global `~/.claude/CLAUDE.md` block already encodes this routing (`opusplan` alias; do-now directive 2026-06-13); this ADR ships it as a durable, adopter-facing plugin primitive.

**Open questions this decision resolves:**

- Can `model:` frontmatter enforce the model for slash commands, or only for agent defs?
- Which phases get which default model, and what is the override path?
- Is a prompt-level nudge sufficient for commands, or is this a gap that needs a different mechanism?

## Decision

### 1. Agent defs use `model:` frontmatter; slash commands use prompt-level nudge lines

Agent defs (`worker.md`, `researcher.md`, `tech-lead.md`) spawn sub-processes; the host applies `model:` frontmatter at spawn time. Slash commands run in the user's active session — the host does not apply `model:` to commands — so each command carries a single-line nudge:

```
Recommended model for this phase: claude-sonnet-4-6 (/model sonnet to switch)
```

Both paths are needed. Agent-def frontmatter is enforcement; command nudge is advisory. The gap (commands cannot enforce) is accepted as the honest state until the host exposes a command-level model override API.

**Why not omit the nudge and accept the gap?** The nudge is low-cost and surfaces the recommendation at point-of-use, where the operator is most likely to act on it. An invisible default that the operator can't see is harder to override correctly. The nudge makes the routing policy legible without asserting control it doesn't have.

### 2. Routing policy: strong model for execution, lighter model for planning

| Primitive | Default model | Rationale |
|---|---|---|
| `worker.md` | `claude-opus-4-8` | Autonomous multi-step code execution — quality cliff is the bigger risk |
| `researcher.md` | `claude-sonnet-4-6` | Read-only research, scoped analysis |
| `tech-lead.md` | `claude-sonnet-4-6` | Planning, authoring, structural decisions |
| `/work` command | Opus nudge | Mirrors `worker.md`; per-session model already set by user |
| `/bugfix` command | Opus nudge | Same profile as `/work` |
| `/plan` command | Sonnet nudge | Authoring and structural work |
| `/review` command | Sonnet nudge | Read-only adversarial analysis |
| `/design` command | Sonnet nudge | Design authoring |

**Why Opus for `/work` and `/bugfix`?** These are the phases where a mis-route to a cheaper model has the highest cost — a failed autonomous task pass burns more wall-clock time and tokens recovering than the Opus premium costs upfront. `/plan` and `/review` are bounded, human-interleaved, and recoverable if shallow.

**Why not route everything to Sonnet and let the operator escalate?** The operator's global directive already settles this call: `/work`/`/bugfix` stay on the strong model. The plugin matches the operator's standing policy.

### 3. Routing defaults are operator-overridable

The `model:` frontmatter sets the *default*; the operator overrides it with `claude --model <name>` at spawn time or `/model <name>` in-session. No behavior is locked. An adopter running a constrained plan (tight budget, fast iteration) can override without modifying the plugin.

### 4. Version bump: `developer-workflows` → `0.13.0`

Routing defaults are user-visible behavior; they warrant a minor bump from `0.12.x`.

## Consequences

**Positive**

- Adopters get phase-appropriate routing without any configuration — the safest default (strong model for execution) is the out-of-the-box experience.
- The routing policy is legible in the plugin source (`model:` frontmatter + nudge lines) — no external docs needed to understand what model a given phase uses.
- Command nudges are visible at point-of-use and actionable without leaving the session.

**Negative / accepted debt**

- Slash commands cannot enforce model routing — the nudge is advisory only. An operator who ignores the nudge and runs `/work` on Sonnet will not be blocked. **Re-audit if** the host exposes a command-level model enforcement API.
- `model:` frontmatter values are pinned to named model strings (`claude-opus-4-8`, `claude-sonnet-4-6`) — a model deprecation requires a patch. **Re-audit trigger:** either named model is deprecated or superseded in the Anthropic model catalog.

**Load-bearing assumptions + re-audit triggers**

- *Agent defs spawn sub-processes that honor `model:` frontmatter.* Re-audit if the host changes how Agent tool invocations resolve the model field.
- *`opusplan` alias (Plan→Sonnet, Work→Opus) is a valid CC routing mode.* Re-audit if the alias is removed or renamed.
- *The global `~/.claude/CLAUDE.md` token-discipline block (2026-06-13) is the spec.* Any divergence from that block in these routing defaults is a defect, not an intentional design call.

## Related

- [Developer-Workflows token efficiency](../explanation/Developer-Workflows-Token-Efficiency) — the parent feature page
- [ADR 0027](developer-plugin-suite) — the `output-style`/`rule` discovery-path decision (companion in Part D)
- [Customization types](../reference/Customization-Types) — `agent` kind and how `model:` applies
- [Manifest Schema](../reference/Manifest-Schema) — frontmatter fields including `model:`
