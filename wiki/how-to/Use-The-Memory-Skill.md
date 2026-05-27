# How to use the memory skill

> [!NOTE]
> The `memory` skill **moved to [Agent M](https://github.com/alexherrero/agentm)** in v2.0.0 (V4 #36 reorg).
>
> See the Agent M wiki for the operational documentation:
>
> - [Agent M wiki — Use-The-Memory-Skill](https://github.com/alexherrero/agentm/wiki/Use-The-Memory-Skill)
>
> Crickets retains pointer here for v1.x search-engine traffic and to preserve cross-link integrity in legacy documentation.

## Why it moved

Per the device-wide-by-default architecture (ADR 0012), Agent M is the canonical home for agentic-memory primitives — the memory skill, the four recall + reflect hooks, the `memory-idea-researcher` sub-agent, and the embedding stack (`sqlite-vec` + `sentence-transformers`) all consolidated under Agent M in V4 #36. Crickets v2.0.0 retains base primitives universal to any project (PII scrubbing, Dependabot fixing, operator-control hooks, the evaluator family); Agent M owns the compound flows that make a harness a learning assistant.

## Cross-references

- [Device-Wide Architecture HLD](../explanation/designs/device-wide-architecture.md) — full V4 design rationale.
- [Agent Memory Evolution HLD § V4.2](../explanation/designs/agent-memory-evolution.md) — release-evolution narrative.
- [ADR 0012 — device-wide-by-default](../explanation/decisions/0012-device-wide-by-default.md).
