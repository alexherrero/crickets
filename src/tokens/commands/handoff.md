---
name: handoff
description: Snapshot an expensive session's outputs into a vault handoff directory, then hand each downstream step to a fresh session — as a one-click background-task chip where the host offers them, and always as paste-ready prompts carrying a machine-readable tier/model label.
kind: command
supported_hosts: [claude-code]
version: 0.2.0
argument-hint: "<dest-dir> [--title <entry title> --model <model-id> --tier <tier> --effort <effort> --prompt <text>]..."
---

You are running `/handoff` — it generalizes the Mythos `PROMPTS.md` pattern (`<vault>/projects/agentm/_harness/mythos-readiness-handoff/PROMPTS.md`): when a session did expensive, hard-won work and the remaining steps are cheap and mechanical, snapshot the outputs and hand off to fresh, cheaper sessions instead of continuing in the expensive one.

**Arguments:** $ARGUMENTS

## What to do

1. **Resolve the destination directory.** The first positional argument is the destination — normally a subdirectory under the vault's `_harness/` (resolve `<vault>` via `agentm_config --get vault_path` or the session-start hook), matching the Mythos precedent (`<vault>/projects/<repo>/_harness/<handoff-slug>/`).

2. **Identify the session outputs to snapshot.** These are the files this session produced that a downstream session needs to read — findings, draft plans, research JSON, anything the paste-ready prompts below will reference. Read their current contents.

3. **Author one `HandoffEntry` per downstream prompt.** For each step you're handing off, decide: a title, the paste-ready prompt text (self-contained — the downstream session has no memory of this one), and its **tier/model/effort** classification via `${CLAUDE_PLUGIN_ROOT}/scripts/classify_work_type.py`'s `classify_work_type()` (or a direct table lookup against `routing_table.py` if the work-type is already known) — never guess a model name freehand.

4. **Build the pack.** Call the backing script:

   ```bash
   python3 -c "
   import sys, json
   sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts')
   from handoff_pack import HandoffEntry, build_handoff_pack
   from pathlib import Path
   entries = [HandoffEntry(**e) for e in json.load(open('/tmp/handoff_entries.json'))]
   outputs = json.load(open('/tmp/handoff_outputs.json'))
   manifest = build_handoff_pack(entries, outputs, Path('<dest-dir>'))
   print(json.dumps(manifest, indent=2))
   "
   ```

   (Write the entries/outputs to a temp JSON file first, or call `build_handoff_pack` directly from a short inline script — either way, the write path is the one deterministic function, never hand-authored file-by-file.) This writes `<dest-dir>/prompts.json` (the structured manifest — every prompt's label is a `{tier, model_id, effort}` dict, not prose) and `<dest-dir>/PROMPTS.md` (the paste-ready human rendering, generated from the same data).

5. **Offer each prompt as a background-task chip (graceful-skip).** The pack's whole cost to the operator is opening a session and pasting; a chip removes both. If the host exposes the `mcp__ccd_session__spawn_task` tool (Claude Code's desktop app), call it **once per entry in `manifest["prompts"]`, in the order they appear**, so each downstream step becomes a card the operator starts with one click. If the tool is absent (terminal Claude Code, Antigravity), **skip this step silently** — `PROMPTS.md` is the unchanged fallback, and step 6 still reports every prompt.

   Build each chip from the manifest entry, never from a re-derivation:

   - **`title`** — the entry's `title`, trimmed to an imperative phrase under 60 chars.
   - **`prompt`** — the entry's `prompt_text`, prefixed with `handoff_pack.HANDOFF_MARKER` on its own first line. The marker matters as much here as in `PROMPTS.md`: a chip's prompt lands as the first *user* turn of the new session, so without it agentm's reflect miner mines agent-authored text as the operator's own words. Import the constant; never retype it.
   - **`tldr`** — one or two plain sentences: what this session already did, and what the chip's session will finish.
   - **`cwd`** — only when the entry's work belongs to a different repo than this session's.

   **State the label in the prompt body.** A chip carries no `model` or `effort` parameter — its session inherits the host's defaults, which is exactly the silent frontier-tier inheritance the routing table exists to prevent. So write the entry's label into the prompt itself as a plain line (`Run this at tier T1 · model claude-haiku-4-5-20251001 · effort low.`) and tell the operator in step 6 which chips need the model switched after opening. The structured label in `prompts.json` stays the machine-readable source; this line is what survives into the chip.

   Record each returned `task_id` — step 6 reports it, and it is what `dismiss_task` needs if a chip is superseded before the operator clicks it.

6. **Report.** Print the destination path, the list of snapshotted files, and each prompt's title + label. When chips were spawned, say so and name the ones whose label differs from this session's model, so the operator knows which to switch on open. Tell the operator: *"Handoff pack written to `<dest-dir>`. Click a chip to start that step, or paste from `PROMPTS.md` into a fresh session at the stated model."* When chips were skipped, drop the first clause and say why (the host has no chip surface).

## Recoverability gate

Writing a new handoff directory is **recoverable** (it's a fresh directory of copies, not an edit to existing state) — announce the destination path and proceed, no confirmation needed. If `<dest-dir>` already contains a `prompts.json` from a prior pack, warn before overwriting (an accidental double-invocation clobbering a still-in-use pack is the one recoverable-but-worth-flagging case here).

Spawning a chip is **recoverable** too, and weaker than a write: a chip starts nothing on its own — it waits for the operator's click, and `dismiss_task` withdraws one that goes stale. Announce the count and proceed. Do **not** silently spawn chips for a pack the operator did not ask you to build.
