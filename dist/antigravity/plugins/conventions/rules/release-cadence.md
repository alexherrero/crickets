---
name: release-cadence
description: A finished plan that changes behavior cuts a release — no more bundling several features into one changelog entry. Commit-subject vocabulary standard — a stranger-readable subject, conventional prefix kept, roadmap id where one applies, internal codenames banned from subjects.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: release-cadence

Migrated in (Consolidation arc, CONS-8) from the Consolidation-arc verdict's ruling 4. The verdict's own evidence: eleven distinct features once shipped inside one release tagged "Minor," and internal codenames (`AA5`, `C5`, `FIN-3`, wave letters) leaked into commit subjects, PR titles, and release notes — readable to the session that wrote them, opaque to anyone else, including the operator returning to the history a week later. This rule codifies the fix as two standing conventions: cadence and vocabulary.

### Cadence — a finished plan that changes behavior cuts a release

When a plan completes and its changes are user-visible (new primitives, changed behavior, a fixed defect a user would notice) — cut a release for it. Do not bundle it with the next plan's changes into a single later release "to save a release cycle." Bundling is what produced the "eleven features under one Minor" evidence this rule exists to prevent: a release whose notes can't actually tell a reader what changed, because too much changed at once.

A plan that ships **no** user-visible change (a pure refactor with no behavioral difference, an internal test-only addition) does not need its own release — `ship-release`'s own version-bump-policy already distinguishes patch/minor/major; this rule is about *frequency*, not size. The test is not "is this big enough to deserve a release" — it's "did a plan just finish, and does what it shipped change behavior a user or operator would notice." If yes, release it now.

### Vocabulary — commit-subject standard

Every commit subject follows this shape:

1. **A stranger can read it.** The subject describes what changed in plain terms — someone with zero context on the plan, the arc, or the internal shorthand should understand roughly what happened from the subject line alone.
2. **The conventional prefix stays.** `feat:` / `fix:` / `perf:` / `refactor:` / `docs:` / `chore:` / `test:` / `ci:` / `build:` (and the `!:` / `BREAKING CHANGE:` markers) are kept — `ship-release`'s own commit classification (see its "Classify commits in the range" step) sizes the next version from these prefixes, so dropping them breaks version auto-sizing, not just readability.
3. **The roadmap id lands in parentheses where one applies.** `fix(github-projects): plan_goal missing on a progress entry no longer KeyErrors the aggregate render (#180)` — the id is discoverable without needing the internal plan name to look it up.
4. **Internal codenames are banned from subjects.** Wave letters, session/plan shorthand (`AA5`, `C5`, `FIN-3`, `CONS-8`, `R08`, `G12`, and the like) do not appear in a commit **subject**. They are legitimate in pack files, `progress.md`, and the plan's own body — anywhere a session tracking the plan reads it — but a commit subject is a permanent, public-facing record, and a codename there is exactly the "readable to the session that wrote it, opaque to everyone else" failure this rule exists to end.

A mechanical commit-message hook (developer-safety plugin) enforces the codename-ban + slop-vocabulary half of this at commit time; this rule states the standard the hook enforces, not the hook's own mechanics (see the `developer-safety` plugin's commit-msg hook for that).

### What is NOT an acceptable bypass

| Stated bypass | Why it is not acceptable |
|---|---|
| "I'll just bundle this with the next plan, it's a small change" | Small-change bundling is exactly how eleven features ended up under one "Minor" tag. If the plan finished and changed behavior, release it now. |
| "The codename is shorter and everyone on this arc knows what it means" | The commit history outlives the arc. A subject readable only to someone who was in this specific arc's sessions is not readable — write the plain-English version; put the codename in `progress.md` if you want the cross-reference. |
| "I dropped the conventional prefix since the subject already explains it" | `ship-release`'s auto-sizing parses the prefix mechanically — a subject without one either falls through to a default classification or breaks sizing outright. Keep the prefix. |

### Enforcement

Before committing or before cutting a release, check:

1. Did the last finished plan that changed behavior get its own release, or is it waiting to be bundled with something else?
2. Does every commit subject in this release's range read plainly to someone with no arc context?
3. Does every subject keep its conventional prefix, and does every subject touching a tracked roadmap item name that item's id?
4. Does any subject contain an internal codename (wave letter, session/plan shorthand)? If yes, that is the one thing to fix before the commit lands.

If all four are satisfied, cadence and vocabulary are compliant.

## See also

- [`coalescence-gate`](coalescence-gate.md) — item 2 of the arc-exit checklist (roadmap ids in the release body) depends on this rule's cadence half.
- `ship-release` skill — the mechanical release cutter; its "Classify commits in the range" step is what parses the conventional prefixes this rule requires.
- `developer-safety`'s commit-msg hook — the mechanical enforcement of the vocabulary half (codename + slop-vocabulary rejection in subjects).
