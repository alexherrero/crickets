# crickets source of truth (`src/`)

Single source of truth for the crickets customization catalog. Authors write each customization **once** here; `scripts/generate.py` (lands in part 2) emits native host plugins (Claude Code + Antigravity) into `dist/` from this tree.

Part of the **Crickets** native-plugin architecture — see the design at [crickets-build-system](https://github.com/alexherrero/crickets/wiki/crickets-build-system).

## Folder-per-group

One folder per **functional group** (a "plugin"). A primitive's group is simply the folder it lives in — the grouping is legible from the tree. Cross-plugin reuse (e.g. a group that builds on Developer) is expressed by **plugin dependencies at generation time** (`requires:` in the group manifest), never by a primitive living in two groups. So no file is duplicated across groups.

Each group folder holds:

- a `group.yaml` manifest (schema: [`src/SCHEMA.md`](SCHEMA.md), defined in task 2) — `name` / `description` / `category` / `requires:` / `standalone:`.
- primitive sub-folders by `kind`: `skills/`, `agents/`, `hooks/`, `commands/`, `mcp/`, … Each primitive keeps its existing frontmatter (`kind`, `supported_hosts`).

## Groups

This foundations part stands up the four groups that house an existing crickets primitive. The full catalog (Testing, Releasing, Design-docs, knowledge/personal, …) is built in bucket ④.

| Group | Purpose | Composition |
|---|---|---|
| `developer` | The base — phase/work conventions + control hooks + the base reviewer agent | base (`standalone: true`) |
| `pii` | PII guardrail (scanner skill + pre-push) | `standalone: true` |
| `github-ci` | CI / dependency-update tooling | `requires: [developer]` |
| `wiki` | Diátaxis wiki authoring support | `requires: [developer]` |

## Migration map (existing crickets primitives → group)

| Primitive | kind | Current path | → Group |
|---|---|---|---|
| `pii-scrubber` | skill | `skills/pii-scrubber/` | `pii` |
| `dependabot-fixer` | skill | `skills/dependabot-fixer/` | `github-ci` |
| `commit-on-stop` | hook | `hooks/commit-on-stop/` | `developer` |
| `kill-switch` | hook | `hooks/kill-switch/` | `developer` |
| `steer` | hook | `hooks/steer/` | `developer` |
| `evaluator` | agent | `agents/evaluator.md` | `developer` |
| `diataxis-evaluator` | agent | `agents/diataxis-evaluator.md` | `wiki` |

**7 primitives.** The copy + group manifests land in task 3.

## Transition (parts 1–5)

`src/` is the new canonical source. The old top-level primitive dirs (`skills/`, `agents/`, `hooks/`) + the `install.sh` dispatch remain in place until **part 5** (`distribution-clean-break`) deletes them — the operator's source-mode install symlinks into the old dirs, so they must keep resolving during the transition. During the transition, **edit primitives in `src/`**; the old dirs are frozen copies that part 5 removes.
