<!-- mode: index -->
# GitHub CI

CI + dependency-update tooling. Today it ships one skill — **`dependabot-fixer`**, which repairs breakage on Dependabot PRs. It's the first **non-standalone** crickets plugin: it `requires` `developer-workflows`.

## Install

```bash
claude plugin install github-ci@crickets
```

Installing it pulls in **`developer-workflows`** (its hard dependency). On Antigravity, install by path (see [Install crickets plugins](Install-Into-Project)); the skill runs on both hosts.

## What it ships

| Primitive | Kind | What it does |
|---|---|---|
| **`dependabot-fixer`** | skill | on a red `dependabot/*` PR, reads the failing CI logs + the upstream CHANGELOG, applies a bounded fix loop, pushes commits to the branch, and comments residual risk on the PR. **Never merges**; aborts honestly when the fix needs human judgment. |

It triggers three ways: the branch is `dependabot/*` and CI is red, you ask to "fix the dependabot PR," or you invoke `/dependabot-fix [pr-number]`. Per-project fix recipes live in the harness's `.harness/known-migrations.md`.

## How it composes

- **Requires `developer-workflows`** — a **hard** dependency (`standalone: false`), unlike the standalone plugins. This is the `requires:` half of the composition model — the plugin won't install or run without its base, where `enhances:` (used by `developer-safety` / `code-review`) is soft and optional. See [Manifest schema](Manifest-Schema).
- **Hosts** — both; the skill is host-symmetric.

## Why it works

Dependency bumps break in mechanical, well-understood ways, so a bounded autonomous loop — read the failing logs + the upstream CHANGELOG, patch, re-run — clears the common cases without a human babysitting each one. The guardrails keep judgment where it belongs: it **never merges**, surfaces residual risk as a PR comment rather than hiding it, and aborts honestly when a fix needs a person. Automation handles the rote 80%; the human keeps the call on the rest.

## Related

- [Developer Workflows](Developer-Workflows) — the base plugin this requires.
- [Manifest schema](Manifest-Schema) — `requires:` vs `enhances:` and the `standalone` invariant.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Install crickets plugins](Install-Into-Project) — all three install modes.
