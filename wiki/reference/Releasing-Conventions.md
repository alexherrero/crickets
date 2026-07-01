<!-- mode: reference -->
# Releasing Conventions

## Architecture

Releasing Conventions is the discipline layer for cutting a release. It does not run the tag-and-publish mechanics itself; instead it makes the rules explicit and repeatable — what has to be true before you tag, what a changelog entry should look like, and how to coordinate two repos that release together. It sits on top of `developer-workflows`, so its checklist is what the `/release` phase leans on before anything ships.

### Diagram

_None / not needed._

### How it works

The plugin ships two primitives that fire at different moments. The `version-bump-required` rule watches diffs: when a change adds, modifies, or removes a user-visible primitive under `src/` without bumping the affected group's `group.yaml` `version`, the rule flags it — and it knows the one legitimate exception, the concurrent-worker single-writer protocol where the integrator owns the bump rather than the PR author. The `ship-release` skill is the pre-tag gate: it walks a pre-release checklist (CI green on every OS, version bumped, CHANGELOG authored, `dist/` regenerated and committed, `features.json` current, no orphan PRs, `check-all.sh` green), fixes the changelog shape, and locks paired-release order for coordinated cross-repo releases. Because the plugin requires `developer-workflows`, the skill's checklist becomes the discipline the `/release` phase enforces before it tags or publishes.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | [Developer-Workflows](Developer-Workflows) | The `/release` phase this discipline gates; the skill's checklist is what that phase applies before tagging. Both must be enabled for the skill to load. |
| Required by (hard) | — | None. |

### Why not

Releasing Conventions encodes one opinionated way to release, and it will not suit every project. Reach for something else if:

- Your release rules differ — a different changelog format, a different bump policy, or no cross-repo coordination — and you would have to fight the built-in checklist rather than lean on it.
- You already have a release tool or CI pipeline that owns these gates, and a second discipline layer on top only adds friction.
- The change is small or the project is throwaway, where a full pre-release checklist and a version-bump rule are more ceremony than the work needs.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`ship-release`](https://github.com/alexherrero/crickets/blob/main/src/releasing-conventions/skills/ship-release/SKILL.md) | skill | Pre-release checklist, changelog shape, paired-release order, and version-bump policy applied before you tag or publish. |
| [`version-bump-required`](https://github.com/alexherrero/crickets/blob/main/src/releasing-conventions/rules/version-bump-required.md) | rule | Flags a diff that touches a user-visible primitive without bumping the group's `group.yaml` version. |

### Configuration

No configuration — the plugin works out of the box. It requires `developer-workflows` to be enabled as its base.

## See also

- [Developer-Workflows](Developer-Workflows) — the `/release` phase this discipline gates, plus `/work`, `/plan`, and `/bugfix`.
- [Customization Types](Customization-Types) — what `kind: rule` and `kind: skill` mean.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)