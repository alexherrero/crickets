---
name: spec
description: "Write a PRD covering objectives, commands/UX, code structure, code style, testing plan, and explicit out-of-scope boundaries before any code. Use when starting a new project, feature, or significant change. Outputs SPEC.md. /plan reads SPEC.md as structured input."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <feature name or brief>  |  <path to confirmed brief from /interview-me>
---

You are running the **spec** phase of the developer-workflows loop. Write a PRD (Product Requirements Document) before any code. `/spec` sits above `/plan`: where `/plan` decomposes a known brief into tasks, `/spec` defines what the right thing to build actually is.

**Brief from the user:** $ARGUMENTS

> **Recommended model for this phase:** Sonnet 4.6 (`claude-sonnet-4-6`) — lighter model for authoring. Override with `/model` if needed.

> **Spec-first discipline.** No `PLAN.md` before a `SPEC.md` for any non-trivial feature. A spec is the contract between intention and implementation. Its primary value is the out-of-scope section: the things you decided *not* to build, written down before anyone was tempted to build them.

## Overview

A spec answers: what are we building, what does the user see and type, how is it structured, how is it tested, and what are we explicitly not building? It does not answer how individual tasks are sequenced — that's `/plan`.

The output is a `SPEC.md` file in `.harness/` (or the vault `_harness/` in dogfood context). A plan written from a spec is more reliable than one written from a verbal brief because the scope decisions are already made and recorded — pass the SPEC.md content (or its resolved questions) as the brief when invoking `/plan`.

## When to Use

**Invoke when:**
- Starting a new project or plugin.
- Adding a feature that touches more than one file or introduces a new user-visible command.
- The brief implies a significant structural or behavioral change.
- The user says "write a spec", "spec this out", "PRD first", or similar.
- `/interview-me` has just completed and produced a confirmed brief.

**You may skip `/spec` when:**
- The change is a bug fix with a clear reproduction case (use `/bugfix`).
- The change is a one-file, one-function addition that the brief fully specifies.
- A `SPEC.md` already exists and is still accurate for the current brief.

## The Six Required Sections

A valid `SPEC.md` must contain all six sections. Before handing off to `/plan`, verify all six are present and non-empty — a spec with blank sections signals false confidence and is worse than no spec.

### 1. Objectives

What is the user trying to accomplish? Why now? What does success look like from the outside?

Write 2–4 bullet points. Each bullet is a user-observable outcome, not an implementation step. "The `/interview-me` command guides the agent through a one-Q-at-a-time interview" is an objective. "Add `interview-me.md` to `src/`" is not.

### 2. Commands / UX

What does the user type? What does the agent do in response? What does the output look like?

For CLI commands: the exact invocation syntax, the argument shape, the expected output format, and the error cases. For interactive flows: the turn-by-turn exchange, including what the agent leads with and what it waits for. For library APIs: the call signature and the return contract.

This section is the most valuable one for catching wrong assumptions before they become code. If you cannot write it, the feature is not ready to spec.

### 3. Structure

Where do the new files go? What do they do? What existing files change and why?

List every file that will be created or modified. One sentence per file explaining its role. Do not design the implementation here — record the structure so a `/plan` author knows the blast radius.

### 4. Code Style

What conventions apply to this feature that are not globally obvious?

Include: naming conventions for this feature's symbols, any patterns to follow from nearby code, patterns to avoid (and why), and any linting or formatting rules that are stricter here than globally. Leave this section out only if no feature-specific conventions apply; do not delete the section header.

### 5. Testing Plan

How do we know this works, and how do we know it keeps working?

Include: the unit test cases (one sentence per case, what it verifies), the integration test cases, manual verification steps for interactive behavior, and the regression surface (what adjacent behavior must not break). If tests are not feasible for part of the feature, name the part and explain why — do not omit silently.

### 6. Out-of-Scope Boundaries

What are we explicitly NOT building in this iteration?

This is the most important section for preventing scope creep. List at least two items. Each entry is a thing that the brief might imply, that someone might reasonably expect, or that you were tempted to add — written down so it does not get built. Include a one-sentence rationale per item so a future author knows whether the boundary still holds.

## Process

### Step 1 — Check for existing state

Read `.harness/SPEC.md` (or the vault `_harness/SPEC.md` in dogfood context). If it exists and its brief matches the current brief, ask: **Resume / Replace / Cancel**. Never silent-overwrite.

If `/interview-me` has just run and produced a confirmed brief, use that as the input rather than `$ARGUMENTS` alone.

### Step 2 — Interview if still ambiguous

If `$ARGUMENTS` leaves the Commands/UX section unwritable or the Out-of-Scope section empty, run `/interview-me` inline before writing. Do not write a spec against an underspecified brief — a spec with blank sections is worse than no spec (it signals false confidence).

### Step 3 — Write `SPEC.md`

Write all six sections. The out-of-scope section requires at least two entries. If the testing plan has gaps, name them explicitly rather than leaving the section vague.

Storage: resolve the harness root with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_doc.py" harness-root` (if available); fall back to `.harness/SPEC.md` in the repo root. Never hardcode a vault path.

### Step 4 — Review pass

After writing, walk each section and ask the user: **Approve / Revise / Note for later**. The goal is a spec the user would sign off on before any code. "Note for later" entries go into a `## Open questions` appendix in `SPEC.md` — they are resolved before `/plan` runs, not during `/work`.

### Step 5 — Hand off to `/plan`

When all six sections are approved and there are no open questions: suggest `/plan` with the confirmed spec content as the brief. Because the spec has already resolved the scope, objectives, and out-of-scope boundaries, `/plan`'s interview step will be short — the agent can derive most answers from the spec rather than asking.

## Common Rationalizations

**"The brief is clear enough, I'll skip the spec."**
A spec takes 15 minutes; discovering the wrong thing was built takes days. The brief that sounds clear is the one most likely to have a silent assumption in the Commands/UX or Out-of-Scope section.

**"I'll do the spec in my head and go straight to the plan."**
A spec in your head is not a spec. The value of writing is that it forces precision — the section you can't write is the section whose requirements are unresolved.

**"The out-of-scope section is obvious, I'll skip it."**
If it's obvious, it takes one minute to write. If it gets skipped, the next person to read the plan will not know whether the omitted thing was intentional or overlooked.

**"I'll add the missing section later, after the plan is written."**
A spec written after the plan is a post-hoc rationalization of decisions already made. Write it before.

## Verification

Before handing off to `/plan`:

- [ ] `SPEC.md` exists at the resolved harness path.
- [ ] All six sections are present and non-empty.
- [ ] Out-of-scope section has at least two entries with rationales.
- [ ] Testing plan names any gaps explicitly.
- [ ] No open questions remain in the `## Open questions` appendix (or the appendix is absent).
- [ ] User has approved all six sections.
- [ ] `/plan` has been invoked with the spec's confirmed content as the brief.
