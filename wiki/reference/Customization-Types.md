# Customization types

crickets recognizes seven primitive kinds. You declare the kind in each primitive's `kind` field. You author a primitive under its kind's subdir inside a plugin group. You use the path `src/<group>/<subdir>/<name>`. The generator emits it into that group's plugin. It emits for each host in its `supported_hosts`. See [Per-host paths](Per-Host-Paths) for where each lands. See [Manifest Schema](Manifest-Schema) for the frontmatter contract.

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

These seven ship today. The `kind` enum also reserves `mcp-server`, `status-line`, `workflow`, and `settings-fragment`. No primitive uses them yet. The generator emits none. The full enum lives in [Manifest Schema](Manifest-Schema).

> [!NOTE]
> **Group-level `scripts/` is not a `kind`.** A `src/<group>/scripts/` dir holds verbatim helper scripts (e.g. `code-review/scripts/cross-review.sh`, `development-lifecycle/scripts/agentm_bridge.py`). These scripts lack frontmatter. They lack a `kind`. The system does not discover them as primitives. The generator copies the whole dir wholesale into the plugin at `<plugin>/scripts/`. It excludes `__pycache__`. This happens for both hosts. A primitive references a bundled script through the host's plugin path. You use `${CLAUDE_PLUGIN_ROOT}/scripts/<name>` on Claude Code. You use a **relative** `scripts/<name>` on Antigravity. Antigravity runs primitives from inside the plugin dir. It sets no plugin-root variable. See [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md) § Group-level assets.

## Choosing skill vs command vs agent

| You want… | Use |
|---|---|
| a helper the agent triggers on a keyword or context match (e.g. `pii-scrubber`) | `skill` |
| a user-typed `/something` command | `command` |
| a specialized agent for a specific task (e.g. [`evaluator`](Evaluator), `explorer`) | `agent` |

You can ship one concept as several primitives. For example, you can ship an [`evaluator`](Evaluator) agent plus a skill that auto-invokes it.

## Grouping primitives into a plugin

Primitives that belong together live in one group. You place them in `src/<group>/`. The generator emits this group as one installable plugin. The group's `group.yaml` declares its dependencies. It declares whether the group is `standalone` or `requires` another group. It declares what the group `enhances`. See [Manifest Schema](Manifest-Schema) for that contract. You place independent customizations in separate groups.

## Related

- [Plugin anatomy](Plugin-Anatomy) explains what a plugin is. It describes the overall structure.
- [Per-host paths](Per-Host-Paths) details where each kind lands in the plugin. It shows this per host.
- [Manifest Schema](Manifest-Schema) defines the frontmatter contract. It defines the `group.yaml` contract.
- [Hooks](Hooks) provides the hook catalog. It explains how hooks run.
- [Add a skill](Add-A-Skill) gives a worked authoring recipe.
