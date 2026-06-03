<p align="center">
  <img src="https://raw.githubusercontent.com/alexherrero/crickets/main/assets/crickets/banner-1600.png" alt="Crickets — Inspired by the Noisy Cricket">
</p>

<p align="center"><em>Inspired by the Noisy Cricket — agent primitives that punch far above their weight.</em></p>

<p align="center">
  <a href="https://github.com/alexherrero/crickets/actions/workflows/ci-all.yml"><img src="https://img.shields.io/github/actions/workflow/status/alexherrero/crickets/ci-all.yml?branch=main&style=for-the-badge&label=CI&labelColor=0a0a0a&logo=github&logoColor=f4efe6" alt="CI"></a>
  <a href="https://github.com/alexherrero/crickets/releases/latest"><img src="https://img.shields.io/github/v/release/alexherrero/crickets?label=LATEST&labelColor=0a0a0a&logo=github&logoColor=f4efe6&style=for-the-badge" alt="Latest release"></a>
  <a href="https://github.com/alexherrero/crickets/blob/main/LICENSE"><img src="https://img.shields.io/badge/LICENSE-MIT-f4efe6?labelColor=0a0a0a&style=for-the-badge" alt="License: MIT"></a>
</p>

<p align="center"><sub>Works with Claude Code + Antigravity — <a href="https://github.com/alexherrero/crickets/wiki/Compatibility">see compatibility</a></sub></p>

**Crickets** is the noisy cricket — small, focused agent customizations that punch above their weight. Skills, hooks, sub-agents, bundles, MCP servers, slash commands, status lines, output styles, workflows, rules, snippets, settings-fragments. The primitives **you** carry into any project to make [Agent M (`agentm`)](https://github.com/alexherrero/agentm) effective.

This wiki is the contributor-facing documentation for Crickets itself. Every page is written for a single reader intent (learn / do / look up / understand) per the Diátaxis convention.

> [!NOTE]
> Repo: [github.com/alexherrero/crickets](https://github.com/alexherrero/crickets). Public, MIT-licensed. PII guardrails (script + skill + pre-push hook) are foundational — see [Purpose and scope](Purpose-And-Scope) for why.

## 📚 New here? Learn by doing.

- [Tutorial 1 — Your first customization](01-First-Customization) — add a hello-world skill, install it into a scratch project, see it land at three host paths. ~10 minutes.

## 🔧 Trying to do something specific?

- [Install crickets plugins](Install-Into-Project) — three install modes (one-liner / marketplace / manual) across Claude Code + Antigravity.
- [Develop a crickets plugin locally](Develop-A-Plugin-Locally) — the source → generate → dogfood → commit loop.
- [Add a skill](Add-A-Skill) — add a new standalone skill.
- [Quality-Gates-Recipe](Quality-Gates-Recipe) — operator-facing recipe for the 5-primitive quality-gates set (replaces the v1.x `quality-gates` bundle; `kind: bundle` reserved-future in v2.0.0).
- [Use the evaluator](Use-The-Evaluator) — dispatch the `evaluator` sub-agent for PASS / NEEDS_WORK grading against a precise rubric.
- [Use the base hooks](Use-The-Base-Hooks) — kill-switch, steer, commit-on-stop. Operator-precision control for long-running Claude Code sessions.

> The `evidence-tracker` hook and the `design`, `memory`, and `diataxis-author` skills, along with Antigravity plugin authoring, moved to [Agent M](https://github.com/alexherrero/agentm) in v2.0.0 (V4 #36 reorg). See the [Agent M wiki](https://github.com/alexherrero/agentm/wiki) for their operational docs.

## 📖 Looking up a detail?

- [Customization Types](Customization-Types) — what each of the 13 kinds means and where to put them (`kind: bundle` + `kind: plugin` reserved-future in v2.0.0).
- [Manifest Schema](Manifest-Schema) — YAML frontmatter contract.
- [Per-Host Paths](Per-Host-Paths) — destination paths per kind per host.
- [Installer CLI](Installer-CLI) — flags, prereqs, exit codes.
- [Compatibility](Compatibility) — supported hosts (Claude Code, Antigravity) + OS matrix + per-manifest `supported_hosts` contract.

## 💡 Want to know why?

- [Purpose and scope](Purpose-And-Scope) — what this repo is for, what it's not.
- [Cross-Repo Memory Protocol](Cross-Repo-Memory-Protocol) — how agentm reads from + writes to the toolkit-side `/memory` skill at phase boundaries.
- [V3 Retrospective](v3-retrospective) — what shipped, what we learned, what's next (closes the V3 arc; ships with harness v3.0.0 + toolkit v1.0.0).
- [Agent Memory Evolution: From ContextVault to V7](agent-memory-evolution) — V1→V7 HLD of the AgentMemory architecture (V3 ships with this release; V4+ is roadmap-deferred).
- [Device-Wide Architecture](device-wide-architecture) — V4 architectural shift from per-repo harness to device-wide agentic OS; rationale for the agentm/crickets split + which primitives live where.
- [Memory-OS Architecture](memory-os-architecture) — **V5, the unbundling**: agentm becomes a storage-agnostic memory OS + plugin host; the workflow/docs/PM/storage capabilities unbundle into crickets plugins. The `memory↔process` + `memory↔storage` seams, the device-local default, and the vault-conserving cutover.
- [Developer Plugin Suite](developer-plugin-suite) — **V5 bucket ④** (the dev-loop foundation): the `developer-workflows` · `developer-safety` · `code-review` plugins + the new `enhances:` soft-composition schema. Child design of Memory-OS Architecture. `Status: final`, planned in 6 parts. See parts: [enhances-schema](enhances-schema), [developer-workflows](developer-workflows), [developer-safety](developer-safety), [code-review](code-review), [auto-enable-runtime](auto-enable-runtime), [seed-retirement](seed-retirement).

### Architecture decisions

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

### Designs

The canonical "Why we built X" entry points (published via the `/design` skill, surfaced here when the parent design's last queued part hits `Status: done` and harness `/release` transitions the design to `launched`).

- [MemoryVault — permanent agent memory via Obsidian-vault-folder + reflection sidecar](memoryvault) — single `memory` skill in `crickets` with sub-commands `save` / `evolve` / `reflect` / `search`; SessionStart + UserPromptSubmit recall hooks; reflection sidecar with tri-modal confidence routing; two-tier idea capture (Ideas.md surface + `_idea-incubator/` deep research); planned in 6 parts across plans #7a (5 parts) + #7b (1 part). See parts: [write-primitives](write-primitives), [recall-loop](recall-loop), [reflection-and-recovery](reflection-and-recovery), [idea-ledger](idea-ledger), [seed-pass](seed-pass), [discovery-mining](discovery-mining).
- [diataxis-author — Diátaxis wiki authoring + maintenance for any repo](diataxis-author) — second major skill after `memory`; subsumes the harness's `migrate-to-diataxis` predecessor; AgentMemory-integrated conventions; planned in 5 parts. See parts: [skill-scaffold](skill-scaffold), [author-classify](author-classify), [check-repair](check-repair), [migrate-subsume](migrate-subsume), [agentmemory-docs-release](agentmemory-docs-release).
- [Crickets v3.0 — Native Host Plugins from a Single Source of Truth](crickets-v3-native-plugins) — retires the bespoke `install.sh` dispatch for a single source of truth + a generator emitting **native Claude Code + Antigravity plugins** (folder-per-group; committed `dist/` + a generated-in-sync CI gate; native `dependencies` on Claude, thin-separate on Antigravity); **three install modes** (one-line default installer / marketplace / manual pick-and-choose); decouples the agentm↔crickets `lib/install/` byte-sync. `Status: final`, planned in 6 parts. See parts: [foundations](foundations), [generator-claude](generator-claude), [antigravity-emitter](antigravity-emitter), [ci-gate](ci-gate), [distribution-clean-break](distribution-clean-break), [dogfood-proof-docs](dogfood-proof-docs).

## Conventions

Page templates, filename rules, and the Diátaxis four-mode split mirror the sibling repo's documentation convention — see [agentm/harness/documentation.md](https://github.com/alexherrero/agentm/blob/main/harness/documentation.md). The mode-purity lint (`scripts/check-wiki.py --strict`) is the same.
