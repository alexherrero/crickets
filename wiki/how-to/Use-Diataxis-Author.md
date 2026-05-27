# How to use diataxis-author

> [!NOTE]
> The `diataxis-author` skill **moved to [Agent M](https://github.com/alexherrero/agentm)** in v2.0.0 (V4 #36 reorg). The `diataxis-evaluator` sub-agent stayed in Crickets — it's a base evaluation primitive Agent M's author skill consumes.
>
> See the Agent M wiki for the operational documentation:
>
> - [Agent M wiki — Use-Diataxis-Author](https://github.com/alexherrero/agentm/wiki/Use-Diataxis-Author)
>
> Crickets retains pointer here for v1.x search-engine traffic.

## What stays in Crickets

The `diataxis-evaluator` sub-agent (at `crickets/agents/diataxis-evaluator.md`) — the grader the author skill consumes. Base evaluators stay in Crickets per the split rationale; compound flows (the author skill itself) live in Agent M.

## Cross-references

- [Use-The-Evaluator](Use-The-Evaluator) — evaluator family overview (includes `diataxis-evaluator`).
- [Device-Wide Architecture HLD](../explanation/designs/device-wide-architecture.md).
- [ADR 0012 — device-wide-by-default](../explanation/decisions/0012-device-wide-by-default.md).
