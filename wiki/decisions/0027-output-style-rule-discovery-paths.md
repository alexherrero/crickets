# ADR 0027 — Discovery paths for `output-style` and `rule` primitives within a plugin group

> [!NOTE]
> Status: accepted
> Date: 2026-06-14

## Context

The crickets manifest schema (`src/SCHEMA.md`) has always listed `output-style` and `rule` in the valid `kind` enum, but until Part D neither kind has an instance in any plugin group, and `generate.py` / `lint_src.py` have no discovery path for them.

Part D ships the first concrete instances of both:

- `src/developer-workflows/output-styles/terse.md` — kind `output-style`
- `src/developer-workflows/rules/edit-over-write.md` — kind `rule`

These require a discovery path (subdir convention + generator traversal). Two competing placements were considered.

**Open questions this decision resolves:**

- Should `output-style` and `rule` primitives live as new top-level plugin groups, or as subdirs within the existing `developer-workflows` group?
- What are the canonical subdir names (`output-styles/` vs `output_styles/`)?
- Does the generator need changes to traverse these new subdirs?

## Decision

### 1. New subdirs within `developer-workflows`, not new top-level plugin groups

`output-styles/` and `rules/` are added as subdirs inside `src/developer-workflows/`, not as standalone top-level groups.

**Why not new top-level groups?** These levers are dev-loop-specific — they codify the token-discipline conventions that apply specifically while the `developer-workflows` phase loop is running. Splitting them into separate groups would give them an independent install lifecycle, but they have no meaning outside `developer-workflows`; an adopter who installs the output-style without the commands it applies to gets nothing useful. Co-locating them in the same group also lets them share the same version bump, keeping the version number as the signal for "these levers are available."

**Why not `requires: developer-workflows` on a sibling group?** A hard dependency (`requires:`) creates an installable pair, which is the correct model when the two groups are independently useful and happen to be co-installed. A Terse output style is not independently useful — it exists as a package of conventions for the dev-loop phase, not as a standalone output discipline. Subdirness is the right container.

### 2. Canonical subdir names: `output-styles/` and `rules/`

Plural, hyphenated, matching the `kind` enum with an `s` suffix. The generator already uses this convention for `hooks/`, `skills/`, `commands/`, `agents/`, `snippets/`.

| Kind | Subdir |
|---|---|
| `skill` | `skills/` |
| `agent` | `agents/` |
| `command` | `commands/` |
| `hook` | `hooks/` |
| `snippet` | `snippets/` |
| `output-style` | `output-styles/` |
| `rule` | `rules/` |

### 3. Generator and linter patches are part of task 2

`generate.py` traversal and `lint_src.py` discovery for these subdirs are audited and patched in task 2 (Terse output style) before writing any instance. Task 3 (Edit-over-Write rule) reuses the same traversal. If no patch is needed (e.g., the generator already walks all subdirs dynamically), that is confirmed and recorded in the task 2 commit.

### 4. Discovery path convention

Mirrors the `hook` discovery path structure:

| Kind | Discovery path |
|---|---|
| `output-style` | `output-styles/<name>.md` (single-file primitive) |
| `rule` | `rules/<name>.md` (single-file primitive) |

Single-file rather than the `hooks/<name>/hook.md` dir-plus-file pattern, because output styles and rules have no companion scripts (unlike hooks, which need a `run.sh` alongside `hook.md`).

## Consequences

**Positive**

- The first concrete `output-style` and `rule` instances live where they are most meaningful — inside the group they augment — and share its version lifecycle.
- The subdir naming is consistent with the existing convention; no new pattern to learn.
- Generator and linter changes are scoped to traversal of two new subdirs — minimal blast radius.

**Negative / accepted debt**

- Until a non-`developer-workflows` group needs an `output-style` or `rule`, the discovery path is only exercised in one group. The convention is correct but unvalidated across multiple groups. **Re-audit when** a second group adds an instance.
- Single-file primitives cannot bundle companion scripts. If a future `rule` or `output-style` needs a script, the dir-plus-file pattern (like `hooks/`) would need to be extended. **Re-audit trigger:** a rule or output-style that needs a runtime script.

**Load-bearing assumptions + re-audit triggers**

- *`generate.py` traversal is additive* — adding `output-styles/` and `rules/` subdirs does not break existing traversal of the five shipping kinds.
- *`lint_src.py` validates `kind` against the enum, not against "is there a discovery path for this kind?"* — a primitive with `kind: output-style` in a group with no generator support is currently emitted without error. The task 2 patch closes this gap; re-audit if `lint_src.py` adds a stricter "discoverable kinds only" check that rejects the new subdirs before the generator is updated.

## Related

- [Developer-Workflows token efficiency](../explanation/Developer-Workflows-Token-Efficiency) — the parent feature page
- [ADR 0026](0026-phase-aware-model-routing) — the routing-defaults decision (companion in Part D)
- [Customization types](../reference/Customization-Types) — what `output-style` and `rule` are
- [Manifest Schema](../reference/Manifest-Schema) — discovery path table (will be updated when this ADR is accepted)
- [`src/SCHEMA.md`](https://github.com/alexherrero/crickets/blob/main/src/SCHEMA.md) — the source schema
