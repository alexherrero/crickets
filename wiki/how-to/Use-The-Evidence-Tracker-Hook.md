# How to use the evidence-tracker hook

> [!NOTE]
> The `evidence-tracker` hook **moved to [Agent M](https://github.com/alexherrero/agentm)** in v2.0.0 (V4 #36 reorg).
>
> See the Agent M wiki for the operational documentation:
>
> - [Agent M wiki — Use-The-Evidence-Tracker-Hook](https://github.com/alexherrero/agentm/wiki/Use-The-Evidence-Tracker-Hook)
>
> Crickets retains pointer here for v1.x search-engine traffic and for the [Quality-Gates-Recipe](Quality-Gates-Recipe), which references the hook as part of the recommended quality-gates set.

## Why it moved

The hook is tightly coupled to Agent M's `/work` phase + `PLAN.md` task-flip semantics — it intercepts `PreToolUse` events on `Read`/`Write`/`Edit` and gates `[ ]` → `[x]` flips on prior evidence reads. Per ADR 0012 the natural home for harness-coupled hooks is Agent M itself, not the toolkit.

## Cross-references

- [Quality-Gates-Recipe](Quality-Gates-Recipe) — full installation recipe (Crickets installs `evaluator` + 3 hooks; Agent M installs `evidence-tracker`).
- [Device-Wide Architecture HLD](../explanation/designs/device-wide-architecture.md).
- [ADR 0009 — evidence-tracker hook](../explanation/decisions/0009-evidence-tracker-hook.md) — original design decision (a 2026-05-27 amendment documents the move to Agent M).
- [ADR 0012 — device-wide-by-default](../explanation/decisions/0012-device-wide-by-default.md).
