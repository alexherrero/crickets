# Base style guide — house voice

The voice layer for authored wiki pages, composed on top of the Diátaxis
structure templates at author time (`template ⊕ base style-guide ⊕ overlay`).
This file is the **committed floor** — it ships with the skill and is always
present. Learned voice lessons layer on top from the on-demand overlay scopes
(global / per-project / per-repo); they carry the specifics, this carries the
house defaults. Keep it tight.

## Voice

- **Second person, direct.** "You" and "your" — not "the operator" or "the
  user". The reader is being addressed; address them. **Role-noun carve-out**
  (2026-07-05, PLAN-r3-voice-mechanism task 5): this bans addressing *the
  reader* in the third person, not every use of "the operator"/"the person" —
  a design doc describing a *different* actor's role (e.g. "the operator
  reviews the plan before the worker starts") is a legitimate role noun, not
  a voice violation.
- **One claim per sentence.** Target 15–25 words, one idea each. Plain language,
  direct verbs. No hedging ("it should be noted that", "it is worth mentioning"),
  no qualifiers ("arguably", "essentially"). The budget is guidance, not a gate —
  vision passages and deliberate telegraphic fragments may run shorter or longer.
- **Paragraph shape.** Target 3–5 sentences, led by the thesis sentence. State
  the point first, then support it.
- **Active voice; imperative for steps.** Actor + verb + target. Write "Run the
  test", not "the test should be run".
- **Trust the reader.** Don't over-qualify, over-explain, or footnote. If a
  sentence needs a footnote to land, rewrite it.
- **Concrete over abstract.** Sensory, specific framing for vision passages —
  not spec-sheet or marketing register.
- **Bold for real emphasis.** Especially around reader agency and key concept
  names on first use. Not decoration.
- **De-perform labels.** Section titles, table headers, bullet leads: pick the
  less-prestigious framing. The body can be substantive; the label should not
  perform. (Brand names are exempt — they're the one label allowed to perform.)
- **Plain-spoken overview + "how it works".** When a page opens with what a thing
  is, or explains how it works, write it the way you'd tell a colleague: what it
  is, why it's useful, how it moves. Keep implementation detail — internal names,
  exact paths, event/hook names, install order — out of that prose; it belongs in
  the reference tables.
- **Say what a thing is and does — never what it isn't, what stays untouched, or what we avoid.** Three anti-patterns to kill on sight: (1) no contrastive "…, not Y" tags — state the positive alone ("Realized as a how-to.", not "Realized as a how-to, not a plugin."); (2) no negative declarations of non-action ("X is untouched/unchanged") — say what we do instead ("uses the storage seam", not "the storage seam is untouched"); (3) no meta-framing throat-clearing ("The key thing is:", "All of it stands on one invariant:") — state the thing directly. **Carve-out:** the Alternatives Considered section and an amendment log's why-not-the-alternative rationale are exempt — naming and rejecting an alternative with reasoning is exactly their job. Even there, lead with the positive decision, then explain the alternative's failure as reasoning, not as a throwaway tag.
- **Plain and warm: complete sentences over compressed fragments — applies to all prose everywhere, not just design docs.** Plain stays; clipped goes. Move from telegraphic colon-led fragments to calm, complete sentences a person would actually say: `the agentm parent: four pillars on a durable memory engine` becomes `is the high-level parent design for AgentM. It is an overview of its four pillars … and how they are built on a durable memory engine.` Six rules: (1) lead a linked term with a bare "— " dash, then a complete sentence whose subject is the linked thing — never let the dash stand in for a colon that introduces a fragment; (2) verb-driven prose, not stacked-noun shorthand; (3) say what a thing *is* and *does* with a real predicate, not a compressed appositive; (4) explain rather than compress — give a distinction or reason its own plain sentence; (5) keep factual qualifiers (status, location, scope) as a trailing clause in a full sentence, not a parenthetical fragment; (6) concise without padding — one idea per sentence — but never sacrifice a complete, readable sentence to save a few words. **Warm is not ornate.** Prefer the common, expected term over a coined or metaphorical one ("technical specifications", not "the exact contract"). Index/landing descriptions are short pointers, not mini-explanations — one essential clause per item. Use makers' "we" and lead each item with "why" on Explanation pages. Don't editorialize how to read a section — point to where the other content lives instead. Composes with positive framing (say the thing, don't negate its opposite) and respects the banned-vocabulary canon.

## Banned

- **Peacock words** that carry no information: groundbreaking, deeply, vital,
  crucial, truly, delve, pioneering, transformative, visionary, "this journey",
  "the magic of X". Strip on sight — replace with the concrete mechanism.
- **Prior-art name-drops in published prose.** No "modeled after X", "inspired
  by Y". Influences shape structure silently; they aren't cited in the text.
- **Encyclopedia entries.** Write about the engagement with a thing — why it
  mattered, what it solved, what it changed — not a generic description that
  would read the same anywhere.
- **Restating instead of linking.** Reference other pages; don't re-derive them.
  The same content at three zoom levels is wrong — pick one, link the rest. When you
  do link, name the seam — what crosses between the two pages, the division of labor —
  not a re-description of the linked page.
- **Machine-checkable terms.** The `convention-drift` check (`/diataxis check`)
  scans pages for the terms on the `banned:` line below; overlay lessons extend
  it with their own `banned:` line. Findings, not failures (unless `--strict`).
  banned: groundbreaking, deeply, vital, crucial, truly, delve, pioneering, transformative, visionary, this journey, it should be noted that, it is worth mentioning, arguably, essentially, first-class, seamless, robust, leverage, comprehensive, load-bearing, powerful, cutting-edge
- **Avoid LLM-tell vocabulary.** Words like "first-class," "seamless," "robust," "leverage," "comprehensive" read as machine-generated. Use the plain word instead: "supported," "smooth," "reliable," "uses," "full." These are **findings, not failures** — a precise term-of-art use (a *first-class* primitive tier, a *robust* retry path) is legitimate; the check surfaces them for a human call. `harness` is the product's core noun (the `.harness/` state dir, the project harness) and is never banned.

## Structure

- **High-level over exhaustive.** Cap at what a reader needs to understand the
  system. Don't substitute for reference pages or ADRs.
- **Tables and bullets over prose** for parallel items (commands, flags, gates,
  options).
- **Decompose and/or chains.** When a sentence chains items with "and" or "or",
  break them into a bulleted list.
- **Introduce every list and table with a colon.** End the lead sentence with a
  colon, and set the list or table off with blank lines so it renders.
- **Simplify aggressively.** Bias toward fewer words, fewer caveats, fewer
  sub-sections.
- **"See also" / "Detail:"** for linking — not exhaustive inline references.
