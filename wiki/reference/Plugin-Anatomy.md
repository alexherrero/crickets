# Plugin anatomy

A crickets plugin is a **functional group of primitives**. These primitives include skills, agents, commands, and hooks. You author them once under `src/<group>/`. A build script generates them into a native host plugin at `dist/<host>/plugins/<group>/`. The host's plugin manager installs this folder. The group folder *is* the plugin. Its name is the plugin slug. crickets doesn't redefine the host plugin format. It generates files into that format. This page outlines the crickets-side anatomy. It shows what you find in a plugin and how plugins relate. Read [the v3 design](crickets-build-system) to learn why you build it this way. Read [Compatibility](Compatibility) for host coverage.

## ⚡ Quick Reference

This is a generated plugin at `dist/<host>/plugins/<group>/`:

```
.claude-plugin/plugin.json   # the plugin manifest   (Antigravity: plugin.json at the plugin root)
skills/<name>/SKILL.md       # skills
agents/<name>.md             # agents
commands/<name>.md           # commands
hooks/hooks.json             # the hook manifest      (Antigravity: hooks.json at the plugin root)
hooks/<name>/                #   per hook: <name>.sh + <name>.ps1 + hook.md + settings-fragment-{bash,pwsh}.json
rules/<name>.md              # Antigravity only — emitted from snippets (Claude has no instruction-file primitive)
scripts/<name>               # group-level helper scripts, copied verbatim (both hosts)
```

Read [Customization types](Customization-Types) to learn what each kind is. Read [Per-host paths](Per-Host-Paths) to find the exact path per host.

## The group manifest

Each `src/<group>/group.yaml` describes the plugin. This file acts like per-primitive frontmatter for a single primitive.

| Field | Meaning |
|---|---|
| `name` · `description` · `category` | marketplace display |
| `standalone` | independently installable (⟺ `requires: []`) |
| `requires` | other groups this plugin hard-depends on |
| `enhances` | groups this plugin augments *when both are installed* (soft) |
| `capabilities` | named capabilities that other plugins' `enhances` can target |

Read [Manifest schema](Manifest-Schema) for the full contract and validation rules.

## How plugins compose

Plugins use three relationships. They scale in coupling.

- **standalone** — It works on its own. It depends on nothing (`requires: []`).
- **`requires`** — It acts as a hard dependency. On Claude Code, the manifest's native `dependencies` auto-installs the base. On Antigravity, the plugin ships thin. You must install the base first.
- **`enhances`** — It acts as a soft dependency. The plugin works alone. It augments a target when you install both. It engages via a capability probe instead of a hard link.

Here is a representative set of shipped plugins. You can find the full roster in the [Designs](Designs) section.

| Plugin | Standalone? | Relation to the base |
|---|---|---|
| `development-lifecycle` | ✅ (base) | declares the capabilities others target (`setup` … `documentation`) |
| `developer-safety` | ✅ | enhances `development-lifecycle` |
| `code-review` | ✅ | enhances `development-lifecycle`' `review` |
| `wiki-maintenance` | ✅ | enhances `development-lifecycle`' `documentation` |
| `pii` | ✅ | independent |
| `github-ci` | ❌ requires `development-lifecycle` | hard dependency |

## From source to installed

The pipeline moves from `src/<group>/` through `python3 scripts/generate.py build` to the committed `dist/<host>/plugins/<group>/`. The host then installs the whole plugin. The generated `dist/` directory is committed. This lets the marketplace serve static files. A CI gate proves it stays in sync with `src/`. You can edit and dogfood your changes via [Modify a plugin](Modify-A-Plugin). You can install plugins via [Install crickets plugins](Install-Into-Project).

## Related

- [Customization types](Customization-Types) — the primitive kinds a plugin holds.
- [Per-host paths](Per-Host-Paths) — where each kind lands, per host.
- [Manifest schema](Manifest-Schema) — `group.yaml` + primitive frontmatter.
- [Modify a plugin](Modify-A-Plugin) — edit `src/`, regenerate, dogfood.
- [Crickets v3.0 — native plugins](crickets-build-system) — the design + rationale.
