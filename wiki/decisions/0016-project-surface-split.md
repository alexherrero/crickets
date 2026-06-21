# ADR 0016 — Project surface split: separate agentm + crickets GitHub Projects

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-06-03

## Context

The operator maintains a roadmap that spans **two sibling repos** — `agentm` (memory/harness engine) and `crickets` (opinionated plugin catalog), carved apart by [ADR 0006 (gemini-cli-host-removal — sibling repo split background)](0006-gemini-cli-host-removal). For ~2 weeks (2026-05-18 → 2026-06-03) work across both repos was tracked in **one shared GitHub Project** at `alexherrero/projects/2` — the agentm-anchored unified Project. That single Project was the "human-readable mirror" of the vault-side `ROADMAP-MASTER.md`, with frozen 6-field schema (Track / Type / Priority / Start / Target / Status) and Track values spanning every line including Crickets v3.0 + Crickets v3.x.

Two pressures surfaced as the project layer matured:

- **The unified Project conflated repo identities.** Every Issue lived in `alexherrero/agentm` (the Project's home repo) — including 14 Crickets v3.x bundle entries for work that would ship from this repo. That worked while crickets was still install-coupled to agentm via `lib/install/` byte-sync, but [ADR 0014](0014-install-decoupling) made the two repos genuinely independent on 2026-06-02. The unified Project surface no longer matched the structural split.
- **The crickets-track buckets were the bigger half going forward.** Bucket ④ Crickets v3.x catalogs 12 opinionated bundles in four waves. Each bundle gets its own plans + tasks once active. The unified Project would shortly carry more crickets-track items than memory-track items, drowning the V4/V5/V6 trajectory and burying the bundle catalog under the memory arc.

The split had been **pre-locked in `ROADMAP-MASTER.md`** at 2026-05-31 (deferred to a trigger), narrowed at 2026-06-01 (single gate: V4 ships fully = #23 closes + paired release lands). On 2026-06-03 the paired pair shipped — agentm `v4.14.0` (decouples from crickets) + crickets `v3.0.0` (native host plugins, this repo's own MAJOR) — satisfying the trigger. This ADR is crickets' record of the resulting split; the agentm-side mirror is [agentm ADR 0008](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0008-project-surface-split.md).

**Open questions the decision resolves:**

- Does crickets get its own Project, or does it stay a guest on agentm's surface?
- How do cross-repo dependencies (e.g. the `github-projects` bundle depending on agentm vault state) render?
- Where does Operator-personal (bucket ⑨ — operator's vault content + Obsidian setup) live, since the Personal-notes bundle (#16) and Ideating bundle (#15) live here while the vault content lives there?
- How does the unified narrative survive a structurally split Project surface?

## Decision

### 1. crickets gets its own user-level GitHub Project

| Project | URL | Owns |
|---|---|---|
| **crickets** (NEW — created 2026-06-03) | https://github.com/users/alexherrero/projects/5 | Crickets v3.0 + Crickets v3.x (the bundle catalog) + Crickets v3.x+ (future evolution) + Backlog + Ideas + anything crickets-specific (including refining the operator's opinionated workflows). The plugin catalog. |
| **agentm** | https://github.com/users/alexherrero/projects/2 | V0 / V1 / V2 / V3 / V4 / V5 / V6 / FRIDAY / V7 + Hardening I + Hardening II + Operator-personal + anything agentm-specific. The memory/harness engine arc. |

**Why a separate Project for crickets, not staying as a guest on agentm's:** post-[ADR 0014](0014-install-decoupling) decoupling, the two repos have independent release cadences. The unified Project required Status flips and Track scheme to satisfy both repos' conventions simultaneously. Two Projects let crickets develop its own bundle-catalog rhythm — Crickets v3.0 closes, v3.x opens, v3.x+ queues — without negotiating with the memory-arc trajectory.

**Why user-level (`alexherrero/projects/5`), not repo-level:** repo-level Projects were attempted earlier and abandoned in favor of user-level for cross-repo issue visibility. User-level retains the ability to include cross-repo cards (see decision #3 below) without forcing one repo's Project to "own" another repo's work. Matches the agentm Project pattern at `alexherrero/projects/2`.

### 2. Bundles + crickets-only work move here; Operator-personal stays in agentm

The transfer that executed:

| What moved (17 issues) | What stayed in agentm |
|---|---|
| Crickets v3.0 Version (#1) + #40 consolidation (#3) + #42 dual-mode (#4) | V0–V7 + FRIDAY + Hardening I/II Versions |
| Crickets v3.x Version (#2) + 13 bundle entries (#5–#17) | V0–V4 historical Roadmap-entries + bugs (54 items) |
|  | Operator-personal Version (#10 in agentm) |
|  | 5 cross-surface drafts (operator inbox) |

**Why Operator-personal stays in agentm, not here:** bucket ⑨ Operator-personal items (`#16` consolidation, `#29` PKM, `#34` vault aesthetic) touch the operator's vault content + Obsidian setup. The vault physically lives alongside agentm's per-project state at `<vault>/projects/agentm/_harness/`. The work *itself* is operator-content-curation, not plugin-development. The plugin-side angle is covered by **this Project**'s bundles #15 *Ideating* and #16 *Personal-notes* — those are implementations of how plugins serve operator-personal use cases. The work-track and the plugin-implementation are different concerns; the work-track stays content-side (agentm Project), the bundle implementations live here.

**Why not cross-list Operator-personal:** GitHub Projects v2 lets any issue appear in multiple Projects, but comment-timeline ownership gets fuzzy. With a single maintainer (operator) the friction is low, but the principle still applies: pick one canonical home so future automation has a deterministic answer. Cross-listing reserves itself for genuine cross-repo dependencies (decision #3).

### 3. Cross-project dependencies ride the issue graph, not the Project layer

GitHub Projects v2 has **no native "Project A depends on Project B milestone" relationship**. Three mechanisms together cover the practical need:

1. **Cross-repo sub-issues.** `addSubIssue` mutation works across repos. An agentm V5 Version Issue can have `crickets#X` bundle sub-issues nested under it; the V5 Version's sub-issue progress field reflects them live. **Verified during the 2026-06-03 transfer** — sub-issue parent-child relationships survived `gh issue transfer` cleanly (Crickets v3.0 Version (now `crickets#1`) retained its 2 children; Crickets v3.x Version (now `crickets#2`) retained its 13 children; no manual re-wiring required).
2. **`Blocked by` references.** `Blocked by alexherrero/agentm#<n>` in a crickets Issue body auto-renders the cross-repo blocker as a linked card with live status.
3. **Cross-Project item-add.** Either Project can include any repo's Issues as visible cards. Reserved for cases where an agentm milestone is genuinely load-bearing for a crickets bundle (or vice versa).

**Why not wait for GitHub to ship native cross-Project dependencies:** the issue graph already covers the substance; the missing feature is just a *rendering* of dependencies in the Project board UI, not the dependency mechanism itself. Sub-issue progress + `Blocked by` references already give us live status without needing GitHub to ship anything new.

### 4. Execution = four collaborative + automated phases

The split executed as:

- **(a) Review together what goes into crickets** — collaborative classification pass. Agent proposed; operator confirmed (with the Operator-personal call landing here). Output: a 17-item transfer inventory.
- **(b) Automated move** — agent ran: created crickets Project (`alexherrero/projects/5`) + mirrored the 6-field schema · created the `roadmap` label in this repo (the agentm side had it; this repo did not) · transferred 17 Issues `alexherrero/agentm` → `alexherrero/crickets` via `gh issue transfer` (preserving history + comments + labels; numbers re-assigned 4–31 → 1–17) · added to crickets Project + restored field values from a pre-transfer snapshot · removed the 17 transferred items from agentm Project · updated `ROADMAP-MASTER.md § Project surface split` with live URLs.
- **(c) Operator creates the views** — same 7-view recipe applied to the new crickets Project (manual web-UI; Projects v2 has no view-creation API). The `Track` filter for view 6 narrows from `track:V4` (agentm) to `track:"Crickets v3.0"` (crickets) since that's the active line.
- **(d) Stub all pending templates** — Issue Templates' `config.yml` in this repo amended to lead with the crickets Project URL (was: leads with the agentm Project as the pre-split host).

**Why not pure mechanics:** step (a) is genuinely collaborative — the Operator-personal classification call cannot be derived from a rubric. Step (c) is irreducibly manual (the API doesn't expose view-creation mutations). A mechanical-only 6-step list would have skipped both touchpoints.

## Consequences

**Positive**

- **crickets Project develops its own release cadence + status flow.** Bundle catalog work no longer waits on agentm's Project conventions or shares Status flips. Crickets v3.0 immediately closes (3 Done), v3.x opens (14 Todo) without intermingling with V4/V5 trajectory.
- **The bundle catalog gets a focused identity.** 14 bundle entries + their future plans + tasks live in a Project board sized to the work. No competing with V0–V7 entries.
- **Cross-repo sub-issues survived the transfer natively.** The `addSubIssue` mutation preserves the parent-child graph when both endpoints transfer together. No manual re-wiring was needed for the 15 sub-issue relationships under Crickets v3.0 + v3.x Versions.
- **The github-projects bundle (Crickets v3.x #13) now has a real two-Project setup to dogfood against.** The meta-loop becomes viable: the bundle that maintains the projects can be developed against the projects it'll maintain. Synthesis-from-the-vault gets concrete targets — both the agentm Project + this Project + their cross-references.
- **Issue numbers re-assigned cleanly in crickets** (1–17 in transfer order). Project board sort order matches issue creation order.
- **`roadmap` label discipline now consistent across both repos.** Pre-split, crickets had no `roadmap` label (issues never lived here). Created during step (b); Issue Templates already auto-apply it on new filings.

**Negative**

- **Two Project boards to navigate.** Operator now bookmarks two sets of filter URLs + maintains two sets of views (same 7-view recipe applied twice). Mitigation: the recipe is well-documented + the surface ownership is sharp (no ambiguity about which Project owns what).
- **Cross-Project filters require URL fan-out.** "Show me everything I'm working on across both Projects" doesn't have a single Projects-v2 query — operator filters each Project separately. Mitigation: live sub-issue progress on parent Version Issues gives a single-page rollup when the dependencies are wired.
- **Historical references use the original V4 numbering** (e.g. "V4 #42" not "crickets#4"). Project items #4–#31 in agentm renumbered to crickets#1–#17 during transfer; references in old commit messages, plan docs, and progress narratives still use the agentm numbering. Mitigation: closeout comments use the original V4 numbering for posterity; going-forward project tracking uses the new crickets numbering.
- **No Project-level dependency rendering between repos.** Cross-repo sub-issues + `Blocked by` carry the relationship in the issue graph, but neither Project board renders "this crickets bundle is gating an agentm V5 Issue" as a board-level filter. Operator must drill into the parent Version Issue to see cross-repo sub-issues.

**Load-bearing assumptions** (re-check on every major-version bump)

- **GitHub Projects v2 continues to support cross-Project item-add + cross-repo sub-issues** as first-class. If either is deprecated or restricted (e.g. moves behind enterprise tier), re-audit whether a single Project + label-based separation is preferable to the two-Project split.
- **`gh issue transfer` continues to preserve history + comments + labels + sub-issue parent-child relationships.** Verified during this ADR's execution. If GitHub changes the transfer semantics (e.g. drops sub-issue preservation), future transfers will need manual re-wiring scripts.
- **The vault-side `ROADMAP-MASTER.md` continues to play the unified-narrative role.** If the master roadmap ever migrates out of the vault (e.g. into one of the repos' wikis), the cross-Project unification mechanism needs to follow it. Today the vault is the asymmetric anchor.
- **crickets stays a plugin catalog with independent release cadence post-#40.** If crickets ever re-couples to agentm at install time (reverses [ADR 0014](0014-install-decoupling)), the unified-Project value reasserts.

**Re-audit triggers** (specific events that should fire a fresh look at this ADR)

- GitHub ships native Project-to-Project dependency relationships → re-audit the issue-graph approach.
- crickets ever re-couples to agentm at install time (reverses [ADR 0014](0014-install-decoupling)) → re-audit unified-Project value.
- Cross-repo sub-issue rendering proves cumbersome in practice (e.g. >5 cross-repo dependencies in a single Version Issue feels noisy) → re-audit whether a different bridge mechanism (cross-Project linked views? canonical aggregation issue?) is warranted.
- The **github-projects bundle (Crickets v3.x #13)** ships and starts auto-synthesizing Project entries from the vault → re-audit whether the manual operator-side classification step (step (a)) becomes redundant or can be automated.
- Operator picks up a fourth project surface (e.g. a `sherwood`-side or external-repo Project) → re-audit whether the two-Project pattern generalizes to N-Projects or needs a meta-layer.

## Related

- [agentm ADR 0008 — Project surface split (sibling)](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0008-project-surface-split.md) — the agentm-side mirror of this ADR.
- [ADR 0014 — install-decoupling (#40)](0014-install-decoupling) — the install-coupling retirement that made the Project split structurally clean (and shipped with crickets v3.0.0 as part of the same paired-pair trigger).
- [ADR 0013 — bundles = native host plugins](crickets-v3-native-plugins) — the native-plugins architecture that gave the bundle catalog its own surface to populate.
- [ADR 0015 — #36 partial revision](crickets-v3-native-plugins) — the bundle-skill move (design / diataxis-author / ship-release agentm→crickets) that populates the bundle catalog this Project tracks.
- `ROADMAP-MASTER.md § Project surface split` (in the operator's vault) — the locked operator-stated framing this ADR records.
