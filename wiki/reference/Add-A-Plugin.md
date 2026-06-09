<!-- mode: how-to -->
# How to add a plugin

> [!NOTE]
> **Goal:** Add a new plugin (a functional group) to crickets — the `group.yaml` plus its primitives, regenerated and dogfooded.
> **Prereqs:** crickets cloned; Python 3 + PyYAML; `claude` and/or `agy`.

A crickets plugin is a **group folder** under `src/<group>/`; the folder name is the plugin slug. See [Plugin anatomy](Plugin-Anatomy) for the shape it generates into.

## Steps

1. **Create the group** at `src/<group>/` (`<group>` is the kebab-case slug) with a `group.yaml`:

   ```yaml
   name: My Plugin
   description: One line — what the plugin does.
   category: Coding
   standalone: true        # true ⟺ requires: []
   # requires: [developer-workflows]   # a hard dependency (then standalone: false)
   # enhances: [developer-workflows]   # soft — augments the target when both are installed
   ```

   Field contract + the `standalone ⟺ requires: []` invariant: [Manifest schema](Manifest-Schema).

2. **Add its primitives** under their kind subdirs — `skills/<name>/SKILL.md`, `agents/<name>.md`, `commands/<name>.md`, `hooks/<name>/`. Each carries its own frontmatter ([add a skill](Add-A-Skill) walks one through). A group-wide helper script goes in `src/<group>/scripts/`.

3. **Lint + regenerate:**

   ```bash
   python3 scripts/lint_src.py
   python3 scripts/generate.py build
   ```

   The generator emits `dist/<host>/plugins/<group>/` for both hosts and updates the marketplace pointer.

4. **Dogfood** — install the generated plugin on a host (`claude --plugin-dir dist/claude-code/plugins/<group>` / `agy plugin install "$PWD/dist/antigravity/plugins/<group>"`) and exercise it. See [Modify a plugin](Modify-A-Plugin).

5. **Commit the source *and* `dist/`** together. The pre-push PII hook scans first.

## Related

- [Plugin anatomy](Plugin-Anatomy) — what a plugin is and how it's structured.
- [Add a skill](Add-A-Skill) — author the primitives that go in the group.
- [Manifest schema](Manifest-Schema) — `group.yaml` + primitive frontmatter.
- [Modify a plugin](Modify-A-Plugin) — the edit → generate → dogfood loop.
