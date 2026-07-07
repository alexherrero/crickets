---
title: privacy — design
status: launched
kind: design
scope: feature
area: crickets/privacy
governs: [src/privacy/]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-23
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23) · locked 2026-06-28 (final AG design sweep).** child-design — **the `privacy` capability** (keep secrets + personal information out of what gets committed and pushed, and keep good privacy practice in the code). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# privacy

## Objective

`privacy` is the capability that keeps **secrets and personal information out of what gets committed and pushed** — and, with a review skill, keeps **good privacy practice in the code itself**. It holds the conventions for safe stand-ins, scans a diff for leaks, blocks a push that would ship one, and reviews the code for privacy-engineering mistakes. The leak scan is **deterministic** (regex / pattern, never LLM judgment) — the property the rest of the portfolio leans on.

## Overview

privacy works in three layers — **proactive** (don't compose a secret), **detect** (scan the diff), **enforce** (block the push) — plus a **review** layer for privacy *practice*. The detect and enforce layers run client-side at the `pre-push` hook, and again in CI, where `check-no-pii.sh --all` + `gitleaks` run as **two independent scanners**. That CI pass is a back-stop that reduces single-pattern blind spots: by the time CI fails the secret is already in pushed history, so the hook is the primary block and CI back-stops both it and the scrubber. The primitives:

| Primitive | Kind | Status | What it does |
|---|---|---|---|
| `pii-patterns` | rule | delivered | Proactive stand-in conventions (RFC-2606 domains · `$HOME` · env-var refs · 555-01xx) — never compose a real secret/PII. |
| `check-no-pii.sh` | script | delivered | The **deterministic detector** — regex/gitleaks patterns over the diff (email · path · openai/github/gitlab/aws keys · phone). |
| `pii-scrubber` | skill | delivered | Interactive remediation — run the detector, surface findings `file:line`, redact, loop until clean. |
| `pre-push` hook | hook | delivered | Mandatory enforcer — blocks a push carrying a finding. |
| `privacy-review` | skill | delivered | Review the codebase's privacy **practices** (data minimization · PII-in-logs · retention · consent) — not string scanning. |

![The privacy capability: a deterministic leak floor (pii-patterns · check-no-pii.sh · pii-scrubber · pre-push — built) plus an LLM privacy-review (to adapt); the floor scrubs incident material for diagnostics, maintenance's cve-security-patch is its reactive sibling, and the review consumes the good opinion](diagrams/crickets-privacy.svg)

*A deterministic leak floor (delivered — regex, never LLM) and an LLM privacy-practice review (to adapt); the floor scrubs incidents for diagnostics; maintenance's `cve-security-patch` is its reactive sibling.*

## Design

### Deterministic by contract

The leak scan is **rule-based and deterministic** — the same input yields the same finding, reproducibly. That reproducibility is what lets other capabilities compose it as a *guard*: the same patterns gate every push, and [diagnostics](crickets-diagnostics.md) scrubs a failure-incident body before it lands in memory.

### The `pre-push` hook is shared

`privacy` **declares** the `pre-push` hook, but [development-lifecycle](crickets-development-lifecycle.md)'s finalize step (`pr_helpers.py`, the "PII GUARD" ordering invariant) **uses** it — privacy owns the patterns + the detector; the hook is shared push-surface infrastructure.

### `privacy-review` — review for privacy *practice* *(delivered)*

A second angle. The string scanner stops a *leaked secret*; it can't catch a *structural* privacy mistake — a personal field flowing into a logger, a store with no deletion path, data collected beyond its consented purpose, PII sent to a third-party SDK — because the defect is in the **shape** of the code, not a literal value in the diff. `privacy-review` is an **LLM-assisted adversarial review** of a diff/PR for privacy-engineering practice, modeled on its sibling `security-auditor` in [code-review](crickets-code-review.md): it reports **falsifiable findings** — `PRIVACY-RISK <file>:<line> [ASVS-id / OWASP-P#]` — never prose, and never fixes.

**What it checks** — the practices, each keyed to a standard: PII into a log / telemetry / third-party sink · no retention or deletion path · incomplete erasure (right-to-be-forgotten) · purpose-limitation + consent reuse · data minimization (over-collection + over-return) · PII in URLs / client storage · plaintext personal data at rest · production data in test fixtures · unscoped access to personal data.

**Adapted from reputable prior art** (not vendored — the adapt-don't-import discipline): **OWASP ASVS V8 Data Protection** (the primary anchor — each requirement is already a testable assertion, so every finding cites an ASVS id), **OWASP Top 10 Privacy Risks** (the ranked taxonomy), the **NIST Privacy Framework** (the category structure), and **ICO data-protection-by-design** guidance.

**Deterministic-first.** The mechanizable checks (PII-in-URL, PII-in-client-storage, plaintext columns, third-party sinks) shell out to grep / a small Semgrep taint pack; the LLM judges only the non-mechanical practices (purpose limitation, consent scoping, retention adequacy, erasure completeness) — so the deterministic floor holds and the model reasons only where it must.

**Shipped 2026-07-07** (`PLAN-wave-d-tokens-and-privacy`, [crickets #166](https://github.com/alexherrero/crickets/pull/166)) — `src/privacy/skills/privacy-review/SKILL.md` (nine practices, four Semgrep-mechanized + five LLM-judged) plus `src/privacy/scripts/privacy-taint-pack.yml` (the four mechanizable pattern categories); the deterministic `pii-scrubber` stays the floor.

### Opinions it consumes

privacy **implements part of `done`** — a change that leaks a secret or PII is not finished; the `pre-push` gate is one of the deterministic checks the `done` standard rests on. The `privacy-review` skill **consumes `good`** (what good privacy practice looks like) and **`how-we-engineer`** (the review discipline), reviewing the code against those standards. *(Hardwired today; requesting an opinion by name is the Phase-3/4 registry work — the [Opinions design](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates).)*

### Where privacy is composed *(designed)*

- **[diagnostics](crickets-diagnostics.md)'s incident-body scrub surface — shipped 2026-07-07.** privacy scrubs *git ranges* and arbitrary text bodies now: `src/privacy/scripts/scrub_text.py` bridges to agentm's `privacy_scrub.scrub_pii()` (the same rules, reused not forked), and diagnostics' `writer.py` calls it explicitly at the crickets call site before every `kind: failure-incident` write.
- **[maintenance](crickets-maintenance.md)'s `cve-security-patch` is privacy's reactive sibling** — privacy owns proactive static patterns; maintenance acts on advisories. Two halves of supply-chain / secret hygiene, opposite triggers.

## Dependencies

- **standalone** — `requires: []`; privacy ships alone.
- **leans on the opinions** — implements part of `done` (the leak-free-push gate); the `privacy-review` skill consumes `good` + `how-we-engineer` ([agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates)).
- **the `pre-push` hook is shared with [development-lifecycle](crickets-development-lifecycle.md)** — its finalize routine enforces it as an ordering invariant.
- **composed by [diagnostics](crickets-diagnostics.md)** — the incident-body scrub (a designed surface, above).
- **pairs with [maintenance](crickets-maintenance.md)** — proactive static to its reactive advisory.
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md).

## Migrations

The capability is renamed `pii` → `privacy` (the bare concern-noun; `capabilities: [privacy]` is already declared, from the Phase-2 hygiene pass). The plugin directory has already moved to `src/privacy/` (Wave A renames, 2026-07-06); `capabilities: [pii, privacy]` still dual-declares both names so existing references resolve. The primitive doc-titles (`pii-patterns`, `pii-scrubber`) follow at the v6.0 rename (the [composition](crickets-composition.md) rename mechanism).

## Risks & open questions

- **`privacy-review` shipped 2026-07-07** — the practice checklist, adapted from OWASP ASVS V8 / Top-10 Privacy Risks / NIST Privacy Framework / ICO, is LLM-assisted *practice* review, distinct from the deterministic string scanner, which stays the trustworthy floor.
- **The incident-body scrub surface shipped 2026-07-07** — `scrub_text()` gives diagnostics' deterministic-scrub composition a scan-arbitrary-text entry point beyond privacy's git-range scan.
- **The `done` gate is still hardwired; `privacy-review`'s opinions are now real.** `privacy-review` declares `opinions: [good, how-we-engineer]` and renders both via the markdown-render-step grammar `PLAN-opinion-consumer-grammar` landed — requesting `done` by name is still Phase-3/4 registry work.
- **Re-audit triggers:** flip `pii` → `privacy` naming at v6.0 (the plugin directory already moved; `capabilities:` dual-declares both — only the primitive doc-titles remain).

## References

- crickets `src/privacy/` (live) — `rules/pii-patterns.md` · `skills/pii-scrubber/SKILL.md` · `skills/privacy-review/SKILL.md` · `scripts/check-no-pii.sh` · `scripts/scrub_text.py` · `scripts/privacy-taint-pack.yml` · `templates/hooks/pre-push`
- **`privacy-review` prior art (adapted from):** OWASP ASVS V8 Data Protection (the testable-requirement anchor) · OWASP Top 10 Privacy Risks v2 · NIST Privacy Framework · ICO data-protection-by-design; output contract modeled on `code-review`'s `security-auditor`; mechanizable checks lean on a Semgrep taint pack. *(The `Privacy-Data-Protection-Skills` agent-skill repo was a format/coverage reference only — verified against the OWASP/NIST/ICO authorities.)*
- **Composed by / paired with:** [diagnostics](crickets-diagnostics.md) (incident scrub) · [maintenance](crickets-maintenance.md) (the reactive `cve-security-patch` sibling)
- **Up:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates) (`done` / `good` / `how-we-engineer`)

## Amendment log

**2026-07-07 — `privacy-review` + Semgrep taint pack + `scrub_text()` surface shipped, opinion-wiring retrofitted (`PLAN-wave-d-tokens-and-privacy`, [crickets #166](https://github.com/alexherrero/crickets/pull/166)).** `src/privacy/skills/privacy-review/SKILL.md` ships nine practices (four Semgrep-mechanized, five LLM-judged) under the `PRIVACY-RISK <file>:<line> [ASVS-id]` contract; `src/privacy/scripts/privacy-taint-pack.yml` covers the four mechanizable categories (PII-in-URL, PII-in-client-storage, plaintext-columns, third-party-sinks); `src/privacy/scripts/scrub_text.py` bridges to agentm's `privacy_scrub.scrub_pii()` (same rules, not forked) and gives diagnostics' `writer.py` an explicit call site before every `kind: failure-incident` write, closing the incident-body scrub gap this doc had flagged. `privacy-review` also declares `opinions: [good, how-we-engineer]`, retrofitted in the same session once `PLAN-opinion-consumer-grammar` ([crickets #167](https://github.com/alexherrero/crickets/pull/167)) landed the markdown-render-step grammar this binding was deferring on — a real connection, not hardwired prose. Also corrected two facts this doc still carried from before the Wave A renames: `governs:` now points at `src/privacy/` (`src/pii/` no longer exists on disk) and the References section drops the stale "live; → `src/privacy/`" framing. **Re-audit triggers cleared:** adapt + build `privacy-review`; build the incident-body scrub surface; wire `opinion_request` for `privacy-review`. Still open: flip `pii` → `privacy` doc-titles at v6.0; wire `done` by name (Phase-3/4 registry work).

**2026-06-28 — lock-down sweep (operator review).** Converted the layers mermaid to a house-style hand-SVG (`diagrams/crickets-privacy.svg`). Confirmed the deterministic leak floor (built) + the LLM privacy-review (to adapt), and that `cve-security-patch` is its reactive sibling. No content change. Locked as a v5–v8 guidepost.

**2026-06-23 — added the layers diagram (diagram backfill).** Per the every-design-carries-a-diagram rule.

**2026-06-23 — authored from the seeded stub (grounded against the live `src/pii/` plugin); revised on operator review.** All four leak-side primitives are delivered — `pii-patterns` (rule), `check-no-pii.sh` (the deterministic detector), `pii-scrubber` (skill), the `pre-push` hook (mandatory enforcer); listed as a table. Named the **deterministic-by-contract** invariant (regex / pattern, never LLM) and resolved the `pre-push` home (privacy declares it; `development-lifecycle`'s finalize uses it). Added two operator-requested pieces: (1) an **Opinions-it-consumes** clause — privacy implements part of `done`, the `privacy-review` skill consumes `good` + `how-we-engineer` (a clause the other designs should carry too); (2) a second angle — a **`privacy-review`** skill for privacy *practice* (data minimization, PII-in-logs, retention, erasure, consent, third-party sinks): an LLM-assisted adversarial review with **falsifiable `PRIVACY-RISK file:line [ASVS-id]` findings**, **adapted from OWASP ASVS V8 / Top-10-Privacy-Risks / NIST Privacy Framework / ICO** (a prior-art investigation, 2026-06-23), **deterministic-first** (mechanizable checks shell out to grep / a Semgrep taint pack; the LLM judges only the non-mechanical practices), distinct from the deterministic `pii-scrubber` floor (`[PENDING-IMPL]`). Also surfaced the **incident-body scrub surface** diagnostics needs and the `cve-security-patch` pairing with maintenance. **Re-audit:** adapt + build privacy-review; build the incident-scrub surface; wire `opinion_request`; flip the name at v6.0.
