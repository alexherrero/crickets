# Per-host paths reference

Where each `kind` lands in each host at install time. The installer reads each customization's `supported_hosts` and dispatches to the rows below.

## ⚡ Quick Reference

| Kind | Claude Code | Antigravity | Gemini CLI |
|---|---|---|---|
| `skill` | `.claude/skills/<name>/SKILL.md` | `.agent/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md` |
| `command` | `.claude/commands/<name>.md` | (n/a — use `workflow` instead) | `.gemini/commands/<name>.toml` |
| `agent` | `.claude/agents/<name>.md` | `.agent/skills/<name>/SKILL.md` (sub-agent-as-skill) | `.gemini/agents/<name>.md` |
| `hook` | `.claude/hooks/<name>` + `.claude/settings.json` merge | (n/a today) | (n/a today) |
| `mcp-server` | `.claude/settings.json` merge OR `.claude/mcp-servers/` | **TBD** | `.gemini/settings.json` merge |
| `status-line` | `.claude/settings.json` merge | (n/a) | (n/a) |
| `output-style` | `.claude/output-styles/<name>.md` | (n/a) | (n/a) |
| `workflow` | (n/a) | `.agent/workflows/<name>.md` | (n/a) |
| `rule` | (n/a) | `.agent/rules/<name>.md` | (n/a) |
| `snippet` | append to repo-root `CLAUDE.md` | append to repo-root `AGENTS.md` | append to repo-root `AGENTS.md` |
| `settings-fragment` | merge into `.claude/settings.json` | **TBD** | merge into `.gemini/settings.json` |

## What's locked vs. TBD

- **Locked** rows reflect the host's documented or de-facto convention as of toolkit v0.1.0.
- **TBD** entries are paths the installer doesn't dispatch to yet because the host's surface isn't formalized in public docs (Antigravity's `mcp-server` + `settings-fragment` conventions).

When a TBD path is encountered, the installer logs a warning and skips that host for that customization. The manifest still validates — `supported_hosts: [antigravity]` for a `mcp-server` is allowed; the installer just can't deliver yet.

**Revisit triggers** (tracked in `agentic-harness/.harness/FOLLOWUPS.md`):

1. Antigravity publishes formal docs on MCP server conventions and/or `settings.json` merge semantics.
2. Google ships the Gemini-CLI successor (the table needs revision when the successor lands).

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

- **Standalone primitive:** `agent-toolkit/<kind-subdir>/<name>/` → destination per table.
- **Inside a bundle:** `agent-toolkit/bundles/<bundle>/<kind-subdir>/<name>/` → same destination per table (the bundle structure is invisible at the destination — the inner primitive lands at the same path it would as a standalone).

This means a bundle's primitives can collide at the destination with standalone primitives of the same name. v0.1.0 has no such collision (one bundle with one inner skill, three standalone skills with unique names); future versions may need a collision policy. Tracked as an open question.

## Related

- [Customization Types](Customization-Types) — what each kind means.
- [Manifest Schema](Manifest-Schema) — frontmatter required to participate in dispatch.
- [Installer CLI](Installer-CLI) — flag reference.
- [Add a Skill](Add-A-Skill) — the most common dispatch path walked through.
