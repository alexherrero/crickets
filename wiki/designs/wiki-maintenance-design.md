---
title: Wiki-Maintenance — an opinionated, template-driven wiki maintainer
status: launched
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-04
updated: 2026-06-09
last_major_revision: 2026-06-09
prd:
project: https://github.com/users/alexherrero/projects/5
---

<!--
  Published child design under the memory-os-architecture HLD (V5 — the unbundling).
  crickets v3.x bucket ④ (Wave 1 critical): plugin 2 of 3 (after the developer-plugin-suite).
  Expands-and-enhances the already-launched diataxis-author.md base: it packages the wiki
  toolchain as a native plugin AND evolves the skill's contract from "enforce Diátaxis modes"
  toward "conform to the operator's templates + house style," via an operator-in-the-loop
  learning loop. So it touches both packaging AND skill internals.
  Authored via /design author. Status lifecycle: draft → review → final → launched.
  Do not hand-edit `status:` — the skill drives it.
-->

# Wiki-Maintenance — an opinionated, template-driven wiki maintainer

## Context

### Objective

crickets v3.x **bucket ④ (Wave 1, critical)** continues the **V5 "unbundling"** ([memory-os-architecture HLD](https://github.com/alexherrero/agentm/wiki/memory-os-architecture)) by giving the operator a native plugin that **maintains a wiki the way the operator actually wants it written — and gets closer to that target every time it's used.** After the **developer-plugin-suite** ([design `launched`](developer-plugin-suite.md), crickets v3.1.0) shipped the dev-loop foundation, **`wiki-maintenance`** is plugin **2 of 3** — a *proper maintainer* of the wiki: it keeps pages current as the code and decisions change, and it authors and repairs them against a **prescriptive template library** so every page shares the same structure, the operator's tone, and a voice that is **genuinely useful to humans and free of AI slop and jargon**. What makes it more than a one-shot writer is a **learning loop**: the operator reviews what it produces, edits it, and the skill studies the delta — what changed and why — then **updates its own templates and style guide** so the next page starts closer to the mark. The problem it solves is that machine-written docs drift, bloat, and read like generic AI prose; the outcome it targets is a wiki that reads like the operator wrote it. It was buildable because #40 shipped the generator and the **#36 skill move** (deferred to ④ by [ADR 0015](crickets-v3-native-plugins)) lands here — and because ④ could not close, nor the ⑤ V5 slim fully unblock, while the documentation toolchain stayed trapped in agentm. **Build state: parts 1–4 shipped; part 5 (the dogfood finale) is running now — the operator-paced wiki rewrite is its execution.**

### Background

- **The stub it expanded.** The thin `src/wiki/` group existed at design time — a `group.yaml` (`requires: [developer-workflows]`, `standalone: false`) plus a single `diataxis-evaluator` agent. It was **renamed to `src/wiki-maintenance/`**: the plugin *group* is `wiki-maintenance`; **`wiki-author`** is the authoring/learning *skill* inside it (the rename resolved the earlier group-name == skill-name collision).
- **Expand-and-enhance from Diátaxis — not replace it.** The existing tooling (the agentm-native `diataxis-author` skill, the `diataxis-evaluator` agent, and the `check-wiki.py` structural linter) is built around the Diátaxis four-mode taxonomy. This design **keeps that as the starting base** and grows from it, rather than ripping it out. Diátaxis is the floor, not the ceiling: where rigid single-taxonomy classification proves less useful than its reputation, the operator's prescriptive templates and house style take over. The skill and linter **stay for now** and are refined *through experience* as this plugin is built. The [launched `diataxis-author` design](diataxis-author.md) remains the canonical record of the skill internals; this design is the layer that packages it and evolves its contract.
- **The learning loop is the core mechanism.** Authoring is iterative and operator-in-the-loop: the skill writes (or rewrites) a page → the operator makes sensible edits → the operator asks the skill to **understand what was changed and why** → the skill distills that delta into durable updates to its **own templates and style guide** → repeat on that page until the operator is satisfied → move to the next page. Over many pages the output converges on the operator's expectations. Where structure recurs, it's **captured as a template** — the same move the `/design` skill made for design docs.
- **What's being folded in** (the *maintainer* pieces, all currently agentm-native, **copied not moved**): the `documenter` agent — the structural worker that keeps pages up-to-date, dispatched at every phase boundary through the dev-suite wave; the authoring/repair skills; the `recent-wiki-changes` helper; and the deterministic structural linter (`check-wiki.py`). The agentm copies stay until the V5 ⑤ slim removes the duplicates.
- **"No AI slop" is a first-class feature, not a nicety.** It ties to the catalog's docs conventions (`docs-prose-style` · `docs-cover-ours-link-theirs` · `docs-soft-warning-tradeoff` · `no-internal-google-refs`). The plugin actively enforces the operator's voice and strips machine tells, filler, and generic jargon — and the learning loop is how that voice gets *captured* over time rather than hand-specified up front.
- **The finale is a heavy dogfood phase.** The plugin concludes by running the learning loop against a batch of **real agentm wiki pages**: the skill rewrites them, the operator critiques, it learns and rewrites until satisfied, then persists what it learned into its templates/style guide — and repeats on the next page. That phase is simultaneously the **validation** (does it produce pages the operator accepts?) and the **training corpus** (the edits are what tune the templates).
- **Composition mechanism:** **`enhances:`** soft-composition ([ADR 0017](decisions/0017-enhances-soft-composition.md)), shipped by the dev-suite — the same pattern code-review uses to enhance `/review`.

## Design

### Overview

**`wiki-maintenance`** is a native crickets plugin (`standalone: true`) that bundles the wiki toolchain — the **`wiki-author`** + **`diataxis-author`** skills (dispatch + the authoring/learning engine), the **`documenter`** agent (phase-boundary structural sweeps), the `diataxis-evaluator` + `style-scope-evaluator` read-only agents, the **`wiki-watch`** skill + command (§7's watcher), the `recent-wiki-changes` helper, and the `check-wiki.py` linter. It composes with `developer-workflows` via **`enhances:`** soft-composition ([ADR 0017](decisions/0017-enhances-soft-composition.md)): the phase commands already scaffold a `documenter` dispatch at every boundary, and this plugin is what that dispatch resolves to.

Quality rests on **two layers that the skill consults on every page**. **Templates** fix *structure* — the recurring section skeletons per kind of page (the same move `/design` made for design docs). A **style guide** fixes *voice* — human-first, slop-free, jargon-free, in the operator's register. Both ship a **base** in the repo as the plugin's starting opinion (expanded-and-enhanced from the inherited Diátaxis tooling, never ripped out); the operator's personal voice accretes on top as a **learned overlay**.

The **learning loop** grows that overlay. The skill authors or rewrites a page → the operator edits → the skill studies the delta and distills it **not** into a one-off "fix this page" rule but into a **generalizable voice lesson**: a snippet of guidance plus a worked example showing how the operator expresses themselves in that *kind* of situation — usually broader than any single page type. Those lessons are **durable memories**, stored wherever durable memory is configured (**repo / machine-user / common vault**, per the MemoryVault scope model). The skill reads **base ⊕ overlay** at author time and writes new lessons to the overlay. The operator may **promote** a proven overlay lesson into the shipped repo base — an **operator-gated** action; downstream consumers keep their own local overlay and don't write back to the base.

### Infrastructure

**Generation + deployment.** Like every crickets group, `wiki-maintenance` is authored in `src/wiki-maintenance/` and generated by `scripts/generate.py` into committed `dist/<host>/plugins/wiki-maintenance/` for both hosts (Claude Code + Antigravity `agy`), plus the marketplaces + root pointer. Its primitives map to host runtime surfaces:

- **`wiki-author` skill** → runs in-conversation in the main agent; reads templates + style overlay and authors/edits pages via `Read`/`Write`/`Edit`/`Glob`/`Grep` (no `Bash`, matching `/design`).
- **`documenter` agent** → a read+write sub-agent dispatched at phase boundaries by the developer-workflows phase commands.
- **`diataxis-evaluator` agent** → a read-only classifier sub-agent.
- **`recent-wiki-changes` + `check-wiki.py`** → group-level `scripts/` assets (bundled by the generator's `copy_group_scripts`, which already excludes `__pycache__/*.pyc`); run via `Bash`/`python3` as deterministic helpers/gates.

**Composition shape — soft `enhances`, not hard `requires`.** The `wiki-author` skill is independently useful — it runs on any wiki with no dev-loop present — so the group is `standalone: true`. The real coupling is soft and points the other way: developer-workflows' phase commands dispatch the documenter at boundaries **iff** this plugin is installed, exactly as code-review enhances `/review`. The group drops the inherited hard `requires: [developer-workflows]` for a capability-targeted `enhances`, and re-categorizes from `Coding` to `documentation`:

```yaml
name: Wiki Maintenance
description: Opinionated, template-driven wiki maintenance — the wiki-author authoring/learning
  skill, the documenter agent, the diataxis-evaluator, recent-wiki-changes, and the check-wiki.py
  linter. Maintains a wiki in the operator's voice; enhances developer-workflows' phase-boundary
  documentation when both are installed.
category: documentation
requires: []
standalone: true
enhances:
  - group: developer-workflows
    capability: documentation
    effect: "phase commands dispatch the documenter to author/repair wiki pages at phase boundaries"
```

**Realizing the enhance (the runtime half).** Today the documenter dispatch in the phase commands is **prose-only graceful-skip** with no probe — the enhance would be *declared but unwired*. This design **wires it deterministically**, mirroring the auto-enable-runtime task that wired `/review`: developer-workflows exposes a `documentation` capability, and the phase commands call `capability_probe.py` and dispatch the documenter on a hit. Because this edits the already-launched developer-workflows plugin, it is scoped as **its own task** in the sequence (and can split to a fast-follow if it grows) — never a silent half-wire.

**Overlay store.** The learned overlay reads/writes from the configured durable-memory location (repo / machine-user / common vault — the MemoryVault scope model); readiness + fallback are covered under Dependencies.

### Detailed Design

The wiki toolchain already implements the *shape* this design needs; the work is to **generalize what it learns from structure to voice, make capture edit-driven, and add a continuous mode** (§7).

**1. Skill + worker topology (kept, not merged).** `wiki-author` stays the operator-facing **dispatcher** (trigger phrases → resolve repo via cwd/`repo_registry` + page kind → dispatch `documenter`, preview-before-write). `diataxis-author` stays the **authoring engine** (mode/template-fill/filename, drift detection + repair, classification) and owns the templates + convention read/write — **the learning loop lives here.** `documenter` stays the `wiki/**`-scoped mechanical writer; `check-wiki.py` stays the structural gate. A **new read-only `style-scope-evaluator` sub-agent** recommends where each captured lesson belongs (global / per-project / per-repo) — see §3. The dogfood phase may consolidate the two skills later; for now the split is preserved.

**2. Two layers, mapped onto what exists.** **Templates (structure)** = `diataxis-author/templates/*.md` — the inherited base family; new page kinds added as templates over time. **Style guide (voice)** = a **new** base artifact — the operator's house voice (human-first, slop-free, jargon-free, register), seeded from the existing `docs-prose-style` conventions. **Overlay (learned voice)** = the existing scoped convention store, read **on-demand** via the `documenter-context` resolver — deliberately *not* `_always-load`. Today the global Diátaxis conventions sit in `_always-load/diataxis-*.md`, which injects them into **every** session's context (doc-related or not); this design moves the global wiki conventions **out of `_always-load`** into a global **on-demand** store (parallel to the per-project `projects/<slug>/wiki-style/*.md` — e.g. a reserved `_global` slug the resolver reads via its existing per-project path), so they load only when authoring. Three on-demand scopes carry both voice lessons and structural conventions: **global** (on-demand, not always-load) · **per-project** (`projects/<slug>/wiki-style/`) · **per-repo** (`wiki/.diataxis-conventions.md`). *(Forward link: when agentm V6 indexed-recall lands, even the global tier becomes vector-discovered rather than file-read — flagged in [`agent-memory-evolution.md`](https://github.com/alexherrero/agentm/wiki/agent-memory-evolution) §V6.)*

**3. The learning loop — generalize + edit-driven capture (the real new work).** Today `diataxis-author` captures *decisions* (operator-confirmed). This design adds an **edit-driven** capture: operator edits a drafted page → the skill **diffs** draft vs edited, **clusters** changes by kind (word choice · rhythm · structure · cuts = slop/jargon removed · additions) → for each cluster proposes a **voice lesson** `{trigger/scenario, scope, guidance, before→after example}` → **confirms the generality with the operator** ("I read this as: *in any X, prefer Y* — right, narrower, or broader?") → the read-only **`style-scope-evaluator`** recommends the storage scope (**global / per-project / per-repo** — is this voice rule universal, project-specific, or repo-specific?), which the operator confirms → writes the confirmed lesson to that scope's on-demand store via the existing `agentmemory_conventions.py` capture path. **Two judgments, both operator-gated:** generality (operator-validated, never auto-committed) and scope (evaluator-recommended, operator-confirmed).

**4. Read-back + drift.** At author time the engine loads **template ⊕ base style-guide ⊕ overlay lessons** (scope precedence: vault → project → repo, narrower wins). The currently-**stubbed** `diataxis/convention-drift` check is **wired live** against the style overlay, so `check-wiki.py` / `/diataxis check` flags *voice* drift, not just structural violations.

**5. Promotion gate.** `promote` (operator-only): copies a proven overlay lesson into the repo base style-guide, then regenerate. Installed consumer plugins have no write path to their `dist/` base — they accrue only a local overlay; promotion is a maintainer source-edit + commit.

**6. Documenter wiring (runtime half).** developer-workflows exposes a `documentation` capability; phase commands `capability_probe.py` → dispatch `documenter`, which runs the same template ⊕ style ⊕ overlay flow.

**7. Continuous mode — the wiki-watcher.** A session-level mode that runs the documenter on a **watch loop** rather than one-shot at a phase boundary: it watches a repo (GitHub) and/or the active `PLAN.md` / design / `ROADMAP.md`, decides whether each change is doc-worthy, and dispatches the `documenter` to author the update — **directly or by PR**, configurable per repo. **PR is the default autonomous boundary** (a human merges); direct-commit is opt-in per trusted repo. **Hosting ships as W1** — a self-scheduling session using the host's loop/wakeup — to prove the loop end-to-end; **W2 (cron-headless) and W3 (external-poll → trigger) are the documented follow-ons** (roadmap item surfaced at `/plan`). **Config rides the existing architecture, no new file:** `.agentm-config.json` carries host enablement, a **per-repo marker** carries run config (watch + dispatch mode), and the `repo_registry` index (`<vault>/_meta/repos.json`) resolves which wiki a watched repo maps to — honoring the locked **DC-8 index-vs-run-config split** (cross-device *indexes* in the vault; *run config* on-host/per-repo). **Correctness rests on durable state:** per-source **cursors** + a **processed-set** make dispatch idempotent (never drop a change, never double-dispatch); a **significance gate** decides whether a diff warrants a doc update (filters noise → bounds PR volume); an **audit log** (`saw → decided → dispatched`, with PR links) is the monitoring surface. The watcher **reuses the `documenter`** for the authoring itself — it adds the trigger / config / dispatch / idempotency scaffolding around it, not a second writer. *(W1 ships in part 4; W3 + a scheduled-routine mode are the deferred enhancement in Technical Debt & Risks #3.)*

## Alternatives Considered

1. **One "engineering-docs" plugin (wiki + HLD/design-docs merged).** Rejected: different verbs (maintain an existing tree vs. a forward-looking author→translate→sequence pipeline with a draft→review→final→launched state machine); `/design`'s natural coupling neighbor is `developer-workflows` (it emits the `PLAN.md` the dev-loop consumes), not the wiki; merging would balloon the Wave-1-critical plugin and delay closing ④. The synergy rides an `enhances: [wiki-maintenance]` edge on the future design-docs plugin instead.
2. **Faithful Diátaxis enforcement (the inherited contract, unchanged).** Rejected: rigid single-taxonomy classification proved less useful in practice than its reputation. We expand-and-enhance *from* Diátaxis (it stays the base/floor) toward the operator's prescriptive templates + house voice, refined through experience — rather than enforcing four modes as the law.
3. **Auto-infer + auto-commit learned voice lessons (no operator confirmation).** Rejected: overfits to the single page that triggered the edit and drifts silently. Generality is operator-validated — the skill proposes, the operator confirms/narrows/broadens.
4. **Hard `requires: [developer-workflows]` (`standalone: false`), inherited from the stub.** Rejected: the `wiki-author`/`diataxis-author` skills run on any wiki with no dev-loop present. `standalone: true` + a capability-targeted `enhances` (code-review parity) states the coupling honestly.
5. **Leave the documenter dispatch prose-only graceful-skip.** Rejected: a declared-but-unwired enhance is the worst of both. We wire it deterministically via `capability_probe.py` (auto-enable-runtime parity), scoped as its own task.
6. **Fold the shared infra (`harness_memory.py` / `repo_registry.py` / `agentm_config.py`) into the plugin for "true" standalone.** Rejected: those are kernel-resident shared infra used by every phase, the SessionStart hooks, and the `memory` skill — the slim won't delete them, so vendored copies would orphan and diverge. The plugin depends on them with graceful-skip; only the wiki-owned primitives fold in.
7. **A new standalone `.wiki-watch.yml` config for the watcher.** Rejected: duplicates the operator's existing config architecture. The watcher rides `.agentm-config.json` (host enablement) + a per-repo marker (run config) + the `repo_registry` index — honoring the locked DC-8 index-vs-run-config split.
8. **Watcher hosting via W2 (cron-headless) or W3 (external-poll → trigger) as the first cut.** Deferred, not rejected: W1 (self-scheduling session) ships first to prove the loop end-to-end; W3 is the documented follow-on (recorded in §7 + the roadmap at `/plan`).

## Dependencies

**crickets groups / plugins**
- **`developer-workflows`** — *soft*, via the capability-targeted `enhances` (the `documentation` capability it exposes for the phase-boundary documenter dispatch). Not a hard `requires:` — the plugin is `standalone: true`.
- **Future `design-docs` plugin** — the *reverse* edge: it will declare `enhances: [wiki-maintenance]`. Not a dependency of this plugin; noted for direction.

**agentm kernel infra (graceful-skip — bucket B)**
- **`harness_memory.py`** (the auto-context / `documenter-context` resolver), **`repo_registry.py`** (cross-device repo index), **`agentm_config.py`** / `.agentm-config.json` (run-mode + vault path). Kernel-resident, *not* folded in. The skills already degrade cleanly: `rc 1` (vault unreachable) → built-in + per-repo conventions; `rc 2` (slug unregistered) → operator-global conventions still resolve. So the **core author/learn works standalone**; cross-repo resolution + the scoped overlay light up when the kernel is present. V5 placement of this seam is an open re-audit (recorded in the V5 HLD).

**Durable storage**
- **The convention/overlay store** — read **on-demand** via the resolver, deliberately **outside `_always-load`** so it doesn't weigh down every session's context. Three scopes: **global** (on-demand, reserved `_global` slug), **per-project** (`projects/<slug>/wiki-style/`), **per-repo** (`wiki/.diataxis-conventions.md`). Scope follows the harness storage config (repo / device-user / central vault). *Future: when agentm V6 indexed-recall ships, the global tier moves from file-read to vector-discovery — see the V6 re-audit in [`agent-memory-evolution.md`](https://github.com/alexherrero/agentm/wiki/agent-memory-evolution).*

**External tools**
- **`git`** — diffs (the learning-loop delta + the watcher), branches, direct-commit mode.
- **`gh`** (+ GitHub auth) — *watcher only*: read for change-polling, push/PR for dispatch. Graceful-skip (non-watcher paths don't need it).
- **A scheduler** — *watcher only*: W1 uses the host's loop/wakeup; W3 (later) uses cron + trigger. Host-specific; the watcher mode no-ops where unavailable.
- **`python3`** (stdlib-only, ADR 0001) — `check-wiki.py` + the skill scripts.

**Build-time**
- **The crickets generator** (`generate.py` + `copy_group_scripts`) — bundles the group `scripts/` assets; already present.

**Cross-plugin edit**
- The documenter-wiring task edits the **already-launched `developer-workflows`** source (to expose the `documentation` capability + add the probe-dispatch). A deliberate, scoped cross-plugin change — not a runtime dependency.

**Seed**
- **`docs-prose-style` conventions** — seed the base style guide (the voice layer's starting opinion).

## Migrations

1. **Group rename + composition flip.** `src/wiki/` → `src/wiki-maintenance/`; regenerate `dist/`. The `wiki` plugin leaves the marketplaces/default-set and `wiki-maintenance` takes its place; `requires: [developer-workflows]`/`standalone:false` → `requires:[]`/`standalone:true`/`enhances`; `category: Coding` → `documentation`. **Operator live-migration is a flag, not a blocker** (same as the seed-retirement): the repo push doesn't auto-affect the machine — on next `claude plugin marketplace update crickets`, the operator installs the new `wiki-maintenance` plugin rather than piecemeal-updating `wiki`.
2. **Bucket-A fold-in — copy-not-move, parallel-run.** Copy the wiki-owned primitives (`wiki-author` + `diataxis-author` skills incl. their `scripts/`+`templates/`, the `documenter` agent, `check-wiki.py`, `recent-wiki-changes`, `diataxis-evaluator`) from agentm into `src/wiki-maintenance/`. The agentm copies **stay** (parallel-run) until the **V5 ⑤ slim** deletes them *after this proves out* — the same copy-then-delete-after-proof discipline the V3 generator and the seed-retirement used. **Bucket B is explicitly not migrated** (kernel-resident; depend + graceful-skip).
3. **`_always-load` → on-demand convention relocation (operator-vault data).** The global Diátaxis conventions move from `_always-load/diataxis-*.md` to the global on-demand store (the reserved `_global` slug path). This touches the operator's live vault, so it's a **preview-first, reversible operator-run step** (mirroring `migrate-harness-to-vault` / `rename-vault-personal-projects`), never auto. Verified safe: the only readers are the wiki primitives (via the resolver), which switch to reading the relocated location.
4. **`convention-drift` check: stub → live.** The `diataxis/convention-drift` rule (v1 stub, always `None`) goes live against the style overlay. Behavioral change: existing wikis may surface new *voice*-drift findings — expected and **non-breaking** (findings, not hard failures, unless `--strict`).
5. **Documenter dispatch: prose → deterministic.** Phase boundaries shift from prose graceful-skip to a `capability_probe.py`-backed dispatch when `wiki-maintenance` is installed. **Non-breaking** — still graceful-skips when absent.
6. **Deprecation.** `migrate-to-diataxis` is already subsumed by `diataxis-author` (one-shot legacy→four-mode migration); it is **not carried** into the plugin (dead path), removed from agentm at the slim.

## Technical Debt & Risks

1. **The generalization step is the make-or-break, and it's LLM-judgment.** Abstracting an edit-delta into a *generalizable* voice lesson can over- or under-generalize. Mitigation: two operator gates (generality + scope); start narrow. *Re-audit if lesson-conflict rate or overlay growth climbs — that's the signal generalization is mis-scoped.*
2. **Overlay precedence conflicts.** As lessons accrue across global/project/repo, contradictory lessons can merge surprisingly. Mitigation: documented precedence (vault→project→repo, narrower + recent wins); `convention-drift` surfaces inconsistency. *Re-audit if the operator hits a "why did it write that?" the precedence doesn't explain.*
3. **The watcher ships as W1 (session-bound, polling) — deferred to W3.** W1 is tied to a live session and polls; it misses changes while not running. **Deferred enhancement: W3 (external-poll → trigger) + a scheduled-routine mode** — recorded as the roadmap follow-on (surfaced as a Project/backlog item at `/plan`). *Re-audit when watch volume or always-on need outgrows a session-bound loop.*
4. **Autonomous dispatch writes without interactive preview.** PR-as-preview is the boundary; **direct mode bypasses it**. Mitigation: PR default + significance gate + audit log + rollback; direct mode opt-in per trusted repo. *Re-audit on the first bad auto-PR/commit, or if the significance gate's false-positive (PR-spam) rate is non-trivial.*
5. **Cross-plugin edit to the launched `developer-workflows`.** Adding the `documentation` capability + probe-dispatch could regress a shipped plugin. Mitigation: own scoped task, full gate battery, **wake-on-CI before `[x]`**. *Re-audit if developer-workflows' test coverage doesn't exercise the new capability path.*
6. **Bucket-B graceful-skip degrades silently.** Absent kernel infra → cross-repo + learned-voice silently fall back to built-ins. Mitigation: the `rc 1`/`rc 2` stderr warnings + the skill surfaces degraded mode. *Re-audit on Antigravity/headless hosts where the resolver or vault may be unavailable.*
7. **Two-skill split may be redundant** (`wiki-author` dispatches, `diataxis-author` does the learning). Accepted for now; the dogfood phase decides consolidation. *Re-audit if the split causes ownership friction during the dogfood.*

## Quality Attributes

### Security

Real. The watcher holds `gh` push/PR scope and (in direct mode) commits to wikis; the skill writes to the operator's durable store. Mitigation: least-privilege `gh` scope; PR-default limits blast radius; direct mode opt-in per trusted repo; the public-repo PII guardrails (pre-push hook + `pii-scrubber`) gate anything committed.

### Reliability

Real. The watcher must not drop changes or double-dispatch. Mitigation: durable cursors + a processed-set (idempotency); retry/backoff on dispatch failure; graceful-skip (never hard-fail) when the resolver/vault is unreachable.

### Data Integrity

Real. The overlay, cursors, and the `_always-load` relocation are durable state. Mitigation: atomic writes via the existing `safe_write_replace_style` mtime-check pattern; the relocation is preview-first + reversible; overlay precedence is documented and deterministic.

### Privacy

Real (crickets is **public**). Voice lessons + watcher logs can capture private content (vault paths, repo text). Mitigation: the overlay lives in the operator's durable store, **never committed** to the public plugin; the shipped base style-guide carries no private data; watcher audit logs stay local; PII guardrails enforce on any push.

### Scalability

Moderate. Overlay growth + watching many repos. Mitigation: on-demand read (not always-load) keeps per-session context bounded regardless of overlay size; the significance gate + cadence bound dispatch volume; agentm V6 indexed-recall is the long-term scaling answer.

### Latency

Low. Author-time adds one resolver read (template ⊕ style ⊕ overlay) — a fast local read, scoped on-demand. The watcher is fully async (never user-blocking).

### Abuse

Real. A noisy repo could drive runaway PR-spam. Mitigation: significance gate + idempotency + per-repo rate limit + PR-default (a human merges). Shared mitigation with the autonomous-dispatch risk.

### Accessibility

Real, and central. Human-readable, slop-free, jargon-free prose *is* the product — readability is a first-class design goal, not an afterthought. No GUI surface, so no UI-a11y dimension.

### Testability

Real. The learning loop + watcher are stateful and partly LLM-judgment. Mitigation: deterministic parts (`check-wiki.py`, resolver, cursors, dispatch plumbing, scope precedence) are unit-tested under the standard `check-all.sh` battery; the watcher loop is mockable (inject deltas); the judgment parts (generalization, significance) are fixture- + operator-validated.

### Internationalization & Localization

N/A: the operator's wikis are English-only and the voice/style model is intentionally language-specific; no localization requirement.

### Compliance

N/A: a personal documentation toolkit under no regulatory regime; public-repo data hygiene is handled under Privacy.

## Project management

### Work estimates

*(these became the `/design sequence` parts; 1–4 shipped, 5 in progress)*

1. **Scaffold + fold-in + rename** — group `wiki`→`wiki-maintenance`, composition flip, copy bucket-A primitives, regenerate `dist/`, update tests. *Medium-heavy (broad but mechanical).*
2. **Style layer + learning loop** — base style-guide artifact, edit-driven generalization capture, the `style-scope-evaluator`, `_always-load`→on-demand relocation, `convention-drift` stub→live. *Heavy — the real new work.*
3. **Documenter runtime wiring** — developer-workflows `documentation` capability + probe-dispatch. *Medium (cross-plugin, deterministic).*
4. **The wiki-watcher (W1)** — watch loop, cursors, config (riding `.agentm-config.json` + per-repo marker + `repo_registry`), significance gate, PR/direct dispatch, audit log. *Heavy — most net-new surface.*
5. **Dogfood finale** — run the learning loop on real agentm wiki pages; operator critiques → converge → promote. *Heavy, operator-paced (validation + training corpus).*

### Documentation Plan

- This published design doc (the "why we built it" entry point).
- A **how-to** (install + the author/learn loop + watcher modes) and a **reference** for the watch config.
- **Prefer amending ADR 0004 / ADR 0008** (the Diátaxis spec + diataxis-author decisions) over a new ADR — the identity pivot (Diátaxis as floor, not law) + the `standalone:true`+`enhances` call are amendments to existing records, not fresh decisions. ADR-spam avoided per convention.
- The documenter authors/updates the affected pages at phase boundaries; `check-wiki.py --strict` gates all new pages.

### Launch Plans

- Shipping **granularly across crickets 3.x minors**, parts in dependency order (1→2→3 core, 4 watcher, 5 dogfood). Plugin install *is* the feature flag — no separate flag.
- **Watcher is opt-in** (off until configured); **direct-commit mode opt-in per repo** (PR default). Operator live-migration is a flag (install the new plugin), not a blocker.

## Operations

### SLAs

No formal SLA (personal toolkit). The watcher's poll cadence is operator-configured; graceful-skip guarantees no hard dependency blocks a session.

### Monitoring and Alerting

The watcher's **run-log / audit trail** (saw → decided → dispatched, with PR links) is the monitoring surface; failures surface in the log + stderr for operator review at next session. Build health via `check-all.sh` + CI. No external alerting (local-only).

### Logging Plan

Watcher audit log lives in the durable store (e.g. `_harness/wiki-watch/`), **local, never committed**; `rc 1`/`rc 2` graceful-skip warnings on stderr; the learning loop logs each confirmed lesson (text + scope). No PII in any committed log.

### Rollback Strategy

A bad auto-PR is closed; a bad auto-commit is `git revert`-ed. The `_always-load` relocation is **reversible** (preview-first + `--rollback`, mirroring `migrate-harness-to-vault`). The rename/flip rolls back via normal `dist/` regeneration. Overlay lessons are operator-deletable. The **slim (deleting agentm copies) is gated on dogfood proof** — rollback = simply don't delete; parallel-run holds.

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-06-04 | Authored, finalized, translated, and sequenced via `/design` in one day. Full 10-section draft: the identity pivot (Diátaxis as floor, not law → template-driven + operator-voice learning loop); group renamed `wiki`→`wiki-maintenance`; `standalone:true`+`enhances` composition; the wiki-watcher continuous mode (§7 — W1-now/W3-later, PR-default, config riding `.agentm-config.json` + per-repo marker + `repo_registry`, cursors/processed-set, significance gate, audit log; completed at translate time as the one stubbed subsection); bucket-A fold-in vs bucket-B kernel-graceful-skip; `_always-load`→on-demand convention storage. Cross-doc notes placed in `memory-os-architecture` + `agent-memory-evolution`. Translated to 5 parts and sequenced (Kahn order: scaffold-fold-in → documenter-wiring → style-learning-loop → wiki-watcher → dogfood-finale, the finale strengthened to sort last); state written to the vault `_harness/`. | final |
| 2026-06-07 | **Parts 1–4 built** — scaffold-fold-in (group rename + bucket-A copy-not-move), documenter-wiring (the `documentation` capability + probe-dispatch), style-learning-loop (base style guide ⊕ overlay, edit-driven capture, `style-scope-evaluator`, the `_always-load`→`_global` on-demand relocation), and the wiki-watcher W1 (`wiki-watch` skill + command — one idempotent cycle, cooldown-gated + cursor-backed, PR-default). | final |
| 2026-06-09 | **Part 5 (dogfood finale) completed → wave `/release` — launched.** The operator-paced learning loop ran against the real crickets wiki (two waves, ~40+ pages: every user-facing page through draft → operator edit → voice-lesson capture; the section-template library + per-folder-sidebar IA grew out of it; ~25 lessons confirmed into the overlay). The **first real `/diataxis promote`** graduated the llm-tell-vocabulary lesson into the committed base (operator-gated per DC-F1; base-alone composition verified on both hosts). Confidential proof log written; **the docs portion of the V5 ⑤ slim is unblocked** (Migration-2 gate satisfied; agentm's parallel copies untouched). Design content also reviewed against shipped reality (tense, the shipped primitive set incl. `wiki-watch` + `style-scope-evaluator`; structure unchanged). Ships as **crickets v3.2.0**. Status `final → launched`. | launched |
