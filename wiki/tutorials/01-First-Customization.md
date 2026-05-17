# Tutorial 1 — Your first customization

> [!NOTE]
> **Goal:** Add a hello-world skill to `agent-toolkit`, install it into a scratch project, and verify it lands at the right host paths. End state: a working customization you wrote, dispatched across all three supported hosts.
> **Time:** ~10 minutes.
> **Prereqs:** `agent-toolkit` cloned locally; `python3` + `pyyaml` installed (`pip install pyyaml`); `git` on PATH.

Walks through the full lifecycle of adding a customization. You'll create a skill, validate the manifest, run the installer into a scratch dir, and inspect the result.

## Step 1 — Set up

Open a terminal at your toolkit checkout:

```bash
cd ~/Antigravity/agent-toolkit
```

Confirm the repo is clean:

```bash
git status --short
```

(If output is non-empty, stash or commit changes first — you'll be adding new files in step 2.)

## Step 2 — Create your skill

You'll add a `hello-world` skill that returns a friendly greeting when invoked.

```bash
mkdir -p skills/hello-world
```

Create `skills/hello-world/SKILL.md` with this content:

```markdown
---
name: hello-world
description: Return a friendly greeting when the user types "hello" or invokes the skill explicitly. A placeholder for learning how the toolkit's customizations work.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# hello-world

A reference skill that demonstrates the agent-toolkit's customization shape.

## When invoked

Return: *"Hello from agent-toolkit! This is a placeholder skill — feel free to delete it."*

Do not attempt to do anything else. The skill exists for installer-dispatch testing, not real workflow help.

## Why it exists

To dogfood the toolkit's customization lifecycle. Once you've walked through this tutorial, delete the skill or replace it with something useful.
```

## Step 3 — Validate the manifest

Confirm the YAML frontmatter passes the schema check:

```bash
python3 scripts/validate-manifests.py
```

Expected output:

```
validate-manifests: clean (1 bundle(s), 4 standalone skill(s))
```

The count is your new `hello-world` plus the skills the toolkit already ships (`pii-scrubber`, `dependabot-fixer`, `ship-release`, `design`, `memory` as of v0.9.0). If the count doesn't increase by 1, your `hello-world` manifest didn't parse — re-check the frontmatter for typos.

## Step 4 — Install into a scratch project

Create a scratch git repo:

```bash
SCRATCH=$(mktemp -d)
cd $SCRATCH && git init -q && cd ~/Antigravity/agent-toolkit
```

Run the installer against the scratch:

```bash
bash install.sh $SCRATCH
```

You should see lines like:

```
==> agent-toolkit install: /var/folders/.../tmp.xxx
==> installing bundle: example-bundle
    created .claude/skills/example-skill
    created .agent/skills/example-skill
==> installing skill: hello-world
    created .claude/skills/hello-world
    created .agent/skills/hello-world
==> installing skill: pii-scrubber
    created .claude/skills/pii-scrubber
    ...
==> pre-push hook
    installed .git/hooks/pre-push

agent-toolkit install: complete.
```

(v0.9.0 removed standalone Gemini CLI host support per ROADMAP item #15 — `.agents/skills/*` no longer populated. See [ADR 0006](../explanation/decisions/0006-gemini-cli-host-removal).)

## Step 5 — Inspect what landed

Confirm your skill installed at both supported host paths:

```bash
ls $SCRATCH/.claude/skills/hello-world/
ls $SCRATCH/.agent/skills/hello-world/
```

Each should show `SKILL.md`. Open one of them — it should be byte-identical to what you wrote in step 2.

```bash
cat $SCRATCH/.claude/skills/hello-world/SKILL.md
```

## Step 6 — Run the installer in update mode

Edit your skill's description (any small change):

```bash
cd ~/Antigravity/agent-toolkit
# (edit skills/hello-world/SKILL.md — change the description to something different)
```

Re-run the installer with `--update`:

```bash
bash install.sh --update $SCRATCH
```

You should see:

```
==> sync mode: wiping toolkit-managed dirs before recreate from source
    removed .claude/skills/
    removed .agent/skills/
    wiped N managed dir(s); rebuilding from source
==> installing bundle: example-bundle
    created .claude/skills/example-skill
    ...
```

The managed dirs got wiped and recreated. Inspect the destination to confirm your edit propagated:

```bash
cat $SCRATCH/.claude/skills/hello-world/SKILL.md | head -5
```

## Step 7 — Clean up

```bash
rm -rf $SCRATCH
```

If you want to keep the `hello-world` skill in your toolkit: commit it (the pre-push hook will scan for PII before push). If you don't:

```bash
cd ~/Antigravity/agent-toolkit
rm -rf skills/hello-world
```

## What you learned

- **Skills live at `skills/<name>/SKILL.md`** with YAML frontmatter declaring `name`, `description`, `kind`, `supported_hosts`, and `version`.
- **The installer dispatches per `supported_hosts`** — one source manifest lands at host-native paths (`.claude/skills/`, `.agent/skills/`) at install time.
- **`--update` is a true-sync** — managed parent dirs get wiped and recreated, picking up edits without needing manual cleanup.
- **`validate-manifests.py` catches schema errors** before the installer runs them — typos in frontmatter surface as `file:line` errors with clear remediation hints.
- **The pre-push hook is the PII guardrail** — every push to the toolkit gets scanned; you'd fail the push if `hello-world` accidentally contained an email or API key.

## Next

- [Add a Skill](Add-A-Skill) — the recipe form (shorter; assumes you've done this tutorial).
- [Add a Bundle](Add-A-Bundle) — when you have multiple primitives that ship together.
- [Manifest Schema](Manifest-Schema) — every frontmatter field, with edge cases.
- [Per-Host Paths](Per-Host-Paths) — destination paths for kinds beyond `skill`.
