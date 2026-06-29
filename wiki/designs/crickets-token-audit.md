---
title: token-audit — design
status: launched
kind: design
scope: feature
area: crickets/token-audit
governs: [src/token-audit/]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-23
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23) · locked 2026-06-28 (final AG design sweep).** child-design — **the `token-audit` capability** (token-cost measurement + live metering — the measurement slice of the `efficient` opinion). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# token-audit (→ `tokens` at v6.0)

## Objective

`token-audit` **measures what a session costs** — a deterministic cost breakdown after the fact and a live status-line meter during. It is the *measurement* half of the **`efficient`** opinion: the opinion sets the budget and the quality floor; this capability supplies the cost truth that budget is weighed against. It declares `[token-audit]` (→ `[tokens]` at v6.0).

## Overview

The primitives, all delivered (+ one fold):

| Primitive | Kind | What it does |
|---|---|---|
| `/token-audit` | command | The cost breakdown — reads the session JSONL, splits cached vs fresh, rolls up 5-hour windows, prices each. |
| `analyzer.py` | script | The streaming JSONL cost reader — cache split, window roll-up, the always-load floor. |
| `pricing.py` | script | One pinned source of model rates — the only place a price lives. |
| `status_line_meter.py` | script | The live status-line meter (**folded in** from `status-line-meter`). |

![The token-audit capability: /token-audit (on-demand operator breakdown) and the status_line_meter.py live meter (folds in) both read pricing.py's pinned per-model rates; analyzer.py computes the cache split, 5h windows, and floor; on session-stop it logs a session-cost record to memory (designed), reviewed in dreaming into an efficiency trend that flags creep (designed); token-audit is the measurement half of the efficient opinion](diagrams/crickets-token-audit.svg)

*A deterministic cost analyzer (cache-split · 5-hour windows · the always-load floor) behind both the on-demand `/token-audit` breakdown and the passive live meter; `pricing.py` is the one pinned rate source. Designed (grey): on session-stop the analyzer auto-logs a per-model `session-cost` record to memory, which the dreaming pass reviews to surface an efficiency trend. It supplies the cost truth the `efficient` opinion weighs its budget against.*

## Design

### Deterministic measurement

`analyzer.py` reads the session JSONL and computes cost mechanically — no model in the loop. It splits **cached vs fresh** input (the cache discount is the dominant lever in the token-discipline routing), rolls usage into the **5-hour billing windows** the plan caps on, and accounts for the always-loaded context floor. Same transcript → same number, every run. `pricing.py` is the single pinned source of per-model rates, so a rate change touches one file.

### Two surfaces, one engine

`/token-audit` is the after-the-fact breakdown (where the tokens went, which window, cache hit-rate); `status_line_meter.py` is the live meter that keeps the current burn in view during a session. Both read the same analyzer: the meter is that one measurement, surfaced live during the session.

### How it's invoked

token-audit engages at three altitudes — two delivered, one designed:

- **Passive (live)** — `status_line_meter.py` keeps the current burn in view throughout a session; nobody invokes it, it is always on.
- **On-demand** — `/token-audit` is **operator-invoked**: the detailed after-the-fact breakdown, run when you want to see where the tokens went.
- **Ambient capture + periodic review *(designed)*** — on session-stop a hook auto-runs the analyzer and **logs the per-model cost breakdown into memory** as a durable `session-cost` record (a new memory kind). The memory engine's **dreaming pass** (its periodic reflection / consolidation cycle) then reviews those records to surface an efficiency *trend* — flagging when token use creeps up over time, to act on later. This turns token-audit from a point-in-time lookup into a longitudinal signal on the **`efficient`** opinion. **`[PENDING-IMPL]`** — the auto-on-stop capture (a Stop hook writing the `session-cost` entry) and the dreaming-pass review are designed, not built; today the capability is operator-invoked plus the passive meter.

### Opinions it consumes

token-audit is **the measurement half of `efficient`.** The opinion is the judgment — *cheap as the job allows, above the quality floor*; this capability is the deterministic cost truth that judgment needs to be real and not a vibe. The arrow is one-way: `efficient` (and the model-routing discipline it backs) cites this capability's numbers; the capability never reaches up into the opinion. *(Hardwired today; requesting `efficient` by name is the Phase-3/4 registry work — the [Opinions design](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates).)*

## Dependencies

- **standalone** — `requires: []`; ships alone.
- **serves the `efficient` opinion** ([agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates)) — the measurement slice; the budget + quality floor live in agentm.
- **(designed) couples to the agentm memory engine** — the auto-on-stop capture writes a `session-cost` memory record and the dreaming pass reviews it; the *delivered* capability stays standalone.
- **(forward-referenced) the pricing-drift mitigation** is the `content-refresh` primitive — tentatively homed in [maintenance](crickets-maintenance.md) as an optional scheduled task — which would periodically re-pin `pricing.py` from source (post-review pass to confirm its home + author it).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md).

## Migrations

- **The `status-line-meter` fold** — `status_line_meter.py` moves in; its standalone `enhances:` edge dissolves and becomes internal. One capability owns measurement + metering.
- **The v6.0 rename** `token-audit` → **`tokens`** (object-over-action); the group declares both names so existing references resolve (the [composition](crickets-composition.md) rename mechanism). The `efficiency` rename was **rejected** — it collides with the `efficient` opinion the capability's own tools request, and inverts the one-way rule (a capability naming itself after the opinion it serves).
- **Sibling audits, not a widened scope** — other efficiency dimensions (latency, memory) get their own audit tools; this one stays token-cost.

## Risks & open questions

- **All shipping primitives delivered** — `/token-audit`, `analyzer.py`, `pricing.py`, `status_line_meter.py`; the fold + rename are mechanical. The auto-capture + dreaming review are the designed additions (below).
- **`pricing.py` drifts against real rates** — a pinned table goes stale when a vendor reprices; the single-source design keeps the fix to one file, but the re-pin is manual today. The standing mitigation is the **`content-refresh`** primitive — tentatively homed in [maintenance](crickets-maintenance.md) as an optional, scheduled task (it refreshes the harness's external-sourced content against a checklist: model pricing, adapted-skill upstreams, etc.) — which would automate the `pricing.py` re-pin; confirm its home + author it at the post-review pass.
- **The auto-capture + dreaming review are designed, not built** — the `session-cost` memory kind, the Stop-hook capture, and the dreaming-pass efficiency-trend review are `[PENDING-IMPL]`; today token-audit is operator-invoked plus the passive meter.
- **Re-audit triggers:** stand up the content-refresh capability to automate the `pricing.py` re-pin (manual re-pin until then); build the auto-on-stop `session-cost` capture + the dreaming-pass review; execute the `status-line-meter` fold + the `tokens` rename at v6.0; spin a sibling audit when a non-token efficiency dimension needs measuring.

## References

- crickets `src/token-audit/` + `src/status-line-meter/` (the folding-in source) — `/token-audit` · `analyzer.py` · `pricing.py` · `status_line_meter.py`; declares `[token-audit]` (→ `[tokens]`)
- **Up / serves:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates) (`efficient`)

## Amendment log

**2026-06-28 — lock-down sweep (operator review).** Converted the primitives mermaid to a house-style hand-SVG (`diagrams/crickets-token-audit.svg`); and restored the missing `## Amendment log` heading (the design had none). Confirmed token-audit is the measurement half of the `efficient` opinion (`/token-audit` + the live meter over `pricing.py`'s pinned rates; `analyzer.py`'s cache split · 5h windows · floor), and that the session-cost → dreaming → efficiency-trend chain is designed. Locked as a v5–v8 guidepost.

**2026-06-23 — authored, reviewed, and finalized.** Authored from the seeded stub and grounded against the live `src/token-audit` + `src/status-line-meter` plugins. token-audit is the **measurement half of `efficient`** — a deterministic cost analyzer (cache split · 5-hour windows · the always-load floor; same transcript → same number) behind two surfaces: the on-demand `/token-audit` breakdown and the passive live meter (folding in `status_line_meter.py`); `pricing.py` is the single pinned rate source. The `### Opinions` arrow is one-way (the opinion cites the numbers; the capability never reaches up). Recorded the rejected `efficiency` rename and the v6.0 `tokens` target (resolver aliasing).

On review: added a **How it's invoked** subsection — three altitudes (passive live meter · operator-invoked `/token-audit` · a *designed* auto-capture-on-session-stop that logs a per-model `session-cost` memory record, reviewed in the **dreaming** pass to surface an efficiency trend; `[PENDING-IMPL]`) — and reframed the **`pricing.py`-drift** risk to forward-reference the **`content-refresh`** primitive (tentatively homed in `maintenance` as an optional scheduled task) as the standing re-pin mitigation. **Re-audit:** build the auto-capture + dreaming review; stand up `content-refresh` to automate the `pricing.py` re-pin; execute the `status-line-meter` fold + the `tokens` rename at v6.0.
