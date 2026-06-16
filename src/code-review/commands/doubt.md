---
name: doubt
description: "Subjects every non-trivial decision to a fresh-context adversarial review before it stands. Use when correctness matters more than speed, when working in unfamiliar code, when stakes are high (production, security-sensitive, irreversible), or when a confident output would be cheaper to verify now than to debug later. Do NOT use for mechanical operations, one-line renames, or following clear unambiguous instructions."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: either
---

You are running **/doubt** — in-flight adversarial review of a specific decision before it stands.

## Overview

**/doubt is in-flight; /code-review is post-hoc.** `/code-review` reviews a diff after code is written — it catches what slipped through. `/doubt` fires before a decision stands, while course-correction is still cheap: before you write the code, before you commit the architecture, before you invoke a destructive action. A single doubt cycle that surfaces a contract-misread saves a rewrite. A skipped doubt cycle on a wrong assumption ships it.

The mechanism is a bounded CLAIM→EXTRACT→DOUBT→RECONCILE→STOP loop with a hard cap of 3 cycles. Fresh context is the load-bearing property — the reviewer never sees your reasoning, only the artifact and its contract.

## When to Use

**Use /doubt when:**

- Correctness matters more than speed — a wrong call is expensive to undo
- You're working in unfamiliar code and your confidence is borrowed
- Stakes are high: production paths, security-sensitive logic, irreversible operations
- A confident output would be cheaper to verify now than to debug later

**Explicit exclusions — do NOT use /doubt for:**

- Mechanical operations with no ambiguity (copying, reformatting, scaffolding)
- One-line renames where the intent is obvious and the scope is contained
- Clear, unambiguous instructions where the correct action has exactly one interpretation

If you can't name the decision (the CLAIM step fails), the task isn't non-trivial yet — finish clarifying it first.

## The Process

### Step 1 — CLAIM

Name the decision and why it matters. Two to three lines, no more. The claim is private — it never goes to the reviewer.

> Example: "Choosing to use `os.open` with `O_BINARY` flag instead of the default text mode so the staged→active copy is byte-verbatim on Windows. This matters because the copy is a gate artifact; byte divergence would cause integrity failures on Windows CI."

### Step 2 — EXTRACT

Isolate ARTIFACT and CONTRACT. Strip your reasoning from both.

- **ARTIFACT** — the code, schema, migration, config block, or exact action you're about to take. No inline commentary explaining your reasoning.
- **CONTRACT** — what the artifact is required to do: the spec, the constraint, the verification clause, the invariant. No reasoning about why you chose this approach.

The invariant: **CLAIM never reaches the reviewer.** Handing over your conclusion biases the reviewer toward agreement. The reviewer sees only what the artifact does and what it must do.

### Step 3 — DOUBT

Assemble and dispatch:

```
=== ARTIFACT ===
<artifact text — no CLAIM, no reasoning>

=== CONTRACT ===
<contract text — no CLAIM, no reasoning>
```

Write to `/tmp/doubt-material.txt`, then invoke the cross-model reviewer:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/cross-review.sh" < /tmp/doubt-material.txt
```

The adversarial prompt to the reviewer is: **"find issues, assume overconfidence, do NOT validate."**

**Exit code handling:**
- **Exit 0** — cross-model reviewer returned findings. Use them.
- **Exit 1 or 2** — gemini unavailable or contract violated. Fall back to the in-process `adversarial-reviewer` agent with the same `/tmp/doubt-material.txt` material and the same adversarial prompt.

**Interactive vs non-interactive branching:**

After the single-model DOUBT step completes in an **interactive session**, always offer cross-model escalation:

> *"Single-model review complete — want a cross-model second opinion?"*

This offer is mandatory even when you think the decision is low-stakes. The user decides, not the agent.

In a **non-interactive context** (CI, /loop, autonomous-loop): announce the skip explicitly in output — *"Non-interactive session: skipping cross-model escalation offer."* — then proceed. Never invoke the Gemini CLI or any external tool without explicit user authorization in the current session.

### Step 4 — RECONCILE

For every finding the reviewer returned, classify it against the artifact text (not against your reasoning):

| Class | Meaning |
|---|---|
| `contract-misread` | The reviewer misread the contract — the artifact satisfies it when read correctly |
| `valid+actionable` | The finding is correct and requires a change to the artifact |
| `valid-tradeoff` | The finding is correct but the tradeoff is accepted — log the acceptance explicitly |
| `noise` | The finding is not grounded in the artifact or contract text |

A classification must cite the artifact line or contract clause it's based on. "I think it's fine" is not a classification.

**Doubt theater:** if across ≥2 cycles you have substantive findings and zero are classified `valid+actionable`, you are validating, not doubting. Stop immediately and escalate to the user — *"Doubt theater detected: 2+ cycles with findings, none actioned. Escalating."*

### Step 5 — STOP

Stop when:
- All findings in the current cycle are `contract-misread`, `valid-tradeoff`, or `noise` (no `valid+actionable` items remain)
- 3 cycles are complete (the hard cap — escalate to user rather than loop again)
- The user says "ship it"

If the hard cap (3 cycles) is hit with unresolved `valid+actionable` findings, escalate: *"3-cycle cap reached with unresolved findings — operator decision needed before proceeding."*

---

**Doubt cycle checklist:**

```
- [ ] Step 1: CLAIM — wrote the decision + why-it-matters (private; never sent to reviewer)
- [ ] Step 2: EXTRACT — isolated artifact + contract, stripped reasoning from both
- [ ] Step 3: DOUBT — invoked fresh-context reviewer with adversarial prompt
- [ ] Step 4: RECONCILE — classified every finding against the artifact text
- [ ] Step 5: STOP — met stop condition (trivial findings, 3 cycles, or user override)
```

### Common Rationalizations

| Rationalization | Why it's wrong |
|---|---|
| "I'm confident, skip the doubt step" | Confidence correlates poorly with correctness on novel problems. Moments of certainty are exactly when blind spots hide. |
| "Spawning a reviewer is expensive" | Debugging a wrong commit in production is more expensive. The check is bounded; the bug isn't. |
| "The reviewer disagreed so I was wrong" | The reviewer lacks your context — disagreement is information, not verdict. Re-read the artifact, classify, then decide. |
| "I already did /review, that covers it" | /review is a post-hoc verdict on written code. /doubt is in-flight per-decision when course-correction is still cheap. |
| "User said yes once, so I can keep invoking the CLI" | Each invocation is its own authorization. Re-confirm the exact command before every run. |

## Red Flags

- Prompting the reviewer with "is this good?" instead of "find issues, assume overconfidence, do NOT validate"
- Passing the CLAIM — your conclusion, your reasoning — to the reviewer
- Looping more than 3 cycles without escalating to the user
- Doubt theater: ≥2 cycles with substantive findings and zero classified as `valid+actionable`
- Silently skipping the cross-model offer in an interactive doubt cycle

## Verification checklist

After each doubt cycle, confirm:

```
[ ] CLAIM not passed to reviewer
[ ] ARTIFACT + CONTRACT only in the temp file (no CLAIM, no reasoning)
[ ] Every finding classified with an artifact/contract citation
[ ] Stop condition evaluated after every RECONCILE
[ ] Cross-model offer made (interactive) or skip announced (non-interactive)
```
