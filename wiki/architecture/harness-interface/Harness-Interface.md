<!-- mode: index -->
# Harness interface ↔ Agent M

_The seam between this toolkit and the sibling `agentm` harness — what each owns, and how they compose without depending on each other._

`agentm` owns the phase-gated workflow (`/plan` · `/work` · `/review` · `/release` · `/bugfix`) and the canonical phase specs. crickets owns the customizations — skills, agents, hooks, and the rest — that ride on top. Neither requires the other to exist: the harness *suggests* crickets primitives (e.g. `ship-release`) as graceful-skip steps, and crickets primitives *enhance* the harness phases when both are installed. The split was made in crickets v2.0.0.

Cross-references:

- [Crickets split — agentm ADR 0006 ↗](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0006-crickets-split.md) — the decision to split harness from toolkit.
- [Purpose and scope](Purpose-And-Scope) — what crickets is and is not.

## See also

[Architecture](Architecture) · [Explanation](Explanation) · [Home](Home)
