# ADR 0006: Gemini-CLI host removal

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-17
> **Related:** [ADR 0001 — agent-toolkit purpose](0001-agent-toolkit-purpose) (amended 2026-05-17) · [ADR 0002 — evaluator design](0002-evaluator-design) (amended 2026-05-17) · [ADR 0004 — design skill](0004-design-skill) (amended 2026-05-17 for the external-review-handoff option; this ADR is the parallel host-scope amendment) · [ROADMAP item #15](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md) · [Plan #15](https://github.com/alexherrero/agentic-harness/blob/main/.harness/PLAN.archive.20260517-gemini-cli-removal.md) (post-completion)

## Context

The agent-toolkit shipped from v0.1.0 with three supported hosts: Claude Code, Antigravity, Gemini CLI. The host scope was chosen on the principle that the toolkit ships *user-portable* customizations to any agent surface the user runs.

By v0.8.x (early 2026-05), four things had become true:

1. **The operator (one person) runs Claude Code + Antigravity in practice.** Standalone Gemini CLI was added defensively in case it grew into the workflow, but in practice the operator's Gemini usage happens *inside* Antigravity's IDE-level integration (a different surface than standalone CLI).
2. **Maintenance load scaled with host count.** Three install destinations meant three sets of paths in `install.sh` / `install.ps1`, three columns in `Per-Host-Paths.md`, three branches in tests, three case-arms in every dispatch function. The third host's payoff (zero observed use) wasn't justifying its share of the maintenance cost.
3. **The MemoryVault design** (locked 2026-05-15, plan #7 part 1 task 1 scaffold shipped 2026-05-16) chose to ship its `memory` skill with `supported_hosts: [claude-code, antigravity]` — first new skill post-this-decision. Continuing to ship existing skills with the three-host scope created an inconsistency between memory and everything else.
4. **Standalone Gemini CLI's future is uncertain.** Google's coding-agent strategy as of 2026-05 leans on Antigravity (the IDE). The standalone CLI may persist, get replaced by a successor, or fade entirely — but it's not a host the operator actively builds for. Building for it speculatively was no longer worth the surface.

The decision to drop standalone Gemini CLI was logged in ROADMAP item #15 (added 2026-05-16) and executed as plan #15 (planned + executed 2026-05-16/17).

## Decision

**Drop standalone Gemini CLI from the toolkit's supported hosts.** Keep Claude Code and Antigravity. Gemini-in-Antigravity (the IDE-level Gemini integration) stays as a supported surface — it's a feature of Antigravity, not the standalone CLI.

Concretely:

- **Manifests**: `supported_hosts: [claude-code, antigravity, gemini-cli]` → `[claude-code, antigravity]` across every shipped customization (skills, agents, hooks, bundles). The schema's allowed values tighten to `{claude-code, antigravity}`.
- **Installer**: the `gemini-cli` dispatch arms in `install_skill` / `install_hook` / `install_agent` are removed. `.agents/skills/<name>/` (the legacy gemini-cli skill destination) and `.gemini/agents/<name>.md` (the legacy gemini-cli agent destination) are no longer created.
- **Validator**: `validate-manifests.py` tightens `HOST_ENUM` to `{claude-code, antigravity}`. A new `REMOVED_HOSTS` dict provides an actionable error message pointing operators at the v0.9.0 CHANGELOG and clarifying that Antigravity (Gemini-in-IDE) stays supported.
- **Legacy auto-cleanup with operator confirmation**: at install time, the installer detects pre-existing `.agents/skills/<known-name>/` and `.gemini/agents/<known-name>.md` from prior installs, prompts operator with N default (`"Move to backup .agents/skills.agent-toolkit-bak.<ts>/ and remove from active install path? [y/N]"`); on opt-in moves (not hard-deletes) to timestamped backups per the pre-push hook backup convention. New `--no-legacy-cleanup` / `-NoLegacyCleanup` flag suppresses the prompt for CI / scripted installs. Non-interactive stdin auto-defaults to N with explanatory notice.
- **Tests**: smoke install scripts gain negative-existence assertions (`.agents/` + `.gemini/` MUST NOT exist after install) + new automated tests for `--no-legacy-cleanup` suppression + validator-rejects-gemini-cli with v0.9.0 message.
- **ADRs 0001 + 0002 + 0004**: get amendments (not rewrites — audit trail preserved) noting the host-scope reduction.
- **Wiki sweep**: `Per-Host-Paths.md` drops the 3rd column; `Manifest-Schema.md` drops gemini-cli from allowed values; `Customization-Types.md`, `Installer-CLI.md`, the how-tos, and the tutorial drop forward-looking gemini-cli + `.agents/` + `.gemini/` references. Historical content (CHANGELOG entries from prior versions, prior ADR text) is preserved as audit trail.
- **MemoryVault design materials**: parent design Document History gets a row noting the host-scope correction is now applied fleet-wide (no longer "until #15 sweeps them"); part files + queued PLAN.md files updated to reflect 2-host scope.

### Why this shape (rationales for the key choices)

**Backup-not-hard-delete for legacy entries.** The pre-push hook installer (the prior dispatch in `install_pre_push_hook`) already establishes a backup-then-replace convention for unmanaged content. Auto-deletion of user filesystem state is invasive — operators may have customized `.agents/skills/<name>/` content that the installer doesn't recognize as toolkit-managed (though the detection logic is name-matched, so this is unlikely to bite). Backup preserves recoverability; operators can `rm -rf` the backup themselves after verifying nothing important is in it.

**Prompt-with-N-default instead of silent cleanup or hard delete.** Operators may not realize they have legacy state until the prompt fires. Defaulting to N means a hands-off operator's filesystem is never touched without explicit Y. The prompt itself is single-line + auto-defaults on non-interactive stdin, so doesn't block CI.

**ADR amendments, not rewrites.** ADRs 0001 + 0002 + 0004 referenced the three-host scope in their original text. Rewriting that text would erase the audit trail of what was decided when. Amendments at the bottom preserve the original narrative + add a clear "this changed in v0.9.0" annotation. Same pattern as ADR 0004's amendment 2026-05-16 for the external-review-handoff option.

**Antigravity stays.** Antigravity is the IDE-level integration — different surface than standalone Gemini CLI. Gemini-in-IDE is reachable from inside Antigravity's UI; standalone Gemini CLI is a separate process. The operator works in IDEs, not CLI-only. Antigravity covers the Gemini use cases that matter.

**Memory skill correction applied pre-#15.** The memory skill scaffold (shipped 2026-05-16 in v0.8.x via plan #7a part 1 task 1) excluded gemini-cli from day 1 because the #15 decision had been added to ROADMAP between the parent design's finalization (2026-05-15) and the scaffold ship (2026-05-16). Rather than ship memory with gemini-cli only to have #15 strip it back out, the first new skill post-#15-decision shipped with the post-#15 host scope. v0.9.0 then swept existing skills (pii-scrubber, design, dependabot-fixer, ship-release, evaluator, base hooks, example bundle) to match — closes the inconsistency window.

## Consequences

### Positive

- **Smaller surface to maintain.** Two hosts × N customizations is a third less dispatch code, test coverage, and doc surface than three hosts × N. Installer + tests + wiki + ADRs all shrink.
- **Test infrastructure tightens.** Smoke install now actively defends against gemini-cli coming back via negative-existence assertions on `.agents/` + `.gemini/`. Validator surfaces removed-host errors with actionable next-step text.
- **Cross-host manifest consistency.** Every shipped customization now has the same `supported_hosts: [claude-code, antigravity]` shape (modulo the few that are `[claude-code]`-only by design — the hooks). No special cases to remember.
- **Legacy state cleanup is safe + visible.** Operators with prior installs see one interactive prompt at next install time, opt in to a backup-then-remove pattern, and the toolkit doesn't leave dangling unmanaged paths. The `--no-legacy-cleanup` flag covers CI cases that want silence.
- **Documentation honesty improves.** Per-Host-Paths.md's "TBD" entries for `mcp-server` + `settings-fragment` on Antigravity are now the only forward-looking ambiguity. The Gemini-CLI column had multiple `(n/a)` + speculative entries that added noise without value.

### Negative

- **Pre-existing user installs see a one-time prompt.** Operators who installed v0.5.0-v0.8.x and populated `.agents/skills/` see the cleanup prompt at next install. Single-prompt cost; backup-then-remove flow is safe; `--no-legacy-cleanup` suppresses for those who want.
- **Backup directory accumulates if operator runs install many times + opts in repeatedly.** Each opt-in creates a timestamped backup; over many installs, multiple `.agents/skills.agent-toolkit-bak.<ts>/` dirs accumulate. Mitigation: timestamps make GC trivial (`find .agents/ -name 'skills.agent-toolkit-bak.*' -mtime +30 -exec rm -rf {} \;`); documented in CHANGELOG. Accepted as low-priority since operators typically run install rarely.
- **Loss of future optionality.** If a Gemini-CLI successor ships and turns out to be a primary workflow surface, re-adding it requires undoing #15's sweep + restoring the third column / dispatch arms / manifests. Mitigation: the historical 3-host scope is preserved in prior CHANGELOG entries + ADR original text; the install path skeleton is still understandable from those references. Cost of re-add ≈ cost of #15 ≈ ~1 week's worth of plan work.
- **Wiki cross-references explode.** The sweep touches ~12 wiki pages + 3 ADR amendments + this new ADR. Lots of small edits; risk of missed gemini-cli mention somewhere. Mitigation: grep across `wiki/` + `README.md` + `skills/memory/SKILL.md` after sweep returns only audit-trail mentions ("removed in v0.9.0" pointers); validator + smoke install enforce the manifest + installer side.

### Load-bearing assumptions (re-audit triggers)

| Assumption | Re-audit when |
|---|---|
| Antigravity covers Gemini use cases | Antigravity becomes Gemini-restricted, gets shut down, or its IDE-level Gemini integration changes shape such that standalone CLI becomes the only Gemini surface |
| Operators reliably distinguish toolkit-managed `.agents/skills/<name>/` from their own non-toolkit content during cleanup prompt | If an operator reports the cleanup prompt fired on a `.agents/skills/<unmanaged-name>/` they cared about — the detection's manifest-name-match is the safety net but isn't bulletproof |
| The backup-not-hard-delete pattern is the right safety net | If the backup dir accumulates faster than expected (operator runs install many times) OR if operators complain about manual `rm` requirement → consider explicit backup-rotation logic or a `/memory cleanup --legacy` follow-up command |
| Gemini-CLI successor doesn't ship within ~6 months | If Google announces a Gemini-CLI successor that's worth re-adding, this ADR gets superseded by a new ADR that re-introduces the host (or a successor host) |

## Related

- [ROADMAP item #15](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md) — the roadmap entry that triggered this plan
- [ADR 0001 — agent-toolkit purpose](0001-agent-toolkit-purpose) — amended 2026-05-17 to note the host-scope reduction
- [ADR 0002 — evaluator design](0002-evaluator-design) — amended 2026-05-17 to note the evaluator's host-scope change
- [ADR 0004 — design skill](0004-design-skill) — amended 2026-05-16 for external-review-handoff option; the v0.9.0 host-scope reduction applies to the design skill too (the manifest sweep in task 2 dropped gemini-cli from `skills/design/SKILL.md`)
- [Per-Host Paths reference](../../reference/Per-Host-Paths) — destination table now 2-column
- [Customization Types reference](../../reference/Customization-Types) — kind × host matrix updated
- [Manifest Schema reference](../../reference/Manifest-Schema) — `supported_hosts` allowed values tightened
- [Installer CLI reference](../../reference/Installer-CLI) — `--no-legacy-cleanup` flag documented + legacy cleanup section
- [agent-toolkit CHANGELOG.md](https://github.com/alexherrero/agent-toolkit/blob/main/CHANGELOG.md) — v0.9.0 entry (lands in task 6)
- [agentic-harness CHANGELOG.md](https://github.com/alexherrero/agentic-harness/blob/main/CHANGELOG.md) — paired v2.4.0 entry (lands in task 6)
