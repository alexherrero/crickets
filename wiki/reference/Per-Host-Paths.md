# Per-host paths reference

Where each `kind` lands in each host at install time. The installer reads each customization's `supported_hosts` and dispatches to the rows below.

## ⚡ Quick Reference

| Kind | Claude Code | Antigravity |
|---|---|---|
| `skill` | `.claude/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md` |
| `command` | `.claude/commands/<name>.md` | (n/a — use `workflow` instead) |
| `agent` | `.claude/agents/<name>.md` | `.agents/skills/<name>/SKILL.md` (sub-agent-as-skill) |
| `hook` | `.claude/hooks/<name>` + `.claude/settings.json` merge | (n/a — Antigravity hooks are SDK Python decorators, no file-based surface; see Known gaps in [Compatibility](Compatibility)) |
| `mcp-server` | `.claude/settings.json` merge OR `.claude/mcp-servers/` | **TBD** |
| `status-line` | `.claude/settings.json` merge | (n/a) |
| `output-style` | `.claude/output-styles/<name>.md` | (n/a) |
| `workflow` | (n/a) | `.agents/workflows/<name>.md` |
| `rule` | (n/a) | `.agents/rules/<name>.md` |
| `snippet` | **(dropped)** — Claude Code has no instruction-file primitive in the plugin surface | `<plugin>/rules/<name>.md` (emitted as an Antigravity `rules/` file) |
| `settings-fragment` | merge into `.claude/settings.json` | **TBD** |
| `plugin` | (n/a — Antigravity-specific bundle format) | `~/.gemini/config/plugins/<name>/plugin.json` + `<name>/skills/<skill>/SKILL.md` (user-global) |
| `scripts/` (group asset, *not a `kind`*) | `<plugin>/scripts/` | `<plugin>/scripts/` |

> [!NOTE]
> **`scripts/` is a group-level asset dir, not a discovered `kind`.** A `src/<group>/scripts/` directory of verbatim helper scripts (e.g. `cross-review.sh`, `capability_probe.py`) is copied **wholesale** (excluding `__pycache__`) into the emitted plugin at `dist/<host>/plugins/<group>/scripts/` — host-agnostic, both hosts identically. Primitives reference a bundled script via the host plugin-root path (`${CLAUDE_PLUGIN_ROOT}/scripts/<name>` on Claude Code). See [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md) § Group-level assets.

> [!IMPORTANT]
> **Antigravity 2.0 / agy uses `.agents/` (plural)** for project-local discovery, NOT `.agent/` (singular like Antigravity 1.x). Confirmed via `agy` v1.0.2 binary inspection: `{workspace}/.agents/skills/{skill_name}/SKILL.md`. Crickets v1.2.0 (paired with agentm v3.2.0) updates the installer dispatch from `.agent/` → `.agents/` for the `antigravity` host slug. **This is a breaking change for users with crickets v1.0.x installed against Antigravity 1.x's `.agent/` convention** — re-run `bash install.sh --update <target-project>` to migrate; the installer wipes the old `.agent/` dir on update (or operators can manually `mv .agent .agents` in their target project). See [ADR 0011](decisions/0011-antigravity-2-host-support) for the host-evolution rationale + the 2026-06-18 Gemini-CLI sunset context.

> [!NOTE]
> **Gemini CLI host removed in v0.9.0** per [ROADMAP item #15](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md). Standalone Gemini CLI is no longer a supported host; the legacy 3-column table is preserved in the v0.8.x and earlier wiki history. **Antigravity 2.0 + Antigravity CLI** (which replaced Gemini CLI on 2026-05-19) stay as a single first-class host under the `antigravity` slug. See [ADR 0006](decisions/0006-gemini-cli-host-removal) for the original host-scope-reduction rationale + [ADR 0011](decisions/0011-antigravity-2-host-support) for the 2.0 host support decision.

## What's locked vs. TBD

- **Locked** rows reflect the host's documented or de-facto convention as of toolkit v1.2.0.
- **TBD** entries are paths the installer doesn't dispatch to yet because the host's surface isn't formalized in public docs (Antigravity's `mcp-server` + `settings-fragment` conventions). The Antigravity hook row is **(n/a) not TBD** — confirmed in v1.2.0 research that Antigravity has no file-based hook surface; see Known gaps in [Compatibility](Compatibility).

When a TBD path is encountered, the installer logs a warning and skips that host for that customization. The manifest still validates — `supported_hosts: [antigravity]` for a `mcp-server` is allowed; the installer just can't deliver yet.

**Revisit triggers** (tracked in `agentm/.harness/FOLLOWUPS.md`):

1. Antigravity publishes formal docs on MCP server conventions and/or `settings.json` merge semantics.
2. Google ships a comparable file-based hook surface in agy / Antigravity 2.x (today: Python SDK decorators only).
3. The `kind: workflow` + `kind: rule` Antigravity path conventions get explicit documentation (currently inferred from Antigravity 1.x `.agent/` + agy 2.0 `.agents/` plural pattern; not directly confirmed in agy binary strings for workflows/rules specifically).

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
