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
- **diagnose** — when it breaks, read the logs, classify the failure, and propose ranked hypotheses (`/diagnose`, *greenfield*).
- **remember** — write the failure as an incident to memory, so the pattern is recallable.
- **recall** — on the next failure, surface prior similar incidents before re-deriving.

The failure-diagnosis engine depends on agentm's **memory system** — cross-session failure-pattern memory is the recall engine put to work.

![Layered failure analysis: a failure (CI · test · runtime) → Layer 0 classify (build/test/type/lint/runtime) → Layer 1 fingerprint (exact-match); a hit returns the prior incident + fix with zero inference, a miss falls back to Layer 2 semantic search (RRF + graph hop) which aliases back to fingerprint; both feed ranked hypotheses, then a failure-incident memory is written (scrubbed by privacy)](diagrams/crickets-diagnostics.svg)

*Deterministic-first: classify, then a fingerprint exact-match (a hit returns the prior fix with zero inference); only a miss falls to semantic recall; the incident is scrubbed + written, and a drifted match aliases back so the next recurrence is an exact hit.*

## Design

### `/observe` — the instrumentation side *(delivered)*

The discipline for *adding* observability to code, so a failure leaves usable signal for `/diagnose` to read.
- *Entry:* invoked when instrumenting a production path — typically while building a feature, and again from `/launch` before go-live.
- *Exit:* structured logging, RED metrics (rate · errors · duration), OpenTelemetry spans, and symptom-based alerts wired; a test request confirms metrics emit.
- *Automated:* log events (not strings); RED metrics on new paths; trace spans; symptom-based alerting (an infra-only alert with no symptom check is rejected).
- *Artifacts:* none in memory — `/observe` instruments the codebase itself.

*(`/observe` lives here; `/launch` in [development-lifecycle](crickets-development-lifecycle.md) calls it before go-live — a soft cross-capability reference.)*

### `/diagnose` — the failure-diagnosis engine *(greenfield)*

Takes a failure and returns ranked causes, remembering each one. It never mutates code — it emits hypotheses and logs an incident; the fix is a caller's.
- *Entry:* `/diagnose <log-or-failure-input>` — invoked when something breaks (a red CI run, a failing test, a runtime stack trace), directly or by a repair caller.
- *Exit:* the failure classified, 2–3 ranked hypotheses (each with a confidence signal + a suggested next probe), and one failure-incident written to memory.
- *Automated:* the recall ladder below — **classify → recall (fingerprint-first) → generate → write** — never a fix.
- *Enhancements:* hypothesis verification — ask the adversarial reviewers *real bug, or an assumption?* ([code-review](crickets-code-review.md)).
- *Artifacts:* one `kind: failure-incident` memory entry per run, via the save path → the configured memory backend (the device-local store, or `<vault>/…` when agentm is mounted).

**`[PENDING-IMPL]`** — build the classifier + symptom extraction + hypothesis generator (documenter flips to as-built when the engine lands); today nothing does failure analysis.

### Cross-session failure-pattern memory

`/diagnose` doesn't re-reason from scratch each time — it **recalls deterministically first, and infers only when nothing matches**. The recall ladder, over a corpus of **`kind: failure-incident`** entries:

- **Layer 0 — classify (free, deterministic).** Read the error namespace — `build` · `test` · `type` · `lint` · `runtime` — from the exit code, the emitting tool, and parsed structured output (a rule id like `TS2345`, a failing-test id, an exception class). No inference; the cheapest layer, and it picks the fingerprint's namespace.
- **Layer 1 — fingerprint exact-match (the "seen this exact failure?" lookup).** Normalize the error signature from stable fields only — error class + the top in-app frame(s) (file basename · symbol · line), with volatile tokens stripped (absolute paths, PIDs, timestamps, hashes, addresses) — and hash it (`fingerprint`, with a versioned `fp_algo`). Stored as a frontmatter key, it materializes as an **indexed column in the SQLite metadata table (V6-11)**, so recall is `SELECT path WHERE fingerprint = :fp` — an exact-match lookup that returns the prior incident + its fix **with zero inference**, short-circuiting the vector search entirely on a hit.
- **Layer 2 — semantic fallback (only on a miss).** A genuinely new or drifted failure falls through to the V6 hybrid path: an exact metadata prefilter (namespace · project · `status: active`) first, then sqlite-vec + BM25 fused by RRF, plus one knowledge-graph hop along a `same-root-cause` / `supersedes` edge to catch "same cause, drifted signature."

**It gets more deterministic with use.** When Layer 2 finds a drifted match that is the same failure, the new signature attaches as an additional `fingerprint` alias on the existing incident — so the next recurrence collapses to a Layer-1 exact hit. The corpus leans *less* on inference over time, not more. The flip side is the **cold start**: a genuinely new failure — or an empty corpus — gets pure Layer-2 inference, so the deterministic win is *recurrence-only*. Early on, diagnostics is an LLM diagnoser with a growing memory; it sharpens as the corpus fills — the same accumulate-and-compound curve as the rest of memory.

A failure-incident is one markdown entry (symptom · root cause · fix/workaround · outcome), `kind: failure-incident` — a new kind, distinct from `kind: fix` because an incident may have no fix yet — superseded via the existing `evolve` primitive. It leans on the **agentm memory engine by name** (`recall` + the metadata table + the save path), one-way; agentm never depends back on diagnostics. Because the body is captured from logs + stack traces, it is **deterministically scrubbed** of secrets and PII before it lands — a regex/pattern pass (the [privacy](crickets-privacy.md) scrubber), never an LLM judgment and never optional on a log capture.

**`[PENDING-IMPL]`** — build the fingerprint normalizer + the `failure-incident` kind + the recall ladder **alongside V6-11** (the metadata-table column is Layer-1's substrate — they ship together; documenter flips when they land).

### Scheduled health passes (designed)

A scheduled pass could run health checks against projects during idle/dream cycles and append a report — still diagnosis, not repair. This leans on agentm's **scheduler**, which is designed-not-built (the [Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)). `diagnostics` names the interface and defers the slice.

**`[PENDING-IMPL]`** — build the scheduled health pass once the agentm scheduler ships (documenter); on-demand `/diagnose` ships first.

### The boundary — a diagnosis engine, never a repairer

`diagnostics` analyzes and remembers; it **never fixes**. Repair is always a **caller's** job, by composition:

- **`maintenance`** (the renamed `github-ci`) owns reactive known-breakage repair — its `dependabot-fixer` calls the diagnose engine to classify a red-CI failure, then runs its own bounded dependency-fix loop.
- **`development-lifecycle`** owns defect repair — `/bugfix` may call the diagnose engine for its Analyze step, then fixes under the loop.

The shape they share is find-cause → fix → verify — a shared *shape*, not a shared *concern*. The lock: **`diagnostics` = the engine; `maintenance` + `development-lifecycle` = the callers; no capability both diagnoses and repairs.** This is also where `github-ci`'s reframe lands — `maintenance` is the caller-home for dependency repair, `diagnostics` is the primitive-home for diagnosis.

### First slice

On-demand `/diagnose`: classify → recall (fingerprint-first) → rank hypotheses → log a `failure-incident` — built **with V6-11** so Layer-1 is deterministic from day one. Scheduled health passes are deferred (blocked on the scheduler).

### Opinions it consumes

diagnostics leans on **`how-we-engineer`** — its deterministic-first discipline (classify before hypothesize, recall before infer) is that opinion applied to diagnosis — and composes code-review's **`good`** when it asks the reviewers to verify a hypothesis. *(Hardwired today; request-by-name is Phase-3/4 — the [Opinions design](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates).)*

## Dependencies

- **enhances `development-lifecycle`** (soft) — failure analysis strengthens `/review` and `/work`; `/bugfix`'s Analyze step may call the diagnose engine.
- **composed by `maintenance`** — `dependabot-fixer` calls the diagnose engine, then runs its own dependency-fix loop (the repair stays in the caller).
- **enhances `code-review`** (soft) — diagnosis can ask the adversarial reviewers to verify a hypothesis.
- **enhanced by `privacy`** — incident bodies are run through privacy's **deterministic** secret/PII scrubber (`check-no-pii.sh` patterns + gitleaks rules — regex, not inference) before the memory write. *(Forward note: privacy today scrubs git ranges; an incident-body scrub surface is a `[PENDING-IMPL]` on the [privacy](crickets-privacy.md) sub-design.)*
- **leans on the agentm memory engine by name** — `recall` + the **V6-11 SQLite metadata table** (the fingerprint index) + the save path; one-way, agentm never depends back. Introduces the `failure-incident` kind into the open `kind` taxonomy ([agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)).
- **leans on the agentm scheduler** (designed-not-built) for the scheduled-health slice only ([Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md); the Troubleshooter/SRE persona is in [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas).

## Risks & open questions

- **Fingerprint mis-calibration — determinism cuts both ways.** A too-loose signature **under-groups** (two distinct failures share a `fingerprint` → Layer-1 confidently returns the *wrong* prior fix); a too-tight one **over-groups** (a real recurrence misses and silently degrades to inference). Determinism makes a bad fingerprint *more* dangerous than a fuzzy semantic match — it's served with confidence and short-circuits the fallback. A Layer-1 hit is therefore a **strong prior, not gospel** — the hypotheses are still verified — backed by a human/auto fingerprint override + the alias mechanism. The `fp_algo` normalization is the lever: who owns the volatile-token strip list, and bumping `v1 → v2` invalidates + re-derives the corpus's fingerprints — settle ownership + cadence before incidents accrete.
- **Secrets / PII in incidents — a deterministic scrub on write is mandatory.** Logs + stack traces routinely carry tokens, keys, absolute paths, PII; an incident write persists them. Every write runs through privacy's **deterministic** scrubber first (regex/pattern, not LLM judgment) — never optional on a log capture. *(privacy scrubs git ranges today; an incident-body scrub surface is a `[PENDING-IMPL]` on the [privacy](crickets-privacy.md) sub-design.)*
- **Layer-1 must be project-scoped.** `SELECT WHERE fingerprint = :fp` **collides across projects** if the fingerprint doesn't carry the repo (same error class + frame in two repos → the wrong incident). Fold `project` into the fingerprint namespace, or filter Layer-1 on project too.
- **The greenfield is real** — the diagnose engine + the recall ladder are the heaviest build of the new capabilities.
- **V6-11 is a hard prerequisite for Layer-1** — the deterministic short-circuit needs the indexed `fingerprint` column, so the metadata table is built alongside diagnostics (operator call); no grep-over-frontmatter interim.
- **`/bugfix` coupling is a phasing call** — composition is the design; whether `/bugfix`'s Analyze wires to the engine on day one or after diagnostics proves out is a build-phase decision.
- **The scheduled slice is blocked** on the unbuilt agentm scheduler — named and deferred.
- **Re-audit triggers:** calibrate the fingerprint (over/under-grouping) on a real incident corpus; confirm the privacy incident-scrub surface ships before the first incident write; add a **failure-incident retention / consolidation** policy (one-off incidents accrete as noise — ties to the V6 lifecycle layer) before volume; sequence the **engine before its callers** (`dependabot-fixer` + `/bugfix` keep inline diagnosis until diagnostics ships, then compose it); flip the `[PENDING-IMPL]` markers as the engine + V6-11, then the scheduled pass, land; confirm `maintenance` is the dependency-repair caller-home when the `github-ci` rename lands.

## References

- **The observability command:** `/observe` (`observe.md`) — the instrumentation discipline
- **The memory substrate it leans on:** agentm `harness/skills/memory/scripts/recall.py` (the recall engine) · `scripts/memory_mcp_tools.py` (`memory_recall` / `phase_recall`) · the **V6-11 SQLite metadata table** (the `fingerprint` exact-match column) — [agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)
- **The scheduler (designed-not-built):** [agentm Experience design](https://github.com/alexherrero/agentm/wiki/agentm-experience-and-dreaming)
- **Siblings:** [crickets HLD](crickets-hld.md) · [development-lifecycle](crickets-development-lifecycle.md) (`/observe`'s caller via `/launch`; `/bugfix` calls the engine) · `maintenance` (the renamed `github-ci`; `dependabot-fixer` calls the engine) · [composition](crickets-composition.md) · [agentm Personas](https://github.com/alexherrero/agentm/wiki/agentm-personas) (Troubleshooter/SRE) · [agentm Memory System](https://github.com/alexherrero/agentm/wiki/agentm-memory-system)

## Amendment log

**2026-06-28 — lock-down sweep (operator review).** Converted the failure-analysis mermaid to a house-style hand-SVG (`diagrams/crickets-diagnostics.svg`). Confirmed the layered pipeline (classify → fingerprint exact-match → hit/zero-inference or semantic fallback → ranked hypotheses) and the `failure-incident` memory scrubbed by `privacy`. No content change. Locked as a v5–v8 guidepost.

**2026-06-23 — added the recall-ladder diagram (diagram backfill).** Per the every-design-carries-a-diagram rule.

**2026-06-23 — added an Opinions-it-consumes clause (portfolio backfill).** Made explicit which opinions diagnostics leans on (`how-we-engineer`; `good` via code-review) — a standard Design clause adopted across the capability designs.

**2026-06-23 — authored, reviewed, and finalized.**

The `diagnostics` capability: a **diagnosis engine that never fixes** — `/observe` (instrumentation, delivered) + `/diagnose` (failure analysis, greenfield). When something breaks it classifies the failure, ranks hypotheses, and logs a `kind: failure-incident` to memory. Repair is a **caller's** job by composition — `maintenance` (the renamed `github-ci`, via `dependabot-fixer`) and `development-lifecycle` (`/bugfix`) call the engine; no capability both diagnoses and repairs. (Why not a `diagnostics-and-repair` merge: it re-creates the seam the lifecycle merge just removed, `/bugfix` is loop-wired, and dependency-repair is a `maintenance` concern.) `/observe`'s home is settled here.

Cross-session failure memory is a **deterministic-first recall ladder**: Layer 0 classify (build/test/type/lint/runtime) → Layer 1 `fingerprint` exact-match via the **V6-11** indexed column (zero-inference short-circuit) → Layer 2 semantic fallback (RRF + a graph hop), with self-reinforcing fingerprint aliases (more deterministic with use), on a new **`kind: failure-incident`**, built alongside V6-11. Risk-hardened against its own failure modes: fingerprint **mis-calibration** (a Layer-1 hit is a strong prior, not gospel), a **mandatory deterministic PII/secret scrub** on incident-write (privacy's regex/gitleaks scrubber — a `[PENDING-IMPL]` incident-body surface), and **project-scoped Layer-1**; cold-start (recurrence-only win) folded into the memory section. **Built-vs-designed:** `/observe` delivered; the engine + ladder + V6-11 greenfield; the scheduled health pass blocked on the unbuilt scheduler. **Re-audit triggers:** calibrate the fingerprint + settle `fp_algo` ownership; ship the privacy incident-scrub surface before the first write; add a failure-incident retention policy; sequence the engine before its callers; flip `[PENDING-IMPL]` as the engine + V6-11 land; confirm `maintenance` is the dependency-repair caller-home at the `github-ci` rename.
