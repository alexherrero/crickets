---
name: simplify
description: "Simplify code for clarity and maintainability without removing load-bearing structure. Applies Chesterton's Fence (understand why code exists before removing it) and the Rule of 500 (long functions/files as signals to investigate). Use after a feature lands to reduce accidental complexity."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <file, directory, or diff range — defaults to uncommitted working-tree diff>
---

You are running **/simplify** — targeted simplification for clarity and maintainability. The goal is to reduce accidental complexity without removing load-bearing code.

**Target:** $ARGUMENTS — a file, directory, or diff range. Defaults to the uncommitted working-tree diff if empty.

## Overview

Simplification is not removal. Code that looks redundant usually has a reason it is there; code that looks long usually has a constraint that produced the length. The job of `/simplify` is to reduce *accidental* complexity — naming that obscures intent, duplication that has no semantic meaning, structure that adds indirection without adding clarity — while leaving *essential* complexity untouched.

The two principles below are the load-bearing part of this command. Apply them before any change.

## Key Principles

### Chesterton's Fence

> Before you remove or simplify any piece of code, be able to state in one sentence why it is there.

If you cannot state the reason — if the code is "obviously dead" or "clearly redundant" but you cannot say what it was protecting against — it is not safe to remove. The fence was put there for a reason. Your job is to find the reason, not to assume there isn't one.

Acceptable reasons: handles a known edge case; works around a third-party bug; satisfies a constraint documented elsewhere; is used by a caller not visible in the immediate context. If you find the reason and it is still valid, the code stays. If you find the reason and it is no longer valid, document that explicitly in the commit message.

### Rule of 500

A function over 500 lines is a smell. A file over 500 lines probably has more than one responsibility.

These are **signals to investigate**, not hard gates. The right response to a 600-line function is to ask: "what is this doing, and do the pieces belong together?" — not to mechanically split it. Sometimes the 600-line function is six 100-line concerns that genuinely belong together; usually it is two 300-line concerns that don't.

## Process

### Step 1 — Read without editing

Read the target diff or file. Identify:
- Lines that are genuinely ambiguous in purpose.
- Naming that obscures rather than describes.
- Structure that adds indirection without adding clarity.
- Duplication that has no semantic value.

Do **not** form an edit list yet. Understanding comes before changes.

### Step 2 — Apply Chesterton's Fence to every candidate removal

For each piece of code you are considering removing or collapsing: state the reason it exists before touching it. If you cannot state the reason, skip the removal and leave a comment in your output noting the gap.

### Step 3 — Simplify what passes the check

Make only the changes you can justify under Chesterton's Fence. For each change, one sentence of rationale in the commit message is required.

### Step 4 — Flag Rule of 500 violations

If the target contains functions or files over 500 lines, note them explicitly — the location, the line count, and a hypothesis about what distinct concerns are mixed. Do not split them without operator approval; flag them for follow-up.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "This code is obviously dead, I'll remove it." | Chesterton's Fence: if you cannot state why it's there, you cannot safely remove it. "Obviously dead" is a confidence claim, not a safety check. |
| "This function is too long, I'll split it." | The Rule of 500 is a signal to investigate, not a mandate to split. Understand what the length is protecting before restructuring. |
| "I'll simplify and add the rationale later." | The rationale is the safety check. Writing it later means skipping the check. |

## Verification checklist

Before committing:

- [ ] Every removal can be justified in one sentence.
- [ ] No removal was made under "obviously dead" reasoning without finding the actual reason.
- [ ] Rule of 500 violations are flagged, not silently fixed.
- [ ] Functionality is unchanged — no behavioral diff, only structural.
- [ ] Commit message includes one-sentence rationale per removed/collapsed piece.
