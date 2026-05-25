# Manifest schema reference

YAML frontmatter contract for every customization in `crickets`. Validated by `scripts/validate-manifests.py` on every commit.

## ⚡ Quick Reference

| Field | Type | Required | Allowed values / shape |
|---|---|---|---|
| `name` | string | yes | Matches dirname (or `bundle` for `bundle.md`). |
| `description` | string | yes | Non-empty; one or two sentences. |
| `kind` | enum string | yes | `bundle` \| `skill` \| `command` \| `agent` \| `hook` \| `mcp-server` \| `status-line` \| `output-style` \| `workflow` \| `rule` \| `snippet` \| `settings-fragment` |
| `supported_hosts` | list of strings | yes | Non-empty subset of `[claude-code, antigravity]`. (Gemini CLI host removed in v0.9.0 per [ROADMAP item #15](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md); see [ADR 0006](decisions/0006-gemini-cli-host-removal). Validator emits a `removed host` error with v0.9.0 CHANGELOG pointer if `gemini-cli` is still present.) |
| `version` | string | yes | Semver-shape `MAJOR.MINOR.PATCH` with optional `-prerelease` suffix |
| `contents` | list of mappings | bundles only | Non-empty list of `{<kind>: <name>}` items; each resolves to a file/dir within the bundle |
| `install_scope` | enum string | optional | `user` \| `project` \| `either` (default: `either`) |
| `deprecated` | string | optional | Lifecycle marker — reason for deprecation |

## Standalone primitive (example: skill)

File path: `skills/<name>/SKILL.md` (for skills; other kinds use `<kind>/<name>.<ext>` per [Per-Host Paths](Per-Host-Paths)).

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

## Bundle

File path: `bundles/<name>/bundle.md` + primitive subdirs (e.g. `bundles/<name>/skills/<primitive-name>/SKILL.md`).

```yaml
---
name: example-bundle
description: Reference skeleton showing how to package a multi-primitive customization.
kind: bundle
supported_hosts: [claude-code, antigravity]
contents:
  - skill: example-skill
  - hook: pre-push-extra      # (when other-kind support lands; v0.1.0 only handles skill kind in bundles)
version: 0.1.0
---

<bundle body — what this bundle does as a whole>
```

Primitives **inside** a bundle have a relaxed schema — they inherit `kind`, `supported_hosts`, and `version` from the parent bundle's manifest. Only `name` and `description` are required in their own frontmatter.

## Validation rules

The `scripts/validate-manifests.py` script asserts every manifest in the repo:

1. Has YAML frontmatter delimited by `---` lines.
2. Frontmatter is a mapping (not a list, not a scalar).
3. Required fields present and non-empty.
4. `kind` is in the 12-entry enum.
5. `supported_hosts` is a non-empty subset of the canonical 3 hosts.
6. `version` matches semver shape (regex: `^\d+\.\d+\.\d+(-[0-9A-Za-z-.]+)?$`).
7. `install_scope`, if present, is in `{user, project, either}`.
8. For bundles: `contents` is a non-empty list of single-key mappings, and each mapping's value resolves to a file/dir within the bundle.
9. `name` matches the customization's directory name (or `bundle` for `bundle.md`).

Run locally:

```bash
python3 scripts/validate-manifests.py
```

Exit `0` on clean; exit `1` with `file:line` on first failure.

## Optional fields explained

### `install_scope`

- `user` — the customization belongs at user-global path (e.g. `~/.claude/skills/<name>/`). Installs once per user, available across all projects.
- `project` — the customization belongs at project-local path (e.g. `<project>/.claude/skills/<name>/`). Installs per-project.
- `either` (default) — defer to the user's invocation. Project-local install (`bash install.sh <target>`) lands in project paths; user-global install is a future invocation mode.

v0.1.0 of the toolkit always installs into project paths (the installer takes a `<target-project-path>` argument). `install_scope` is captured in the schema for forward compatibility — when user-global installation lands in a future toolkit release (likely paired with the `dev-machine-setup` plan), the field becomes load-bearing.

### `deprecated`

- A string reason. Validator accepts any non-empty string.
- Installer prints a warning when a deprecated customization is installed.
- Future toolkit version may auto-skip deprecated customizations under `--all` and require explicit `--bundle <name>` / `--skill <name>` to install them.

## Related

- [Customization Types](Customization-Types) — what each `kind` means and where to put it.
- [Per-Host Paths](Per-Host-Paths) — destination paths per kind per host.
- [Installer CLI](Installer-CLI) — flags and modes.
- [Add a Skill](Add-A-Skill) — practical recipe.
- [ADR 0001](0001-crickets-purpose) — why the schema looks like this.
