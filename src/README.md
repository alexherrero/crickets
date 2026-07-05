# crickets source of truth (`src/`)

Single source of truth for the crickets customization catalog. Authors write each customization **once** here; `scripts/generate.py` emits native host plugins (Claude Code + Antigravity) into `dist/` from this tree:

```bash
python3 scripts/generate.py build   # write dist/ + the root marketplace pointer(s) from src/
python3 scripts/generate.py check   # exit non-zero if dist/ has drifted from src/ (the CI gate)
python3 scripts/generate.py clean   # remove dist/ + the root pointer(s)
```

Part of the **Crickets** native-plugin architecture — see the design at [crickets-build-system](https://github.com/alexherrero/crickets/wiki/crickets-build-system).

## Folder-per-group

One folder per **functional group** (a "plugin"). A primitive's group is simply the folder it lives in — the grouping is legible from the tree. Cross-plugin reuse (e.g. a group that builds on Developer Workflows) is expressed by **plugin dependencies at generation time** (`requires:` in the group manifest), never by a primitive living in two groups. So no file is duplicated across groups.

Each group folder holds:

- a `group.yaml` manifest (schema: [`src/SCHEMA.md`](SCHEMA.md)) — `name` / `description` / `category` / `requires:` / `standalone:` / `capabilities:` / `enhances:` / `version:`.
- primitive sub-folders by `kind`: `skills/`, `agents/`, `hooks/`, `commands/`, `mcp/`, `output-styles/`, `rules/`, `snippets/`. Each primitive keeps its own frontmatter (`kind`, `supported_hosts`, plus kind-specific fields).
- optionally `scripts/` and/or `templates/` — host-agnostic asset dirs copied verbatim into the emitted plugin (not a discovered primitive kind; e.g. `code-review`'s `cross-review.sh`, `wiki-maintenance`'s section-template library).

## Groups

The current catalog — 13 plugins, one group per row. `requires:` is a hard dependency (installed by both the plugin manager and `bootstrap.sh`); `enhances:` (not shown) is soft composition — see [Plugins](https://github.com/alexherrero/crickets/wiki/Plugins) for the full per-plugin description and [Plugin anatomy](https://github.com/alexherrero/crickets/wiki/Plugin-Anatomy) for the shared structure.

| Group | Purpose | `requires:` |
|---|---|---|
| `developer-workflows` | The phase-gated dev loop (`/setup` … `/bugfix`) the other plugins build on | `[]` |
| `developer-safety` | Kill switch, `steer`, `commit-on-stop`, commit conventions | `[]` |
| `code-review` | Adversarial review of any diff or PR | `[]` |
| `github-ci` | CI / dependency-update tooling (`dependabot-fixer`) | `[developer-workflows]` |
| `wiki-maintenance` | Keeps the wiki true to the code, in-voice | `[]` |
| `pii` | PII guardrail (scanner skill + pre-push) | `[]` |
| `design-docs` | Design-doc + ADR authoring (`/design`) | `[developer-workflows]` |
| `github-projects` | One-way vault→GitHub Project board sync | `[developer-workflows]` |
| `obsidian-vault` | The Obsidian/Google-Drive vault storage backend for agentm | `[]` |
| `releasing-conventions` | Release discipline + the ship-release workflow | `[developer-workflows]` |
| `testing-conventions` | Day-to-day testing principles | `[developer-workflows]` |
| `token-audit` | Deterministic JSONL session-cost analyzer | `[]` |
| `status-line-meter` | Live context/cost meter for the Claude Code status line | `[]` |

## Emitted output

`generate.py build` writes `dist/claude-code/plugins/<slug>/` and `dist/antigravity/plugins/<slug>/` per group, plus each host's root marketplace pointer (`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`). A kind a given host's emitter can't express is either dropped with a logged reason (e.g. Claude Code has no instruction-file primitive, so `kind: snippet` is dropped there) or folded into the nearest real surface (e.g. Antigravity has no `output-style` mechanism, so that content ships as a `rules/` file instead) — see `scripts/emit_claude.py` / `scripts/emit_antigravity.py` and the `KIND_HOST_EXPRESSIBLE` table in `scripts/src_model.py`, which `scripts/lint_src.py` checks every primitive's `supported_hosts` claim against.
