<!-- Status: implemented — style-learning-loop. Core loop (capture → gates → scope → write → read-back, steps 1–6) wired by the part-3 capture diff. Step 7 (the one-time _always-load → _global relocation migration) shipped in part 4 — the `/diataxis relocate` mechanism (preview-first/reversible) is wired; it's operator-run and today a no-op (no diataxis-*.md exist in _always-load yet). Step 8 (voice-drift check via convention-drift) shipped in part 3 task 5: `convention-drift` is live, scanning each page for the banned terms declared on `banned:` directives in the resolved style overlay; findings are info (non-failing) by default, error under --strict. The loop is now wired end-to-end. -->

# How to run the style-learning loop

> [!NOTE]
> **Status:** implemented end-to-end (steps 1–8). The edit-driven capture path is usable: `/diataxis author` composes drafts from `template ⊕ base style-guide ⊕ overlay`, and `/diataxis capture` diffs your edits into voice lessons that the next draft reads back. The one-time `_always-load → _global` relocation has a wired, preview-first/reversible tool (`/diataxis relocate`) — operator-run, and today typically a no-op (no `diataxis-*.md` exist in `_always-load` yet). Step 8, the voice-drift check (`convention-drift`), is now live: `/diataxis check` flags every banned term a page uses against the resolved style overlay — findings (info) by default, escalating to failures under `--strict`.
> **Goal:** Teach the `wiki-author` skill your house voice by editing a drafted page and letting it capture a generalizable voice lesson into the right convention store.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); a wiki under `wiki/`; `git`. Optional: a configured durable-memory vault — without one, lessons fall back to per-repo conventions.

## Steps

1. Ask `wiki-author` to draft or rewrite a page (`/diataxis author`). It composes the output from `template ⊕ base style-guide ⊕ overlay` — structure from the template, voice from the committed base style-guide plus any learned overlay lessons. The resolver reads overlay lessons on-demand from the global, per-project, and per-repo scopes (narrower scope wins) and falls back to the base floor alone when no overlay is present. The composed voice arrives as an author-facing comment block after the page H1; delete it before publishing.

2. Edit the drafted page yourself — tighten word choice, fix rhythm, cut slop or jargon, restructure. Save both versions (the draft and your edited copy) so the next step can diff them.

3. Run `/diataxis capture <draft> <edited>`. The skill calls `capture.py propose`, which diffs draft↔edited and clusters the changes by kind (word choice · rhythm · structure · cuts = slop/jargon removed · additions), emitting one draft lesson proposal `{trigger, guidance, before→after}` per non-empty bucket as JSON. This step writes nothing.

4. For each proposal, confirm the **generality** (gate 1). Read the `before→after` and rewrite the scaffold guidance into the real lesson — _"in any how-to, cut hedging adverbs"_ — with a semantic trigger. Reject one-offs; a lesson true only for this one page is not worth storing. Nothing is captured without your confirmation.

5. Confirm the **scope** (gate 2). `/diataxis capture` dispatches the read-only `style-scope-evaluator` sub-agent with your confirmed lesson and the existing overlay stores. It recommends exactly one scope — `global`, `per-project`, or `per-repo` — and you confirm or override. The evaluator only recommends (tool allowlist `Read, Glob, Grep`; no writes); when torn it recommends the narrower, reversible scope.

6. The skill calls `capture.py save`, writing the confirmed lesson to that scope's on-demand store (never `_always-load`): global `projects/_global/wiki-style/` · per-project `projects/<slug>/wiki-style/` · per-repo `wiki/.diataxis-conventions.md`. The write goes through an operator-confirm gate that denies non-TTY/batch writes by default — nothing auto-commits. Per-repo writes land outside the MemoryVault; without the agentm `permeable_boundary` kernel (crickets-local) the write degrades to the local confirm and announces the degraded mode on stderr — never silent. The next `/diataxis author` draft reads the lesson back automatically (step 1's resolver).

7. _(One-time, operator-run.)_ Relocate any global Diátaxis conventions out of `_always-load` into the on-demand `projects/_global/wiki-style/` store. Run `/diataxis relocate --preview` first — it prints the `WOULD:` lines and mutates nothing; review them, then run `/diataxis relocate` to copy (it leaves the source in place and records a rollback manifest at `<dest>/.relocated-from-always-load`), `/diataxis relocate --cleanup --yes` to delete the source after a byte-identical verify, or `/diataxis relocate --rollback` to reverse the move via the manifest. The migration is conflict-safe and idempotent. Today this is typically a **no-op**: no `diataxis-*.md` exist in `_always-load` yet, because the capture loop (steps 3–6) writes lessons straight to `_global/`. The tool ships the mechanism for when they do; widening `--source-glob` to relocate an existing entry (e.g. `docs-prose-style`) is an operator call you make after reviewing the preview.

8. Check for voice drift. Run `/diataxis check` — alongside the structural rules it now runs `convention-drift`, which resolves the style overlay (base style-guide ⊕ on-demand voice lessons, via step 1's resolver), collects every banned term declared on a `banned:` directive in those sources, and scans each wiki page. Each banned term a page uses emits one finding (`voice drift: page uses banned term …`) with a suggested fix. Findings are `info` severity — surfaced but non-failing — by default; pass `--strict` to escalate them to `error` so they fail the check like structural violations. To extend the banned list, add a `banned:` line to the committed base style-guide or to an overlay lesson; the next `/diataxis check` picks it up. (`banned:` lines inside ``` fences are ignored, and the author-facing house-style scaffolding block is stripped before scanning, so banned words quoted in those places are not flagged.)

## Related

- **Related reference:** [Customization types](Customization-Types) — documents the `wiki-maintenance` plugin and its primitives.
- [Compatibility](Compatibility) — supported hosts + per-manifest `supported_hosts` contract.
- [Wiki-Maintenance design](../explanation/designs/wiki-maintenance.md) — why the voice layer and the operator-in-the-loop learning loop exist.
- [Add a skill](Add-A-Skill) — how skills are packaged and shipped in crickets.
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
