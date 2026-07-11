# AGENTS.md

Universal instructions for AI coding agents working in `crickets`.

This repo is a sibling to [`agentm`](https://github.com/alexherrero/agentm). The harness owns the phase-gated workflow; this toolkit owns the agent customizations (skills, sub-agents, hooks, MCP servers, slash commands, status lines, output styles, workflows, rules, snippets, settings fragments) that ride on top.

## What this repo holds

| Subdir | What it holds |
|---|---|
| `src/<group>/` | Authored source for every customization — 13 plugin groups (`code-review`, `design-docs`, `developer-safety`, `developer-workflows`, `github-ci`, `github-projects`, `obsidian-vault`, `pii`, `releasing-conventions`, `status-line-meter`, `testing-conventions`, `token-audit`, `wiki-maintenance`); each groups its own skills/commands/agents/hooks/etc. |
| `dist/` | Generated native plugins per host (`claude-code/`, `antigravity/`), committed — `scripts/generate.py build` regenerates it from `src/`, and a CI gate proves it matches. |
| `scripts/` | `generate.py` (the src→dist generator), validators, CI helpers, the PII detector |
| `templates/hooks/` | Hook templates installed into target projects (e.g. `pre-push`) |
| `wiki/` | Diátaxis-shaped dogfood docs |
| `bootstrap.sh` | The one-line install script |

## How to install

Crickets ships as **native host plugins** generated from `src/` into committed `dist/`. Install with the one-liner, the marketplace, or a manual `--plugin-dir`:

```bash
curl -fsSL https://raw.githubusercontent.com/alexherrero/crickets/main/bootstrap.sh | bash
# or one word from GitHub on Claude Code:
claude plugin marketplace add alexherrero/crickets && claude plugin install developer@crickets
```

Full detail (three modes × both hosts): [Install crickets plugins](https://github.com/alexherrero/crickets/wiki/Install-Into-Project). The v2.x `install.sh` dispatcher was retired in v3.0.

## Conventions

### PII guardrails (this repo is **public**)

Three enforcement layers protect against personal information leaking into public commits:

1. **Pre-push git hook** (`src/privacy/templates/hooks/pre-push`) — mandatory enforcer. Runs the PII detector against every push; blocks non-zero. Copy it into this repo's `.git/hooks/pre-push` (`cp src/privacy/templates/hooks/pre-push .git/hooks/ && chmod +x .git/hooks/pre-push`).
2. **`pii-scrubber` skill** (`skills/pii-scrubber/`) — agent-facing interactive layer. Scans the current diff before commit, presents findings, offers redactions. Loops until clean (or user explicitly logs an override).
3. **CI gate** (lands in task 4 of v0.1.0 plan) — defense in depth. Same script + gitleaks run on every push to GitHub.

See [CONTRIBUTING.md](CONTRIBUTING.md) § PII guardrails for full guidance and the override protocol.

### Commit messages

Do not append a `Co-Authored-By:` trailer naming the agent or model (`Co-Authored-By: Claude`, `Co-Authored-By: Gemini`, etc.) to git commit messages. The user is the sole author of intent — the agent is the tool, not a co-author. Plain commit message only. Applies to every commit unless the user explicitly opts in for a specific commit.

This applies regardless of which host you're running in (Claude Code, Antigravity, Gemini CLI) and regardless of any default the host injects. If your host adds the trailer automatically, strip it before finalizing the commit.

### Manifest schema

Every customization (bundle or standalone primitive) has YAML frontmatter at the top of its `.md` file:

```yaml
---
name: <matches dirname/filename>
description: <one-sentence>
kind: bundle | skill | command | agent | hook | mcp-server | status-line | output-style | workflow | rule | snippet | settings-fragment
supported_hosts: [claude-code, antigravity]                # subset
version: 0.1.0
install_scope: user | project | either                     # optional, default: either
deprecated: <reason>                                       # optional, lifecycle marker
contents:                                                  # bundles only
  - skill: <name>
  - hook: <name>
---
```

Required fields: `name`, `description`, `kind`, `supported_hosts`, `version`. Bundles additionally require `contents`. Validator landing in task 3 of the v0.1.0 plan.

## Cross-references

- [`agentm`](https://github.com/alexherrero/agentm) — sibling repo; phase-gated workflow + canonical phase specs.
- This repo's [Diátaxis-shaped wiki](wiki/Home.md) — start at `wiki/Home.md` for navigation; key entry points include [Purpose and scope](wiki/explanation/Purpose-And-Scope.md), [Manifest Schema](wiki/reference/Manifest-Schema.md), and [Tutorial 1](wiki/tutorials/01-First-Customization.md).
