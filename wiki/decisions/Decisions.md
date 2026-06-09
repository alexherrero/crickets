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

## Retrospectives

- [V3 Retrospective](v3-retrospective) — what shipped across the V3 arc, what we learned, what's next.

## Related

- [Home](Home) — the wiki landing page.
- [Purpose and scope](Purpose-And-Scope) — the founding rationale ADR 0001 records.
