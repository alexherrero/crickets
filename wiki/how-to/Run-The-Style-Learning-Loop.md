<!-- Status: implemented — style-learning-loop (wiki-maintenance part 3/5). Core loop (capture → gates → scope → write → read-back, steps 1–6) wired by the part-3 capture diff. Steps 7 (the one-time _always-load → _global relocation migration) and 8 (voice-drift check via convention-drift) remain pending — they ship in part 5. -->

# How to run the style-learning loop

> [!NOTE]
> **Status:** implemented for the core loop (steps 1–6). The edit-driven capture path is end-to-end usable: `/diataxis author` composes drafts from `template ⊕ base style-guide ⊕ overlay`, and `/diataxis capture` diffs your edits into voice lessons that the next draft reads back. **Steps 7–8 remain pending:** the one-time `_always-load → _global` relocation migration and the live voice-drift check (`convention-drift`) both ship in `wiki-maintenance` part 5.
> **Goal:** Teach the `wiki-author` skill your house voice by editing a drafted page and letting it capture a generalizable voice lesson into the right convention store.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); a wiki under `wiki/`; `git`. Optional: a configured durable-memory vault — without one, lessons fall back to per-repo conventions.

## Steps

1. Ask `wiki-author` to draft or rewrite a page (`/diataxis author`). It composes the output from `template ⊕ base style-guide ⊕ overlay` — structure from the template, voice from the committed base style-guide plus any learned overlay lessons. The resolver reads overlay lessons on-demand from the global, per-project, and per-repo scopes (narrower scope wins) and falls back to the base floor alone when no overlay is present. The composed voice arrives as an author-facing comment block after the page H1; delete it before publishing.

2. Edit the drafted page yourself — tighten word choice, fix rhythm, cut slop or jargon, restructure. Save both versions (the draft and your edited copy) so the next step can diff them.

3. Run `/diataxis capture <draft> <edited>`. The skill calls `capture.py propose`, which diffs draft↔edited and clusters the changes by kind (word choice · rhythm · structure · cuts = slop/jargon removed · additions), emitting one draft lesson proposal `{trigger, guidance, before→after}` per non-empty bucket as JSON. This step writes nothing.

4. For each proposal, confirm the **generality** (gate 1). Read the `before→after` and rewrite the scaffold guidance into the real lesson — _"in any how-to, cut hedging adverbs"_ — with a semantic trigger. Reject one-offs; a lesson true only for this one page is not worth storing. Nothing is captured without your confirmation.

5. Confirm the **scope** (gate 2). `/diataxis capture` dispatches the read-only `style-scope-evaluator` sub-agent with your confirmed lesson and the existing overlay stores. It recommends exactly one scope — `global`, `per-project`, or `per-repo` — and you confirm or override. The evaluator only recommends (tool allowlist `Read, Glob, Grep`; no writes); when torn it recommends the narrower, reversible scope.

6. The skill calls `capture.py save`, writing the confirmed lesson to that scope's on-demand store (never `_always-load`): global `projects/_global/wiki-style/` · per-project `projects/<slug>/wiki-style/` · per-repo `wiki/.diataxis-conventions.md`. The write goes through an operator-confirm gate that denies non-TTY/batch writes by default — nothing auto-commits. Per-repo writes land outside the MemoryVault; without the agentm `permeable_boundary` kernel (crickets-local) the write degrades to the local confirm and announces the degraded mode on stderr — never silent. The next `/diataxis author` draft reads the lesson back automatically (step 1's resolver).

7. _(Pending — ships in `wiki-maintenance` part 5.)_ (One-time) Relocate the global Diátaxis conventions out of `_always-load` into the on-demand `_global` store. The operator-run migration is **preview-first and reversible** (`--rollback`), so review the preview before applying. The capture write-path already targets the `_global` store, but the one-shot relocation tool is not yet wired. _Filled by human._

8. _(Pending — ships in `wiki-maintenance` part 5.)_ Check for voice drift. `/diataxis check` (or `check-wiki.py`) will flag voice-drift findings against the style overlay, not just structural violations — findings, not hard failures, unless you pass `--strict`. Today the `convention-drift` rule is a v1 stub (always returns no finding); the live AgentMemory-backed comparison lands in part 5. _Filled by human._

## Related

- **Related reference:** [Customization types](Customization-Types) — documents the `wiki-maintenance` plugin and its primitives.
- [Compatibility](Compatibility) — supported hosts + per-manifest `supported_hosts` contract.
- [Wiki-Maintenance design](../explanation/designs/wiki-maintenance.md) — why the voice layer and the operator-in-the-loop learning loop exist.
- [Add a skill](Add-A-Skill) — how skills are packaged and shipped in crickets.
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
