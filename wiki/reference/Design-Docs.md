<!-- mode: reference -->
# Design Docs

## Architecture

Design Docs gives your agent the two authoring disciplines that sit upstream of writing code: turning a design into an ordered set of plans, and capturing an architectural decision in a shape a future reader can trust. It packages both as one installable unit — the `/design` command and the `adr` skill — so a repo gets the design-authoring surface without pulling in anything else.

### Diagram

_None / not needed._

### How it works

The plugin carries two primitives. The `/design` command surfaces the three-verb pipeline — `author` a design doc to `Status: final`, `translate` the approved doc into structural `parts/`, then `sequence` those parts into topo-ordered named plans. The command is a thin wrapper: it provides the `/design` surface so design-docs users can reach the verb, but the workflow logic — the status lifecycle, storage resolution, and helper scripts — lives in `developer-workflows`, which the plugin requires. The `adr` skill is the other half. It encodes when an Architecture Decision Record is worth writing, the canonical five-section shape (Context, Decision with a "why not the alternative" per call, Consequences with re-audit triggers, Related), and treats the `adr-shape` entry in `~/.claude/CLAUDE.md` as its authoritative source. The skill is a standing instruction — it fires whenever the agent meets an architectural decision, not only when you invoke it. Because both crickets and agentm have retired the standalone-ADR model in favour of amendment logs on living designs, the `adr` skill now mainly serves other repos that still keep ADR files.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | [Developer-Workflows](Developer-Workflows) | The `/design` command delegates to developer-workflows' `/design` implementation; without it the command has nothing to delegate to. |
| Required by (hard) | — | None. |

### Why not

Design Docs is opinionated about how design authoring should flow, and it will not fit every project. Reach for something else if:

- You do not run the harness's plan-driven workflow — the `/design` pipeline assumes `developer-workflows` is installed to do the real work, so on its own the command is inert.
- Your project still keeps standalone ADR files and wants a heavier decision-record tool; the `adr` skill teaches a format and a discipline, it does not manage an ADR index or lifecycle.
- The change in front of you is small and self-explanatory. A one-file fix rarely needs a design doc or a decision record, and running the pipeline for it is more ceremony than the work warrants.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`/design`](https://github.com/alexherrero/crickets/blob/main/src/design-docs/commands/design.md) | command | Author → translate → sequence a design doc into named plans; delegates to developer-workflows. |
| [`adr`](https://github.com/alexherrero/crickets/blob/main/src/design-docs/skills/adr/SKILL.md) | skill | Decision-record discipline — when to write an ADR and the five-section shape with re-audit triggers. |

### Configuration

No configuration — the plugin works out of the box. The `/design` command reads its workflow settings from `developer-workflows`, and the `adr` skill draws its canonical shape from the `adr-shape` entry in `~/.claude/CLAUDE.md`; neither adds a config key of its own.

## See also

- [How to author a design](Author-A-Design) — the step-by-step guide for `/design author → translate → sequence`.
- [How to record an architectural decision](Record-An-Architectural-Decision) — the amendment-log workflow, and where the `adr` skill still applies.
- [Developer-Workflows](Developer-Workflows) — owns the `/design` and `/document-decision` implementations this plugin builds on.
- [Development lifecycle design](crickets-development-lifecycle) · [Design-docs design](crickets-design) — the deeper design.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)