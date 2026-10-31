# Compatibility

crickets runs on Claude Code and Antigravity, on all three OSes — this table shows how each component behaves per host.

## ⚡ Quick Reference

| Host | Status | Notes |
|---|---|---|
| **Claude Code** (Anthropic CLI / IDE) | ✅ supported | the primary surface; CI-verified on every push |
| **Antigravity 2.0** + the **`agy`** CLI | ✅ supported | built for `agy` 1.4; CI checks the plugin shape (`check-agy-plugin-shape`), and `agy plugin validate` runs by hand ([what differs](#what-differs-on-antigravity)) |

Every customization declares `supported_hosts:` in its manifest, and the generator emits each plugin only for the hosts it supports. Destination paths per kind: [Per-Host Paths](Per-Host-Paths).

## Operating systems

Linux, macOS, and Windows (PowerShell 7+) are tested on every pull request (a plain push to `main` only runs a light syntax check) — the per-OS workflows, the aggregate badge, and the gate battery are in [CI gates](CI-Gates).

## Per-plugin host support

Claude Code supports every plugin fully; the **Support** column reflects Antigravity completeness.

| Plugin | Support | Antigravity gaps |
|---|---|---|
| `development-lifecycle` | ⚠️ Partial | the `compact-nudge-resume` hook is Claude-only; a bare `/plan` is `agy`'s own planning mode, so type `/development-lifecycle:plan` |
| `developer-safety` | ⚠️ Partial | all four hooks run on macOS and Linux; the PowerShell twins aren't wired for `agy` yet |
| `code-review` | ⚠️ Partial | the `evidence-tracker` hook is Claude-only; the agents use the session's tools and model |
| `maintenance` | ✅ Supported | — |
| `privacy` | ✅ Supported | — |
| `wiki` | ⚠️ Partial | `/wiki-init` ships, but `/wiki-watch`, `/recent-wiki-changes` and the `wiki-author` skill are Claude-only ([why](Antigravity-Limitations)) |
| `design` | ✅ Supported | — |
| `github-projects` | ✅ Supported | — |
| `obsidian-vault` | ✅ Supported | — |
| `conventions` | ✅ Supported | — |
| `tokens` | ⚠️ Partial | `status-line-meter` is Claude Code only (no status-line surface on Antigravity); `token-audit`'s `/token-audit` command is Claude-only; `session-cost-capture` runs on both |
| `diagnostics` | ✅ Supported | — |
| `research` | ✅ Supported | — |

## Hook effectiveness

`agy` 1.4 runs plugin hooks from a `hooks.json` at the plugin root, and it speaks JSON: a hook answers with one JSON object on stdout (`{"decision": "deny"}` for a tool call, `{"injectSteps": [...]}` to add context). crickets hooks are written for Claude Code, which reads exit codes and plain stdout. So every hook on Antigravity runs through `hooks/_agy_hook_adapter.py`, which runs the original script unchanged and translates its answer. [Hooks](Hooks) has the translation table.

| Hook | Plugin | Claude Code | Antigravity | How it runs there |
|---|---|---|---|---|
| `kill-switch` | `developer-safety` | ✅ effective | ✅ effective | exit code 2 becomes `agy`'s deny, with the script's message as the reason |
| `steer` | `developer-safety` | ✅ effective | ✅ effective | `agy` has no `UserPromptSubmit`, so it runs on `PreInvocation`, once per user message |
| `commit-on-stop` | `developer-safety` | ✅ effective | ✅ effective | a side effect on `Stop`, no answer needed |
| `coauthor-guard` | `developer-safety` | ✅ effective | ✅ effective | `SessionStart`; whatever it prints reaches the model as a system message |
| `harness-context` | `development-lifecycle` | ✅ effective | ✅ effective | `SessionStart`; the `.harness/` paths reach the model |
| `conflict-merger-session-start` | `obsidian-vault` | ✅ effective | ✅ effective | `SessionStart` |
| `session-cost-capture` | `tokens` | ✅ effective | ✅ effective | a side effect on `Stop` |
| `evidence-tracker` | `code-review` | ✅ effective | ❌ Claude-only | built around Claude's tool payloads; not ported |
| `compact-nudge-resume` | `development-lifecycle` | ✅ effective | ❌ Claude-only | reads Claude Code's session file |

Watched running inside `agy` 1.4.11 on 2026-10-30: `kill-switch` (blocks with its message when `.harness/STOP` exists, lets the call through when it doesn't), `steer` (the note reaches the model once, then the file is renamed), and `harness-context` (the `PLAN.md` path reaches the model). The other four are wired the same way and covered by the adapter's tests, but nobody has watched them run inside `agy` yet.

**A trap worth knowing:** `agy` reads a bare `{}` from a `PreToolUse` hook as a deny. A tool hook with nothing to say must print nothing at all. The adapter does this, and a test pins it.

Authoring a host-portable hook? Resolve the workspace from stdin, not `cwd` — see [Hooks](Hooks).

## What differs on Antigravity

| On Claude Code | On Antigravity | Why |
|---|---|---|
| a command is `commands/<name>.md` | a command is a skill, `skills/<name>/SKILL.md` | `agy` plugins load no `commands/` folder |
| `/plan` runs the crickets command | `/plan` is `agy`'s own planning mode; the crickets one is `/development-lifecycle:plan` | `agy`'s built-in command wins a name clash |
| an agent lists its `tools:` and `model:` | the agent uses the session's tools and model | `agy` wants its own tool names and skips an agent with a Claude model tier |
| a rule just has a description | a rule has a `trigger:` (`always_on` for snippets, `model_decision` for rules) | `agy` never applies a rule without one |
| a skill can be any length | a skill body over about 24 KB is split: a short `SKILL.md` points at `references/` | `agy` loads only the first 24 KB |

## Snippet emission

The `snippet` kind is an instruction fragment. The generator emits it **as an Antigravity `rules/` file** (`<plugin>/rules/<name>.md`) and **drops it on Claude Code**, which has no instruction-file primitive to land it in. So `developer-safety`'s `commit-no-coauthor` + `worktrees-operator-initiated` conventions ship as Antigravity rules with no Claude-Code form. See [Per-Host Paths](Per-Host-Paths).

## Antigravity 2.0 gaps

Two Antigravity surfaces still have **no file-based authoring path**, so crickets can't ship into them from the manifest model:

- **Scheduled tasks / triggers** — Python registration patterns, no file-based config; crickets ships none.
- **Multi-agent orchestration** — operator-facing (`start_subagent`); no plugin-author surface for spawn policy.

Hooks used to be on this list. `agy` 1.4 added a file-based hook surface, and crickets uses it now. The register also tracks the smaller differences above, each with its re-address trigger, in [Antigravity limitations](Antigravity-Limitations).

## Out-of-scope hosts

- **Gemini CLI** — dropped in v0.9.0 (2026-05-17, "Gemini-CLI host removal"). Google replaced it with the Antigravity CLI (`agy`), which **is** supported; consumer Gemini CLI sunsets 2026-06-18. ([agentm Foundations HLD — crickets split](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld).)
- **Codex** — never had an adapter.

## See also

- [Troubleshooting](Troubleshooting) — when a host that *should* work stops working.
- [Antigravity limitations](Antigravity-Limitations) — the host-gap register.
- [Hooks](Hooks) — the full hook catalog.
- [Per-Host Paths](Per-Host-Paths) — destinations per kind, per host.
- [Manifest Schema](Manifest-Schema) — the `supported_hosts` declaration.
