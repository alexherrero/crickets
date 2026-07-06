# Documentation templates + stylistic conventions

The normative source `documenter` and `diataxis-author` write against — restored from agentm's `harness/documentation.md` (the harness-side predecessor this plugin subsumed), which crickets never carried a copy of even though `documenter.md` linked to it (R2.4 task 5).

## Templates

Every wiki file starts with `#` H1 + a one-paragraph summary. No YAML front-matter. The core shapes below cover the common cases; section-specific templates follow crickets' canonical `wiki-maintenance` set rather than a fixed count:

### Template 1 — "Page" (the default)

```markdown
# <Title>

<1-paragraph summary: what this page covers and who it's for.>

## ⚡ Quick Reference

| Question | Answer |
|---|---|
| <common lookup> | <answer with cross-links> |
| Where's the code? | [`path/to/file.ts`](github-url) |
| Related pages | [Page One](Page-One), [Page Two](Page-Two) |

## <Semantic section>
<prose, tables, diagrams, alerts, code blocks>

## <Semantic section>
...
```

`⚡ Quick Reference` is encouraged, optional for tiny pages. Section headers are chosen for the page — not a fixed list.

### Template 2 — "Status" extension

Layered on Template 1. Used for explanation pages `documenter` tracks through `pending → implemented → deprecated`: `explanation/<feature-or-subsystem>.md`.

```markdown
# Feature: <Title>

> [!NOTE]
> **Status:** pending
> **Plan:** `.harness/PLAN.md#task-N`
> **Last updated:** YYYY-MM-DD

<1-paragraph summary.>

## ⚡ Quick Reference
| ... | ... |

## Intent
<user-facing why. documenter leaves this alone after /plan writes it.>

## Design
<how it works. Tables, diagrams, `file:line` links. documenter updates if plan shifted.>

## Implementation
<filled in by documenter post-/work. Real `file:line` references, actual behavior.>

## Notes
<footguns, follow-ups, deferred items.>
```

### Template 3 — "Decision record" (amendment-log entry)

The ADR model is retired: a load-bearing decision is recorded as an entry in the governing living design's `## Amendment log` (under `designs/`), not a standalone file. Reconcile the design's body to the new truth and append the entry in the same atomic change.

```markdown
**YYYY-MM-DD — <summary of the change>.**
<decision prose>. *Why not the alternative:* <why-not>. *Re-audit trigger:* <condition that would make this wrong>.
```

### Template 4 — "How-to" (incl. onboarding walkthroughs)

For `how-to/<Verb-Object>.md` and the numbered onboarding pages (`how-to/<NN>-<slug>.md`) that the six-section frame folds in where a separate `tutorials/` dir used to live. Opens with a `> [!NOTE]` Goal / (Time, for onboarding /) Prereqs block; body is numbered steps.

```markdown
# <Verb the reader is doing>

> [!NOTE]
> **Goal:** <one sentence: what the reader will have accomplished.>
> **Time:** ~<N> minutes.   <!-- onboarding walkthrough only -->
> **Prereqs:** <environment, tools, prior knowledge.>

<1-paragraph framing for an onboarding walkthrough; a plain how-to skips straight to Steps.>

## Step 1 — <verb the reader is doing>   <!-- onboarding uses numbered ## Step N H2s -->
<prose + commands>

## Step 2 — ...

## What you learned   <!-- onboarding walkthrough only -->
- ...

## Next   <!-- onboarding only: links to ≥1 other how-to and ≥1 reference -->
- <link>
```

Plain how-to variant: skip the onboarding framing paragraph and the "What you learned" / "Next" sections; use a `## Steps` H2 with a numbered markdown list. **Do not add `## Rationale` / `## Why` / `## Background` / `## Context` — those are explanation H2s and will fail the section-purity lint.**

## Stylistic conventions

- **Tables over bullet lists** for comparative information.
- **Diagrams** — ASCII in fenced code blocks or Mermaid. Use one whenever a relationship is clearer drawn than described.
- **GitHub alerts** for load-bearing callouts: `> [!NOTE]`, `> [!IMPORTANT]`, `> [!WARNING]`.
- **Emoji section markers**, consistent across pages: 🔧 How-to · 📖 Reference · 🏛️ Architecture · 📐 Designs · 💡 Explanation · 🛠️ Operational · ⚡ Quick Reference.
- **Cross-links**: wiki pages by basename (`Home`, `01-Getting-Started`, etc.), full GitHub URLs with `#L<line>` for code references.
