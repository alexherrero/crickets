# Manifest schema

Every crickets primitive and plugin carries a YAML manifest, in two layers: per-primitive **frontmatter** (atop each `SKILL.md` / `hook.md` / agent `.md` / …) describes the primitive, and a per-group **`group.yaml`** describes the plugin. Both are validated by `scripts/lint_src.py` (run in CI + `check-all.sh`); the source of truth is [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md).

## ⚡ Quick Reference

Primitive frontmatter — the fields atop a primitive's manifest file:

| Field | Required | Type | Allowed values / shape |
|---|---|---|---|
| `name` | yes | string | matches the primitive's dir/file name |
| `description` | yes | string | non-empty; one or two sentences |
| `kind` | yes | enum | `skill` · `agent` · `hook` · `command` · `mcp-server` · `status-line` · `output-style` · `workflow` · `rule` · `snippet` · `settings-fragment` |
| `supported_hosts` | yes | list | non-empty subset of `[claude-code, antigravity]` |
| `version` | no | string | semver `MAJOR.MINOR.PATCH` (optional `-prerelease`) |
| `install_scope` | no | enum | `user` · `project` · `either` (default `either`) |

The primitive's **group is the folder it lives in** — there is no `group:` field. `install_scope` is advisory: the host's plugin-install command (`claude plugin install … --scope user|project`) sets actual placement.

## The group manifest (`group.yaml`)

One per `src/<group>/`; describes the plugin. The group **slug** is the folder name, never a field.

| Field | Required | Type | Meaning |
|---|---|---|---|
| `name` · `description` | yes | string | marketplace display |
| `category` | no | string | marketplace category (default `Coding`) |
| `standalone` | yes | bool | independently installable |
| `requires` | no | list | groups this plugin **hard**-depends on (each an existing `src/<slug>/`) |
| `capabilities` | no | list | named capabilities other plugins' `enhances` can target |
| `enhances` | no | list | groups this plugin **softly** augments when both are installed — a slug, or `{group, capability?, effect}` |

**Invariant (lint-enforced):** `standalone: true` ⟺ `requires: []`. A plugin that requires another is *integrated*; one that requires nothing is standalone. `enhances` is orthogonal — soft, so a `standalone` plugin may still `enhance` a target.

```yaml
# src/code-review/group.yaml
name: Code Review
requires: []
standalone: true
enhances:
  - group: developer-workflows
    capability: review
    effect: "/review dispatches the adversarial reviewers"
```

See [Plugin anatomy](Plugin-Anatomy) for how these compose into a plugin.

## Primitive frontmatter (example: skill)

A skill at `skills/<name>/SKILL.md`; other kinds use `<kind>/<name>.<ext>` (see [Per-host paths](Per-Host-Paths)).

```yaml
---
name: pii-scrubber
description: Scan the current git diff for personal information before commit or push.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

<skill body — operational instructions for the agent>
```

## Which kinds the generator discovers

The generator finds a primitive by walking a group's `<kind>/` subdir for a manifest file:

| Kind | Discovered at |
|---|---|
| `skill` | `skills/<name>/SKILL.md` |
| `agent` | `agents/<name>.md` |
| `command` | `commands/<name>.md` |
| `hook` | `hooks/<name>/hook.md` |
| `snippet` | `snippets/<name>.md` |

The other enum values (`mcp-server`, `status-line`, `output-style`, `workflow`, `rule`, `settings-fragment`) are valid `kind`s but have no discovery path or instance yet. A group's `scripts/` dir is a **group asset**, not a kind — copied verbatim to `<plugin>/scripts/` and referenced as `${CLAUDE_PLUGIN_ROOT}/scripts/<name>` on Claude Code, or the relative `scripts/<name>` on Antigravity (which runs from inside the plugin dir).

## Validation

`scripts/lint_src.py` asserts:

- **`group.yaml`** — `name` / `description` / `standalone` present; `standalone` a bool; `requires` a list of existing group slugs; the invariant `standalone ⟺ requires:[]`; `capabilities` a list; each `enhances` target exists, isn't the group itself, isn't also in `requires`, and any named `capability` is declared on the target.
- **Primitive frontmatter** — `name` / `description` / `kind` / `supported_hosts` present; `supported_hosts` a non-empty subset of `[claude-code, antigravity]`.

```bash
python3 scripts/lint_src.py
```

## Related

- [Plugin anatomy](Plugin-Anatomy) — what a plugin is + its overall structure.
- [Customization types](Customization-Types) — what each `kind` means.
- [Per-host paths](Per-Host-Paths) — where each kind lands, per host.
- [Modify a plugin](Modify-A-Plugin) — edit `src/`, regenerate, dogfood.
- [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md) — the source schema this mirrors.
