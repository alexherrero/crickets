---
name: wiki-init
description: Scaffold a repo's wiki to the wiki-maintenance intent-group structure (folders, per-folder sidebars, section landings). Idempotent + preview-first; never clobbers existing pages.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: [optional — "--preview", "--sections a,b,c", "--name <project>"]
---

You are provisioning the current repo's wiki to the **wiki-maintenance intent-group
structure** (ADR 0018). This is an **agent action** — plugins have no target-repo
install hook, so you run the bundled scaffolder yourself.

**Argument (if any):** $ARGUMENTS

## What it does

Scaffolds `wiki/` with the section folders (default `get-started · do · reference ·
why`; override with `--sections`), each with a **section-index landing**
(`<!-- mode: index -->`) + a per-folder `_Sidebar.md`, plus the curated `Home.md`
and the root `_Sidebar.md`. The scaffold is **gate-passing by construction** — a
fresh wiki/ has zero hard `check-wiki` issues.

It is **idempotent + preview-first**: it fills only what's missing and **never
overwrites an operator-authored page**; a second run is a no-op.

## How to run it

1. **Always preview first** — show the gap-fill plan, write nothing:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wiki_init.py" --preview $ARGUMENTS
   ```

2. Present the plan to the operator. On confirmation, **apply** (drop `--preview`):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wiki_init.py" --yes $ARGUMENTS
   ```

   (`--yes` skips the script's own prompt since you already confirmed; omit it to
   keep the interactive guard.)

3. `--sections a,b,c` selects the folder set; `--name <project>` sets the
   Home/_Sidebar titles (defaults to the repo directory name).

## Non-negotiables

- **Preview before any write.** The operator sees the exact file list first.
- **Never clobber.** The scaffolder only writes missing files; if it would touch
  an existing page, that's a bug — stop and report.
- **Don't hand-edit `wiki/` to "fix" the scaffold.** If the scaffolded wiki fails
  `check-wiki`, that's a scaffolder defect — surface it.
