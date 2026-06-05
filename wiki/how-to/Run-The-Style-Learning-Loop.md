<!-- Status: pending — style-learning-loop (wiki-maintenance part 3/5). Flip to implemented at /work once the diff proves each step. -->

# How to run the style-learning loop

> [!NOTE]
> **Status:** pending — ships with `wiki-maintenance` part 3 (style layer + learning loop). Steps are scaffolded from the design; the `/work` phase fills them from the diff.
> **Goal:** Teach the `wiki-author` skill your house voice by editing a drafted page and letting it capture a generalizable voice lesson into the right convention store.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); a wiki under `wiki/`; `git`. Optional: a configured durable-memory vault — without one, lessons fall back to per-repo conventions.

## Steps

1. Ask `wiki-author` to draft or rewrite a page. It composes the output from `template ⊕ base style-guide ⊕ overlay` — structure from the template, voice from the base style-guide plus any learned overlay lessons. _Filled by human._

2. Edit the drafted page yourself — tighten word choice, fix rhythm, cut slop or jargon, restructure. Save your edits. _Filled by human._

3. Ask the skill to study the delta. It diffs draft vs. edited and clusters the changes by kind (word choice · rhythm · structure · cuts · additions). _Filled by human._

4. For each cluster, confirm the **generality** when prompted. The skill proposes a voice lesson as _"in any X, prefer Y"_ — reply whether that reading is right, narrower, or broader. Nothing is captured without your confirmation. _Filled by human._

5. Confirm the **scope** the `style-scope-evaluator` recommends — `global`, `per-project`, or `per-repo`. The evaluator only recommends (it is read-only); you confirm the final placement. _Filled by human._

6. The confirmed lesson is written to that scope's on-demand store (not `_always-load`): global `_global` slug · per-project `projects/<slug>/wiki-style/` · per-repo `wiki/.diataxis-conventions.md`. The next draft reads it back automatically. _Filled by human._

7. (One-time) Relocate the global Diátaxis conventions out of `_always-load` into the on-demand `_global` store. Run the operator-run migration — it is **preview-first and reversible** (`--rollback`), so review the preview before applying. _Filled by human._

8. Check for voice drift. `/diataxis check` (or `check-wiki.py`) now flags voice-drift findings against the style overlay, not just structural violations. These are findings, not hard failures, unless you pass `--strict`. _Filled by human._

## Related

- **Related reference:** [Customization types](Customization-Types) — documents the `wiki-maintenance` plugin and its primitives.
- [Compatibility](Compatibility) — supported hosts + per-manifest `supported_hosts` contract.
- [Wiki-Maintenance design](../explanation/designs/wiki-maintenance.md) — why the voice layer and the operator-in-the-loop learning loop exist.
- [Add a skill](Add-A-Skill) — how skills are packaged and shipped in crickets.
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
