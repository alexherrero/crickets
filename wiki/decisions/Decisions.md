<!-- mode: index -->
# Architecture decisions

Every load-bearing call in crickets is recorded as an Architecture Decision Record (ADR): the context, the decision with explicit *"why X, and why not Y"* reasoning, and the consequences with re-audit triggers so a stale assumption surfaces later instead of rotting silently.

This page is the index. The homepage links here once instead of listing every ADR.

## Records

- [ADR 0001 — crickets purpose, scope, public-with-PII-guardrails](0001-crickets-purpose)
- [ADR 0002 — evaluator sub-agent design](0002-evaluator-design)
- [ADR 0003 — base operator-control hooks](0003-base-operator-hooks)
- [ADR 0004 — design skill: human-facing design pipeline → agent execution handoff](0004-design-skill)
- [ADR 0006 — Gemini CLI host removal](0006-gemini-cli-host-removal)
- [ADR 0007 — MemoryVault Discovery + Mining](0007-memoryvault-discovery)
- [ADR 0008 — diataxis-author skill](0008-diataxis-author)
- [ADR 0009 — evidence-tracker hook](0009-evidence-tracker-hook)
- [ADR 0011 — Antigravity 2.0 host support](0011-antigravity-2-host-support)
- [ADR 0012 — device-wide-by-default](0012-device-wide-by-default)
- [ADR 0013 — bundles are native host plugins](0013-bundles-native-plugins)
- [ADR 0014 — #40 install-decoupling](0014-install-decoupling)
- [ADR 0015 — #36 partial-revision](0015-partial-revision-36)
- [ADR 0016 — Project surface split](0016-project-surface-split)
- [ADR 0017 — Soft composition (`enhances:`) + the developer split + capability probe](0017-enhances-soft-composition)
- [ADR 0018 — Per-folder sidebars: intent-grouped wiki folders with collapse/expand nav](0018-per-folder-sidebars)
- [ADR 0019 — Wiki provisioning: gate-distribution split + supersession-gated retirement](0019-wiki-provisioning)
- [ADR 0020 — Seven-section wiki taxonomy: fixed frame + per-project Architecture manifest + conditional gates](0020-seven-section-wiki-taxonomy)
- [ADR 0021 — Per-plugin marketplace versioning sourced from `group.yaml`](0021-per-plugin-versioning)
- [ADR 0022 — Retire `worktrees-never-auto`: worktrees first-class but operator-initiated](0022-retire-worktrees-never-auto)
- [ADR 0023 — Gate the integrated tree, not the worker branch: merge-then-gate with hard-reset rollback](0023-gate-on-integrated-tree)
- [ADR 0024 — Package `/design` as a command (tested Python helper + thin prompt), not a skill](0024-design-as-command)
- [ADR 0025 — One-way vault → GitHub-Project board synthesis (`github-projects`)](0025-board-sync-vault-to-project)
- [ADR 0026 — Phase-aware model routing in developer-workflows](0026-phase-aware-model-routing) _(proposed, Part D pending)_
- [ADR 0027 — Discovery paths for `output-style` and `rule` primitives](0027-output-style-rule-discovery-paths) _(proposed, Part D pending)_
- [ADR 0028 — Worktree authority broadened: config opt-in is operator authority for auto-spawn](0028-worktree-authority-config-opt-in)
- [ADR 0029 — Concurrent-release coordination: tag-from-main, branch protection, single writer](0029-concurrent-release-coordination)
- [ADR 0030 — Generated artifacts have a single writer: defer the version bump to the serialized integrator](0030-generated-artifact-single-writer)

## Retrospectives

- [V3 Retrospective](v3-retrospective) — what shipped across the V3 arc, what we learned, what's next.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-15** — ADR 0030 (generated-artifact single writer) added; records deferring the version bump to the serialized integrator (Model A — defer-bump-only) so concurrent worker branches never write the shared `marketplace.json` registry, removing the cross-plugin collision class seen in the first concurrent run. `dist-sync` stays fully authoritative everywhere; only `version-bump` becomes branch-aware. Extends ADR 0029's single-writer model from tags to generated artifacts.
- **2026-06-14** — ADR 0028 (worktree authority broadened) added; records that a durable `isolation.mode: worktree-per-plan` config opt-in IS operator authority for worktree creation, partially superseding ADR 0022's "explicit command only" framing; ADR 0023 untouched; prohibition updated to "without operator authority" (not "autonomously").
- **2026-06-14** — ADR 0026 (phase-aware model routing) + ADR 0027 (output-style/rule discovery paths) proposed for Part D (agentm #46); both pending implementation.
- **2026-06-14** — ADR 0025 (board-sync vault→project) added; records the `github-projects` plugin's one-way deterministic synthesis — DC-1 materialization (feature-and-up always; Plan/Task active-plan-only), DC-2 frozen six-field set (only `Type`/`project_surface` code-enforced; `Track`/`Priority`/`Status` free-form), DC-4 single idempotent render+write path, silent-source stripping on the public board, and `requires: developer-workflows` (vault path from config, not a hard agentm dependency).
- **2026-06-14** — ADR 0024 (design as command) added; records packaging the crickets `/design` port as a command (tested Python helper + thin prompt) wired onto `stage_plan.py`, not a no-Bash skill — a divergent port of the agentm skill (ADR 0004), not a supersession.
- **2026-06-13** — ADR 0023 (gate the integrated tree) added; records gating the post-merge tree (not the worker branch in isolation) and the merge-then-gate-with-hard-reset-rollback that keeps `main` never-broken when `/integrate-worker` lands a worker, with no push.
- **2026-06-13** — ADR 0022 (retire `worktrees-never-auto`) added; records retiring the blanket "never create worktrees" prohibition for "worktrees first-class but operator-initiated" once `/spawn-worker` made worker worktrees a real workflow, keeping the no-autonomous-spawn guarantee.
- **2026-06-11** — ADR 0021 (per-plugin versioning) added; records sourcing each plugin's marketplace version from `group.yaml` so `claude plugin update` works, plus the anti-recurrence bump guard.
- **2026-06-11** — ADR 0020 (seven-section wiki taxonomy) added; records the fixed frame, the per-project Architecture manifest, and the two conditional-section gates.
- **2026-06-10** — ADR 0019 (wiki provisioning) added; records the gate-distribution split + supersession-gated retirement.
- **2026-06-08** — ADR 0018 (per-folder sidebars) added; the ADRs moved into `decisions/`.

## See also

- [Home](Home) — the wiki landing page.
- [Purpose and scope](Purpose-And-Scope) — the founding rationale ADR 0001 records.
