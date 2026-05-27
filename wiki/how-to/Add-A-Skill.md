# How to add a new skill

> [!NOTE]
> **Goal:** Add a new standalone skill to `crickets` and ship it via the installer.
> **Prereqs:** You know what the skill does and which hosts it targets; `crickets` cloned locally.

## Steps

1. Pick a name (`CamelCase-With-Dashes` per filename convention; globally unique across all customizations):

   ```bash
   SKILL_NAME=my-new-skill
   ```

2. Create the directory:

   ```bash
   cd ~/Antigravity/crickets
   mkdir -p skills/$SKILL_NAME
   ```

3. Create `skills/<name>/SKILL.md` with full frontmatter:

   ```yaml
   ---
   name: my-new-skill
   description: One or two sentences describing when this skill triggers and what it does.
   kind: skill
   supported_hosts: [claude-code, antigravity]
   version: 0.1.0
   install_scope: project
   ---

   <skill body — operational instructions for the agent>
   ```

   See [Manifest Schema](Manifest-Schema) for the full field list and validation rules.

4. Write the skill body. Keep it operational — preconditions, workflow, hard rules, output contract. See `skills/pii-scrubber/SKILL.md` as a reference.

5. Validate locally:

   ```bash
   python3 scripts/validate-manifests.py
   ```

   Output should be: `validate-manifests: clean (X bundle(s), Y standalone skill(s))` with `Y` increased by one.

6. Test the dispatch by installing into a scratch dir:

   ```bash
   TARGET=$(mktemp -d)
   cd $TARGET && git init -q
   bash ~/Antigravity/crickets/install.sh $TARGET
   ls $TARGET/.claude/skills/$SKILL_NAME/    # should contain SKILL.md
   ls $TARGET/.agents/skills/$SKILL_NAME/     # same
   # Note: .agents/skills/ removed in v0.9.0 (Gemini CLI host dropped per ROADMAP #15).
   rm -rf $TARGET
   ```

7. Commit your changes. The pre-push hook will scan your changes for PII before the push goes out — fix any findings before pushing.

## Variants

### Host-specific skill

If the skill only makes sense on one host (e.g. a Claude Code hook that has no Antigravity equivalent), narrow `supported_hosts`:

```yaml
supported_hosts: [claude-code]
```

The installer skips the dispatch for hosts not in the list.

### Skill with supporting scripts

Skills can ship more than just `SKILL.md`. Place supporting files under the same dir:

```
skills/<name>/
├── SKILL.md                # manifest + body
├── scripts/
│   └── <helper>.sh         # invoked from the skill body
└── templates/
    └── <template>.md       # used by the skill at runtime
```

The installer copies the whole dir (managed-dir wipe-and-recreate on `--update`). Reference supporting files from `SKILL.md` body via relative paths.

### Skill inside a bundle

`kind: bundle` is reserved-future in v2.0.0 (no bundles ship). For multi-primitive packaging recipes, see the [Quality-Gates-Recipe](Quality-Gates-Recipe) — the docs-only pattern that replaced the v1.x quality-gates bundle.

## Verify

After adding the skill:

1. `python3 scripts/validate-manifests.py` exits 0.
2. `bash scripts/smoke-install-bash.sh` exits 0 (the expected-files list might need updating if your skill is in the smoke test's assertion list — but for net-new skills not in the smoke list, the test still passes since it only asserts a subset).
3. The skill body's instructions actually do what they claim — test by invoking the skill in your host.

## Related

- [Manifest Schema](Manifest-Schema) — frontmatter contract.
- [Per-Host Paths](Per-Host-Paths) — where the skill lands per host.
- [Customization Types](Customization-Types) — when a skill is the right kind vs. command/agent/hook.
- [Quality-Gates-Recipe](Quality-Gates-Recipe) — docs-only recipe pattern that replaces the v1.x quality-gates bundle.
- [First Customization tutorial](01-First-Customization) — full walkthrough.
