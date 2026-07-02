# Why phase-gating

Why each session runs exactly one phase, and why the state that carries between them lives on disk rather than in the conversation.

A session does one phase and then stops. You plan in a plan session; you write code in a work session; you review in a review session — one responsibility at a time, never all four braided into a single sprawling pass. And because the next session is a fresh start, the handoff happens through a durable file, not the chat history. Context is ephemeral — it evaporates the moment a session ends — so the thing that lets the next session pick up where this one left off has to outlive the conversation. That is what `.harness/PLAN.md` and `progress.md` are for: the file is the memory. Whatever isn't written down is gone, so we write it down.

## How the gating works

Crickets and AgentM split the development lifecycle into discrete, gated phases — plan → work → review → release — instead of freestyling all of it in one pass. Each phase has an entry condition, a single responsibility, and an exit gate: you don't write code in the plan phase, and you don't merge in the work phase.

The payoff is that context stays scoped and verification stays honest. A single sprawling session blurs planning, coding, and review until none is done well; gated phases keep each step small enough to finish and check before the next begins. It adapts the **Stage-Gate** model from product development — staged work with explicit go/no-go gates — to an agent loop.

## Research & precedent

- **Phase-gate (Stage-Gate) process** — Robert G. Cooper's staged model with go/no-go decision gates between phases ([phase-gate process](https://en.wikipedia.org/wiki/Phase-gate_process)).

## Related

- [Why deterministic gates run first](Why-Deterministic-Gates)
- [Purpose and scope](Purpose-And-Scope)
