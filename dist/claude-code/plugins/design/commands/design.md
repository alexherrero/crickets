---
name: design
description: "Write or update the living design note a project keeps in its vault: objective, current design, open questions, amendment log. One note per area, kept true by amending it; no template walk, no status gate, nothing published to wiki/designs/. Use when a decision settles something a design should say."
kind: command
supported_hosts: [claude-code, antigravity]
version: 1.0.0
argument-hint: <slug or topic> [<what changed or was decided>]
opinions: [good, how-we-engineer]
---

You are running **design**: keep the project's living design note true. A living design is one note per area of the project. Its body says what is true now; its amendment log says how it got there. `/plan` reads it for the locked calls a plan must honour, and `/spec` reads it for the rules a task is held to.

**Topic from the user:** $ARGUMENTS

> **Recommended model for this phase:** Sonnet 5.5 (`claude-sonnet-5-5`) — lighter model for planning and authoring. Override with `/model` if needed.

## Process

### 1. Find the note

Ask where the project keeps its designs: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/project_homes.py" home designs`. It prints the folder; **exit 3** (no agentm, no vault) means there is no vault to write to: say so, and use `.harness/design-<slug>.md` in the repo, which you create. List the folder and open the note whose slug or aliases match the topic. If none does, this is a new note.

Never write into a folder agentm did not name, and never into `wiki/designs/`: pages already there stay as they are until the wiki moves, and are not touched by this command.

### 2. New note

Write it with this frontmatter and these four sections, and nothing else:

```
---
type: design
status: active
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
slug: <slug>
aliases: [<names people will look it up by>]
tags: [<project>, <area>]
governs: [<repo folders or files this note holds the locked calls for, optional>]
summary: "<one line>"
---
```

- **Objective** — what this area is for and what it must stay true to, in a short paragraph.
- **Current design** — how it works now: the locked calls, each with its reason. A call someone could be tempted to reopen says why the alternative lost.
- **Open questions** — what is not settled, or `none`.
- **Amendment log** — newest last, one entry per change: *date · what changed · why not the alternative · the re-audit trigger*.

`aliases`, `tags` and `governs` are how `/plan` finds the note for a task, so fill them in: a plan that touches `src/design/` is matched by a `governs` entry naming that folder, or by an alias equal to the area name.

### 3. Existing note

Change the body so it states the new truth, and add the amendment-log entry **in the same edit**. The body and the log never disagree: a decision that is only in the log has not happened, and a body that changed with no entry has lost its history. Set `updated:` to today. Do not restate the whole note; touch the lines that changed. Size the edit to the decision, not to a reflex for a full rewrite:

<!-- opinion:how-we-engineer -->
How we engineer means the phase discipline: plan before code, one task at a
time gated on real verification, bugs get a Report → Analyze → Fix → Verify
pass instead of a patch-and-hope, and sizing matches the actual scope
instead of over- or under-building it.
<!-- /opinion:how-we-engineer -->

### 4. Show it, once

Before the operator reads it, read the diff the way a reviewer would who assumes it is wrong:

<!-- opinion:good -->
Good means it survives an adversarial pass primed to assume bugs exist, not
a friendly skim. The standard is a failing test, a specific file:line
defect, or an explicit "no issues found" after genuinely looking — prose
critique without one of those three is not a review.
<!-- /opinion:good -->

Applied to a design note: an approval means each call survives a hostile read, not that it looks plausible; a vague or unverifiable claim gets revised, not passed. Then show the diff and ask the operator to approve or revise. There is no status to flip and no review stage; the note is live from the first save.

### 5. Prose

Offer the `prose-pass` skill when the operator wants the wording simplified; do not run it unasked. It runs `prose_pass.py` (Gemini simplifies, Claude fact-checks and applies). No `--overlay` override needed: the default overlay is design-doc prose, which is this genre. If the script prints `PROSE-PASS-DEGRADED:`, relay the line verbatim and do the pass yourself, Claude-only. The pass is a courtesy and never blocks saving the note.

## Verification

- [ ] The note is in the folder agentm named (or `.harness/design-<slug>.md` with no vault), not in `wiki/designs/`.
- [ ] The body and the amendment log say the same thing, and the entry names a re-audit trigger.
- [ ] `aliases`, `tags` or `governs` let `/plan` find it.
