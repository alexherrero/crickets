# Purpose and scope

Why crickets was created, and for what — the "why does this repo exist" read in under five minutes.

crickets exists so the agent customizations that travel with you — skills, sub-agents, commands, hooks — have a home of their own, one that doesn't crowd the workflow harness. Those customizations grow over time, and if they lived inside agentm they'd slowly bloat a repo whose whole point is a tight, phase-gated workflow. So the two are split by what they own: agentm owns the workflow, crickets owns the customizations. Each stays small and clear about its job, and either one can grow without dragging the other along. The full decision, with consequences, is the [Crickets HLD](crickets-hld).

## ⚡ Quick Reference

| Question | Answer |
|---|---|
| What is it? | A personal collection of agent customizations — skills, sub-agents, commands, hooks — shipped as **native host plugins** for Claude Code and Antigravity. |
| Sibling to? | [`agentm`](https://github.com/alexherrero/agentm) — the phase-gated workflow harness. The harness owns *workflow*; crickets owns *customizations*. |
| How does it install? | The host's plugin manager — `claude plugin install <plugin>@crickets`, the bootstrap one-liner, or a manual `--plugin-dir`. See [Install crickets plugins](Install-Into-Project). |
| What's in it? | 13 plugins (groups) generated from one source — see [Plugins](Plugins) for the roster and [Plugin anatomy](Plugin-Anatomy) for the shared structure; the primitive kinds are in [Customization types](Customization-Types). |
| How is it built? | Author once under `src/<group>/`; `generate.py` emits a native plugin per host into `dist/`. |

## What it's for

A place to keep agent customizations that:

- **Travel across projects.** Install a plugin once; the host's plugin manager makes it available everywhere — nothing is copied per-project.
- **Travel across hosts.** One source primitive (`kind` + `supported_hosts`) generates a Claude Code plugin *and* an Antigravity plugin.
- **Stay version-controlled.** Customizations are markdown + YAML, so diffs, rollbacks, and audit history are first-class. The generated `dist/` is committed too, and a CI gate proves it matches `src/`.
- **Don't bloat the workflow harness.** agentm stays focused on phase-gated workflow; crickets absorbs the customization growth.

## What it's NOT for

- **Workflow state substrate.** `agentm` owns the durable phase state (`.harness/PLAN.md` / `progress.md`, the vault write protocol, named-plan resolution) that `/plan` · `/work` · `/review` · `/release` · `/bugfix` run on. Since the V5 unbundling, each phase's canonical spec ships in crickets's `developer-workflows` plugin — `agentm` no longer vendors them, having retired the byte-duplicated copies.
- **Project-specific config.** A particular project's `.claude/` / `.harness/` files belong in that project's repo. crickets ships *portable* customizations, not one codebase's lint config.
- **Binary artifacts.** Text only — markdown, YAML, JSON, shell. A customization that needs binaries ships a pointer, not the bytes.

## How it relates to agentm

Sibling repos, cloned side by side (`~/Antigravity/agentm/`, `~/Antigravity/crickets/`):

```
  crickets — developer-workflows plugin ships the canonical phase specs
    /setup · /plan · /work · /review · /release · /bugfix
        │  phase specs read/write agentm's durable state (graceful-skip — neither requires the other)
        ▼
  agentm — durable state substrate + memory engine
    .harness/PLAN.md · progress.md · vault write protocol · named-plan resolver

  crickets ships every customization, phases included, the same way:
    src/<group>/  →  generate.py  →  dist/<host>/plugins/<group>/
```

They're **decoupled** — independent release cycles, and no shared install code ([Build system design](crickets-build-system) retired the old byte-synced `lib/install/`). Both are public, with the same PII guardrails (the pre-push hook + `check-no-pii.sh` + gitleaks).

## Non-goals

- **Duplicating the state substrate.** `agentm` owns the durable phase state; a crickets plugin that touches a phase (`developer-workflows` shipping the spec itself, or `code-review` engaging at `/review`) reads/writes that substrate via the resolver bridge rather than reimplementing it, and graceful-skips when the capability is absent.
- **Cross-host parity enforcement.** Each primitive declares its own `supported_hosts`; there's no "every primitive must support both hosts" rule. A Claude-only hook is fine.
- **A catalog supermarket.** The catalog stays small, opinionated, and deliberate — each primitive earns its keep through use, not by being a catalog entry.

## Related

- [Crickets HLD — purpose, scope, public-with-PII-guardrails](crickets-hld) — the decision with full context + consequences.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is.
- [Customization types](Customization-Types) — the primitive kinds.
- [Install crickets plugins](Install-Into-Project) — the install modes.
