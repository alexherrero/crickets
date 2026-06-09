<!-- mode: how-to -->
# How to add a skill

> [!NOTE]
> **Goal:** Add a skill to a crickets plugin — author the `SKILL.md`, regenerate, and dogfood it.
> **Prereqs:** crickets cloned; Python 3 + PyYAML; `claude` and/or `agy`. You know what the skill does and which hosts it targets.

A skill lives **inside a plugin group** — `src/<group>/skills/<name>/SKILL.md`. Pick the group it belongs to (e.g. `pii`, `wiki-maintenance`); if it needs a new one, [add the plugin first](Add-A-Plugin).

## Steps

1. **Author the skill** at `src/<group>/skills/<name>/SKILL.md` (`<name>` is `kebab-case`, globally unique):

   ```yaml
   ---
   name: my-skill
   description: One or two sentences — when it triggers and what it does.
   kind: skill
   supported_hosts: [claude-code, antigravity]
   version: 0.1.0
   ---

   <skill body — operational instructions for the agent: preconditions, workflow, hard rules, output contract>
   ```

   The body *is* the skill; keep it operational. `src/pii/skills/pii-scrubber/SKILL.md` is a good model. Field contract: [Manifest schema](Manifest-Schema).

2. **Lint the source:**

   ```bash
   python3 scripts/lint_src.py
   ```

3. **Regenerate + dogfood** — `python3 scripts/generate.py build`, then load the plugin on a host and exercise the skill. The full edit → generate → dogfood loop is in [Modify a plugin](Modify-A-Plugin).

4. **Commit the source *and* `dist/`** together (`git add src/ dist/`) — they ship as one change. The pre-push PII hook scans first.

## Variants

- **Host-specific** — narrow `supported_hosts` (e.g. `[claude-code]`); the generator emits the skill only for the listed hosts.
- **Supporting files** — a skill can ship more than `SKILL.md`. A file used only by this skill lives in its own dir (`skills/<name>/…`, referenced by a relative path); a helper shared across the plugin's primitives goes in the group's `scripts/` (referenced via `${CLAUDE_PLUGIN_ROOT}/scripts/<name>` — see [Per-host paths](Per-Host-Paths)).

## Related

- [Add a plugin](Add-A-Plugin) — create a new plugin group to house the skill.
- [Modify a plugin](Modify-A-Plugin) — the edit → generate → dogfood loop.
- [Manifest schema](Manifest-Schema) — the frontmatter contract.
- [Customization types](Customization-Types) — skill vs command / agent / hook.
- [Per-host paths](Per-Host-Paths) — where the skill lands per host.
