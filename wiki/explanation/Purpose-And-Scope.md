# Purpose and scope

What crickets is, what it isn't, and how it relates to agentm — the "why does this repo exist" read in under five minutes. The full decision, with consequences, is the [Crickets HLD](crickets-hld).

## ⚡ Quick Reference

| Question | Answer |
|---|---|
| What is it? | A personal collection of agent customizations — skills, sub-agents, commands, hooks — shipped as **native host plugins** for Claude Code and Antigravity. |
| Sibling to? | [`agentm`](https://github.com/alexherrero/agentm) — the phase-gated workflow harness. The harness owns *workflow*; crickets owns *customizations*. |
| How does it install? | The host's plugin manager — `claude plugin install <plugin>@crickets`, the bootstrap one-liner, or a manual `--plugin-dir`. See [Install crickets plugins](Install-Into-Project). |
| What's in it? | Six plugins (groups) generated from one source — see [Plugin anatomy](Plugin-Anatomy); the primitive kinds are in [Customization types](Customization-Types). |
| How is it built? | Author once under `src/<group>/`; `generate.py` emits a native plugin per host into `dist/`. |

## What it's for

A place to keep agent customizations that:

- **Travel across projects.** Install a plugin once; the host's plugin manager makes it available everywhere — nothing is copied per-project.
- **Travel across hosts.** One source primitive (`kind` + `supported_hosts`) generates a Claude Code plugin *and* an Antigravity plugin.
- **Stay version-controlled.** Customizations are markdown + YAML, so diffs, rollbacks, and audit history are first-class. The generated `dist/` is committed too, and a CI gate proves it matches `src/`.
- **Don't bloat the workflow harness.** agentm stays focused on phase-gated workflow; crickets absorbs the customization growth.

## What it's NOT for

- **Workflow primitives.** `/plan` · `/work` · `/review` · `/release` · `/bugfix` and their phase specs live in agentm. crickets's `developer-workflows` plugin *extracts* the phase loop, but the canonical specs stay in the harness.
- **Project-specific config.** A particular project's `.claude/` / `.harness/` files belong in that project's repo. crickets ships *portable* customizations, not one codebase's lint config.
- **Binary artifacts.** Text only — markdown, YAML, JSON, shell. A customization that needs binaries ships a pointer, not the bytes.

## How it relates to agentm

Sibling repos, cloned side by side (`~/Antigravity/agentm/`, `~/Antigravity/crickets/`):

```
  agentm — phase-gated workflow + on-disk state
    /setup · /plan · /work · /review · /release · /bugfix
        │  its phase specs suggest crickets plugins (graceful-skip — neither requires the other)
        ▼
  crickets — customizations as native host plugins
    src/<group>/  →  generate.py  →  dist/<host>/plugins/<group>/
```

They're **decoupled** — independent release cycles, and no shared install code ([Build system design](crickets-build-system) retired the old byte-synced `lib/install/`). Both are public, with the same PII guardrails (the pre-push hook + `check-no-pii.sh` + gitleaks).

## Non-goals

- **Replacing the harness's phases.** The phases stay in agentm; a crickets plugin that touches one (e.g. `code-review` at `/review`) engages via a capability probe and graceful-skips when absent.
- **Cross-host parity enforcement.** Each primitive declares its own `supported_hosts`; there's no "every primitive must support both hosts" rule. A Claude-only hook is fine.
- **A catalog supermarket.** Small, opinionated, deliberate — each primitive earns its keep through use, not by being a catalog entry.

## Related

- [Crickets HLD — purpose, scope, public-with-PII-guardrails](crickets-hld) — the decision with full context + consequences.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is.
- [Customization types](Customization-Types) — the primitive kinds.
- [Install crickets plugins](Install-Into-Project) — the install modes.
