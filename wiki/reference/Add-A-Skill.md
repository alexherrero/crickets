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

   The body *is* the skill; keep it operational. `src/privacy/skills/pii-scrubber/SKILL.md` is a good model. The field contract lives in [Manifest schema](Manifest-Schema).

2. **Lint the source:**

   ```bash
   python3 scripts/lint_src.py
   ```

3. **Regenerate + dogfood** — `python3 scripts/generate.py build`, then load the plugin on a host and exercise the skill. The full edit → generate → dogfood loop is in [Modify a plugin](Modify-A-Plugin).

4. **Commit the source *and* `dist/`** together (`git add src/ dist/`) — they ship as one change. The pre-push PII hook scans first.

## Variants

- **Host-specific** — narrow `supported_hosts` (e.g. `[claude-code]`); the generator emits the skill only for the listed hosts.
- **Supporting files** — a skill can ship more than `SKILL.md`. A file used only by this skill lives in its own dir (`skills/<name>/…`, referenced by a relative path); a helper shared across the plugin's primitives goes in the group's `scripts/` (referenced via `${CLAUDE_PLUGIN_ROOT}/scripts/<name>` — see [Per-host paths](Per-Host-Paths)).

## Anatomy Patterns

Two optional sections make mandatory steps harder to skip and observable failures harder to ignore; add them when a skill has either property.

### Common Rationalizations table

A two-column table mapping agent excuses to immediate refutations. Include this in any skill that has mandatory steps the agent might rationalize skipping under pressure (confidence, time, apparent obviousness).

Format:

```markdown
## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "<excuse the agent tells itself>" | "<why the excuse is wrong>" |
```

Example row (from `/work`):

| Excuse | Why it's wrong |
|---|---|
| "This task is small enough to skip the pre-check" | The pre-check exists precisely for tasks you're confident about — confidence is when blind spots hide. |

The table fires at invocation time, in context — stronger than always-load conventions because it's read in the same turn as the step it guards.

### Red Flags

A bulleted list of observable signs the skill is being violated. Include this in any skill with failure modes that are recognizable from the outside (e.g. from a review pass or an operator watching progress).

Format:

```markdown
## Red Flags

- <Observable sign that the skill is being violated.>
```

Example bullet (from `/work`'s `## Failure modes to avoid`, the section this pattern generalizes from):

- **Skipping failed gates** ("I'll fix it next session"). Green before `[x]`.

Red Flags serve a different purpose than Rationalizations: they help reviewers and operators catch violations after the fact, not prevent them in-context.

## Related

- [Add a plugin](Add-A-Plugin) — create a new plugin group to house the skill.
- [Modify a plugin](Modify-A-Plugin) — the edit → generate → dogfood loop.
- [Manifest schema](Manifest-Schema) — the frontmatter contract.
- [Customization types](Customization-Types) — skill vs command / agent / hook.
- [Per-host paths](Per-Host-Paths) — where the skill lands per host.
