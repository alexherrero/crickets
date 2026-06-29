<!-- mode: index -->
# Customization model

_What a crickets customization is made of: the primitive kinds, and how plugins compose._

A crickets customization is a **primitive** — a skill, command, agent, hook, or snippet — described by a YAML manifest. Primitives that belong together live in one **plugin**, and the plugin is the unit you install. You author one primitive per file; its frontmatter says what kind it is and which hosts it runs on.

## How it works

A primitive's `kind` field decides both what it does and where you author it — `src/<group>/<kind-dir>/<name>`. The generator discovers it by walking that subdir, and a per-group `group.yaml` describes the plugin around it. Seven kinds ship today; the schema reserves four more (`mcp-server`, `status-line`, `workflow`, `settings-fragment`) with no instance yet.

| Kind | What it is |
|---|---|
| **`skill`** | an agent-invoked helper — the model triggers it on a context match. |
| **`command`** | a user-typed `/slash` command. |
| **`agent`** | a sub-agent for fan-out work. |
| **`hook`** | a script the host runs at a session event. |
| **`snippet`** | a standing instruction fragment. |
| **`output-style`** | a host output style (e.g. `terse`). |
| **`rule`** | a standing rule fragment (e.g. `edit-over-write`). |

Plugins compose two ways. A plugin `requires:` another when it hard-depends on it — it is then *integrated*, not `standalone`. A plugin `enhances:` another when it augments it only if both are installed: soft, and skipped when the target is absent.

## How it fits

- **[Plugins](Plugins)** — the unit primitives ship in. Each `src/<group>/` is one plugin; `group.yaml`'s `requires:` / `enhances:` are where one plugin's relationship to another is declared.
- **[Build & distribution](Build-And-Distribution)** — what reads these manifests. The generator switches on `kind` and `supported_hosts` to emit each plugin.
- **[Host adapters](Host-Adapters)** — where a primitive's `supported_hosts` + `kind` resolve to a real destination. The model declares intent; the adapter places the artifact.

## See also

Detail:

- [Customization types](Customization-Types) — the full primitive catalogue, kind by kind.
- [Manifest schema](Manifest-Schema) — every frontmatter and `group.yaml` field, and when each is required.
- [Add a skill](Add-A-Skill) · [Add a plugin](Add-A-Plugin) · [Modify a plugin](Modify-A-Plugin) — the authoring how-tos.

[Architecture](Architecture) · [Reference](Reference) · [Home](Home)
