<!-- mode: index -->
# Harness interface ↔ Agent M

_The seam between this toolkit and the sibling `agentm` harness — what each owns, and how they compose without depending on each other._

`agentm` is the phase-gated workflow harness; crickets is the toolkit of customizations that ride on it. The two are **siblings, not layers** — each ships and versions on its own, and neither requires the other to be installed. agentm owns the phases (`/plan` · `/work` · `/review` · `/release` · `/bugfix`) and their canonical specs; crickets owns the skills, commands, agents, and hooks that run inside them.

## How it works

The seam is graceful-skip in both directions, so each side works alone. A harness phase spec *suggests* a crickets primitive but runs without it; a crickets plugin *enhances* a phase only when that phase is present, deciding through a capability probe that goes inert when it isn't.

| Direction | Mechanism |
|---|---|
| **harness → toolkit** | a phase spec names a crickets primitive (e.g. `/release` suggests `ship-release`) and graceful-skips when it's absent. |
| **toolkit → harness** | a crickets plugin declares `enhances:` against a phase and probes for it at run time, staying inert when the phase isn't installed. |

## How it fits

- **[Customization model](Customization-Model)** — the mechanism behind the toolkit→harness direction. `enhances:` soft-composition plus the capability probe are what let a plugin augment a phase without hard-wiring to it.
- **[Plugins](Plugins)** — the concrete seam. `developer-workflows` extracts the phase loop into an installable plugin, while the canonical specs stay in agentm.

## See also

Detail:

- [Purpose and scope](Purpose-And-Scope) — what crickets is and is not, and how it sits beside agentm.
- [Crickets split — agentm ADR 0006 ↗](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0006-crickets-split.md) — the decision that drew this seam.

[Architecture](Architecture) · [Explanation](Explanation) · [Home](Home)
