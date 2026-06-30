<!-- mode: index -->
# Designs

Design documents for crickets, organized by parent/child with the high-level or parent design (HLD) followed by its children. This is a complete index of all current and planned designs.

In addition to its high-level design for crickets and its children, crickets also lists the designs for all of its plugins here for clarity in a separate section. This is done to disambiguate plugins from the main components of crickets, as they stand architecturally separate.

For a list of designs as they relate to the architecture of crickets and roles, see [here](Architecture).

Shared root: [Foundations](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld) — (*Final*) lays out the nine principles that guide the development of agentm and crickets, and how the person (agentm) and its tools (crickets) relate. It lives in the AgentM wiki, and both HLDs inherit it by reference.

## Crickets HLD

[Crickets HLD](crickets-hld) — is the high-level parent design for crickets. It is an overview of the toolkit: small, stateless plugins, each authored once and generated as a native plugin for every host (Claude Code and Antigravity), that compose with one another and onto AgentM. The designs below are crickets' own machinery — how it is built and how it composes:

| Design                                                                                           | What it covers                                                                                                           | Status |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ | :----: |
| [Build system](crickets-build-system)                                                            | How one source becomes native plugins for both hosts, with a check that fails if the generated copies drift              | Final  |
| [Composition](crickets-composition)                                                              | How plugins connect — one building on another, or leaning on an AgentM standard, without reaching into each other's code | Final  |
| [Model + effort routing](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing) | is shared with AgentM — its design lives in the AgentM wiki; the crickets plugins carry the per-role settings            | Final  |

## Plugins

Each capability is its own plugin with its own design, standing apart from the architecture above.

| Plugin | What it covers | Status |
|---|---|:---:|
| [Development-lifecycle](crickets-development-lifecycle) | The dev loop — plan, work, review, release, and the rest of a feature's life | Final |
| [Code review](crickets-code-review) | Adversarial review of a change: assume there's a bug and prove otherwise | Final |
| [Design](crickets-design) | Writing design docs at the right size, from a quick sketch to a full architecture | Final |
| [Developer safety](crickets-developer-safety) | The safety net for an autonomous session: stop/redirect controls, a recoverability check, auto-saved work | Final |
| [Wiki](crickets-wiki) | Keeping the docs true to the code, in your house voice | Final |
| [Research](crickets-research) | Bringing in what the agent hasn't seen — codebase search, web lookups, scheduled learning | Planned |
| [GitHub projects](crickets-github-projects) | Mirroring your plans and progress onto a GitHub board, one way | Final |
| [Reporting](crickets-reporting) | The operator-facing digest of what autonomous work did | Planned |
| [Maintenance](crickets-maintenance) | Keeping a shipped codebase healthy: dependency repair, security patches, tech-debt tracking | Final |
| [Diagnostics](crickets-diagnostics) | Analyzing failures and suggesting what went wrong; it diagnoses, it doesn't fix | Planned |
| [Conventions](crickets-conventions) | The house standards for testing, releasing, docs, and more, kept in one place | Final |
| [Token audit](crickets-token-audit) | Measuring what a session costs, with a live meter | Final |
| [Privacy](crickets-privacy) | Keeping secrets and personal data out of what gets committed or shared | Final |
| [Obsidian vault](crickets-obsidian-vault) | Keeps the vault in a synced folder | Final |
| [vault-git](crickets-vault-git) | Git-backed vault storage — version history and off-device backup | Planned |

## See also

[Architecture](Architecture) · [Home](Home)
