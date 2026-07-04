---
name: interview-me
description: "Extracts what the user actually wants through a one-Q+hypothesis interview until ~95% confidence. Use when an ask is underspecified, when you catch yourself silently filling in ambiguous requirements, or when the user invokes 'interview me' / 'grill me' / 'are we sure?'. Do not invoke in non-interactive contexts (CI, /loop, autonomous-loop) — flag as underspecified instead."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <brief or topic to clarify>
---

You are running **interview-me** — a structured one-question-at-a-time brief extraction. The goal is to reach ~95% confidence about what the user actually wants before any planning or implementation starts.

**Topic from the user:** $ARGUMENTS

> **Recommended model for this phase:** Sonnet 5 (`claude-sonnet-5`). Override with `/model` if needed.

## Overview

A brief that *sounds* clear usually isn't. Silent assumption-filling is the most common source of wasted work — the plan that was executed exactly as written but wasn't what anyone needed. This command surfaces and resolves those ambiguities before code is written.

The mechanism is hypothesis-driven: the agent leads with a belief about the answer, then asks one question at a time. The user reacts to a wrong guess rather than generating from scratch. This is faster than open-ended questions and forces the agent to commit to a hypothesis — which exposes false confidence.

## When to Use

**Invoke when:**
- The brief leaves open a decision that would materially change the implementation.
- You notice yourself silently choosing between two reasonable interpretations.
- The user says "interview me", "grill me", "are we sure?", or similar.
- The brief is a sentence or two and covers a non-trivial feature.

**Do NOT invoke when:**
- Running in a non-interactive context (CI pipeline, `/loop`, autonomous-loop, `/spawn-worker` without a human present) — flag the brief as underspecified and surface the unresolved questions as blockers instead.
- The brief is fully specified and derivable from the codebase.
- You've already completed a `/spec` that resolves the open questions.

## The Process

### Step 1 — State your hypothesis + confidence

Before asking anything, commit to a belief. Open every response (until confidence ≥95%) with:

```
HYPOTHESIS: <one sentence — your current best model of what the user wants>
CONFIDENCE: <0–100%>
```

If confidence is already ≥95%, skip to the stop condition. The hypothesis is not a question; it is a claim you are willing to be wrong about.

### Step 2 — Ask ONE question with your best-guess answer

After the hypothesis block, ask exactly one question. Immediately follow it with your current best-guess answer:

```
Q: <the single most important unresolved question>
My guess: <your best-guess answer — specific, not "I'm not sure">
```

The guess is required. "I don't know" is not a valid guess — pick the most likely option and commit. The user reacts to a wrong guess faster than they generate an answer from scratch.

### Step 3 — Wait for the reaction, then update

After the user responds:
1. Update the HYPOTHESIS to reflect what you learned.
2. Update CONFIDENCE.
3. If confidence < 95%: return to Step 2 with the next most important unresolved question.
4. If confidence ≥ 95%: proceed to the stop condition.

Each question resolves one ambiguity. The order matters — ask the question whose answer would most change your hypothesis first.

### Stop condition — confidence ≥ 95%

When you can predict the user's answer before they give it, you are done. At that point:

1. Write a concise brief (3–5 sentences) summarizing what the user wants, including at least one explicit out-of-scope item.
2. Ask the user to confirm the brief is correct.
3. On confirmation: suggest the next command (`/spec` for non-trivial features; `/plan` otherwise) and pass the confirmed brief as the argument.

## Common Rationalizations

**"I'll just ask 3 questions at once."**
Batching questions buries your hypotheses and skips the reaction step — one at a time is load-bearing, not style. When you ask three questions, the user answers all three at once and you learn less about which question was actually doing the clarifying work.

**"The brief is probably fine, I'll just start planning."**
Silent assumption-filling is the failure mode this command exists to prevent. If you noticed an ambiguity but decided to proceed anyway, you are making a product decision that belongs to the user.

**"The user will correct me if I'm wrong."**
They will — after you've written the plan and half the implementation. The cost of a wrong assumption compounds.

**"I've already asked two questions, that's enough."**
Stop when confidence ≥95%, not when a round number of questions has been asked. Two questions that leave the core ambiguity unresolved are insufficient; one question that resolves it is enough.

## Verification checklist

Before declaring the interview complete:

- [ ] HYPOTHESIS was stated before every question.
- [ ] Only ONE question was asked per turn.
- [ ] Every question included a specific best-guess answer.
- [ ] Confidence ≥95% was reached before the summary was written.
- [ ] The confirmed brief includes at least one explicit out-of-scope item.
- [ ] The next command (`/spec` or `/plan`) was suggested with the confirmed brief as input.
