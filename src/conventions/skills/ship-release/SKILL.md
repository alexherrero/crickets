---
name: ship-release
description: Release discipline and mechanics in one skill — pre-release checklist (CI green on every OS, version bump committed, CHANGELOG authored, dist/ committed, paired-release order locked for cross-repo releases), then the mechanical cut (conventional-commit semver auto-sizing, CHANGELOG prepend, tag, push, `gh release create`).
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.2.2
install_scope: project
---

You are running the `ship-release` skill. Work through the pre-release checklist below before cutting anything, then run the mechanical workflow to tag and publish. Trigger phrases: "ship a release", "cut a release", "tag a release", or reviewing a diff that claims to be "release-ready."

## When to invoke

- Before tagging a release commit.
- Before publishing an updated plugin to any marketplace.
- When reviewing a diff that claims to be "release-ready."

## Pre-release checklist

Work through every item. If any is incomplete, fix it before proceeding — do not tag a release to force a fix.

1. **CI green across the full OS matrix.** Every job (Linux, macOS, Windows) must be green on the release commit. A red job on any OS is a hard block — not a known issue to ship around.
2. **Version bumped.** The affected group's `group.yaml` `version` field must be incremented from the base branch. Semver rules (see **Version bump policy** below). Never tag a release whose `group.yaml` version matches the prior tag.
3. **CHANGELOG authored.** A CHANGELOG entry exists for this release under the correct version heading. It follows the project's changelog shape (see **Changelog shape** below).
4. **`dist/` regenerated and committed.** For repos where `dist/` is generated from `src/` (e.g. crickets), `generate.py build` must have been run and the result committed. The drift gate (`generate drift` in `check-all.sh`) enforces this — run it before tagging.
5. **`features.json` current.** Every feature this release ships must have `passes: true`. Features still under development must not appear in the release notes.
6. **No orphan PRs.** No open PRs that should be part of this release are left unmerged. A release should represent a complete, coherent unit of work.
7. **`check-all.sh` green.** Run the full gate battery (`bash scripts/check-all.sh`) on the release commit and confirm every gate passes before tagging.
8. **Cadence and commit-subject vocabulary** (see the [`release-cadence`](../../rules/release-cadence.md) rule). A finished plan that changes behavior gets its own release — don't bundle it into a later one. Every commit subject in the range reads plainly to a stranger, keeps its conventional prefix, names a roadmap id where one applies, and carries no internal codename.

## Changelog shape

Follow the "CHANGELOG + ADR shapes" convention in the project's `CLAUDE.md`. The key requirements:

- Lead with a framing paragraph explaining what this release is about (not just a list of commits).
- Sections: **Added** (new user-visible capabilities), **Changed** (modifications to existing behavior), **Internal** (infrastructure, refactors, CI) — omit empty sections.
- For paired releases across sibling repos, URL-link the sibling's release page in the entry. Never describe a paired release without the cross-link.

Do not define the exact format here — `CLAUDE.md` is the authoritative source. If the project's CLAUDE.md does not have the "CHANGELOG + ADR shapes" section, surface that as a gap before proceeding.

## Paired-release discipline

When two or more repos release together (e.g. `crickets` + `agentm`):

1. **Lock the order explicitly** in the plan before any tagging begins. State which repo ships first and which URL-links the other. The second repo ships after the first release URL exists.
2. **CI green on both release commits** before closing the plan. Never close a paired release with one side green and the other red.
3. **Don't leave one side tagged overnight.** A tagged release on one side with the other side still open creates a window where the cross-linked URL is missing. Complete both sides in the same session.
4. **Document the order in the plan's locked design calls** so a future session resuming the work knows which side to land first.

## Version bump policy

- **Patch** — bug fixes only; no new primitives, no changed behavior.
- **Minor** — new primitives (skills, rules, commands, agents), new commands, new user-visible capabilities.
- **Major** — breaking changes: removed primitives, changed frontmatter schema, incompatible behavioral changes.
- **Bump only the affected group's `group.yaml`.** A change to `developer-workflows` does not bump `code-review`. Each group versions independently.
- **Never bump on a worker branch.** In the concurrent-worker (Model-A) protocol, `group.yaml` version bumps are integrator-only — performed once by `/integrate-worker` after all workers for a release batch have merged. A solo PR (no concurrent workers) bumps the group.yaml in the same PR.
- **Never skip a version.** If the last release was `0.3.1` and you're shipping a minor, the next version is `0.4.0`, not `0.5.0` or `1.0.0`.

## Mechanical workflow

Once the pre-release checklist above is satisfied, cut the release.

### Preconditions (check first, abort if not met)

1. `gh auth status` — authenticated.
2. Current branch is the default branch (`gh repo view --json defaultBranchRef -q .defaultBranchRef.name`).
3. Working tree clean: `git status --porcelain` empty.
4. Local is pushed: `git fetch && [ -z "$(git log origin/HEAD..HEAD --oneline)" ]`.
5. At least one commit since the last tag. If `git describe --tags HEAD` equals the last tag exactly, abort with "nothing to ship".

### Input handling

The user may pass:
- **No argument** → auto-size from commits.
- **`patch` / `minor` / `major`** → force that size.
- **`vX.Y.Z`** → use verbatim, skip auto-sizing.
- **`--dry-run`** → compute + print, don't tag.
- **`--draft`** → create as draft release.

### 1. Classify commits in the range

```bash
PREV=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
RANGE="${PREV:+${PREV}..}HEAD"
git log "$RANGE" --pretty=format:'%s%n%b%n---COMMIT---'
```

Classification rules:
- `feat!:`, `fix!:`, any `!:` subject, or body contains `BREAKING CHANGE:` → **major**
- `feat:` or `feat(scope):` → **minor**
- `fix:`, `perf:`, `refactor:` → **patch**
- `docs:`, `chore:`, `test:`, `ci:`, `build:` → **no-bump**
- Anything else → **patch**

Take the max across all commits. Respect the user's size hint if it's *larger*; warn + confirm if it's *smaller*.

### 2. Compute next version

Parse `PREV` as `vMAJOR.MINOR.PATCH`. Bump per the resolved size. If no prior tag, propose `v0.1.0`. This should already match the `group.yaml` bump from checklist item 2 — if it doesn't, flag the mismatch before proceeding rather than silently retagging a different version than what shipped.

### 3. Draft release notes

Group commits by section (Added / Changed / Fixed / Breaking / Internal), newest first, following the **Changelog shape** above. Show the draft to the user for edit before tagging. Sections with no commits are omitted.

### 4. Update CHANGELOG.md

Prepend a new section to `CHANGELOG.md` at repo root (create if missing, with a Keep-a-Changelog-style header). Show the diff and confirm. Do not commit yet — the latest-release note (next step) lands in the same commit.

### 5. Update the latest-release note (if the repo has one)

Many repos carry a one-line **latest-release note** — a blockquote callout in `README.md` and the wiki `Home.md` of the form `**Latest release: [vX.Y.Z](…/releases/tag/vX.Y.Z).** <one plain-language sentence on what shipped>`. It is a documented, release-driven element (see the project's `documentation` convention, "Home.md and the repo README"): the README mirrors Home, so update **both** in the same pass. Rewrite the version number, the release-tag link, and the summary sentence so it describes *this* release in plain, user-facing terms — a benefit or headline change, not a changelog dump. Then commit `CHANGELOG.md` + both notes together with message `chore(release): vX.Y.Z`; show the diff before committing.

If the repo has no such note, skip this step. Leave the wiki Architecture "Recent changes" block alone — that is a separate, as-needed architectural narrative, not a per-release element.

### 6. Tag + push + release

```bash
git tag -a "vX.Y.Z" -m "Release vX.Y.Z — <title>"
git push origin HEAD
git push origin "vX.Y.Z"
gh release create "vX.Y.Z" \
  --title "vX.Y.Z — <title>" \
  --notes-file .release-notes.md \
  --verify-tag
```

If any step fails, delete the local tag (`git tag -d vX.Y.Z`) before exiting.

### 7. Print the release URL

`gh release view vX.Y.Z --json url -q .url`.

### 8. Confirm + link

Print the release URL. If the project's wiki has a `how-to/Cut-A-Release.md` or `operational/Runbook.md`, remind the user to note anything about the release that a future operator would need to know (rollback steps, migrations).

## Guardrails

- Never push to a non-default branch.
- Never overwrite or move existing tags.
- Never include uncommitted changes.
- Never amend the release commit after tagging.

## Output contract

On success:

```
ship-release: cut vX.Y.Z
  commits:   N (maj/min/patch classification)
  notes:     CHANGELOG.md + latest-release note (README + Home) updated + pushed
  release:   https://github.com/<owner>/<repo>/releases/tag/vX.Y.Z
```

On abort, one line: what failed and what the user should do next.

## Failure modes

- **Unpushed commits on default branch** → abort. The release tag must point at a commit that's on the remote, otherwise the GitHub release references a SHA collaborators don't have.
- **Dirty working tree** → abort. Don't force-stash.
- **Existing tag collision** → abort. Never overwrite.
- **Push fails** (protected branch, auth) → leave the local tag in place; print the `gh release create` invocation the user can run by hand after they push.
- **User rejects the draft notes** → save the draft to `.release-notes.md` and exit; user edits and re-runs the skill.

## Migration history

Two same-named skills existed side by side: the discipline checklist, authored directly in crickets `releasing-conventions` (v0.1.0), and the mechanical executor, originally shipped in `agentm v0.8.0` as a harness-bundled skill and migrated to crickets in toolkit v0.1.0 (paired with `agentm v2.0.0`) because the mechanics are broadly useful outside harness-installed projects. The migrated copy kept living in `agentm harness/skills/ship-release/` as well, so the two repos drifted into duplicate skills of the same name, with this file pointing at "the standalone skill" for mechanics it didn't itself contain. **Consolidated 2026-07-01 (v0.2.0):** the mechanical sections above are folded in; agentm's local copy is removed, and agentm now treats `ship-release` as a crickets-provided graceful-skip skill (its `R-changelog` detection rule still recommends installing it, exactly as `R-dependabot` recommends `dependabot-fixer`). The `/release` phase (crickets `developer-workflows`) suggests this skill as the post-merge follow-up, with a graceful-skip line if `crickets` isn't installed.

**Refined 2026-07-01 (v0.2.1):** added the "Update the latest-release note" step (README + wiki `Home.md`). The merged mechanical workflow tagged the release without touching the documented, release-driven latest-release note, so every cut left it one version behind — a step the old manual habit carried but the skill never encoded. The Architecture "Recent changes" block is deliberately out of scope: it is a separate, as-needed architectural narrative, not a per-release element.

**Refined 2026-07-11 (v0.2.2, Consolidation arc CONS-8):** added checklist item 8, pointing at the new `release-cadence` rule — the Consolidation-arc evidence found eleven distinct features once shipped under one release tagged "Minor," and internal codenames leaking into commit subjects. The rule states the standard; this skill's checklist is where a session actually checks it before tagging.
