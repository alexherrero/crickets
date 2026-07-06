---
page-template: component-overview
sections:
  - intro
  - how-it-works
  - component-composition
  - see-also
---
<!--
  PAGE TEMPLATE: component-overview — the landing for one Architecture component (one
  per entry in wiki/architecture.yml). A COLLECTION OF SECTIONS; the `sections:` list
  IS the page, composed in order. Author a component landing by editing the list —
  drop sections that don't apply, reorder freely. The list below is the DEFAULT frame;
  the optional `safety` section is not in it — insert it after `component-composition`
  (i.e. after how-it-fits, before see-also) only on a component that carries a guardrail
  or host-gap story (Build & distribution → `## Safety`; Host adapters → `## Host gaps`).

  A component overview is a real landing, not a redirect to Reference: it LEADS with
  how the component works (the `how-it-works` section), then how it fits with its
  sibling components, then demotes field-level detail to a See also pointer. Marked
  `<!-- mode: index -->` — a shape-exempt landing, not one of the four Diátaxis modes.

  This is the richer shape an Architecture landing should grow into. The bare in-code
  `_ARCH_LANDING` scaffold (wiki_init.py) still emits a stub that just passes
  check-wiki on first scaffold; this page-type is what a hand-author (today) or the
  composer (later) fills that stub out to.

  Cross-cutting opinions a component overview enforces:
    - subtitle states the tension, not the topic: one italic em-dash line naming what's
      interesting about this component (the asymmetry, the seam) — a flat restatement of
      the title wastes the line. A straight pipeline can stay plain; an asymmetry shouldn't.
    - lead with substance: how-it-works before any link-out
    - tables / bullets for the parallel parts (pipeline stages, primitive kinds, paths)
    - state the end state as current — no version history (→ CHANGELOG / ADR)
    - field-level detail is the Reference page's job; name it in See also, don't inline
    - a cross-cutting concern (a guardrail, a host gap) is its OWN section after how-it-fits
      — the optional `safety` section — never a how-it-fits bullet; included only when one exists
    - plain, present-tense prose (the `user-facing-prose` voice lesson)

  FOLLOW-UP (not built yet): the composer (§6) reads this manifest, loads each section,
  applies the resolved voice (base ⊕ overlay) + the target language, and concatenates.
  Until then this manifest is the spec + the assembly order; author from the section
  files directly.
-->
