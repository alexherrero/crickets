---
title: build-system — design
status: launched
kind: design
scope: feature
area: crickets/build-system
governs: [scripts/generate.py, scripts/src_model.py, scripts/emit_*.py, scripts/lint_src.py, bootstrap.sh]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-21
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-21).** child-design — the build pipeline, parent [crickets HLD](crickets-hld.md). Subsumes the launched `crickets-v3-native-plugins.md` design (the *why*; this is the *how* — now its single home; AG Wave 2, 2026-06-24). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3).

# Crickets build system

## Objective

**Write once, generate everywhere.** A capability is authored a single time, in plain text, and a build step renders it into the native shape each host expects — so the same capability runs on Claude Code, Antigravity, and any host added later, with no hand-maintained per-host copies to drift apart.

## Overview

One source → one deterministic generator → a native plugin per host → install, with a drift gate keeping the committed output honest:

![Build pipeline: the single source src/&lt;group&gt;/ feeds the deterministic generator, which emits a native plugin per host (Claude Code, Antigravity); bootstrap installs them, and a drift gate re-runs the generator to confirm the committed dist matches the source](diagrams/crickets-build-pipeline.svg)

*One source → one generator → a native plugin per host → install; the drift gate keeps the committed output honest.*

A capability lives in one folder; the generator emits a per-host plugin from it; `bootstrap` installs them; and a check gate re-runs the generator to confirm the committed `dist/` still matches the source. Each step's mechanics are below.

## Design

### The single source

A capability lives in one folder, `src/<group>/`, with a **two-layer manifest** (the contract is `src/SCHEMA.md`):

- **`group.yaml`** — the capability's identity: name, category, `requires:` / `enhances:` / `capabilities:`.
- **The primitives** — skills, agents, commands, hooks, rules, output-styles — each a file with its own frontmatter.

Plus host-agnostic group assets (`scripts/`, `templates/`) the primitives draw on. A reader authors a new capability by following `SCHEMA.md`. By way of example, `src/developer-workflows/` — `group.yaml` sits beside `commands/`, `agents/`, `hooks/` subfolders.

### The generator

A deterministic generator (`scripts/generate.py`), reading the source through one shared parser (`src_model.py`), emits a **native plugin per host** — `dist/claude-code/` and `dist/antigravity/` — each in that host's own shape via a per-host emitter (`emit_claude.py`, `emit_antigravity.py`). **Determinism is load-bearing**: sorted iteration and stable JSON keys make the output byte-reproducible, which is what lets a CI gate trust it.

- **The committed `dist/` + the drift gate.** `dist/` is committed, and `python3 scripts/generate.py check` re-runs the generator and fails if the committed output diverges from the source — so "generated, never hand-edited" is *enforced*, not just intended (the gate is in `check-all.sh` + CI).
- **Adding a host = adding an emitter.** Emitters register against a `HostEmitter` base via a small registry (`_EMITTER_MODULES`), so a new host is a new emitter module, not a change to the core driver.
- **Install.** Three modes in decreasing automation: **`bootstrap.sh`** (device-wide `--scope user` into `~/.claude/` by default — the one-liner), **marketplace** (explicit `claude install` / `agy install` from the emitted `marketplace.json`), **manual** (direct file placement). `install.sh` / `install.ps1` are retired — native host plugin systems replace them. crickets stands alone (no install dependency on agentm; agentm bundles crickets in its own one-liner). The generator-emitted `default-set.json` + per-host `marketplace.json` carry install metadata + soft-composition links.

### Host-agnostic source, host-specific output

The *definition* is single-source; the *generation* is deliberately **partial** where a host lacks a surface — a host gets only the subset of a capability's primitives it can express, and each skip is logged at generation time (so coverage gaps are visible, not silent). The validator (`lint_src.py`) checks the source; the emitters record what they drop. As-built today: the **Antigravity** emitter skips primitives Antigravity can't express (an output-style and several instruction-file rules) and its hooks are observe-only; the **Claude** emitter drops a couple of snippet instruction-files Claude has no type for.

## Dependencies

- **Subsumes** the earlier crickets-v3-native-plugins design (the architecture *why*; this child is the *how* — now its single home; the two ADRs it had absorbed, 0013 + 0015, are preserved in the Amendment log).
- **Relies on** `src/SCHEMA.md` (the two-layer manifest contract) and each host's native plugin CLI (for install).
- **Sibling** [composition](crickets-composition.md) — the `capabilities:` / `enhances:` metadata the generator emits, and where the composition lints live.
- Native-plugin generation decisions (bundles → plugins; proof scope; device-wide install; install.sh retirement) are in the Amendment log; the `enhances:`/`capabilities:` composition mechanics are in [composition](crickets-composition.md).

## Risks & open questions

- **Not full parity** — the honest claim is "one definition, generated and drift-gated for every host, with named skips where a host can't represent a primitive," not parity. The per-host skip *rationale* (why each gap exists, the fallback) is a candidate for its own **host-coverage** sub-design — noted here, not enumerated.
- **Determinism is a standing risk** — any non-deterministic output (unsorted iteration, unstable keys) makes the drift gate flap; it must stay sorted/stable.
- *(No `[PENDING-IMPL]` markers: the pipeline is **as-built** — the generator, emitters, drift gate, and installer all ship. The placeholder rule applies only where a design describes something not-yet-built.)*
- **Re-audit triggers:** re-derive the per-host skip list against the live emitters at the lift; confirm `generate.py check` is wired into CI; the crickets-v3-native-plugins reconcile is done (subsumed here 2026-06-24, AG Wave 2).

## References

- **Tools:** `scripts/generate.py` (driver + `check`), `src_model.py` (shared parser), `emit_claude.py` / `emit_antigravity.py` (per-host emitters), `lint_src.py` (source validation), `bootstrap.sh` (installer)
- **Schema:** `src/SCHEMA.md` — the two-layer manifest contract; the source of truth for authoring a capability
- **Artifacts:** `dist/default-set.json` + the per-host `marketplace.json` (generator-emitted install metadata)
- **Designs / decisions:** generation + install decisions (folded from ADRs 0013, 0015, 0012, 0014) are in the Amendment log; soft-composition (`enhances:` / `capabilities:`) lives in [composition](crickets-composition.md)

## Amendment log

**2026-06-24 — subsumed the launched `crickets-v3-native-plugins.md` design (AG Wave 2, move-and-retire).** This design was the *how* reconciling that earlier *why*; it now subsumes it outright. The v3 design is deleted (git history + its six part files retain the full text); its still-live value — the two C4-folded ADRs it had absorbed (AG Phase-2) — is preserved below with decision + why-not + re-audit. The body already holds the as-built pipeline; the per-host emitter differences (the Claude/Antigravity mapping, the `SessionStart` gap, snippets → `rules/`) live in the live emitters + `wiki/reference/Per-Host-Paths.md`.

- **ADR 0013 — bundles are native host plugins, generated from one source (2026-06-02).** One source of truth under `src/<group>/` + a deterministic stdlib-only `generate.py` emits native per-host plugins into committed `dist/{claude-code,antigravity}/`; functional grouping (folder) is the unit of distribution; cross-plugin reuse is generation-time dependencies, never a duplicated primitive; a `generate.py check` drift gate makes determinism load-bearing. Antigravity composition is **thin-separate** (no native deps — confirmed at the #40 dogfood: `agy` 1.0.2 has no dependency resolution); Claude uses native `dependencies`. *Why not hand-author per-host / generate-at-install / trust-manual-rebuild:* each recreates adapter drift, breaks the static marketplace + auditable diff, or lets generated output silently drift. *Re-audit trigger:* a host plugin-manifest/marketplace schema change, or a host requiring nondeterministic output.
- **ADR 0015 — #36 partial-revision: #40 proves the architecture, defers the catalog (2026-06-02).** #40 proved the model on crickets' existing primitives (4 groups / 7 primitives — every emitter path) + dogfooded install on both hosts; the #36 skill relocations (`design` → design-docs, `diataxis-author` → wiki, `ship-release` → releasing) + the full catalog (testing / releasing / knowledge) were explicitly deferred to bucket ④. *Why record the boundary as a contract:* so a reader of the sparse post-#40 catalog sees it was partially-revised on purpose, not abandoned. *Re-audit trigger:* the first genuinely-new bucket-④ bundle (does a new primitive kind / host mapping need generator rework?), or the crickets/agentm split shifting again.

*Why not keep `crickets-v3-native-plugins.md` as a standalone living design:* it was already up-pointered and reconciled by this design — keeping the husk forces a chain-read; the living body here is the single source. *Re-audit trigger:* a host plugin/marketplace schema change (regenerate + dogfood).

**2026-06-24 — folded ADRs 0012 / 0014 into this design (AG Phase 4, move-and-retire).**

**0012 — Device-wide harness install + vault-backed state by default (2026-05-26).** `--scope user` (device-wide into `~/.claude/`) becomes the default install. Harness state moves from `<project>/.harness/` to `<vault>/projects/<slug>/_harness/`. Project resolution via a composable resolver chain. Auto-detect bootstrap on first session. agentm bundles crickets in its one-liner; crickets stands alone. Hard-cut deprecation of legacy paths at agentm v4.0.0. Why not per-project-default: clutter in every repo, install drift, tools are operator-scoped not project-scoped. Why not database: vault stays markdown-canonical + filesystem-only. Why not shared install-bundle repo: adds a third repo and complicates discovery. *Re-audit triggers:* GDrive sync lag >30 s; >100 projects or >200 always-load entries; multi-operator use case; Antigravity forks its surface across desktop/CLI.

**0014 — Install decoupling: retire install.sh + agentm↔crickets lib-sync (2026-06-02).** Delete `install.sh`/`install.ps1`, `lib/install/`, `check-lib-parity.sh` from crickets; replace with native host plugin systems. agentm keeps its own `lib/install/`; repos decouple at install time. Three install modes: bootstrap.sh, marketplace, manual. Delivered as crickets v3.0 major. Why not extract `lib/install/` into a shared repo/submodule: preserves bespoke installer that native plugins make unnecessary and adds a third repo. Why not gradual deprecation: no external consumers; clean major-version cut is cheaper. *Re-audit triggers:* agentm's install model changes to again want shared code with crickets; either host drops or substantially changes plugin install; Antigravity gains hook-veto support.

**2026-06-21 — authored, reviewed, and finalized.**

Migrated from the crickets HLD (the build-pipeline mechanics), deepened against the live code, conformed to the abbreviated-design template (Objective / Overview / Design) with a pipeline diagram in Overview, then taken through an operator edit pass (trimmed banner + Objective meta). Documents the write-once-generate-everywhere model: one `src/<group>/` source → the deterministic `generate.py` → a native plugin per host, drift-gated by `generate.py check` and installed by `bootstrap.sh`; honest about partial per-host generation (named skips, not full parity).

Content-final; carries **no `[PENDING-IMPL]` markers** — the pipeline is as-built. `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). **Re-audit triggers:** re-derive the per-host skip list against the live emitters at the lift; confirm `generate.py check` is in CI; the crickets-v3-native-plugins reconcile is done (subsumed here 2026-06-24, AG Wave 2).
