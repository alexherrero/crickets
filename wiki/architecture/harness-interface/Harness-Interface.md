<!-- mode: index -->
# Harness interface ↔ AgentM

_The seam between this toolkit and the sibling `agentm` harness — what each owns, and how they compose without depending on each other._

`agentm` is the durable-state substrate and memory engine; crickets is the toolkit of customizations that ride on it — including, since the V5 unbundling, the phases themselves. The two are **siblings, not layers** — each ships and versions on its own, and neither requires the other to be installed. `agentm` owns the durable phase state (`.harness/PLAN.md` / `progress.md`, the vault write protocol, named-plan resolution); crickets's `development-lifecycle` plugin owns the phases' canonical specs (`/plan` · `/work` · `/review` · `/release` · `/bugfix`), plus the skills, commands, agents, and hooks that run inside them.

## How it works

The seam is graceful-skip in both directions, so each side works alone. A `development-lifecycle` phase spec *reads/writes* agentm's durable state through the `resolve_plan.py` bridge when a vault-backed agentm install is present, and falls back to plain local `.harness/` state when it isn't; a crickets plugin *enhances* a phase only when that phase is present, deciding through a capability probe that goes inert when it isn't.

| Direction | Mechanism |
|---|---|
| **toolkit phase spec → harness substrate** | `development-lifecycle`'s phase specs resolve their `(PLAN, progress)` pair through agentm's `resolve-active-plan` bridge, and graceful-skip to local singleton state when agentm isn't installed. |
| **toolkit plugin → toolkit phase** | a crickets plugin declares `enhances:` against a phase (e.g. `code-review` at `/review`) and probes for it at run time, staying inert when the phase plugin isn't installed. |

## How it fits

- **[Customization model](Customization-Model)** — the mechanism behind the toolkit-plugin→toolkit-phase direction. `enhances:` soft-composition plus the capability probe are what let a plugin augment a phase without hard-wiring to it.
- **[Plugins](Plugins)** — the concrete seam. `development-lifecycle` ships the phase loop as an installable plugin, with its canonical specs; `agentm` retired its byte-duplicated copies at the V5 unbundling.

## See also

Detail:

- [Purpose and scope](Purpose-And-Scope) — what crickets is and is not, and how it sits beside agentm.
- [Crickets split — agentm Foundations HLD ↗](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld) — the decision that drew this seam.

[Architecture](Architecture) · [Explanation](Explanation) · [Home](Home)
