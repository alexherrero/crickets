# Customization types

The primitive **kinds** crickets recognizes via each primitive's `kind` field. You author a primitive under its kind's subdir inside a plugin group — `src/<group>/<subdir>/<name>` — and the generator emits it into that group's plugin for each host in its `supported_hosts`. This page is what each kind *is* and when to reach for which; for where each lands see [Per-host paths](Per-Host-Paths), and for the frontmatter contract see [Manifest Schema](Manifest-Schema).

## ⚡ Quick Reference

| Kind | Authored in | What it is | Effective on |
|---|---|---|---|
| `skill` | `skills/<name>/SKILL.md` | agent-invoked helper — the model triggers it on a context match | both |
| `command` | `commands/<name>.md` | user-typed `/slash` command | both |
| `agent` | `agents/<name>.md` | specialized sub-agent for fan-out work | both |
| `hook` | `hooks/<name>/` | script the host runs at a session event ([Hooks](Hooks)) | both — observe-only on Antigravity |
| `snippet` | `snippets/<name>.md` | standing instruction fragment — emits as an Antigravity `rules/` file; Claude plugins can't ship instruction files, so it's dropped and the convention is carried directly in `CLAUDE.md` / `AGENTS.md` instead | Antigravity |
| `output-style` | `output-styles/<name>.md` | named output-style — agent reads it when referenced by name (e.g. `terse`); adjusts verbosity or format | both |
| `rule` | `rules/<name>.md` | standing behavioral rule — merged into the agent's context as a persistent instruction (e.g. `edit-over-write`) | both |

These seven ship today. The `kind` enum also reserves `mcp-server`, `status-line`, `workflow`, and `settings-fragment` — no primitive uses them yet, so the generator emits none. The full enum lives in [Manifest Schema](Manifest-Schema).

> [!NOTE]
> **Group-level `scripts/` is not a `kind`.** A `src/<group>/scripts/` dir holds verbatim helper scripts (e.g. `code-review/scripts/cross-review.sh`, `developer-workflows/scripts/find_capability.py`) — no frontmatter, no `kind`, not discovered as a primitive. The generator copies the whole dir wholesale (excluding `__pycache__`) into the plugin at `<plugin>/scripts/`, both hosts. A primitive references a bundled script through the host's plugin path — `${CLAUDE_PLUGIN_ROOT}/scripts/<name>` on Claude Code, or a **relative** `scripts/<name>` on Antigravity, which runs primitives from inside the plugin dir and sets no plugin-root variable. See [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md) § Group-level assets.

## Choosing skill vs command vs agent

| You want… | Use |
|---|---|
| a helper the agent triggers on a keyword or context match (e.g. `pii-scrubber`) | `skill` |
| a user-typed `/something` command | `command` |
| a specialized agent for a specific task (e.g. [`evaluator`](Evaluator), `explorer`) | `agent` |

One concept can ship as several primitives — e.g. an [`evaluator`](Evaluator) agent plus a skill that auto-invokes it.

## Grouping primitives into a plugin

Primitives that belong together live in one group (`src/<group>/`), which emits as one installable plugin. The group's `group.yaml` declares whether it's `standalone` or `requires` another group, and what it `enhances` — see [Manifest Schema](Manifest-Schema) for that contract. Independent customizations go in separate groups.

## Related

- [Plugin anatomy](Plugin-Anatomy) — what a plugin is + its overall structure.
- [Per-host paths](Per-Host-Paths) — where each kind lands in the plugin, per host.
- [Manifest Schema](Manifest-Schema) — the frontmatter + `group.yaml` contract.
- [Hooks](Hooks) — the hook catalog + how hooks run.
- [Add a skill](Add-A-Skill) — a worked authoring recipe.
