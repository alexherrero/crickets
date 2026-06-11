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

## Cost warning on non-public targets

The scaffolder drops one GitHub Actions workflow (`wiki-sync.yml` — a `lint-wiki`
job runs the gate on every push/PR, an `update-wiki` job publishes only
`needs: lint-wiki`, so a broken wiki never reaches the GitHub Wiki). Actions
minutes are **free only on public repos** — on a private/internal target they're
billed. The preview auto-detects visibility (via `gh`) and prints a billed-minutes
warning when the target isn't public; the apply prompt then gates on it. **Surface
that warning to the operator and get an explicit OK before applying** — don't
auto-confirm a non-public run. Use `--no-ci` to scaffold the wiki only (no
workflow, no billing surface).

## Non-negotiables

- **Preview before any write.** The operator sees the exact file list first.
- **Never clobber.** The scaffolder only writes missing files; if it would touch
  an existing page, that's a bug — stop and report.
- **Honor the non-public cost warning.** If the preview warns about billed Actions
  minutes, relay it and confirm before applying; never silently `--yes` past it.
- **Don't hand-edit `wiki/` to "fix" the scaffold.** If the scaffolded wiki fails
  `check-wiki`, that's a scaffolder defect — surface it.
