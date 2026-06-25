<!-- mode: index -->
# GitHub CI

_CI + dependency-update tooling. Ships `dependabot-fixer` — a bounded autonomous loop that clears mechanical Dependabot breakage without merging._

## How it composes

- **Requires `developer-workflows`** — a **hard** dependency (`standalone: false`). This is the `requires:` half of the composition model (unlike `enhances:`, used by `developer-safety` / `code-review`, which is soft + optional). See [Manifest schema](Manifest-Schema).
- **Hosts** — both; the skill is host-symmetric.

## Why it works

Dependency bumps break in mechanical, well-understood ways, so a bounded autonomous loop — read the failing logs + the upstream CHANGELOG, patch, re-run — clears the common cases without a human babysitting each one. It **never merges**, surfaces residual risk as a PR comment, and aborts honestly when a fix needs a person.

## Related

- [Developer Workflows](Developer-Workflows) — the base plugin this requires.
- [Manifest schema](Manifest-Schema) — `requires:` vs `enhances:` and the `standalone` invariant.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Install crickets plugins](Install-Into-Project) — all three install modes.

[Architecture](Architecture) · [Plugins](Plugins) · [Home](Home)
