# CLAUDE.md

This repo is [`crickets`](https://github.com/alexherrero/crickets). Universal instructions live in [AGENTS.md](AGENTS.md) — read that first.

## Claude Code specifics

- Skills install into target's `.claude/skills/<name>/SKILL.md` per the Agent Skills standard.
- Sub-agents install into `.claude/agents/<name>.md`.
- Hooks install into `.claude/hooks/<name>` + entries merged into `.claude/settings.json` (lands in task 3).
- The `pii-scrubber` skill is the agent-facing PII guardrail; **the pre-push git hook is the mandatory enforcer.** Invoke `pii-scrubber` before any `git push` — the hook will catch you anyway, but the skill fixes findings rather than just blocking.
- **Commit messages: no `Co-Authored-By: Claude` trailer.** See [AGENTS.md § Conventions § Commit messages](AGENTS.md#commit-messages) — the rule is host-agnostic; this bullet is the Claude-specific reminder because Claude Code emits the trailer by default.

For anything not Claude-specific, [AGENTS.md](AGENTS.md) is authoritative.

<!-- Conventions auto-load below — moved here from the global ~/.claude/CLAUDE.md for the token-efficiency floor-trim (2026-06-13). crickets keeps the agentm import because it runs on the agentm phase harness. -->
@AGENTS.md
@~/Antigravity/agentm/AGENTS.md
