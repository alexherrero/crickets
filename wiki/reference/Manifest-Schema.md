# Manifest schema

You configure crickets primitives and plugins with YAML manifests. You use two layers. The per-primitive **frontmatter** describes the primitive. You place this atop each `SKILL.md` / `hook.md` / agent `.md` / …. The per-group **`group.yaml`** describes the plugin. The `scripts/lint_src.py` script validates both layers. You run this script in CI + `check-all.sh`. You can find the source of truth at [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md).

## ⚡ Quick Reference

You use these fields in the primitive frontmatter atop a manifest file:

| Field | Required | Type | Allowed values / shape |
|---|---|---|---|
| `name` | yes | string | matches the primitive's dir/file name |
| `description` | yes | string | non-empty; one or two sentences |
| `kind` | yes | enum | `skill` · `agent` · `hook` · `command` · `mcp-server` · `status-line` · `output-style` · `workflow` · `rule` · `snippet` · `settings-fragment` |
| `supported_hosts` | yes | list | non-empty subset of `[claude-code, antigravity]` |
| `version` | no | string | semver `MAJOR.MINOR.PATCH` (optional `-prerelease`) |
| `install_scope` | no | enum | `user` · `project` · `either` (default `either`) |

The primitive's **group is the folder it lives in**. You do not use a `group:` field. The `install_scope` field is advisory. You set the actual placement with the host's plugin-install command (`claude plugin install … --scope user|project`).

## The group manifest (`group.yaml`)

You place one `group.yaml` in each `src/<group>/`. This file describes the plugin. The group **slug** is the folder name. You never write it as a field.

| Field | Required | Type | Meaning |
|---|---|---|---|
| `name` · `description` | yes | string | marketplace display |
| `category` | no | string | marketplace category (default `Coding`) |
| `standalone` | yes | bool | independently installable |
| `requires` | no | list | groups this plugin **hard**-depends on (each an existing `src/<slug>/`) |
| `capabilities` | no | list | named capabilities other plugins' `enhances` can target |
| `enhances` | no | list | groups this plugin **softly** augments when both are installed — a slug, or `{group, capability?, effect}` |

**Invariant (lint-enforced):** `standalone: true` ⟺ `requires: []`. You create an *integrated* plugin when it requires another. You create a standalone plugin when it requires nothing. The `enhances` field is orthogonal. It acts as a soft augmentation. A `standalone` plugin may still `enhance` a target.

```yaml
# src/code-review/group.yaml
name: Code Review
requires: []
standalone: true
enhances:
  - group: development-lifecycle
    capability: review
    effect: "/review dispatches the adversarial reviewers"
```

You can read [Plugin anatomy](Plugin-Anatomy) to learn how you compose these into a plugin.

## Primitive frontmatter (example: skill)

You place a skill at `skills/<name>/SKILL.md`. You use `<kind>/<name>.<ext>` for other kinds. You can read [Per-host paths](Per-Host-Paths) for details.

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

The generator finds a primitive by walking a group's `<kind>/` subdir. It looks for a manifest file:

| Kind | Discovered at |
|---|---|
| `skill` | `skills/<name>/SKILL.md` |
| `agent` | `agents/<name>.md` |
| `command` | `commands/<name>.md` |
| `hook` | `hooks/<name>/hook.md` |
| `snippet` | `snippets/<name>.md` |
| `output-style` | `output-styles/<name>.md` |
| `rule` | `rules/<name>.md` |

The other enum values (`mcp-server`, `status-line`, `workflow`, `settings-fragment`) are valid `kind`s. They have no discovery path or instance yet. A group's `scripts/` dir is a **group asset**. It is not a kind. The generator copies it verbatim to `<plugin>/scripts/`. You reference it as `${CLAUDE_PLUGIN_ROOT}/scripts/<name>` on Claude Code. You reference it as the relative `scripts/<name>` on Antigravity. Antigravity runs from inside the plugin dir.

## Validation

The `scripts/lint_src.py` script asserts these rules:

- **`group.yaml`** — You must provide `name` / `description` / `standalone`. The `standalone` field must be a bool. The `requires` field must be a list of existing group slugs. You must maintain the invariant `standalone ⟺ requires:[]`. The `capabilities` field must be a list. Each `enhances` target must exist. The target cannot be the group itself. The target cannot be in `requires`. You must declare any named `capability` on the target.
- **Primitive frontmatter** — You must provide `name` / `description` / `kind` / `supported_hosts`. The `supported_hosts` field must be a non-empty subset of `[claude-code, antigravity]`.

```bash
python3 scripts/lint_src.py
```

## Related

- [Plugin anatomy](Plugin-Anatomy) — You learn what a plugin is + its overall structure.
- [Customization types](Customization-Types) — You learn what each `kind` means.
- [Per-host paths](Per-Host-Paths) — You learn where each kind lands, per host.
- [Modify a plugin](Modify-A-Plugin) — You learn how to edit `src/`, regenerate, and dogfood.
- [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md) — You can read the source schema this mirrors.
