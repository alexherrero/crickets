# Per-host paths reference

Where each `kind` lands in each host at install time. The installer reads each customization's `supported_hosts` and dispatches to the rows below.

## ⚡ Quick Reference

| Kind | Claude Code | Antigravity |
|---|---|---|
| `skill` | `.claude/skills/<name>/SKILL.md` | `.agent/skills/<name>/SKILL.md` |
| `command` | `.claude/commands/<name>.md` | (n/a — use `workflow` instead) |
| `agent` | `.claude/agents/<name>.md` | `.agent/skills/<name>/SKILL.md` (sub-agent-as-skill) |
| `hook` | `.claude/hooks/<name>` + `.claude/settings.json` merge | (n/a today) |
| `mcp-server` | `.claude/settings.json` merge OR `.claude/mcp-servers/` | **TBD** |
| `status-line` | `.claude/settings.json` merge | (n/a) |
| `output-style` | `.claude/output-styles/<name>.md` | (n/a) |
| `workflow` | (n/a) | `.agent/workflows/<name>.md` |
| `rule` | (n/a) | `.agent/rules/<name>.md` |
| `snippet` | append to repo-root `CLAUDE.md` | append to repo-root `AGENTS.md` |
| `settings-fragment` | merge into `.claude/settings.json` | **TBD** |

> [!NOTE]
> **Gemini CLI host removed in v0.9.0** per [ROADMAP item #15](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md). Standalone Gemini CLI is no longer a supported host; the legacy 3-column table is preserved in the v0.8.x and earlier wiki history. Antigravity (Gemini-in-IDE) stays as a supported host — different surface. See [ADR 0006](decisions/0006-gemini-cli-host-removal) for the host-scope-reduction rationale.

## What's locked vs. TBD

- **Locked** rows reflect the host's documented or de-facto convention as of toolkit v0.9.0.
- **TBD** entries are paths the installer doesn't dispatch to yet because the host's surface isn't formalized in public docs (Antigravity's `mcp-server` + `settings-fragment` conventions).

When a TBD path is encountered, the installer logs a warning and skips that host for that customization. The manifest still validates — `supported_hosts: [antigravity]` for a `mcp-server` is allowed; the installer just can't deliver yet.

**Revisit triggers** (tracked in `agentm/.harness/FOLLOWUPS.md`):

1. Antigravity publishes formal docs on MCP server conventions and/or `settings.json` merge semantics.
2. Google ships a Gemini-CLI successor that's worth re-adding (would require new ROADMAP item revisiting #15's decision).

## How dispatch works at install time

For each customization the installer encounters:

1. Read `kind` + `supported_hosts` from frontmatter.
2. For each host in `supported_hosts`:
   - Look up the (kind, host) cell in the table above.
   - If the cell is a path: copy source to that path (creating parent dirs as needed). Use `cp_managed_dir` semantics — wipe-and-recreate on `--update`, skip-if-exists otherwise.
   - If the cell is "(n/a)": skip silently. The customization simply isn't installable on that host.
   - If the cell is **TBD**: log a warning and skip.

## Standalone vs. inside-bundle

Both follow the same dispatch table. Source paths differ:

- **Standalone primitive:** `crickets/<kind-subdir>/<name>/` → destination per table.
- **Inside a bundle:** `crickets/bundles/<bundle>/<kind-subdir>/<name>/` → same destination per table (the bundle structure is invisible at the destination — the inner primitive lands at the same path it would as a standalone).

This means a bundle's primitives can collide at the destination with standalone primitives of the same name. v0.1.0 has no such collision (one bundle with one inner skill, three standalone skills with unique names); future versions may need a collision policy. Tracked as an open question.

## Related

- [Customization Types](Customization-Types) — what each kind means.
- [Manifest Schema](Manifest-Schema) — frontmatter required to participate in dispatch.
- [Installer CLI](Installer-CLI) — flag reference.
- [Add a Skill](Add-A-Skill) — the most common dispatch path walked through.
