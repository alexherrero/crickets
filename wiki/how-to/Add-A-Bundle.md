# How to add a new bundle

> [!NOTE]
> **Goal:** Package multiple primitive customizations (skill + hook + agent + ...) into a single installable unit.
> **Prereqs:** You have at least two primitives that work together and should ship as one; `agent-toolkit` cloned locally.

Use a bundle when primitives **depend on each other** — the design breaks if you install one without the others. If the primitives are independently useful, ship them standalone via [Add a Skill](Add-A-Skill) instead.

## Steps

1. Pick a bundle name (`CamelCase-With-Dashes`, globally unique):

   ```bash
   BUNDLE_NAME=my-bundle
   ```

2. Create the bundle directory:

   ```bash
   cd ~/Antigravity/agent-toolkit
   mkdir -p bundles/$BUNDLE_NAME
   ```

3. Create `bundles/<name>/bundle.md` with full frontmatter + a `contents:` list enumerating each inner primitive:

   ```yaml
   ---
   name: my-bundle
   description: What this bundle delivers as a coherent unit.
   kind: bundle
   supported_hosts: [claude-code, antigravity]
   contents:
     - skill: inner-skill-name
     - hook: inner-hook-name
   version: 0.1.0
   ---

   <bundle body — what the bundle does as a whole>
   ```

4. Add each inner primitive under the bundle dir:

   ```bash
   mkdir -p bundles/$BUNDLE_NAME/skills/inner-skill-name
   # Write bundles/<name>/skills/inner-skill-name/SKILL.md (relaxed frontmatter — only name + description required; kind/supported_hosts/version inherit from bundle)
   ```

   For an inner skill, the SKILL.md frontmatter only needs:

   ```yaml
   ---
   name: inner-skill-name
   description: What this inner primitive does.
   ---
   ```

   For other inner-primitive kinds (when their installer support lands in toolkit v0.2.0+), follow the same relaxed-frontmatter convention.

5. Validate locally:

   ```bash
   python3 scripts/validate-manifests.py
   ```

   Output should be: `validate-manifests: clean (X bundle(s), Y standalone skill(s))` with `X` increased by one.

6. Test the dispatch:

   ```bash
   TARGET=$(mktemp -d)
   cd $TARGET && git init -q
   bash ~/Antigravity/agent-toolkit/install.sh --bundle $BUNDLE_NAME $TARGET
   ls $TARGET/.claude/skills/   # should contain each inner skill at the host path
   rm -rf $TARGET
   ```

7. Commit your changes. Pre-push hook scans for PII before push.

## Variants

### Bundle with only one primitive kind

Bundles aren't restricted to multi-kind. A bundle with three skills (no hooks, no agents) is fine — it's still useful when the three skills are interdependent. The `contents:` list captures the dependency.

### Bundle with version-pinned inner primitives

The inner primitives inherit `version` from the bundle by default. If you want to pin an inner primitive to a different version (e.g. the inner skill is shared with another bundle at a different version), declare its own `version:` field in the inner manifest — the validator allows it.

This is uncommon. Most bundles want their inner primitives lock-stepped with the bundle's version.

### Deleting a bundle

```bash
git rm -r bundles/my-bundle/
```

The installer skips missing bundles silently. Already-installed bundle contents in target projects survive until the next `--update` (which wipes managed parents and recreates from current source — orphan files get cleaned).

## Verify

1. `python3 scripts/validate-manifests.py` exits 0.
2. `bash scripts/smoke-install-bash.sh` still passes.
3. `bash install.sh --bundle <name> <target>` lands every inner primitive at its expected host path.

## Related

- [Manifest Schema § Bundle](Manifest-Schema) — bundle-specific frontmatter rules.
- [Customization Types § When to use bundle vs. standalone](Customization-Types) — design guidance.
- [Add a Skill](Add-A-Skill) — for standalone primitives.
- [First Customization tutorial](01-First-Customization) — end-to-end walkthrough that includes a bundle.
