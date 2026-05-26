# How to add a plugin

A `kind: plugin` customization packages one or more skills (and optional references / examples / policies) into a single installable unit for delivery into **Antigravity 2.0 + Antigravity CLI (`agy`)**. Plugins are Antigravity's bundle-shaped primitive — closest crickets analogue is `kind: bundle`, but with JSON manifest at root instead of YAML frontmatter on a `bundle.md`.

This how-to walks through authoring + installing a plugin. The reference implementation is `crickets/plugins/example-plugin/`.

## When to author a plugin (vs. a skill / bundle)

| Use case | Right primitive |
|---|---|
| Single skill, Claude Code + Antigravity both supported | `kind: skill` (existing pattern) |
| Multi-primitive coordinated install (skills + agents + hooks), both hosts | `kind: bundle` |
| Skill(s) packaged for Antigravity marketplace / `agy plugin install <git-url>` distribution | **`kind: plugin`** |
| Skill(s) you want shareable as a standalone git repo for agy users | **`kind: plugin`** |

**Plugins target Antigravity exclusively.** Claude Code has no peer concept; if you want claude-code support too, ship the same SKILL.md files as a `kind: skill` standalone in parallel.

## 1. Create the plugin directory + manifest

Under `crickets/plugins/<plugin-name>/`:

```
plugins/my-plugin/
├── plugin.md                          # required — toolkit-side YAML manifest
├── skills/
│   ├── <skill-name>/
│   │   └── SKILL.md                   # required per skill
│   └── ...
├── references/                        # optional — referenced from SKILL.md
├── examples/                          # optional
└── policies/                          # optional — TOML safety rules
```

`plugin.md` frontmatter (per [Manifest-Schema](../reference/Manifest-Schema)):

```yaml
---
name: my-plugin
description: <one paragraph — what the plugin does, when to use it>
kind: plugin
supported_hosts: [antigravity]
version: 0.1.0
author: <your name or org>
repository: <github URL>
license: <SPDX id, e.g. Apache-2.0>
keywords: [<tag>, <tag>]
contents:
  - skill: <skill-name>
  - skill: <another-skill-name>
---

# <Plugin title>

<plugin body — what this plugin does as a whole; reader-facing>
```

The `name`, `description`, `version`, `author`, `repository`, `license`, `keywords` fields are written into the generated `plugin.json` at install time.

## 2. Author the nested skill(s)

Each `skills/<skill-name>/SKILL.md` follows the standard skill shape (per [Add-A-Skill](Add-A-Skill)):

```yaml
---
name: <skill-name>
description: <activation prompt — describe when the agent should invoke this skill>
---

# <Skill title>

<skill body — operational instructions for the agent>
```

**Two frontmatter fields only** for the nested SKILL.md (`name` + `description`) — this matches Antigravity's expected schema. Crickets-specific fields like `kind` / `supported_hosts` are inherited from the parent plugin's manifest (matching the bundle convention).

## 3. Validate

```bash
python3 crickets/scripts/validate-manifests.py
```

The validator checks `plugin.md` frontmatter shape + verifies nested skills exist at the expected paths.

## 4. Install locally for testing

```bash
bash crickets/scripts/install-plugin.sh my-plugin
```

This:
1. Reads `crickets/plugins/my-plugin/plugin.md`.
2. Generates `~/.gemini/config/plugins/my-plugin/plugin.json` from the YAML frontmatter.
3. Copies nested `skills/`, `references/`, `examples/`, `policies/` to `~/.gemini/config/plugins/my-plugin/`.
4. Writes `installed_version.json` for parity with agy-installed plugins.

Other modes:

```bash
bash crickets/scripts/install-plugin.sh --list           # list available + installed
bash crickets/scripts/install-plugin.sh --uninstall my-plugin
```

## 5. Verify discovery

```bash
agy plugin list
```

> [!NOTE]
> **`agy plugin list` may not show filesystem-installed plugins.** That command tracks plugins imported via `agy plugin install` (Antigravity's own import flow). Plugins installed via `install-plugin.sh` populate the filesystem directly, which agy's runtime DOES scan for skill discovery (per agy's 1.0.1 changelog: *"Added plugin discovery for skills and agents. Automatically scans installed plugin directories..."*) but may not register in the plugin-list metadata. Functional impact: skills inside the plugin ARE discoverable in agy sessions. Cosmetic impact: `plugin list` doesn't reflect them. To force registration, see § 6 below.

The actual functional test:

```bash
cd /tmp                                # any directory works
agy --print "Use the <skill-name> skill" --print-timeout 30s
```

If the agent invokes the skill and responds per its SKILL.md instructions, discovery works.

## 6. (Optional) Distribute via `agy plugin install`

For shareable distribution, publish your plugin as a standalone git repo with `plugin.json` (the GENERATED JSON, not the toolkit-side YAML) at the root + skills underneath:

```
my-plugin-repo/
├── plugin.json
└── skills/
    └── <skill-name>/
        └── SKILL.md
```

Users install via:

```bash
agy plugin install https://github.com/<you>/my-plugin-repo
```

This goes through agy's own import flow and registers the plugin in `agy plugin list`. The downside: you maintain the plugin separately from crickets's source. The upside: marketplace distribution + automatic update support.

**Hybrid approach (recommended)**: author in crickets's `plugins/<name>/` for development + validation, then `git subtree split` the subdirectory to a standalone repo for publication. Or use `install-plugin.sh` for local testing + a separate distribution repo for users.

## 7. (Optional) Add policies

Plugins can ship safety policies that constrain what tools the agent can invoke. Example from `modern-web-guidance-plugin`:

```toml
# policies/<name>.toml
[[rule]]
toolName = "run_shell_command"
commandRegex = "modern-web"
decision = "ask_user"
priority = 100
modes = ["plan"]
```

Place at `plugins/<plugin-name>/policies/<name>.toml`. The installer copies the entire `policies/` dir if present.

## Anti-patterns

- **Don't author a plugin if a `kind: skill` works.** Plugins add packaging overhead; only use them when distributing to Antigravity-only users via marketplace / git URL.
- **Don't duplicate skill content across `kind: skill` and `kind: plugin`.** If the same skill needs to ship to both Claude Code and Antigravity, use `kind: skill` with `supported_hosts: [claude-code, antigravity]` — the installer handles both paths.
- **Don't hand-author `plugin.json`.** Use the toolkit-side `plugin.md` YAML frontmatter; the installer generates the JSON. Manual JSON edits drift from the YAML source of truth.
- **Don't put skills outside `skills/`.** Antigravity's discovery scans `~/.gemini/config/plugins/<plugin>/skills/<skill>/SKILL.md` — flat layout or unconventional paths won't be discovered.

## Related

- [Manifest Schema](../reference/Manifest-Schema) — full `kind: plugin` frontmatter spec.
- [Per-Host Paths](../reference/Per-Host-Paths) — where plugins land at install time.
- [ADR 0011](../explanation/decisions/0011-antigravity-2-host-support) — the host-support decision that introduced `kind: plugin`.
- [Compatibility](../reference/Compatibility) — Antigravity 2.0 + Antigravity CLI compatibility surface.
- [Add a Skill](Add-A-Skill) — authoring a standalone skill (not packaged as a plugin).
- [Add a Bundle](Add-A-Bundle) — authoring a multi-host bundle (Claude Code + Antigravity).
