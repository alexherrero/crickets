---
name: ship-release
description: Pre-release checklist and release discipline — CI green on every OS, version bump committed, CHANGELOG authored, dist/ committed, paired-release order locked for cross-repo releases.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

You are running the `ship-release` skill. Apply these conventions every time you prepare, tag, or publish a release.

> For the **mechanical release workflow** (conventional-commit classification, semver auto-sizing, CHANGELOG prepend, `git tag`, `gh release create`), see the standalone `ship-release` skill. This skill owns the **discipline**: the pre-release checklist, changelog shape, paired-release order, and version bump policy that must be satisfied before any release action fires.

## When to invoke

- Before running `/release` or the `ship-release` standalone skill.
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
7. **`check-all.sh` green.** Run the full gate battery (`bash scripts/check-all.sh`) on the release commit and confirm 10/10 PASS before tagging.

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
