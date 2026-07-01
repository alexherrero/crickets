# Base style guide — house voice

The voice layer for authored wiki pages, composed on top of the Diátaxis
structure templates at author time (`template ⊕ base style-guide ⊕ overlay`).
This file is the **committed floor** — it ships with the skill and is always
present. Learned voice lessons layer on top from the on-demand overlay scopes
(global / per-project / per-repo); they carry the specifics, this carries the
house defaults. Keep it tight.

## Voice

- **Second person, direct.** "You" and "your" — not "the operator" or "the
  user". The reader is being addressed; address them.
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
  banned: groundbreaking, deeply, vital, crucial, truly, delve, pioneering, transformative, visionary, this journey, it should be noted that, it is worth mentioning, arguably, essentially, first-class, seamless, robust, leverage, comprehensive
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
