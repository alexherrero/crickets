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
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-21) · locked 2026-06-28 (final AG design sweep).** child-design — the build pipeline, parent [crickets HLD](crickets-hld.md). Subsumes the launched `crickets-v3-native-plugins.md` design (the *why*; this is the *how* — now its single home; AG Wave 2, 2026-06-24). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3).

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

A deterministic generator (`scripts/generate.py`), reading the source through one shared parser (`src_model.py`), emits a **native plugin per host** — `dist/claude-code/` and `dist/antigravity/` — each in that host's own shape via a per-host emitter (`emit_claude.py`, `emit_antigravity.py`). **Determinism is the property that matters here**: sorted iteration and stable JSON keys make the output byte-reproducible, which is what lets a CI gate trust it.

- **The committed `dist/` + the drift gate.** `dist/` is committed, and `python3 scripts/generate.py check` re-runs the generator and fails if the committed output diverges from the source — so "generated, never hand-edited" is *enforced*, not just intended (the gate is in `check-all.sh` + CI).
- **Adding a host = adding an emitter.** Emitters register against a `HostEmitter` base via a small registry (`_EMITTER_MODULES`), so a new host is a new emitter module, not a change to the core driver.
- **Install.** Three modes in decreasing automation: **`bootstrap.sh`** (device-wide `--scope user` into `~/.claude/` by default — the one-liner), **marketplace** (explicit `claude install` / `agy install` from the emitted `marketplace.json`), **manual** (direct file placement). `install.sh` / `install.ps1` are retired — native host plugin systems replace them. Installed device-wide, per-project harness state lives under the configured vault (`<vault>/projects/<slug>/_harness/`) rather than in each repo's `.harness/` — degrading to a repo-local `.harness/` when no vault is configured. crickets stands alone (no install dependency on agentm; agentm bundles crickets in its own one-liner). The generator-emitted `default-set.json` + per-host `marketplace.json` carry install metadata + soft-composition links.

### Host-agnostic source, host-specific output

The *definition* is single-source; the *generation* is deliberately **partial** where a host lacks a surface — a host gets only the subset of a capability's primitives it can express, and each skip is logged at generation time (so coverage gaps are visible, not silent). The validator (`lint_src.py`) checks the source; the emitters record what they drop. As-built today: the **Antigravity** emitter now emits `rule` and `output-style` kinds into its `rules/` surface (previously dropped), so it has no live skip case against anything currently declared in `src/` — its generic skip branch exists for a future unrecognized `kind`, not a present-day gap; its hook events remain a real gap (no `SessionStart` / `UserPromptSubmit` equivalent). The **Claude** emitter drops `kind: snippet` primitives — Claude has no instruction-file type to hold them.

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

**2026-07-23 — the generator emits a Claude Code marketplace rename tombstone (Loose Ends arc, "Release and generator polish" tasks 2-3) — ADR 0013's own re-audit trigger firing.** ADR 0013 (below) names its re-audit trigger as "a host plugin-manifest/marketplace schema change" — Claude Code shipping a top-level `renames` map in `marketplace.json` (v2.1.193+, confirmed live against `code.claude.com/docs/en/plugin-marketplaces.md`, "Rename or remove a plugin") is exactly that. `group.yaml` gains an optional `renamed_from:` field (documented in `src/SCHEMA.md`); a new pure function, `src_model.build_renames_map()`, walks each group's chain (`renamed_from + [current slug]`) and zips consecutive pairs into the map, so a name renamed twice resolves through both hops rather than collapsing to a single old-to-final jump (Claude Code's own chain-resolution contract requires this). `generate.py`'s driver scopes the map per host to only the groups that host actually emits — a rename entry must never reference a plugin name absent from that host's own marketplace. Proven against two real cases, not synthetic fixtures: `wiki` (`renamed_from: [wiki-maintenance]`, single-hop — the actual FOLLOWUPS-motivating incident, an install hitting a bare `plugin-not-found` on this exact rename, 2026-06-10) and `tokens` (`renamed_from: [status-line-meter, token-audit]`, two-hop). Closes crickets #41's v3.x residual (the generator rename-tombstone, blocked since 2026-06-10 on host support that has now shipped).

**Claude-only; Antigravity is a named skip, not a silent one.** `emit_antigravity.py`'s `write_marketplace`/`write_root_marketplace` both accept the same `renames` parameter (interface parity with the base `HostEmitter`) but explicitly ignore it, with a comment naming why: Antigravity's docs (`antigravity.google/docs/cli/plugins`, checked live) document only `plugin.json`'s shape, no marketplace-level schema at all — there is no field to hang this off. This matches the design's own established "not full parity — the honest claim is one definition, generated and drift-gated for every host, with named skips where a host can't represent a primitive" (Risks & open questions, below) rather than being a new exception to it. The existing host-agnostic fallback (`scripts/reconcile_plugins.py`, shipped 2026-06-10) still covers Antigravity and any pre-v2.1.193 Claude Code install.

*Why not wait for Antigravity to add an equivalent field before shipping either side:* the two host emitters already tolerate divergent per-host coverage everywhere else in this pipeline (the `snippet` kind, hook-event mapping); gating a shipped, real fix for Claude Code on an unscheduled Antigravity feature would leave the actual FOLLOWUPS incident unresolved for no benefit to Antigravity users, who are no worse off than before (the reconcile fallback already covers them). *Why not a hand-maintained rename ledger instead of a `group.yaml` field:* every other piece of a group's marketplace-facing identity (name, description, category, capabilities) is already source-of-truth-in-`group.yaml`, generator-emitted — a separate ledger file would be a second place to remember on every future rename, exactly the drift this pipeline's single-source model exists to prevent.

*Re-audit trigger:* Antigravity ships a marketplace-schema field for the same purpose (extend `emit_antigravity.py` to stop ignoring `renames`, and reconsider whether `renamed_from:`'s single "no equivalent" framing in `src/SCHEMA.md` needs to become per-host); or a `renamed_from:` chain grows long/tangled enough (three-plus hops, or two groups independently claiming overlapping old names) that hand-authored lists stop being the right authoring shape and a dedicated rename-ledger file is warranted instead.

**2026-07-07 — the generator gained content interpolation, not just verbatim copy (PLAN-opinion-consumer-grammar task 2).** Until this task, every single-file primitive (`kind: command|agent|skill`, etc.) emitted byte-for-byte via a plain `shutil.copy2` in each host emitter's `_copy_component()`. Task 2 adds `scripts/src_model.py`'s `interpolate_opinions()` + `render_primitive_text()`, called from both `emit_claude.py` and `emit_antigravity.py` in place of the bare copy: a primitive that declares an `opinions:` frontmatter key and carries an `<!-- opinion:name --> … <!-- /opinion:name -->` marker gets that marker's contents replaced with a committed snapshot's body (`scripts/opinion-snapshots/<name>.md`) at build time — a primitive with no `opinions:` key still emits byte-identical to the old plain copy. This does **not** reopen the Risks section's "as-built, no `[PENDING-IMPL]`" claim below: the feature is fully built (not a placeholder for something un-shipped), determinism is preserved (verified: two consecutive `build` runs produce identical output, `generate.py check` exits 0), and only the single-file copy path is wired — `copytree`-based skill/hook directories are untouched, out of scope, not a broken promise. *Why note this as an amendment rather than silently updating "The generator" section's prose:* the generator's behavior category changed (verbatim-copy-only → copy-with-optional-interpolation) after this design was locked "as-built" on 2026-06-21/28 with no such mechanism existing; a reader relying on the locked claim "one deterministic generator, no splice/placeholder convention" (echoed in this plan's own Constraints section, `emit_claude.py:42`'s `${CLAUDE_PLUGIN_ROOT}` cited as the only prior regex-substitution precedent) needs the record corrected, not just the code. *Why not the alternative (rewrite "The generator" section body in place with no log entry):* the section's prose already generalizes correctly ("emits a native plugin per host... in that host's own shape") and doesn't name copy2 specifically, so no sentence there is now false — the gap was in this Amendment log's history, not the body text. *Re-audit trigger:* if a second interpolation source (beyond `opinions:` snapshots) or a second copy path (`copytree`-based dirs) is added, fold both into "The generator" section's body prose directly rather than accreting further amendment entries describing the same category of change.

**2026-07-05 — doc-truth sweep: corrected two stale/false claims (PLAN-r2-ledger-and-dist task 8).** (1) The folded ADR 0013 record called `generate.py` "stdlib-only" — false: `scripts/generate.py` and `scripts/src_model.py` both `import yaml` (guarded by try/except) to parse `group.yaml`/frontmatter, and every CI workflow installs PyYAML before invoking the generator. Corrected to "a deterministic `generate.py` (PyYAML for manifest parsing, otherwise stdlib)". (2) The "Host-agnostic source, host-specific output" paragraph's "As-built today" sentence was stale — task 4 (commit fb8fbd0) fixed `emit_antigravity.py` to emit `rule` and `output-style` kinds into its `rules/` surface, so Antigravity no longer skips them; verified against the live file that nothing currently declared in `src/` hits Antigravity's generic skip branch anymore (only a future unrecognized `kind` would). Reworded to state Antigravity has no live skip case today (its real remaining gap is hook events, not primitive kinds), and left the Claude-side `kind: snippet` skip as-is since it's still accurate. *Why not the alternative:* PyYAML is a real, permanent, load-bearing dependency (manifest parsing needs a YAML parser) — reintroducing a fake stdlib-only build to match the doc would be worse than fixing the doc. *Re-audit trigger:* re-derive the per-host skip list against the live emitters whenever a new primitive `kind` is added, or whenever PyYAML is dropped or replaced.

**2026-06-28 — lock-down sweep (operator review).** Sized the pipeline diagram (`width`/`height`). Confirmed the single-source-of-truth + determinism (the `generate.py check` drift gate) and the honest partial per-host generation (Antigravity thin-separate; named skips, not full parity). The folded ADR 0012/0013/0014/0015 records and the newest-first log are unchanged. Locked as a v5–v8 guidepost.

**2026-06-24 — subsumed the launched `crickets-v3-native-plugins.md` design (AG Wave 2, move-and-retire).** This design was the *how* reconciling that earlier *why*; it now subsumes it outright. The v3 design is deleted (git history + its six part files retain the full text); its still-live value — the two C4-folded ADRs it had absorbed (AG Phase-2) — is preserved below with decision + why-not + re-audit. The body already holds the as-built pipeline; the per-host emitter differences (the Claude/Antigravity mapping, the `SessionStart` gap, snippets → `rules/`) live in the live emitters + `wiki/reference/Per-Host-Paths.md`.

- **ADR 0013 — bundles are native host plugins, generated from one source (2026-06-02).** One source of truth under `src/<group>/` + a deterministic `generate.py` (PyYAML for manifest parsing, otherwise stdlib) emits native per-host plugins into committed `dist/{claude-code,antigravity}/`; functional grouping (folder) is the unit of distribution; cross-plugin reuse is generation-time dependencies, never a duplicated primitive; a `generate.py check` drift gate makes determinism non-negotiable. Antigravity composition is **thin-separate** (no native deps — confirmed at the #40 dogfood: `agy` 1.0.2 has no dependency resolution); Claude uses native `dependencies`. *Why not hand-author per-host / generate-at-install / trust-manual-rebuild:* each recreates adapter drift, breaks the static marketplace + auditable diff, or lets generated output silently drift. *Re-audit trigger:* a host plugin-manifest/marketplace schema change, or a host requiring nondeterministic output.
- **ADR 0015 — #36 partial-revision: #40 proves the architecture, defers the catalog (2026-06-02).** #40 proved the model on crickets' existing primitives (4 groups / 7 primitives — every emitter path) + dogfooded install on both hosts; the #36 skill relocations (`design` → design-docs, `diataxis-author` → wiki, `ship-release` → releasing) + the full catalog (testing / releasing / knowledge) were explicitly deferred to bucket ④. *Why record the boundary as a contract:* so a reader of the sparse post-#40 catalog sees it was partially-revised on purpose, not abandoned. *Re-audit trigger:* the first genuinely-new bucket-④ bundle (does a new primitive kind / host mapping need generator rework?), or the crickets/agentm split shifting again.

*Why not keep `crickets-v3-native-plugins.md` as a standalone living design:* it was already up-pointered and reconciled by this design — keeping the husk forces a chain-read; the living body here is the single source. *Re-audit trigger:* a host plugin/marketplace schema change (regenerate + dogfood).

**2026-06-24 — folded ADRs 0012 / 0014 into this design (AG Phase 4, move-and-retire).**

**0012 — Device-wide harness install + vault-backed state by default (2026-05-26).** `--scope user` (device-wide into `~/.claude/`) becomes the default install. Harness state moves from `<project>/.harness/` to `<vault>/projects/<slug>/_harness/`. Project resolution via a composable resolver chain. Auto-detect bootstrap on first session. agentm bundles crickets in its one-liner; crickets stands alone. Hard-cut deprecation of legacy paths at agentm v4.0.0. Why not per-project-default: clutter in every repo, install drift, tools are operator-scoped not project-scoped. Why not database: vault stays markdown-canonical + filesystem-only. Why not shared install-bundle repo: adds a third repo and complicates discovery. *Re-audit triggers:* GDrive sync lag >30 s; >100 projects or >200 always-load entries; multi-operator use case; Antigravity forks its surface across desktop/CLI.

**0014 — Install decoupling: retire install.sh + agentm↔crickets lib-sync (2026-06-02).** Delete `install.sh`/`install.ps1`, `lib/install/`, `check-lib-parity.sh` from crickets; replace with native host plugin systems. agentm keeps its own `lib/install/`; repos decouple at install time. Three install modes: bootstrap.sh, marketplace, manual. Delivered as crickets v3.0 major. Why not extract `lib/install/` into a shared repo/submodule: preserves bespoke installer that native plugins make unnecessary and adds a third repo. Why not gradual deprecation: no external consumers; clean major-version cut is cheaper. *Re-audit triggers:* agentm's install model changes to again want shared code with crickets; either host drops or substantially changes plugin install; Antigravity gains hook-veto support.

**2026-06-21 — authored, reviewed, and finalized.**

Migrated from the crickets HLD (the build-pipeline mechanics), deepened against the live code, conformed to the abbreviated-design template (Objective / Overview / Design) with a pipeline diagram in Overview, then taken through an operator edit pass (trimmed banner + Objective meta). Documents the write-once-generate-everywhere model: one `src/<group>/` source → the deterministic `generate.py` → a native plugin per host, drift-gated by `generate.py check` and installed by `bootstrap.sh`; honest about partial per-host generation (named skips, not full parity).

Content-final; carries **no `[PENDING-IMPL]` markers** — the pipeline is as-built. `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). **Re-audit triggers:** re-derive the per-host skip list against the live emitters at the lift; confirm `generate.py check` is in CI; the crickets-v3-native-plugins reconcile is done (subsumed here 2026-06-24, AG Wave 2).
