---
name: handoff-pack
description: Snapshot an expensive session's outputs into a vault handoff directory alongside paste-ready prompts for downstream cheap sessions, each carrying a machine-readable tier/model label.
kind: command
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
argument-hint: "<dest-dir> [--title <entry title> --model <model-id> --tier <tier> --effort <effort> --prompt <text>]..."
---

You are running `/handoff-pack` — it generalizes the Mythos `PROMPTS.md` pattern (`<vault>/projects/agentm/_harness/mythos-readiness-handoff/PROMPTS.md`): when a session did expensive, hard-won work and the remaining steps are cheap and mechanical, snapshot the outputs and hand off paste-ready prompts to fresh, cheaper sessions instead of continuing in the expensive one.

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

5. **Report.** Print the destination path, the list of snapshotted files, and each prompt's title + label. Tell the operator: *"Handoff pack written to `<dest-dir>`. Paste the prompts in `PROMPTS.md` into fresh sessions at the stated models."*

## Recoverability gate

Writing a new handoff directory is **recoverable** (it's a fresh directory of copies, not an edit to existing state) — announce the destination path and proceed, no confirmation needed. If `<dest-dir>` already contains a `prompts.json` from a prior pack, warn before overwriting (an accidental double-invocation clobbering a still-in-use pack is the one recoverable-but-worth-flagging case here).
