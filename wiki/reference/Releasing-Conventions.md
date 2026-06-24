<!-- mode: reference -->
# Releasing Conventions plugin

The `releasing-conventions` plugin (`requires: developer-workflows`) ships two primitives that make release discipline explicit and repeatable: a **rule** that fires when a version bump is missing and a **skill** that encodes the pre-release checklist, changelog shape, and paired-release discipline.

## ⚡ Quick Reference

| Aspect | Value |
|---|---|
| Plugin slug | `releasing-conventions` |
| Version | 0.1.1 |
| Requires | `developer-workflows` |
| Primitives | `version-bump-required` rule · `ship-release` skill |
| Hosts | Claude Code · Antigravity |

## Primitives

### `version-bump-required` rule

Fires when a diff adds, modifies, or removes user-visible primitives (skills, rules, commands, agents, hooks, snippets) under `src/` without a corresponding `group.yaml` `version` increment on the same branch.

The rule distinguishes the one legitimate exception — **concurrent worker branches** using the ADR 0030 single-writer protocol, where the integrator owns the bump — from all other cases where the PR author is responsible.

Trigger: any path under `src/<group>/skills/`, `src/<group>/rules/`, `src/<group>/commands/`, `src/<group>/agents/`, `src/<group>/hooks/`, or `src/<group>/snippets/`.

### `ship-release` skill

Applied before tagging or publishing a release. Covers four areas:

| Area | What it enforces |
|---|---|
| **Pre-release checklist** | CI green on every OS · version bumped · CHANGELOG authored · `dist/` regenerated and committed · `features.json` current · no orphan PRs · `check-all.sh` green |
| **Changelog shape** | Lead framing paragraph · Added / Changed / Internal sections (omit empty) · paired-release cross-links with URLs (never describe a paired release without the sibling release page URL) |
| **Paired-release discipline** | Lock the order explicitly before tagging · CI green on both sides before close · complete both sides in the same session · document the order in the plan's locked design calls |
| **Version bump policy** | Patch: bug fixes only · Minor: new primitives or behavioral additions · Major: breaking changes · one group at a time · never bump on a worker branch in the concurrent-worker protocol |

## Install

```bash
claude plugin install releasing-conventions@crickets
```

Requires `developer-workflows` as a base. Both plugins must be enabled for the skill to load.

## See also

- [developer-workflows plugin](Developer-Workflows) — the `/release` phase command this skill gates; also `/work`, `/plan`, `/bugfix`.
- [ADR 0030](crickets-development-lifecycle) — the single-writer protocol governing concurrent-worker version bumps (the one exception the `version-bump-required` rule acknowledges).
- [ADR 0029](crickets-development-lifecycle) — paired-release order and coordination.
- [Customization Types](Customization-Types) — what `kind: rule` and `kind: skill` are.
