<!-- mode: reference -->
# GitHub CI

## Architecture

GitHub CI handles the mechanical breakage that follows a dependency bump. When Dependabot opens a PR and CI goes red, this plugin reads what failed and tries to fix it on the spot — a bounded, autonomous loop that clears the common cases without asking you to babysit each one. It never merges, so a person stays in the loop for the decision that matters.

### Diagram

_None / not needed._

### How it works

The plugin ships a single skill, `dependabot-fixer`. It triggers when you are on a `dependabot/*` branch with red CI, when you ask it to fix a Dependabot PR, or when you invoke `/dependabot-fix`. It reads the failing CI logs alongside the upstream package's CHANGELOG, and — if the repo has a `.harness/known-migrations.md` recipe for that package — uses the recipe as its first fix attempt. It then applies a bounded fix loop (three iterations by default), pushing each attempt to the Dependabot branch and re-running CI. When it succeeds it comments any residual risk on the PR; when the fix needs human judgment it aborts honestly and says so. It stops at the fix — merging is always left to a person. The `.harness/`-aware paths are soft references: when those files are absent the skill falls back to language defaults, so it works in any repo with Dependabot and CI, not only harness-installed projects.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | [Developer-Workflows](Developer-Workflows) | A hard dependency (`standalone: false`) — GitHub CI installs on top of the base phase loop rather than standing alone. |
| Required by (hard) | — | None. |

### Why not

GitHub CI is deliberately narrow, and it will not fit every setup. Reach for something else if:

- Your dependency updates break in ways that need real design judgment — an API redesign, a behavior change with no clear migration — rather than mechanical patching; the bounded loop is built for the well-understood cases and aborts on the rest.
- You already run a CI-repair or auto-merge tool you trust, and don't want a second automated hand on your Dependabot branches.
- The change is a one-off you'd rather fix by hand — spinning up the loop for a single trivial bump is more than a small change needs.

## Reference

### Commands & skills

The plugin ships one primitive, linked to its source.

| Primitive | Kind | What it does |
|---|---|---|
| [`dependabot-fixer`](https://github.com/alexherrero/crickets/blob/main/src/github-ci/skills/dependabot-fixer/SKILL.md) | skill | Bounded autonomous loop that repairs mechanical breakage on a Dependabot PR — reads failing CI logs and the upstream CHANGELOG, patches, re-runs, comments residual risk. Never merges. |

### Configuration

One optional environment variable tunes the fix loop; otherwise the plugin works out of the box.

| Setting | Default | Effect |
|---|---|---|
| `DEPENDABOT_FIX_BUDGET` | `3` | Caps the number of fix iterations the loop attempts before giving up. |

## See also

- [Developer Workflows](Developer-Workflows) — the base plugin GitHub CI requires.
- [Manifest schema](Manifest-Schema) — `requires:` vs `enhances:` and the `standalone` invariant.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is and how it's structured.
- [Install crickets plugins](Install-Into-Project) — the install modes.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)