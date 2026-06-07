# Why phase-gating

Crickets and Agent M split the development lifecycle into discrete, gated phases — plan → work → review → release — instead of freestyling all of it in one pass. Each phase has an entry condition, a single responsibility, and an exit gate: you don't write code in the plan phase, and you don't merge in the work phase.

The payoff is that context stays scoped and verification stays honest. A single sprawling session blurs planning, coding, and review until none is done well; gated phases keep each step small enough to finish and check before the next begins. It adapts the **Stage-Gate** model from product development — staged work with explicit go/no-go gates — to an agent loop.

## Research & precedent

- **Phase-gate (Stage-Gate) process** — Robert G. Cooper's staged model with go/no-go decision gates between phases ([phase-gate process](https://en.wikipedia.org/wiki/Phase-gate_process)).

## Related

- [Why deterministic gates run first](Why-Deterministic-Gates)
- [Purpose and scope](Purpose-And-Scope)
