---
name: orient
description: Open a project by name — LOCATE it (registered repos, vault projects tree, agentm recall), CONFIRM the match, ORIENT with a short status summary, then stop. Read-only; /open and /orient are the same command.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <project name> [--note]
---

You are running **`/orient`** (also invocable as `/open` — the two commands are one implementation, two entry points). It resolves the operator's "open the file for X" intent to a project/idea/context, confirms the match, and renders a short read-only orientation. **It never resumes work, marks a task, or activates a plan.**

**Arguments:** `$ARGUMENTS` — the project name/description to locate, optionally followed by `--note` (writes the rendered orientation into the confirmed project's own `_harness/` — see step 4).

> **Read-only by contract** (the same posture as [`/queue-status-lite`](queue-status-lite.md)). There is no claim, no lease, no activation, no task marked. This command exists so the operator can rehydrate context in one turn before deciding what to do next; it never decides, resumes, or records anything, except the one narrow write in step 4.

## Non-negotiable constraints

1. **Read-only except the explicit `--note` opt-in.** This command never flips task status, never records progress, never binds or assigns a plan, never activates or resumes work. The only file this command ever writes is the pointer note in step 4, and only when `--note` was passed.
2. **LOCATE degrades gracefully, per source.** Each of the three LOCATE sources (registered repos, the vault `projects/` tree, agentm recall) fails independently and silently to "found nothing" — an absent agentm clone, an unconfigured vault, or an empty registry never raises or blocks the other sources.
3. **CONFIRM before ORIENT, always.** Never render an orientation for a project the operator hasn't confirmed — a single unambiguous match still gets a one-line confirmation, not a silent proceed.
4. **Surface the renderer's output verbatim.** Present `orient_render.py`'s rendered block to the operator as-is — don't parse, re-rank, or editorialize the sections.

## Process

1. **LOCATE.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_project.py" "<query text>" --json`, where `<query text>` is `$ARGUMENTS` with any trailing `--note` stripped. This resolves the three sources (repo-registry, vault projects tree, agentm recall) and returns `{"matches": [...], "classification": "none"|"one"|"many"}`.

2. **CONFIRM**, per the goal-5 contract in the operator's own words:
   - **`classification: "one"`** — state the match's name, its resolved path (`root_path` or `vault_project_path`), and its one-line gloss if present; ask "this one?" and wait for confirmation before proceeding to ORIENT.
   - **`classification: "many"`** — present a short list (name + path per candidate, no more than the returned matches); ask the operator to pick one. Do not guess.
   - **`classification: "none"`** — say so plainly ("couldn't find a project matching '<query>'") and ask the operator to clarify or try a different name. Stop here — there is nothing to orient on.

3. **ORIENT**, once confirmed. `orient_render.py` has no CLI entry point — call its `render_orientation(project)` function directly (a short inline `python3 -c` invocation that imports the module from `${CLAUDE_PLUGIN_ROOT}/scripts/orient_render.py` and passes the confirmed match dict from step 1's JSON). Present the rendered block verbatim: what the project is, its PLAN status chart (✅/⬜ per task), recent progress, queued plans, and board state — whichever sections the renderer included (missing sources are omitted, not stubbed).

4. **Optional: `--note`.** If the operator's invocation included `--note`, additionally call `orient_render.write_orientation_note(harness_dir, rendered_text)` with the confirmed project's resolved `_harness/` dir (via `orient_render.resolve_harness_dir(project)`) and the exact text just rendered in step 3. This is an idempotent overwrite of `<_harness>/orientation-note.md` — mention to the operator that the note was refreshed and where. Skip this step entirely when `--note` was not passed; the base command never writes to disk.

5. **Stop.** Do not resume work, do not open a plan, do not suggest a next command beyond naming what's available (a plan to `/work`, a queued plan to `/plan --activate`). Await the operator's direction — that decision is theirs.

## When there is no agentm clone or no vault configured

LOCATE still works standalone: the registered-repos and recall sources return empty, but a local project resolved by its `root_path`'s own `.harness/` directory still renders a full ORIENT — the same graceful degradation `/queue-status-lite` already relies on. This is the expected standalone behavior, not a failure.
