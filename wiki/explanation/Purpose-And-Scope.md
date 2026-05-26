# Purpose and scope

What `crickets` is, what it isn't, and how it relates to `agentm`. Written to answer "why does this repo exist" in under five minutes; deeper reasoning lives in [ADR 0001](0001-crickets-purpose).

## ⚡ Quick Reference

| Question | Answer |
|---|---|
| What is it? | Personal collection of agent customizations (skills, sub-agents, hooks, MCP servers, slash commands, bundles, etc.) across Claude Code, Antigravity, and Gemini CLI. |
| Sibling to? | [`agentm`](https://github.com/alexherrero/agentm) — the phase-gated workflow harness. The harness owns workflow; this toolkit owns customizations. |
| How does it install? | `bash /path/to/crickets/install.sh /path/to/your-project`. See [Install-Into-Project](Install-Into-Project). |
| What kinds of customizations? | 11 types — see [Customization Types](Customization-Types). |
| How are skills addressed across hosts? | Each customization's manifest declares `supported_hosts`; the installer dispatches per [Per-Host Paths](Per-Host-Paths). |

## What this repo is for

A place to keep agent customizations that:

- **Travel across projects.** Install once into a target project; the toolkit drops them into the right host paths.
- **Travel across hosts.** A skill that works in Claude Code, Antigravity, and Gemini CLI ships from one source manifest; the installer adapts the destination.
- **Stay version-controlled.** Customizations are markdown + YAML frontmatter, so diffs, rollbacks, and audit history are first-class.
- **Don't bloat the workflow harness.** `agentm` stays focused on phase-gated workflow; this repo absorbs the customization-catalog growth.

## What this repo is NOT for

- **Workflow primitives** — `/plan`, `/work`, `/review`, `/release`, `/bugfix` and their phase specs live in `agentm`. The toolkit consumes those (via `dependabot-fixer` and `ship-release`, which the harness's phase specs reference as graceful-skip suggestions), but doesn't redefine them.
- **Project-specific config** — repo-rooted `.claude/` and `.agent/` files for a *specific* project belong in that project's repo. The toolkit ships *user-portable* customizations; project-specific ones (e.g. `.harness/verify.sh` for a particular codebase's lint config) stay with the project.
- **Binary artifacts or large files.** The toolkit is text-only — markdown, YAML, JSON, shell scripts. If a customization needs binaries, it ships pointers (download URLs in its manifest body); not the binaries themselves.

## How it relates to `agentm`

Sibling repos, designed to be cloned as siblings (`~/Antigravity/agentm/`, `~/Antigravity/crickets/`):

```
                  ┌────────────────────────────────────────────┐
                  │  agentm                            │
                  │    workflow phases + state                  │
                  │    (/setup /plan /work /review /release ...) │
                  │    .harness/PLAN.md / progress.md / etc.    │
                  └────────────┬────────────────────────────────┘
                               │ shared lib/install/
                               │ (byte-identical; sync-lib.sh)
                               ▼
                  ┌────────────────────────────────────────────┐
                  │  crickets                              │
                  │    customizations + install plumbing        │
                  │    skills/ commands/ agents/ hooks/ ...     │
                  │    bundles/ + 12 primitive-type subdirs     │
                  └────────────────────────────────────────────┘
```

Both repos:

- Have independent release cycles (the harness is at v2.x; the toolkit shipped its first release at v0.1.0).
- Share `lib/install/` byte-identically — primitives like `cp_managed`, `ensure_boundary_src`, `sync_managed_parents` live in one place and are copied to the other via `scripts/sync-lib.sh`.
- Use the same PII guardrails (`scripts/check-no-pii.sh`, `.gitleaks.toml`, pre-push hook template) — both are public repos.

## Where customizations come from

Two paths:

1. **Migrated from the harness** — `dependabot-fixer` and `ship-release` lived in `agentm` through v1.x, then moved here in toolkit v0.1.0 (paired with harness v2.0.0). The migration freed the harness from the parity tax for those skills and gave them a richer home (the toolkit's manifest schema lets a single SKILL.md ship to all 3 hosts at install time).
2. **Net-new in the toolkit** — `pii-scrubber` was written from scratch as the agent-facing PII guardrail. Future skills (an `evaluator` sub-agent, `kill-switch` + `steer` hooks, a `commit-on-stop` hook, the `quality-gates` bundle) are net-new from the crickets roadmap.

## Non-goals

- **Replacing the harness's phase workflow.** The phases stay in agentm. Skills here that integrate with phases (e.g. `ship-release` referenced from `/release`) use graceful-skip patterns — present in toolkit, suggested by harness, neither requires the other to exist.
- **Cross-host parity enforcement at the manifest level.** Each customization declares its own `supported_hosts`; there's no global "every skill must support all 3 hosts" rule. A Claude-Code-only hook is fine, declared via `supported_hosts: [claude-code]`.
- **A "150-agent supermarket".** Same principle as the harness: small, opinionated, deliberate. Each skill or bundle earns its keep through use, not by being a catalog entry.

## Related

- [ADR 0001 — crickets purpose, scope, public-with-PII-guardrails](0001-crickets-purpose) — the architectural decision with full context + consequences.
- [Customization Types](Customization-Types) — the 12 primitive types this repo holds.
- [Manifest Schema](Manifest-Schema) — the YAML frontmatter contract.
- [Per-Host Paths](Per-Host-Paths) — how each kind maps to a host destination.
- [Install Into Project](Install-Into-Project) — the install recipe.
