<!-- mode: reference -->
# Design Docs plugin

> [!NOTE]
> **ADR model retired in crickets/agentm** (2026-06-24). Load-bearing decisions now go into the **amendment log** of the relevant living design under [`wiki/designs/`](Designs) rather than standalone ADR files. The `adr` skill remains useful for **other repos** that still use the ADR model; in crickets/agentm, use the amendment-log workflow in [How to record a design decision](Record-An-Architectural-Decision).

The `design-docs` plugin (`requires: developer-workflows`) surfaces the design-doc and amendment-log authoring workflow as an installable unit: the **`adr` skill** (decision format discipline + when-to-write, for repos that use ADRs) and the **`/design` command** (the author → translate → sequence pipeline, delegating to `developer-workflows`).

## ⚡ Quick Reference

| Aspect | Value |
|---|---|
| Plugin slug | `design-docs` |
| Version | 0.1.0 |
| Requires | `developer-workflows` |
| Primitives | `adr` skill · `/design` command (delegation wrapper) |
| Hosts | Claude Code · Antigravity |

## Primitives

### `adr` skill

Encodes when to write an Architecture Decision Record, the canonical 5-section shape, and the re-audit-trigger discipline. The skill is a **standing instruction** — it fires whenever the agent encounters an architectural decision, not only when you invoke it explicitly.

The 5-section shape:

| Section | What goes here |
|---|---|
| Opening block | `> [!NOTE]` with `Status: accepted\|superseded\|rejected` + `Date` |
| **Context** | The open question the ADR resolves; relevant constraints; prior art |
| **Decision** | One-sentence decision + rationale; **"why not the alternative" is required per call** |
| **Consequences** | Positive bullets · Negative bullets · Load-bearing assumptions with explicit re-audit triggers |
| **Related** | Cross-refs to other ADRs, design docs, plans, issues |

Re-audit triggers are what separate a living record from a tombstone — each assumption names the condition under which the decision must be reconsidered.

> **ADR skill vs `/document-decision` command:** the `adr` skill teaches the agent the *format and discipline* of ADR writing. The `/document-decision` command (in `developer-workflows`) is the *workflow trigger* — it prompts you to write an ADR at the right moment in a decision process and enforces the "write before implementing" contract. Both work together; the skill is always present, the command is invoked at the decision point.

### `/design` command (delegation wrapper)

Provides the `/design` command surface to `design-docs` users without duplicating the implementation. The full author → translate → sequence pipeline lives in `developer-workflows`; this wrapper surfaces it so the `/design` verb is discoverable in the `design-docs` plugin catalog entry.

Three sub-verbs, strictly ordered:

| Verb | What it does |
|---|---|
| `author` | Walk the 10-section design-doc template to `Status: final`; the only verb that sets `final` |
| `translate` | Split a `Status: final` doc into `parts/` files |
| `sequence` | Topo-sort `parts/` into named plans (first activated, rest queued) |

If `developer-workflows` is not installed, this command has no implementation.

## Install

```bash
claude plugin install design-docs@crickets
```

Requires `developer-workflows` as a base. Both plugins must be enabled for the command and skill to load.

## See also

- [How to author a design](Author-A-Design) — the step-by-step guide for `/design author → translate → sequence`.
- [How to record an architectural decision](Record-An-Architectural-Decision) — the step-by-step guide for `/document-decision` (the ADR workflow trigger).
- [developer-workflows plugin](Developer-Workflows) — owns the `/design` and `/document-decision` implementations.
- [Development lifecycle design](crickets-development-lifecycle) — why `/design` lives in `developer-workflows` and `design-docs` wraps it.
- [Customization Types](Customization-Types) — what `kind: skill` and `kind: command` are.
