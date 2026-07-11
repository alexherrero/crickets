---
name: coalescence-gate
description: Every arc ends with a required close-out checklist that fires when a release closes an arc — narrative rows, roadmap ids in the release body, boards reconciled, the prose gate green, archive moves done, the dark registry reconciled, and an orphan check. A session discipline `/release` enforces, not a new command or CI workflow.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: coalescence-gate

Migrated in (Consolidation arc, CONS-8) from the Consolidation-arc verdict's ruling 8 ("the process fix"). The verdict's own diagnosis: pack-mode work built real things across an arc and lost the thread on them — release notes that don't say what shipped, boards nobody reconciled, a prose gate that ran but never blocked, a growing pile of files nobody archived. The failure wasn't any one surface; it was that **the skip was silent** — nothing forced a session to look at all seven surfaces together before calling an arc done. This rule closes that gap by making the checklist mandatory and explicit, homed where `/release` already gates.

**This is a session discipline, not new machinery.** No new command, no new CI workflow — a coalescence check spans boards, the vault, release bodies, and the wiki, surfaces a repo-local CI job can't see end to end. The discipline lives in the `/release` phase spec (`development-lifecycle`'s `release.md`, constraint 9): when a release closes an arc, work this checklist before tagging.

### The seven items

1. **Narrative rows appended.** The completed-features timeline (a repo's `Completed-Features.md`-equivalent reference page) gains one row per feature this arc shipped — plain English, one sentence, release tag, roadmap id. `ship-release`'s own "append the feature row(s)" step is the maintainer; confirm it ran for everything the arc shipped, not just the release being cut right now.
2. **Release cut with roadmap ids in the body.** The release notes name every roadmap item the release ships (`(#123)`-style or the project's own id shape) — not just a commit list. See the [`release-cadence`](release-cadence.md) rule.
3. **Boards reconciled + a plain-English pass.** `gh project list` for every board this arc touched matches the expected canonical count (drift is a signal something wasn't closed); a plain-English pass confirms Feature/Version titles and `Track` glosses read clearly to a stranger, not just to the session that wrote them.
4. **Prose gate green.** `check-slop.py --strict` (or the project's equivalent anti-slop gate) exits clean on the full tree. Once the gate is wired to block at warning-tier-and-above in `check-all.sh` + CI (the Consolidation arc's ruling 2), this item is **automatic** — it's a check, not new work, at coalescence time.
5. **Archive moves done, eyeline clean.** Every close-out's archive step actually ran — no flat, un-archived close-out artifacts sitting loose in a project's working directory. See the archive-step path change (`archive/`, not a flat path) in the [`agentic-engineering`](../skills/agentic-engineering/SKILL.md) skill's "The `.harness/PLAN.md` shape" section.
6. **Dark-registry reconciled, D4-style.** Walk every entry in the project's dark registry (see the [`dark-registry`](dark-registry.md) rule); for each, either its owning plan shipped (flip the entry to built/live) or it's still genuinely future work (leave it, with the owning plan reaffirmed) — nothing sits dark with a stale or absent owner.
7. **Orphan check — no new zero-caller scripts.** Re-run the project's own orphan/dead-code census (whatever produced the arc's original zero-caller inventory). A script with no caller that entered the tree during the arc and wasn't dark-registered is a regression of the exact sprawl this discipline exists to stop.

### What is NOT an acceptable shortcut

| Stated shortcut | Why it is not acceptable |
|---|---|
| "This release is small, I'll skip the checklist" | The checklist only fires when a release **closes an arc** — a routine mid-arc release is unaffected. If this release does close an arc, size is not an exemption; the whole point is that a small-looking release can still leave every surface unreconciled. |
| "I'll do the board/vault reconciliation in a follow-up session" | An arc that "closes" with open reconciliation work is the pack-mode failure mode this rule exists to end. Do the seven items before tagging, or the release doesn't close the arc yet. |
| "The prose gate is report-only here, so I can't block on it" | Item 4 depends on the gate actually being blocking (ruling 2). A repo that hasn't flipped the gate yet runs item 4 as a manual read (does `check-slop` report anything new since the last sweep?) rather than skipping it outright. |

### Enforcement

Before tagging a release that closes an arc, confirm all seven:

1. Narrative rows appended for every feature the arc shipped.
2. Release body names the roadmap ids it ships.
3. `gh project list` matches the expected board count; titles/`Track` glosses read plainly.
4. The prose gate exits clean on the full tree.
5. Every close-out's archive step ran; the working directory eyeline is clean (no stray flat archive artifacts).
6. Every dark-registry entry's owning plan either shipped (flip it) or is reaffirmed as still-future (leave it, owner intact).
7. The orphan/dead-code census shows no new zero-caller script introduced this arc without a dark-registry entry.

If all seven are true, the release closes the arc. If any is false, that item is the blocker — fix it, then re-check, before tagging.

## See also

- [`release-cadence`](release-cadence.md) — the release-body roadmap-id + commit-vocabulary standard item 2 depends on.
- [`dark-registry`](dark-registry.md) — the registry item 6 walks.
- [`coordinator-dispatch`](coordinator-dispatch.md) — the multi-session-job convention that authored this arc in the first place; the arc's own close-out is the first execution of this checklist against itself.
- [`agentic-engineering`](../skills/agentic-engineering/SKILL.md) — the `.harness/PLAN.md` shape + archive-path convention item 5 checks.
- `development-lifecycle`'s `/release` command (`release.md`, constraint 9) — where this checklist is invoked from.
