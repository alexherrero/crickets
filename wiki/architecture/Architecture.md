<!-- mode: index -->
# Architecture

Crickets is a toolkit of composable plugins for Claude Code and Antigravity. Its architecture is the machinery that builds those plugins, lets them compose, and lets them reach into AgentM — the capabilities themselves come after.

![High-level crickets architecture: a primitive is authored once in src/, the build system composes it and generates a native plugin for Claude Code and Antigravity, the plugins compose via the enhances config, and a one-way bridge reaches into the AgentM substrate of memory, opinions, and personas when AgentM is installed](diagrams/crickets-architecture.svg)

## The architecture

Underneath the plugins, crickets is four systems:

- **The build system** — every primitive is authored once; the build composes it and generates a native plugin, and a check fails if the generated copies ever drift from the source. → [Build & distribution](Build-And-Distribution) · [design](crickets-build-system)
- **Per-host generation** — the build targets each host's surface, so the same primitive lands correctly in Claude Code and in Antigravity. → [Host adapters](Host-Adapters)
- **The `enhances` config** — a manifest model that lets one plugin add to another when both are installed, without either reaching into the other's code. → [Customization model](Customization-Model) · [design](crickets-composition)
- **Reaching into AgentM** — a one-way bridge crickets uses to find and use AgentM's memory, opinions, and personas when AgentM is installed, and to skip gracefully when it isn't. → [Harness interface](Harness-Interface) · [design](crickets-composition)

Crickets stands on the AgentM substrate; see [AgentM's architecture](https://github.com/alexherrero/agentm/wiki/Architecture) to read more about what's underneath.

## The plugins available

The capabilities crickets ships — built, generated, and composed by the systems above:

- [Development-lifecycle](crickets-development-lifecycle) — the dev loop: plan, work, review, release, and the rest of a feature's life.
- [Code review](crickets-code-review) — adversarial review of a change: assume there's a bug and prove otherwise.
- [Design](crickets-design) — writing design docs at the right size, from a quick sketch to a full architecture.
- [Developer safety](crickets-developer-safety) — the safety net for an autonomous session: stop/redirect controls, a recoverability check, auto-saved work.
- [Wiki](crickets-wiki) — keeping the docs true to the code, in your house voice.
- [GitHub projects](crickets-github-projects) — mirroring your plans and progress onto a GitHub board, one way.
- [Maintenance](crickets-maintenance) — keeping a shipped codebase healthy: dependency repair, security patches, tech-debt tracking.
- [Conventions](crickets-conventions) — the house standards for testing, releasing, docs, and more, kept in one place.
- [Token audit](crickets-token-audit) — measuring what a session costs, with a live meter.
- [Privacy](crickets-privacy) — keeping secrets and personal data out of what gets committed or shared.
- [Research](crickets-research) — bringing in what the agent hasn't seen: codebase search, web lookups, scheduled learning *(designed, not yet built)*.
- [Diagnostics](crickets-diagnostics) — analyzing failures and suggesting what went wrong; it diagnoses, it doesn't fix *(designed, not yet built)*.
- [Reporting](crickets-reporting) — the operator-facing digest of what autonomous work did *(designed, not yet built)*.
- [Obsidian vault](crickets-obsidian-vault) — keeps the vault in a synced folder.
- [vault-git](crickets-vault-git) — git-backed vault storage: history and off-device backup *(forthcoming)*.

## Recent changes

> [!NOTE]
> **Latest: the design set is complete and published ([v3.23.0](https://github.com/alexherrero/crickets/releases/tag/v3.23.0), 2026-07-01).** Every plugin now has a combined Architecture + Reference page, and each decision lives in its design's own history — the standalone ADR model is retired. See [Designs](Designs) for the full set.
