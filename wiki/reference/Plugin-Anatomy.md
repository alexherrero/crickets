# Plugin anatomy

A crickets plugin is a **functional group of primitives** — skills, agents, commands, hooks — authored once under `src/<group>/` and generated into a native host plugin at `dist/<host>/plugins/<group>/`, which the host's plugin manager installs. The group folder *is* the plugin, and its name is the plugin slug. crickets doesn't redefine the host plugin format — it generates into it; this page is the crickets-side anatomy: what's in a plugin and how plugins relate. For why it's built this way see [the v3 design](crickets-build-system); for host coverage see [Compatibility](Compatibility).

## ⚡ Quick Reference

A generated plugin — `dist/<host>/plugins/<group>/`:

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

[Customization types](Customization-Types) covers what each kind is; [Per-host paths](Per-Host-Paths) the exact path per host.

## The group manifest

Each `src/<group>/group.yaml` describes the plugin — what per-primitive frontmatter does for a single primitive:

| Field | Meaning |
|---|---|
| `name` · `description` · `category` | marketplace display |
| `standalone` | independently installable (⟺ `requires: []`) |
| `requires` | other groups this plugin hard-depends on |
| `enhances` | groups this plugin augments *when both are installed* (soft) |
| `capabilities` | named capabilities that other plugins' `enhances` can target |

See [Manifest schema](Manifest-Schema) for the full contract + validation rules.

## How plugins compose

Three relationships, in increasing coupling:

- **standalone** — works on its own, depends on nothing (`requires: []`).
- **`requires`** — a hard dependency. On Claude Code the manifest's native `dependencies` auto-installs the base; on Antigravity the plugin ships thin and the docs say "install the base first."
- **`enhances`** — soft: the plugin works alone and *augments* a target when both are installed, engaged by a capability probe rather than a hard link.

The six shipped plugins:

| Plugin | Standalone? | Relation to the base |
|---|---|---|
| `developer-workflows` | ✅ (base) | declares the capabilities others target (`setup` … `documentation`) |
| `developer-safety` | ✅ | enhances `developer-workflows` |
| `code-review` | ✅ | enhances `developer-workflows`' `review` |
| `wiki-maintenance` | ✅ | enhances `developer-workflows`' `documentation` |
| `pii` | ✅ | independent |
| `github-ci` | ❌ requires `developer-workflows` | hard dependency |

## From source to installed

`src/<group>/` → `python3 scripts/generate.py build` → committed `dist/<host>/plugins/<group>/` → the host installs the whole plugin. The generated `dist/` is committed, so the marketplace serves static files and a CI gate proves it stays in sync with `src/`. Edit and dogfood via [Modify a plugin](Modify-A-Plugin); install via [Install crickets plugins](Install-Into-Project).

## Related

- [Customization types](Customization-Types) — the primitive kinds a plugin holds.
- [Per-host paths](Per-Host-Paths) — where each kind lands, per host.
- [Manifest schema](Manifest-Schema) — `group.yaml` + primitive frontmatter.
- [Modify a plugin](Modify-A-Plugin) — edit `src/`, regenerate, dogfood.
- [Crickets v3.0 — native plugins](crickets-build-system) — the design + rationale.
