<!-- mode: how-to -->
# How to add a plugin

> [!NOTE]
> **Goal:** You will add a new plugin to crickets. A plugin is a functional group. You will create the `group.yaml` and its primitives. You will regenerate them. You will dogfood them.
> **Prereqs:** You need crickets cloned. You need Python 3 and PyYAML. You need `claude` and/or `agy`.

A crickets plugin is a **group folder** under `src/<group>/`. The folder name is the plugin slug. See [Plugin anatomy](Plugin-Anatomy) for the shape it generates into.

## Steps

1. **Create the group** at `src/<group>/`. The `<group>` is the kebab-case slug. Create a `group.yaml`:

   ```yaml
   name: My Plugin
   description: One line — what the plugin does.
   category: Coding
   standalone: true        # true ⟺ requires: []
   # requires: [development-lifecycle]   # a hard dependency (then standalone: false)
   # enhances: [development-lifecycle]   # soft — augments the target when both are installed
   ```

   The field contract lives in [Manifest schema](Manifest-Schema). This includes the `standalone ⟺ requires: []` invariant.

2. **Add its primitives** under their kind subdirs. Use `skills/<name>/SKILL.md`, `agents/<name>.md`, `commands/<name>.md`, and `hooks/<name>/`. Each primitive carries its own frontmatter. Read [add a skill](Add-A-Skill) for a walk-through. Put your group-wide helper script in `src/<group>/scripts/`.

3. **Lint + regenerate:**

   ```bash
   python3 scripts/lint_src.py
   python3 scripts/generate.py build
   ```

   The generator emits `dist/<host>/plugins/<group>/` for both hosts. It updates the marketplace pointer.

4. **Dogfood** — install the generated plugin on a host. Run `claude --plugin-dir dist/claude-code/plugins/<group>` or `agy plugin install "$PWD/dist/antigravity/plugins/<group>"`. Exercise it. See [Modify a plugin](Modify-A-Plugin).

5. **Commit the source *and* `dist/`** together. The pre-push PII hook scans your commit first.

## Related

- [Plugin anatomy](Plugin-Anatomy) — Learn what a plugin is. Learn how it is structured.
- [Add a skill](Add-A-Skill) — Author the primitives for your group.
- [Manifest schema](Manifest-Schema) — Read about the `group.yaml` and primitive frontmatter.
- [Modify a plugin](Modify-A-Plugin) — Follow the edit, generate, and dogfood loop.
