---
title: diagnostics — design
status: launched
kind: design
scope: feature
area: crickets/diagnostics
governs: [src/diagnostics/]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-23
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23) · locked 2026-06-28 (final AG design sweep).** child-design — **the `diagnostics` capability** (failure analysis + hypothesis generation + cross-session failure-pattern memory), parent [crickets HLD](crickets-hld.md). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# diagnostics

## Objective

`diagnostics` is the capability that **makes sense of failures**. When something breaks — a CI run, a test, a stack trace at runtime — it reads the output, classifies the failure, proposes ranked hypotheses for the cause, and **remembers the pattern** so the next occurrence is faster to resolve. It is the Troubleshooter/SRE persona's composition. It is a **diagnosis engine** — it analyzes and remembers, it never fixes; repair is a caller's job (`development-lifecycle`'s `/bugfix`, `maintenance`'s dependency fixer). It pairs the observability command `/observe` with a failure-analysis engine.

## Overview

Diagnosis runs as a loop:

- **observe** — instrument the system so a failure leaves usable signal (`/observe`, *delivered*).
- **diagnose** — when it breaks, read the logs, classify the failure, and propose ranked hypotheses (`/diagnose`, *delivered 2026-07-06*).
- **remember** — write the failure as an incident to memory, so the pattern is recallable.
- **recall** — on the next failure, surface prior similar incidents before re-deriving.

The failure-diagnosis engine depends on agentm's **memory system** — cross-session failure-pattern memory is the recall engine put to work.

![Layered failure analysis: a failure (CI · test · runtime) → Layer 0 classify (build/test/type/lint/runtime) → Layer 1 fingerprint (exact-match); a hit returns the prior incident + fix with zero inference, a miss falls back to Layer 2 semantic search (RRF + graph hop) which aliases back to fingerprint; both feed ranked hypotheses, then a failure-incident memory is written (scrubbed by privacy)](diagrams/crickets-diagnostics.svg)

*Deterministic-first: classify, then a fingerprint exact-match (a hit returns the prior fix with zero inference); only a miss falls to semantic recall; the incident is scrubbed + written, and a drifted match aliases back so the next recurrence is an exact hit. As-built (2026-07-06): the diagram's Layer 2 "RRF + graph hop" is the diagram's original aspiration, not what shipped — see the `/diagnose` section and the amendment log below.*

## Design

### `/observe` — the instrumentation side *(delivered)*

The discipline for *adding* observability to code, so a failure leaves usable signal for `/diagnose` to read.
- *Entry:* invoked when instrumenting a production path — typically while building a feature, and again from `/launch` before go-live.
- *Exit:* structured logging, RED metrics (rate · errors · duration), OpenTelemetry spans, and symptom-based alerts wired; a test request confirms metrics emit.
- *Automated:* log events (not strings); RED metrics on new paths; trace spans; symptom-based alerting (an infra-only alert with no symptom check is rejected).
- *Artifacts:* none in memory — `/observe` instruments the codebase itself.

*(`/observe` lives here; `/launch` in [development-lifecycle](crickets-development-lifecycle.md) calls it before go-live — a soft cross-capability reference.)*

### `/diagnose` — the failure-diagnosis engine *(delivered 2026-07-06)*

Takes a failure and returns ranked causes, remembering each one. It never mutates code — it emits hypotheses and logs an incident; the fix is a caller's.
- *Entry:* `/diagnose <log-or-failure-input>` — invoked when something breaks (a red CI run, a failing test, a runtime stack trace), directly or by a repair caller.
- *Exit:* the failure classified, 2–3 ranked hypotheses (each with a confidence signal + a suggested next probe), and one failure-incident written to memory.
- *Automated:* the recall ladder below — **classify → recall (fingerprint-first) → generate → write** — never a fix.
- *Enhancements:* hypothesis verification — ask the adversarial reviewers *real bug, or an assumption?* ([code-review](crickets-code-review.md)).
- *Artifacts:* one `kind: failure-incident` memory entry per run, via the save path → the configured memory backend (the device-local store, or `<vault>/…` when agentm is mounted).

**Shipped 2026-07-06** (PLAN-wave-c-diagnostics, [crickets #153](https://github.com/alexherrero/crickets/pull/153)) — `src/diagnostics/scripts/classify.py` (namespace from exit code/tool/structured output, no inference) + `diagnose.py` (the end-to-end pipeline) + `commands/diagnose.md`. Hypothesis generation is deterministic, not an LLM call: a Layer-2 candidate ranks by its recall score; a cold-start miss falls back to a generic namespace/error-class hypothesis. See the recall-ladder section below for what Layer 2 actually calls.

### Cross-session failure-pattern memory

`/diagnose` doesn't re-reason from scratch each time — it **recalls deterministically first, and infers only when nothing matches**. The recall ladder, over a corpus of **`kind: failure-incident`** entries:

- **Layer 0 — classify (free, deterministic).** Read the error namespace — `build` · `test` · `type` · `lint` · `runtime` — from the exit code, the emitting tool, and parsed structured output (a rule id like `TS2345`, a failing-test id, an exception class). No inference; the cheapest layer, and it picks the fingerprint's namespace.
- **Layer 1 — fingerprint exact-match (the "seen this exact failure?" lookup).** Normalize the error signature from stable fields only — error class + the top in-app frame(s) (file basename · symbol · line), with volatile tokens stripped (absolute paths, PIDs, timestamps, hashes, addresses) — and hash it (`fingerprint`, with a versioned `fp_algo`). **As-built (2026-07-06):** `save_entry(fingerprint=...)` (agentm [#234](https://github.com/alexherrero/agentm/pull/234)) does write `fingerprint` as a frontmatter key, populating the real indexed `entry_meta.fingerprint` column — but that column only updates on an async `drain` cycle, too late to guarantee an *immediate* same-fingerprint-hit within one session. Layer-1's actual read path is a diagnostics-owned sidecar (`<vault>/_meta/diagnostics-fingerprints.json`, keyed `<project>::<fingerprint>` → entry path), written synchronously by the same call that writes the incident. `entry_meta.fingerprint` still gets a real value for other future SQL-side consumers; diagnostics itself never reads it back. Either way: an exact-match lookup returning the prior incident **with zero inference**, short-circuiting Layer 2 entirely on a hit.
- **Layer 2 — semantic fallback (only on a miss).** A genuinely new or drifted failure falls through to the V6 hybrid path: an exact metadata prefilter (`kind: failure-incident` · project · `status: active`), then a similarity/keyword merge. **As-built:** this calls agentm's existing `recall.query()` as-is — a linear-weighted merge (`sim*0.7 + keyword*0.3`), not literal RRF fusion, and no knowledge-graph hop (neither is implemented anywhere in agentm's recall engine today, despite this section's original framing). Building true RRF fusion + a `same-root-cause`/`supersedes` graph hop is real future work, not something this build silently dropped — it was never there to call.

**It gets more deterministic with use.** When Layer 2 finds a drifted match that is the same failure, the new signature attaches as an additional `fingerprint` alias on the existing incident — so the next recurrence collapses to a Layer-1 exact hit. The corpus leans *less* on inference over time, not more. The flip side is the **cold start**: a genuinely new failure — or an empty corpus — gets pure Layer-2 inference, so the deterministic win is *recurrence-only*. Early on, diagnostics is an LLM diagnoser with a growing memory; it sharpens as the corpus fills — the same accumulate-and-compound curve as the rest of memory.

A failure-incident is one markdown entry (symptom · root cause · fix/workaround · outcome), `kind: failure-incident` — a new kind, distinct from `kind: fix` because an incident may have no fix yet — superseded via the existing `evolve` primitive. It leans on the **agentm memory engine by name** (`recall` + the metadata table + the save path), one-way; agentm never depends back on diagnostics. Because the body is captured from logs + stack traces, it is **deterministically scrubbed** of secrets and PII before it lands — a regex/pattern pass (the [privacy](crickets-privacy.md) scrubber), never an LLM judgment and never optional on a log capture.

**Shipped 2026-07-06** (PLAN-wave-c-diagnostics) — the fingerprint normalizer (`fingerprint.py`), the recall ladder (`classify.py` + `recall_ladder.py` + `fingerprint_index.py`), the self-reinforcing alias mechanism, the scrubbed writer (`writer.py`), and `/diagnose` (`diagnose.py`) all landed together, [crickets #153](https://github.com/alexherrero/crickets/pull/153). See the Layer-1/Layer-2 bullets above for the as-built architecture (a sidecar for Layer-1, not `entry_meta.fingerprint` directly; no RRF/graph-hop in Layer-2).

### Scheduled health passes (designed)

A scheduled pass could run health checks against projects during idle/dream cycles and append a report — still diagnosis, not repair. This leans on agentm's **scheduler**, which is designed-not-built (the [Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)). `diagnostics` names the interface and defers the slice.

**`[PENDING-IMPL]`** — build the scheduled health pass once the agentm scheduler ships (documenter); on-demand `/diagnose` ships first.

### The boundary — a diagnosis engine, never a repairer

`diagnostics` analyzes and remembers; it **never fixes**. Repair is always a **caller's** job, by composition:

- **`maintenance`** (the renamed `github-ci`) owns reactive known-breakage repair — its `dependabot-fixer` calls the diagnose engine to classify a red-CI failure, then runs its own bounded dependency-fix loop.
- **`development-lifecycle`** owns defect repair — `/bugfix` may call the diagnose engine for its Analyze step, then fixes under the loop.

The shape they share is find-cause → fix → verify — a shared *shape*, not a shared *concern*. The lock: **`diagnostics` = the engine; `maintenance` + `development-lifecycle` = the callers; no capability both diagnoses and repairs.** This is also where `github-ci`'s reframe lands — `maintenance` is the caller-home for dependency repair, `diagnostics` is the primitive-home for diagnosis.

### First slice

On-demand `/diagnose`: classify → recall (fingerprint-first) → rank hypotheses → log a `failure-incident` — **shipped 2026-07-06**. Scheduled health passes remain deferred (see below) — they now wait only on being built, `/diagnose` having landed to have something to schedule.

### Opinions it consumes

diagnostics **requests `how-we-engineer` by name** — `writer.py`'s `_build_body()` calls `opinion_resolve("how-we-engineer")` (via `agentm_bridge.py`'s path-fallback to agentm's `opinion_resolver.py`) and folds the resolved base+supplement into the written incident's `## Opinion: how-we-engineer` section; its deterministic-first discipline (classify before hypothesize, recall before infer) is that opinion applied to diagnosis. Graceful-skip (the section is simply omitted) when agentm is unresolvable — never blocks the incident write. It also composes code-review's **`good`** when it asks the reviewers to verify a hypothesis — that binding stays hardwired prose today; the markdown-prose consumer grammar it would need is a separate, unlocked design gap (see [agentm-opinion-registry.md](https://github.com/alexherrero/agentm/wiki/agentm-opinion-registry)'s Migrations section).

## Dependencies

- **enhances `development-lifecycle`** (soft) — failure analysis strengthens `/review` and `/work`; `/bugfix`'s Analyze step may call the diagnose engine.
- **composed by `maintenance`** — `dependabot-fixer` calls the diagnose engine, then runs its own dependency-fix loop (the repair stays in the caller).
- **enhances `code-review`** (soft) — diagnosis can ask the adversarial reviewers to verify a hypothesis.
- **enhanced by `privacy`** — incident bodies are run through privacy's **deterministic** secret/PII scrubber before the memory write. **Shipped 2026-07-07:** `writer.py` calls privacy's `scrub_text()` (`src/privacy/scripts/scrub_text.py`, a bridge to agentm's `privacy_scrub.scrub_pii()`) explicitly and visibly at the write site — redundant-but-idempotent alongside agentm's own mandatory `save_entry()`-level `scrub_pii()` gate for `kind="failure-incident"`, so the write path stays correct even if that internal gating ever changes.
- **leans on the agentm memory engine by name** — `recall` + the **V6-11 SQLite metadata table** (the fingerprint index) + the save path; one-way, agentm never depends back. Introduces the `failure-incident` kind into the open `kind` taxonomy ([agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)).
- **leans on the agentm scheduler** (designed-not-built) for the scheduled-health slice only ([Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md); the Troubleshooter/SRE persona is in [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas).

## Risks & open questions

- **Fingerprint mis-calibration — determinism cuts both ways.** A too-loose signature **under-groups** (two distinct failures share a `fingerprint` → Layer-1 confidently returns the *wrong* prior fix); a too-tight one **over-groups** (a real recurrence misses and silently degrades to inference). Determinism makes a bad fingerprint *more* dangerous than a fuzzy semantic match — it's served with confidence and short-circuits the fallback. A Layer-1 hit is therefore a **strong prior, not gospel** — the hypotheses are still verified — backed by a human/auto fingerprint override + the alias mechanism. The `fp_algo` normalization is the lever: who owns the volatile-token strip list, and bumping `v1 → v2` invalidates + re-derives the corpus's fingerprints — settle ownership + cadence before incidents accrete.
- **Secrets / PII in incidents — a deterministic scrub on write is mandatory.** Logs + stack traces routinely carry tokens, keys, absolute paths, PII; an incident write persists them. Every write runs through privacy's **deterministic** scrubber first (regex/pattern, not LLM judgment) — never optional on a log capture. **Shipped 2026-07-07** — `writer.py` calls privacy's `scrub_text()` explicitly before every `kind: failure-incident` write (see Dependencies, above).
- **Layer-1 must be project-scoped.** Two projects sharing an error class + frame must never collide. **As-built:** the sidecar keys on `<project>::<fingerprint>`, so this is resolved at the storage layer, not via a SQL `WHERE` clause — `entry_meta`'s own `project` column (derived from the entry's `group:` frontmatter) also scopes it for any future SQL-side consumer.
- **The greenfield is real** — the diagnose engine + the recall ladder were the heaviest build of the new capabilities; now shipped.
- **`/bugfix` coupling is a phasing call** — composition is the design; whether `/bugfix`'s Analyze wires to the engine on day one or after diagnostics proves out is still a build-phase decision, deliberately out of scope for the first slice.
- **The scheduled slice is blocked** on the unbuilt agentm scheduler — named and deferred, unchanged by this ship.
- **RRF fusion + the knowledge-graph hop are not built** — Layer 2 calls agentm's existing linear-weighted `recall.query()` as-is. Real future work if Layer-2 recall quality proves insufficient in practice, not a silently-dropped requirement of this slice.
- **Re-audit triggers:** calibrate the fingerprint (over/under-grouping) on a real incident corpus and settle `fp_algo` version-bump ownership; add a **failure-incident retention / consolidation** policy (one-off incidents accrete as noise) before volume; decide whether Layer 2 needs real RRF + a graph hop once usage reveals whether the linear-weighted merge under-performs; sequence the **engine before its callers** (`dependabot-fixer` + `/bugfix` keep inline diagnosis until they're wired to call the engine); confirm `maintenance` is the dependency-repair caller-home when the `github-ci` rename lands.

## References

- **The observability command:** `/observe` (`observe.md`) — the instrumentation discipline
- **The memory substrate it leans on:** agentm `harness/skills/memory/scripts/{recall,save,vec_index}.py` via `src/diagnostics/scripts/agentm_bridge.py` (siblings-not-layers path-fallback, mirroring `find_process_seam.py`) · the **V6-11 SQLite metadata table** (the `fingerprint` exact-match column, populated by `save.py` but read back by other future consumers, not by diagnostics' own Layer-1 — see the Layer-1 bullet above) — [agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)
- **The scheduler (designed-not-built):** [agentm Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)
- **Siblings:** [crickets HLD](crickets-hld.md) · [development-lifecycle](crickets-development-lifecycle.md) (`/observe`'s caller via `/launch`; `/bugfix` calls the engine) · `maintenance` (the renamed `github-ci`; `dependabot-fixer` calls the engine) · [composition](crickets-composition.md) · [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas) (Troubleshooter/SRE) · [agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)

## Amendment log

**2026-07-07 — the incident-body scrub surface shipped (`PLAN-wave-d-tokens-and-privacy`, [crickets #166](https://github.com/alexherrero/crickets/pull/166)).** `writer.py` now calls privacy's `scrub_text()` explicitly at the crickets call site before every `kind: failure-incident` write — closing the gap this doc had flagged (privacy scrubbed git ranges only). A design finding surfaced during that plan's build, worth recording here since it changes what "mandatory" meant in practice until this shipped: agentm's `save_entry()` already ran a mandatory `scrub_pii()` gate for `kind="failure-incident"` one layer down (landed 2026-07-05), so incident writes were already scrubbed transitively even before this explicit call site existed — the explicit call is a second, redundant-but-idempotent scrub, not the sole one. *Re-audit trigger:* none open on this surface.

**2026-07-06 — `how-we-engineer` now requested by name (PLAN-wave-d-opinion-wiring task 1).** `writer.py`'s `_build_body()` calls `agentm_bridge.opinion_resolve("how-we-engineer")` (a new bridge function, path-fallback to agentm's top-level `scripts/opinion_resolver.py`, distinct from the existing memory-engine bridge dir) and folds the resolved base+supplement into a `## Opinion: how-we-engineer` section in every written incident. Graceful-skip (section omitted) when agentm is unresolvable, matching the resolver's own never-raise contract — the incident write is never blocked on this. `good` (composed via code-review when verifying a hypothesis) stays hardwired prose; it has no runtime render step to wire into, the same gap the registry design's Migrations section now documents for 7 other bindings across the portfolio. *Re-audit trigger:* revisit if a markdown-prose consumer grammar is ever locked, extending real wiring to the `good` composition too.

**2026-07-06 — `/diagnose` shipped (PLAN-wave-c-diagnostics, [crickets #153](https://github.com/alexherrero/crickets/pull/153); agentm [#234](https://github.com/alexherrero/agentm/pull/234)).** All `[PENDING-IMPL]` markers on the engine flip — the fingerprint normalizer, the classify → recall → rank → write pipeline, the self-reinforcing alias mechanism, and the scrubbed writer all landed together. Two real divergences from this doc's original framing, corrected here rather than silently: (1) Layer-1's actual read path is a diagnostics-owned sidecar (`<vault>/_meta/diagnostics-fingerprints.json`), not `SELECT ... WHERE fingerprint = :fp` against `entry_meta` — that column only populates on an async `drain`, too late for an immediate same-fingerprint-hit guarantee; `entry_meta.fingerprint` still gets a real value (agentm #234 added it as an optional frontmatter field) for other future SQL-side consumers, just not for diagnostics' own read path. (2) Layer 2 calls agentm's existing `recall.query()` (a linear-weighted `sim*0.7 + keyword*0.3` merge) as-is — no RRF fusion, no knowledge-graph hop; neither exists in agentm's recall engine today, so this was never something to call, not something dropped. The scheduled health pass (line "Scheduled health passes") remains deliberately out of scope. *Re-audit trigger:* revisit whether Layer 2 needs real RRF + a graph hop once usage reveals whether the linear-weighted merge is good enough in practice.

**2026-07-06 — cleared both substrate blockers (AG Wave B, wiki-authorship pass on agentm's side).** V6-11 (the indexed `fingerprint` + `project` columns Layer-1 needs) and the agentm runner (what a future scheduled health pass would fire on) both shipped 2026-07-06 — see agentm's [memory index](https://github.com/alexherrero/agentm/wiki/agentm-memory-index) and [runner](https://github.com/alexherrero/agentm/wiki/agentm-runner) designs. Neither was this capability's own build — the diagnose engine, the fingerprint normalizer, and the recall ladder remain greenfield — but downgrading "designed, blocked on unbuilt substrate" to "designed, own build still ahead" throughout this doc reflects that the blockers are gone, not that diagnostics itself shipped. Also resolved the project-scoping risk this doc had flagged as a fingerprint-string-folding problem: V6-11's `project` column lets Layer-1 filter on it directly instead. *Re-audit trigger:* flip `[PENDING-IMPL]` when the engine + ladder ship.

**2026-06-28 — lock-down sweep (operator review).** Converted the failure-analysis mermaid to a house-style hand-SVG (`diagrams/crickets-diagnostics.svg`). Confirmed the layered pipeline (classify → fingerprint exact-match → hit/zero-inference or semantic fallback → ranked hypotheses) and the `failure-incident` memory scrubbed by `privacy`. No content change. Locked as a v5–v8 guidepost.

**2026-06-23 — added the recall-ladder diagram (diagram backfill).** Per the every-design-carries-a-diagram rule.

**2026-06-23 — added an Opinions-it-consumes clause (portfolio backfill).** Made explicit which opinions diagnostics leans on (`how-we-engineer`; `good` via code-review) — a standard Design clause adopted across the capability designs.

**2026-06-23 — authored, reviewed, and finalized.**

The `diagnostics` capability: a **diagnosis engine that never fixes** — `/observe` (instrumentation, delivered) + `/diagnose` (failure analysis, greenfield). When something breaks it classifies the failure, ranks hypotheses, and logs a `kind: failure-incident` to memory. Repair is a **caller's** job by composition — `maintenance` (the renamed `github-ci`, via `dependabot-fixer`) and `development-lifecycle` (`/bugfix`) call the engine; no capability both diagnoses and repairs. (Why not a `diagnostics-and-repair` merge: it re-creates the seam the lifecycle merge just removed, `/bugfix` is loop-wired, and dependency-repair is a `maintenance` concern.) `/observe`'s home is settled here.

Cross-session failure memory is a **deterministic-first recall ladder**: Layer 0 classify (build/test/type/lint/runtime) → Layer 1 `fingerprint` exact-match via the **V6-11** indexed column (zero-inference short-circuit) → Layer 2 semantic fallback (RRF + a graph hop), with self-reinforcing fingerprint aliases (more deterministic with use), on a new **`kind: failure-incident`**. Risk-hardened against its own failure modes: fingerprint **mis-calibration** (a Layer-1 hit is a strong prior, not gospel), a **mandatory deterministic PII/secret scrub** on incident-write (privacy's regex/gitleaks scrubber — a `[PENDING-IMPL]` incident-body surface), and **project-scoped Layer-1** (the V6-11 `project` column resolves this — see Risks). **Built-vs-designed:** `/observe` delivered; **V6-11 shipped 2026-07-06** (the `fingerprint` + `project` columns Layer-1 needs exist now) and **the agentm runner shipped the same day** (so a future scheduled health pass has something to run on) — **the diagnose engine + recall ladder themselves stay greenfield**, no longer blocked on either substrate. **Re-audit triggers:** calibrate the fingerprint + settle `fp_algo` ownership; ship the privacy incident-scrub surface before the first write; add a failure-incident retention policy; sequence the engine before its callers; flip `[PENDING-IMPL]` as the engine lands; confirm `maintenance` is the dependency-repair caller-home at the `github-ci` rename.
