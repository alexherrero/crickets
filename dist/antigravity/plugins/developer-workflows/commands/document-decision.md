---
name: document-decision
description: "ADR trigger workflow — WHEN to write an Architecture Decision Record and HOW to execute it. Trigger conditions: any architectural decision, any public API change, any behavior change not obvious from code. Execution: draft the ADR before implementing, not after; include 'why not the alternative' per call; link from CHANGELOG. References the adr-shape convention — does not redefine it."
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: <decision being made — a one-sentence description of the architectural call — required>
---

You are running **/document-decision** — the ADR trigger workflow for capturing an architectural decision before it calcifies in commits.

**Decision:** $ARGUMENTS — a one-sentence description of the architectural call being made. Required. If you cannot state the decision in one sentence, the decision is not yet clear enough to implement.

## When to Use

Run `/document-decision`:

- When making any architectural decision — a choice between two or more non-trivial approaches where the reasons for the choice are not obvious from the code.
- When changing a public API — any change that affects callers outside the current service or module, including deprecations, additions, and behavior changes.
- When making any behavior change that is not obvious from reading the code — a change where a future reader of the diff would ask "why?".
- When choosing NOT to do something that a reviewer will likely suggest — a proactive ADR prevents the same discussion from recurring.

**Do NOT use** for implementation details that are obvious from the code, routine refactors with no meaningful tradeoff, or changes fully explained by an existing ADR. An ADR answers "why this approach?" — not "what does this code do?"

## Key Principles

### Draft Before Implementing, Not After

The purpose of an ADR is to force clarity on the decision before you commit to it. An ADR written after the implementation is a justification, not a decision record — you already know what won, and the "alternatives considered" section becomes a post-hoc rationalization.

Write the ADR first. If you cannot complete it before implementing, the decision is not settled. A completed ADR means the tradeoffs are understood; an implementation without one means they are not.

### "Why Not the Alternative" Per Call

Every load-bearing call in the Decision section must include an explicit "why not" for the alternative you rejected. "We chose X" is not a decision record — it is an announcement. "We chose X over Y because Z, and we did not choose Y because Q" is a decision record.

Without the "why not," the next engineer who reads the ADR does not know whether the alternative was considered and rejected, or simply not considered. If an assumption behind the rejection changes, they cannot re-audit the decision without knowing what the assumption was.

### Link from CHANGELOG

Every ADR must be linked from the CHANGELOG entry for the release that implements the decision. A decision that is not linked from the CHANGELOG is a decision that will not be found when someone asks "why did we do this in v3.2.0?" The link makes the ADR discoverable at the point of change.

### ADRs Have Re-Audit Triggers

A decision is correct given the assumptions in force when it was made. Assumptions change. Every ADR must name at least one re-audit trigger: a condition under which the decision should be revisited. Without a trigger, a wrong decision will remain in place long after the assumption that made it right has rotted.

## The Process

### Step 1 — State the decision

Before writing the ADR, state the decision in one sentence: "We are choosing X to accomplish Y." If you cannot, stop and clarify the decision. An unclear decision produces an unclear ADR.

### Step 2 — Draft the ADR before implementing

Open the ADR file now, before writing any code. The format is the `adr-shape` convention in your CLAUDE.md; follow it exactly. A brief orientation for new adopters:

The ADR opens with a `> [!NOTE]` block carrying `Status: accepted | superseded | rejected` and the date. It has four sections:

- **Context** — what question this decision resolves; what was true that made the decision necessary. Include the open questions the decision closes.
- **Decision** — what was chosen and why. For every load-bearing call, include the explicit "why not the alternative."
- **Consequences** — positive bullets (what this enables); negative bullets (what this costs or forecloses); load-bearing assumptions with explicit re-audit triggers (e.g. "re-audit if X changes").
- **Related** — cross-refs to other ADRs, plans, or design docs.

For the exact section order, formatting, and conventions, follow the `adr-shape` convention in your CLAUDE.md. The format is owned there; this command adds the trigger and execution steps.

### Step 3 — Fill "why not the alternative" for every load-bearing call

Read back the Decision section. For every choice named, ask: what was the strongest alternative? Why was it rejected? Add a "why not" sentence for each. If the alternative was not considered, note that too — it tells the next reader the search space.

### Step 4 — Name re-audit triggers

In the Consequences section, for each load-bearing assumption, name a concrete condition that would make the decision wrong. "Re-audit if [assumption X] changes" is the minimum. A trigger that is always false is not a trigger.

### Step 5 — Implement

Only now write the code. The ADR is done; the decision is settled. If you discover mid-implementation that the decision is wrong, update the ADR before continuing — do not silently diverge.

### Step 6 — Link from CHANGELOG

In the CHANGELOG entry for this release, add a link to the ADR. The format per the `changelog-shape` convention: the ADR link appears in the narrative or as a cross-reference. The reader of the CHANGELOG must be able to find the ADR without a git blame.

### Step 7 — Verify

Before merging:

1. ADR exists and has all four sections complete (no placeholder text).
2. "Why not the alternative" is present for every load-bearing call in the Decision section.
3. At least one re-audit trigger is named in the Consequences section.
4. CHANGELOG links to the ADR.
5. ADR `Status` is `accepted` (or `superseded` / `rejected` with a reason and a cross-ref to what superseded it).

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "The decision is obvious from the code — no ADR needed." | Code shows what was decided; it does not show why the alternative was rejected. A future reader seeing a flag, a dependency, or an architecture pattern cannot tell whether the obvious alternative was considered. If it was considered and rejected, write the ADR. If it was not considered, write the ADR so the next reader knows the search space. |
| "I'll write the ADR after I finish implementing — I understand it better then." | After implementing, you know what won. The "alternatives" section becomes a post-hoc justification; the "why not" becomes harder to write honestly because you are defending a decision that is already committed. Write it before: if the decision is right, the ADR will confirm it; if the decision is wrong, the ADR will surface it before the implementation exists. |
| "This is a small change — it doesn't rise to the level of an ADR." | Trigger conditions are: any architectural decision; any public API change; any behavior change not obvious from code. "Small" is not a trigger condition. The right question is not "is this big enough?" but "will a future reader ask 'why?'". If yes, write the ADR. |
| "We can reconstruct the reasoning from the PR discussion." | PR discussions are ephemeral: comments are not indexed, threads collapse, and the context that made a comment make sense disappears. An ADR is a durable, findable record. If the reasoning is only in the PR, it is effectively lost. |

## Red Flags

- A significant behavior change merged without an ADR.
- An ADR written after the implementation is already merged (justification, not a decision record).
- A Decision section with no "why not the alternative" for any of the major calls.
- An ADR with no re-audit trigger in Consequences (a decision immune to being wrong forever).
- A CHANGELOG entry that implements a non-obvious architectural choice without linking an ADR.
- An ADR with `Status: accepted` for a decision that was later reversed, without a `Status: superseded` update.

## Verification checklist

- [ ] Decision stated in one sentence before starting the ADR.
- [ ] ADR drafted before any implementation code written.
- [ ] All four sections complete: Context, Decision, Consequences, Related.
- [ ] "Why not the alternative" present for every load-bearing call in Decision.
- [ ] At least one re-audit trigger named in Consequences.
- [ ] CHANGELOG entry for this release links to the ADR.
- [ ] ADR `Status` field is set correctly (`accepted`, `superseded`, or `rejected`).
- [ ] No placeholder text remaining in any section.
