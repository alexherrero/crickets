---
title: token-audit — design
status: launched
kind: design
scope: feature
area: crickets/token-audit
governs: [src/tokens/]
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

### The routing table — single home of current model ids (designed, not built)

Today `model-effort-routing`'s tier chart carries both the abstract policy (tier × effort) and concrete model-id strings per host, bolted into one wiki table — two things with different change cadences. This design specifies pulling the concrete half out into a **versioned data file here**, alongside `pricing.py` — the same one-pinned-source shape, and the natural home: a routing decision and its price are read off the same transcript in the same breath, so they should never be able to disagree about how a model's name is spelled. `model-effort-routing` keeps the tier scale + effort ladder only; this file becomes **the single place a current model id lives.**

Rows are keyed by **work-type** (a superset of persona — it also covers ad-hoc dispatch roles that carry no persona manifest at all: a `/plan` explorer, a `/review` adversarial or cross-model reviewer, a documenter, a verification clerk), each resolving to `(tier, model-id, effort)`. Seeded from the Phase-R evidence: **Sonnet 5 high** validated for staging/tech-lead authoring and for T2-Author work that's transcription-shaped (the design reasoning is already settled elsewhere; the session is careful transcription + sequencing); **Sonnet 5 medium** for wiki/mechanical-plus work (gate-checked, no planning split needed). **T2 · Author itself splits** rather than resolving to one model: roadmap/architecture calls route to **Opus 4.8, high**; transcription-shaped authoring routes to **Sonnet 5, high**. The table's work-type granularity catches variance a single-tier-per-persona map can't express — T1 Execute, for instance, covers both a heavy `opusplan` build stretch and flat-Sonnet mechanical-plus work, same tier, different concrete instantiation.

Two consumers read the table by name, one-way, never re-deriving it: crickets development-lifecycle's dispatch points (routing) and this capability's own routing-conformance report, below (measurement). Kept current by `content-refresh`, in the same pass as `pricing.py` — a model release re-pins both files' id strings together, since they must never disagree about what a given string means.

**The table, seeded** (Phase-R evidence + the live `pricing.py` roster):

| Work-type | Tier | Model id | Effort |
|---|---|---|---|
| Research · adversarial audit | T4 · Deep | `claude-opus-4-8` | `max` (+ `ultracode` orchestration) |
| Roadmap · architecture · priority/board calls | T3 · Architect | `claude-opus-4-8` | `max` |
| T2-Author — roadmap/architecture-shaped authoring | T2 · Author | `claude-opus-4-8` | `high` |
| T2-Author — transcription-shaped authoring (staging, tech-lead) | T2 · Author | `claude-sonnet-5` | `high` |
| Worker build (`/work`, `/bugfix` — the autonomous stretch) | T1 · Execute | `opusplan` (plans on `claude-opus-4-8`, executes on `claude-sonnet-5`) | `medium` |
| Wiki / mechanical-plus (gate-checked, no planning split) | T1 · Execute | `claude-sonnet-5` | `medium` |
| Mechanical edits · log-scraping · deterministic passes | T0 · Mechanical | `claude-sonnet-5` (or `claude-haiku-4-5` for the most rote cases) | `low` |
| *(recognized, not routed)* | — | `claude-fable-5` | — |

`claude-fable-5` is a real, pinned model id (`pricing.py`, ~2× Opus's per-MTok rate — the single most expensive row in the table) that no work-type resolves to today; PROMPTS-NEXT.md's own standing rule for this program is "Fable is not used anywhere in this pack." It is named here explicitly, not omitted, for one reason: an `INHERITED` announcement (development-lifecycle's mandatory fan-out contract, below) that shows `claude-fable-5` is then instantly recognizable as the Mythos failure shape — silent inheritance of the most expensive model at fan-out scale — rather than a name the operator has to look up mid-incident.

**Already-fired, not hypothetical:** the agent-def frontmatter on `worker.md` / `researcher.md` / `tech-lead.md` still pins `claude-sonnet-4-6`, and every command's nudge text still names `claude-sonnet-4-6` / `claude-opus-4-8` — both stale relative to `pricing.py`'s `claude-sonnet-5` row, added one day earlier in the same R0.7 repair pass. This is the content-refresh trigger this design already names, caught live rather than waited-for; `PLAN-efficiency-automation` should carry the roster bump as a concrete task, not just cite it as a future risk.

### The classifier — resolving a dispatch to a table row (designed, not built)

The table is only useful if something deterministic decides which row applies. `classify_work_type` is a small function, hosted alongside the table, that a dispatch point or a staging step calls to get back a work-type key (never a model — that's the table's job, one step later):

1. **Persona-bound dispatch.** The sub-agent's agent-def already declares a tier (its `model:`/`effort:` frontmatter, generalized per [model-effort-routing](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing)'s `tier:` axis). No classification needed — the declaration *is* the answer.
2. **Ad-hoc dispatch role.** Match the role name against the table's work-type keys (`explorer`, `adversarial-reviewer`, `cross-model-reviewer`, `documenter`, `verification-clerk`, and the session-shaped keys above) — an exact-match lookup, not a model making a judgment call.
3. **No match.** Resolve to an explicit **`UNCLASSIFIED-DEFAULT`** tier source — never a silent fallback — at a fixed safe default (T1 · Execute, `claude-sonnet-5`, medium; never `claude-fable-5`, never session-inherited). The mandatory fan-out announcement ([development-lifecycle](crickets-development-lifecycle.md)) names `UNCLASSIFIED-DEFAULT` as its own tier-source value, distinct from table row / frontmatter / `INHERITED`, so a classification gap stays visible instead of being quietly absorbed into "it just worked."

The same function derives a staged plan's per-task tier hint at authoring time and powers the session-start suggestion to the operator — one classifier, three call sites (sub-agent dispatch, plan staging, session-start nudge), never three copies of the same judgment.

**Named honestly as a discoverability cost:** an operator reading `model-effort-routing`'s design now sees the tier structure but not which model is actually running for a given work-type — they have to follow the pointer here. Mitigated by cross-linking both directions (References, below), not eliminated. The Claude-side table is the one built first; Gemini/Antigravity rows lag until that side of the portfolio needs its own consumption path — named honestly, not claimed as symmetric on day one.

### How it's invoked

token-audit engages at four altitudes — two delivered, two designed:

- **Passive (live)** — `status_line_meter.py` keeps the current burn in view throughout a session; nobody invokes it, it is always on.
- **On-demand** — `/token-audit` is **operator-invoked**: the detailed after-the-fact breakdown, run when you want to see where the tokens went.
- **Ambient capture — shipped 2026-07-07** (`PLAN-wave-d-tokens-and-privacy`, [crickets #166](https://github.com/alexherrero/crickets/pull/166)) — on session-stop, the `session-cost-capture` Stop hook (`src/tokens/hooks/session-cost-capture/`) runs `session_cost_writer.py` over the closing transcript and logs a per-model `session-cost` record via agentm's memory write path (`kind: session-cost`, the V6-11 metadata slot shipped 2026-07-06). Graceful no-op with no memory backend configured — never blocks session close. `session_cost_reader.py` reads the records back for the pre-flight fan-out cost gate below, which now runs against real data instead of its fallback profile. **Superseded by design, not yet migrated (2026-07-07)** — the Autonomy arc's [observability ledger and console](https://github.com/alexherrero/agentm/wiki/agentm-autonomy) retargets this capture off the vault onto a device-local JSONL event log, since the vault is curated knowledge on a Google Drive mount and fleet-scale machine records would flood it. `PLAN-observability-ledger` (agentm-side, staged) carries the actual code move — the writer/reader repoint, the vault write's retirement, and the `session-cost` memory kind going vestigial. Until that plan lands, the vault write above is still what's live.
- **Periodic review *(designed, still gated)*** — the memory engine's **dreaming pass** (its periodic reflection / consolidation cycle) reviews the accumulated `session-cost` records to surface an efficiency *trend* — flagging when token use creeps up over time. This turns token-audit from a point-in-time lookup into a longitudinal signal on the **`efficient`** opinion, but it cannot build before the dreaming pass itself does. A correctly-gated stub shipped 2026-07-07 alongside the capture half (`dreaming_trend_stub.py`) — `dreaming_pass_available()` is hard-`False`, so `review_efficiency_trend()` always returns a clean no-op; the trend-analysis logic itself stays **`[PENDING-IMPL]`**, gated on Wave E's dreaming pass.

### The automation layer (designed, not built)

Four additions realize the operator's efficiency protocol (proven manually in the Mythos readiness run — `<vault>/projects/agentm/_harness/mythos-readiness-handoff/PROMPTS.md` + `PROMPTS-NEXT.md`) as capability, not hand-discipline:

- **Budget readout on the status line.** `status_line_meter.py` already renders a per-session cost badge; this adds a **5-hour-window sum** and a **weekly sum** against an operator-configured budget ceiling, degrading the same way the existing badge does — missing config omits the readout, never an error.
- **Pre-flight fan-out cost gate.** Before any multi-agent dispatch, estimate spend = agent-count × observed per-agent cost (drawn from this capability's own `session-cost` records via `analyzer.py`), compared against a configured share of the remaining 5h-window or weekly budget. Below threshold: proceed silently. Above it: **confirm-or-block**, and the output always states **model × agent-count × estimated cost**, so the spend is visible before it happens — the direct fix for the Mythos failure mode (a 112-agent fleet that exhausted the session limit mid-run with no pre-flight estimate in front of the operator). Stated honestly: this is **local, deterministic accounting from transcripts** — hooks cannot read Anthropic's actual remaining quota, so the gate estimates, it never guarantees. **Advisory-only in unattended runs (2026-07-07 ruling, [agentm-autonomy](https://github.com/alexherrero/agentm/wiki/agentm-autonomy)):** confirm-or-block stays for interactive sessions where a human is present to answer; an unattended run gets announce-and-proceed — the estimate is logged as a ledger event, never blocking. The subscription window's own rate limit is the accepted backstop for an unattended runaway, not this gate.
- **`/handoff-pack` command.** Generalizes the Mythos `PROMPTS.md` pattern: snapshots an expensive session's outputs into a vault handoff directory alongside paste-ready prompts. Each prompt carries a **machine-readable tier/model label** alongside the hand-authored annotation, which lets a downstream consumer (including the `/work` escalation tripwire development-lifecycle's amendment adds) write entries in the same format instead of inventing its own.
- **Routing-conformance report.** A new section in `/token-audit` output: a post-hoc read of model-used vs. work-type against this capability's own versioned table (above), plus a count of **announcement-rule violations** — dispatches with no announced model — cross-referencing the mandatory fan-out announcement [development-lifecycle](crickets-development-lifecycle.md)'s amendment adds at the dispatch site.

All four are `[PENDING-IMPL]`; `PLAN-efficiency-automation` stages the build.

### Opinions it consumes

token-audit is **the measurement half of `efficient`.** The opinion is the judgment — *cheap as the job allows, above the quality floor*; this capability is the deterministic cost truth that judgment needs to be real and not a vibe. The automation layer above (the fan-out gate, the conformance report) is more of the same arrow, not a new one: it makes the `efficient` judgment enforceable at the point of dispatch instead of only visible after the fact. The arrow stays one-way: `efficient` (and the model-routing discipline it backs) cites this capability's numbers; the capability never reaches up into the opinion. *(Hardwired today; requesting `efficient` by name is the Phase-3/4 registry work — the [Opinions design](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates).)*

## Dependencies

- **standalone** — `requires: []`; ships alone.
- **serves the `efficient` opinion** ([agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates)) — the measurement slice; the budget + quality floor live in agentm.
- **couples to the agentm memory engine** — the auto-on-stop capture writes a `session-cost` memory record (**delivered** 2026-07-07, **superseded by design** — see the ambient-capture bullet above); the dreaming-pass review remains designed, unchanged in its own gating on the dreaming pass.
- **(designed) feeds the agentm-side [observability ledger](https://github.com/alexherrero/agentm/wiki/agentm-autonomy)** — once `PLAN-observability-ledger` lands, this capability's writer/reader retarget from the vault to that design's device-local JSONL ledger; the fan-out gate reads the ledger's rollup instead of vault entries.
- **(designed) hosts the versioned routing table** that instantiates [model-effort-routing](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing)'s tier scale in concrete model ids — the tier + effort *structure* is that design's policy; the concrete, refreshable "which real model" mapping lives here, colocated with `pricing.py`'s per-model rates since both must agree on spelling.
- **(designed) enhances [development-lifecycle](crickets-development-lifecycle.md)** — a new `enhances:` edge (declared on token-audit, per the composition convention) carrying the fan-out cost gate, the mandatory-announcement contract its dispatch points rely on, and the versioned routing table itself.
- **(forward-referenced) the pricing-drift mitigation** is the `content-refresh` primitive — tentatively homed in [maintenance](crickets-maintenance.md) as an optional scheduled task — which would periodically re-pin `pricing.py` **and** the routing table from source (post-review pass to confirm its home + author it).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md).

## Migrations

- **The `status-line-meter` fold** — `status_line_meter.py` moves in; its standalone `enhances:` edge dissolves and becomes internal. One capability owns measurement + metering.
- **The v6.0 rename** `token-audit` → **`tokens`** (object-over-action); the group declares both names so existing references resolve (the [composition](crickets-composition.md) rename mechanism). The `efficiency` rename was **rejected** — it collides with the `efficient` opinion the capability's own tools request, and inverts the one-way rule (a capability naming itself after the opinion it serves).
- **Sibling audits, not a widened scope** — other efficiency dimensions (latency, memory) get their own audit tools; this one stays token-cost.

## Risks & open questions

- **All shipping primitives delivered** — `/token-audit`, `analyzer.py`, `pricing.py`, `status_line_meter.py`; the fold + rename are mechanical. Ambient capture is now delivered too (2026-07-07, above). The automation layer (budget readout, fan-out gate, `/handoff-pack`, routing-conformance, the versioned routing table) and the periodic review remain the designed additions (above) — note some automation-layer primitives (the fan-out gate, `/handoff-pack`) have since shipped under `PLAN-efficiency-automation`; that plan's own doc reconciliation is tracked separately, out of scope here.
- **Hosting the model-id table here, not in model-effort-routing, trades a policy/data split for a single source of truth.** An operator has to follow a pointer from the tier chart to the concrete table; the alternative (keep them together) was rejected because it re-creates a second place a model id can drift from `pricing.py`'s spelling.
- **The fan-out gate is an estimate, not a guarantee.** Hooks cannot read Anthropic's real remaining quota; the gate's local accounting from `session-cost` records can drift from the true billed number, especially early (few records) or after a pricing change (see the `pricing.py`-drift risk below). State this honestly in the gate's own output, not just here.
- **`pricing.py` (and now the routing table) drift against real rates** — a pinned table goes stale when a vendor reprices or renames a model; the single-source design keeps the fix to one file per concern, but the re-pin is manual today. The standing mitigation is the **`content-refresh`** primitive — tentatively homed in [maintenance](crickets-maintenance.md) as an optional, scheduled task — which would automate the re-pin of both files together; confirm its home + author it at the post-review pass.
- **The capture/review split was a coupled bet on timing; the capture side shipped as the wave pull-forward.** The Stop-hook capture shipped independent of the dreaming pass (2026-07-07) — useful on its own, since the fan-out gate needed it — pulling forward implementation the roadmap had scoped later; that pull-forward is now shipped, not just proposed.
- **Re-audit triggers:** stand up the content-refresh capability to automate the `pricing.py` + routing-table re-pin (manual re-pin until then); wire the dreaming-pass review when the memory engine's relevant wave ships; migrate the fan-out gate + conformance report from hardwired to `opinion_request('efficient')` when the Wave-B opinion registry lands; execute the `status-line-meter` fold + the `tokens` rename at v6.0; add Gemini/Antigravity rows to the routing table when that side of the portfolio needs its own consumption path; replace the local cost estimate with ground truth if a host ever exposes real per-session quota telemetry.

## References

- crickets `src/token-audit/` + `src/status-line-meter/` (the folding-in source) — `/token-audit` · `analyzer.py` · `pricing.py` · `status_line_meter.py`; declares `[token-audit]` (→ `[tokens]`)
- **Up / serves:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates) (`efficient`)
- **Hosts / enhances:** [model-effort-routing](https://github.com/alexherrero/agentm/wiki/agentm-model-effort-routing) (the tier + effort policy this table instantiates in concrete model ids) · [development-lifecycle](crickets-development-lifecycle.md) (the fan-out gate + announcement contract + the table itself)
- **Superseded (designed) by:** [agentm-autonomy](https://github.com/alexherrero/agentm/wiki/agentm-autonomy) — the observability ledger the session-cost capture retargets to
- **Worked example:** `<vault>/projects/agentm/_harness/mythos-readiness-handoff/PROMPTS.md` + `PROMPTS-NEXT.md` — the manual protocol this automates

## Amendment log

**2026-07-07 — the ambient capture is superseded by design, not yet migrated (AA2, agentm-side Autonomy arc).** Operator review of the Autonomy arc's budget-governor draft dropped its enforcement machinery (a subscription plan has no surprise bill; the window rate limit is the accepted backstop) and moved the `session-cost` capture off the vault onto a device-local JSONL ledger — see [agentm-autonomy](https://github.com/alexherrero/agentm/wiki/agentm-autonomy). The pre-flight fan-out gate is demoted to advisory-only for unattended runs (confirm-or-block stays for interactive sessions). Neither change is code yet — `session_cost_writer.py`/`session_cost_reader.py` still target the vault as described below, and the gate still confirms-or-blocks everywhere, until agentm's `PLAN-observability-ledger` lands the retarget. *Re-audit trigger:* flip this capability's own capture description + gate behavior to as-built when that plan ships.

**2026-07-07 — ambient capture shipped + a correctly-gated periodic-review stub (`PLAN-wave-d-tokens-and-privacy`, [crickets #166](https://github.com/alexherrero/crickets/pull/166)).** `session_cost_writer.py` + the `session-cost-capture` Stop hook log a per-model `session-cost` record on session close (graceful no-op with no memory backend, never blocking close); `session_cost_reader.py` closes the read-side loop so the pre-flight fan-out cost gate now runs against real records instead of its `DEFAULT_AGENT_USAGE_PROFILE` fallback. `dreaming_trend_stub.py` stages the periodic-review half as a correctly-gated dark stub — `dreaming_pass_available()` is hard-`False` (the dreaming pass is itself `[PENDING-IMPL]`), so no trend-analysis logic was written ahead of its own dependency. Also corrected a stale `governs:` frontmatter path (`src/token-audit/` → `src/tokens/`, the directory this doc's own Migrations section had already described as renamed). *Re-audit trigger:* wire the dreaming-pass review when the memory engine's relevant wave ships.

**2026-07-06 — the `session-cost` write target now exists (AG Wave B, agentm-side).** `session-cost` is a reserved `kind` value in agentm's V6-11 metadata table, shipped 2026-07-06 (see agentm's [memory index](https://github.com/alexherrero/agentm/wiki/agentm-memory-index) design) — the "it only needs a place to write" half of the ambient-capture bullet is now literally true, not aspirational. `PLAN-session-cost-capture` (the actual hook) is unaffected by this — still its own tracked plan.

**2026-07-04 — P11 v2: automate the efficiency protocol, home the versioned routing table here (operator pressure-test correction).** Adds the single-home versioned routing table (work-type → tier/model-id/effort, colocated with `pricing.py`), **rendered here with real seed values**, plus a `classify_work_type` classifier that resolves a dispatch or a staged plan to a table row (persona-declared tier → ad-hoc role-name match → an explicit `UNCLASSIFIED-DEFAULT` fallback, never a silent guess), splits the prior "ambient capture + periodic review" bullet into a **capture** half pulled forward now (flagged as a Wave-D pull-forward for the roadmap session to confirm, not decided here) and a **review** half unchanged and still gated on the dreaming pass, and adds the automation layer: a 5h-window + weekly budget readout on the status line, a pre-flight fan-out cost gate (deterministic local accounting, confirm-or-block, always stating model × agent-count × estimated cost), a `/handoff-pack` command carrying a machine-readable tier/model label per prompt, and a routing-conformance report counting announcement-rule violations. Also flags a live, already-fired instance of the content-refresh trigger this design names: the agent-def frontmatter + every command nudge still cite `claude-sonnet-4-6` / `claude-opus-4-8`, one day stale against `pricing.py`'s `claude-sonnet-5` row (same R0.7 pass); and names `claude-fable-5` explicitly as a recognized, deliberately-unrouted, premium-priced model id, so an `INHERITED` announcement naming it reads as the Mythos failure shape on sight. *Why not home the table in model-effort-routing instead (the earlier draft's choice):* that design already has to publish the tier scale as a stable, host-portable policy; pinning volatile model-id strings into the same table couples two things with different change cadences, and — more concretely — creates a second place a model-id string can be spelled, which has to stay byte-identical to `pricing.py`'s spelling for the fan-out gate's cost math to be correct. Colocating removes that second copy entirely. *Why not wait for the dreaming pass before building capture:* the fan-out gate needs `session-cost` records now, and capture doesn't need a reader to be worth writing. *Why not let the table itself double as the classifier (skip the separate function):* the table answers "what does this work-type get," the classifier answers "which work-type is this" — collapsing them would silently guess a work-type from a model choice instead of naming the unmatched case, exactly the failure mode `UNCLASSIFIED-DEFAULT` exists to surface. *Re-audit triggers:* roadmap session either confirms or reschedules the Wave-D pull-forward; wire the dreaming-pass review when its wave ships; replace the local cost estimate with ground truth if a host ever exposes real per-session quota telemetry; re-pin the table + `pricing.py` together on every model release via `content-refresh`; bump the agent-def + command-nudge roster to `claude-sonnet-5` (tracked here, executed in `PLAN-efficiency-automation`).

**2026-06-28 — lock-down sweep (operator review).** Converted the primitives mermaid to a house-style hand-SVG (`diagrams/crickets-token-audit.svg`); and restored the missing `## Amendment log` heading (the design had none). Confirmed token-audit is the measurement half of the `efficient` opinion (`/token-audit` + the live meter over `pricing.py`'s pinned rates; `analyzer.py`'s cache split · 5h windows · floor), and that the session-cost → dreaming → efficiency-trend chain is designed. Locked as a v5–v8 guidepost.

**2026-06-23 — authored, reviewed, and finalized.** Authored from the seeded stub and grounded against the live `src/token-audit` + `src/status-line-meter` plugins. token-audit is the **measurement half of `efficient`** — a deterministic cost analyzer (cache split · 5-hour windows · the always-load floor; same transcript → same number) behind two surfaces: the on-demand `/token-audit` breakdown and the passive live meter (folding in `status_line_meter.py`); `pricing.py` is the single pinned rate source. The `### Opinions` arrow is one-way (the opinion cites the numbers; the capability never reaches up). Recorded the rejected `efficiency` rename and the v6.0 `tokens` target (resolver aliasing).

On review: added a **How it's invoked** subsection — three altitudes (passive live meter · operator-invoked `/token-audit` · a *designed* auto-capture-on-session-stop that logs a per-model `session-cost` memory record, reviewed in the **dreaming** pass to surface an efficiency trend; `[PENDING-IMPL]`) — and reframed the **`pricing.py`-drift** risk to forward-reference the **`content-refresh`** primitive (tentatively homed in `maintenance` as an optional scheduled task) as the standing re-pin mitigation. **Re-audit:** build the auto-capture + dreaming review; stand up `content-refresh` to automate the `pricing.py` re-pin; execute the `status-line-meter` fold + the `tokens` rename at v6.0.
