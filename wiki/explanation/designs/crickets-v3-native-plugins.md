---
title: Crickets v3.0 — Native Host Plugins from a Single Source of Truth
status: final
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-01
updated: 2026-06-01
last_major_revision: 2026-06-01
prd:
project:
---

<!--
  Confidential design draft (#40 / ROADMAP-MASTER bucket ③). Lives in
  .harness/designs/ (gitignored) while drafting; promote to
  wiki/explanation/designs/ at Status: final.

  Status lifecycle (skill-enforced; don't hand-edit `status:`):
    draft → review → final → launched.
-->

# Crickets v3.0 — Native Host Plugins from a Single Source of Truth

## Context

### Objective

Crickets ships the operator's developer-workflow customizations — skills, sub-agents, hooks, slash commands, MCP configs — into Claude Code and Antigravity. Today it does that through a bespoke `install.sh` that parses per-primitive YAML manifests and dispatches each one to host-specific paths, and it shares its `lib/install/` layer byte-for-byte with the sibling `agentm` repo. Both target hosts have since shipped *native* plugin systems that already do dispatch, dependency resolution, and distribution for us. Crickets v3.0 retires the bespoke installer in favor of **native host plugins generated from one source of truth**, and **decouples the `agentm`↔`crickets` `lib/install/` byte-sync** — the exact re-audit [ADR 0006](../../wiki/explanation/decisions/0006-crickets-split.md) anticipated. We do it now because the coupling has become chronic and the v3.x bundle catalog (ROADMAP-MASTER ④) cannot be built cleanly on top of the old dispatch model.

### Background

- **The split (ADR 0006, 2026-05-12).** crickets was carved out of agentm to keep the harness README focused and let the customization catalog grow without a parity tax. The v2 mechanism: a custom `install.sh` reads each primitive's YAML frontmatter (`kind`, `supported_hosts`) and copies it to host-native paths; `lib/install/` is shared **byte-identically** with agentm via `sync-lib.sh` + a `check-lib-parity.sh` CI gate. ADR 0006 recorded the load-bearing assumption: *"lib/install/ byte-identity holds… if drift becomes chronic, we revisit submodules or extract a third repo."* v3.0 is that re-audit firing — but the resolution is **go native**, not extract a shared lib.

- **Current state.** crickets is still sparse — `skills/` = dependabot-fixer + pii-scrubber; `agents/` = 3 evaluators; `hooks/` = commit-on-stop / kill-switch / steer; `bundles/` empty; no `plugin.json` anywhere. The v3.x catalog (Developer base + Testing / Releasing / Wiki / Design-docs / GitHub-CI / PII / knowledge bundles) is mostly to-be-built, and several primitives still live in agentm's `harness/` (the #36 moves: `design`, `diataxis-author`, `ship-release`).

- **Both hosts now have native plugin systems (research-verified, 2026-06-01).** Claude Code: `.claude-plugin/plugin.json` with a rich schema including a **native `dependencies` (semver)** field; one `marketplace.json` lists many plugins; components = skills / commands / agents / hooks (auto-merged, `${CLAUDE_PLUGIN_ROOT}`) / MCP / LSP / output-styles. Antigravity: reuses the `.claude-plugin/plugin.json` convention; a separate `.agents/plugins/marketplace.json`; hook events `PreToolUse / PostToolUse / PreInvocation / PostInvocation / Stop`. A live reference repo — `github.com/iicmaster/antigravity-plugins` — already emits one repo → Claude + Codex + Antigravity from shared plugin dirs, which is exactly the pattern this design generalizes.

- **Position in the program.** ROADMAP-MASTER bucket ③ "Crickets v3.0 — Plugins that stand on their own" = **#40** (this design: native-plugin consolidation + lib-sync decouple) + **#42** (dual-mode standalone/integrated). Design-first; the keystone that makes bucket ④ (the catalog) buildable. Sequenced after ② Hardening I but permitted to open pre-V4-close (opening #40's design is itself a documented surface-split trigger).

## Design

### Overview

crickets becomes a **single-source-of-truth repository plus a generator**. Authors write each customization once, in an evolved version of today's per-primitive manifest format (one folder per primitive; YAML frontmatter carrying `kind`, `supported_hosts`, and — new — `requires:` / `standalone:`). Customizations are organized into **functional groups** ("plugins"): Developer (the base), Testing, Releasing, Wiki, Design-docs, GitHub-CI, PII, and the knowledge/personal set. A **build step (the generator)** reads the source of truth and emits, for each functional group, a **native plugin directory per host** — a Claude Code plugin and an Antigravity plugin — plus the two host marketplace manifests. The generated artifacts are **committed to the repo** (so the marketplaces serve static files and a CI gate proves "generated is in sync with source"), and the bespoke `install.sh` *dispatch engine* is **deleted** (clean break, v3.0 major) — the `agentm`↔`crickets` `lib/install/` byte-sync disappears with it. Installation moves entirely onto the hosts' native plugin systems, offered in **three modes**: a **one-line default installer** (`curl … | bash` — wires up the recommended config in one shot, for people who want the full opinionated setup like the operator), the **marketplace** (add `alexherrero/crickets`, browse + install by name), and **manual pick-and-choose** (point a host directly at any committed plugin dir, no marketplace needed). All three land on the same generated native plugins; they differ only in convenience vs. control.

### Infrastructure

No runtime services — crickets is a build-time tool plus a static distribution surface. The moving parts:

- **Source of truth** (`src/`): per-primitive folders, grouped by functional plugin (see Detailed Design).
- **The generator** (`scripts/generate.py`; Python, stdlib-only to match agentm): a deterministic, network-free function `src/ → dist/`.
- **Committed output** (`dist/`): `plugins/<group>/` with `.claude-plugin/plugin.json` + components (shared with Antigravity's plugin dir); plus `.claude-plugin/marketplace.json` (Claude) and `.agents/plugins/marketplace.json` (Antigravity).
- **CI gate**: re-runs the generator and fails if committed output differs from a fresh generation (replaces `check-lib-parity.sh`).
- **Distribution (three modes, same native plugins):** (1) a thin **one-line installer** (`curl … | bash`) that detects the host(s) + installs the default config; (2) the repo as **marketplace** (`claude plugin marketplace add alexherrero/crickets` / `agy` equivalent); (3) **manual** — point a host directly at any committed `dist/plugins/<group>/` dir, no marketplace.
- **Dev loop**: per-host native dev modes (`claude --plugin-dir <generated-dir>` / `agy plugin link`) replace the old source-mode symlink-into-`~/.claude` (see Operations).

### Detailed Design

#### SoT schema + layout

**Layout: folder-per-group** *(Decision 1, 2026-06-01).* The source of truth is organized as one folder per functional group — `src/developer/`, `src/testing/`, `src/releasing/`, `src/wiki/`, `src/design-docs/`, `src/github-ci/`, `src/pii/`, and the knowledge/personal set — each holding its own primitive folders (`skills/`, `agents/`, `hooks/`, `commands/`, `mcp/`, …). A primitive's group is simply the folder it lives in, so the grouping is legible straight from the tree. Cross-plugin reuse (e.g. Testing building on Developer) is expressed by **plugin dependencies at generation time**, not by a primitive belonging to two groups, so no file is duplicated. This choice is invisible to end users: the generator emits one named plugin per group and lists them in the host marketplaces regardless of source layout.

**Group manifest.** Because group = folder, group-level metadata lives in a per-group manifest (e.g. `src/testing/group.yaml`): `name`, `description`, `category`, `requires:` (other group slugs this one depends on), `standalone:` (bool — independently installable). Each primitive folder keeps its existing per-primitive frontmatter (`kind`, `supported_hosts`). This separates "what this plugin is" (group manifest) from "what this primitive is" (primitive frontmatter).

#### Generator

A deterministic, network-free Python (stdlib-only) build script — `scripts/generate.py` — implementing the pure transform `src/ → dist/`:

1. Discover group folders under `src/`; parse each `group.yaml` + every primitive's frontmatter.
2. For each host in `{claude-code, antigravity}` ∩ the group/primitive `supported_hosts`, run that host's **emitter**.
3. Write committed artifacts under `dist/plugins/<group>/` (shared plugin dir per group).
4. Emit the two marketplace manifests (`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`).

A **per-host emitter** is a small module implementing a common interface (`manifest`, `hooks`, `mcp`, `marketplace`). Adding a future host = adding an emitter (honors the extensible-host-scope decision). Determinism is mandatory — sorted iteration, stable JSON key order, no timestamps in output — so the CI gate diff is meaningful.

CLI: `generate.py build` (write `dist/`), `generate.py check` (build to a temp dir, diff against committed `dist/`, non-zero on drift — the CI gate), `generate.py clean`.

#### Per-host mapping

| Aspect | Claude Code | Antigravity |
|---|---|---|
| Plugin manifest | `.claude-plugin/plugin.json` (full schema) | same `.claude-plugin/plugin.json` (min `name`/`version`/`description`/`author`) — shared dir |
| Marketplace | `.claude-plugin/marketplace.json` (`owner`/`metadata`, `source: "./path"`) | `.agents/plugins/marketplace.json` (`interface.displayName`, `source:{source:local,path}`, `policy`, `category`) |
| skills / commands / agents | native dirs | native dirs |
| Hooks file | `hooks/hooks.json` (auto-merge) | `hooks.json` (under `.agents/`) |
| Hook event names | `PreToolUse` / `PostToolUse` / `SessionStart` / `UserPromptSubmit` / `Stop` | `PreToolUse` / `PostToolUse` / `PreInvocation` / `PostInvocation` / `Stop` (**no** SessionStart / UserPromptSubmit) |
| Hook script paths | `${CLAUDE_PLUGIN_ROOT}/…` | relative paths |
| MCP | `.mcp.json` / inline | `mcp_config.json` (`serverUrl`, strict JSON, no `timeout`) |
| Dependencies | native `dependencies` (semver) | thin + documented (verify-on-dogfood) |
| Instruction snippets | folded into a skill/agent | emitted to `rules/` |
| status-line / settings-fragments | out of scope | out of scope |

**SessionStart→AG gap.** Claude hooks bound to `SessionStart` / `UserPromptSubmit` have no Antigravity event. Per hook the generator either marks it `supported_hosts: [claude-code]` (Claude-only) or maps to the nearest AG event (`PreInvocation`, which lacks session-boot semantics). Crickets' own control hooks map cleanly on both hosts: `commit-on-stop` → `Stop`; `kill-switch` / `steer` / `evidence-tracker` → `PreToolUse`. The SessionStart-heavy hooks are agentm's (memory-recall, harness-context) — out of crickets scope.

#### Composition + #42 (`requires:` / `standalone:`)

**Thin — separate + documented** *(Decision 2, 2026-06-01).* A group's `requires:` emits differently per host, but **never by duplicating primitives**:

- **Claude Code** — native: the dependent plugin's `plugin.json` gets `dependencies: [<base>]` (semver), so installing Testing auto-installs Developer. Host-resolved, single copy.
- **Antigravity** — thin: the dependent plugin carries **only its own** primitives; the generator records the dependency in the group manifest + the plugin's README + the marketplace entry, and documents "install Developer first." No inlining, so base + several dependents never double-registers a hook or collides a command.
- **`standalone:` groups** (PII, knowledge/personal) declare no `requires:` and ship self-contained on both hosts — #42's "works standalone" mode; the require-Developer groups are #42's "integrated" mode.

**Load-bearing assumption + re-audit trigger:** Antigravity's native cross-plugin dependency support is *unconfirmed* (research could not read the live `plugin.json` schema). The generator emits AG thin-separate today; **re-audit on first AG dogfood** — if Antigravity exposes a `dependencies`-equivalent field, switch the AG emitter to native deps so both hosts auto-resolve and the "install Developer first" doc step disappears.

#### Coverage-gap handling

The three crickets primitive types with no native plugin home (research-confirmed):

- **`snippets/`** (AGENTS.md/CLAUDE.md instruction fragments): kept in the SoT. Emit to Antigravity `rules/` (native). On Claude — which can't ship standalone instruction files — fold the text into the owning skill's `SKILL.md` or an agent system prompt; if a snippet has no natural skill/agent home, drop it (flagged per snippet).
- **`status-line/`**: out of v3.0 plugin scope (neither host ships it as a clean plugin component) → operator-personal / manual.
- **`settings-fragments/`**: dropped — plugin hooks auto-register, obsoleting the fragment-merge machinery. The rare permission/env default becomes a host-specific doc note, not shipped config.

#### Distribution + install modes

All three modes install the **same committed native plugins** — the committed-`dist/` decision is what makes them possible, since every `dist/plugins/<group>/` is a ready-to-consume plugin dir. They trade convenience for control:

1. **One-line default installer (`curl … | bash`).** A thin bootstrap script (crickets-side — a *wrapper*, **not** the deleted v2 dispatch) that detects the installed host(s) (Claude Code / Antigravity / both), adds the crickets marketplace, and installs + enables the **default configuration**: the operator's recommended set (Developer + Testing + Releasing + Wiki + Design-docs + GitHub-CI, plus standalone PII). The result is byte-for-byte what you'd get clicking through the marketplace, in zero clicks — for people who want the full opinionated setup in one shot (the operator's own path; mirrors the `dev-setup` curl|bash pattern). It only ever calls the hosts' **native** `plugin install` commands; it never parses manifests or copies primitives.
2. **Marketplace (browse + pick).** The native discovery path: `claude plugin marketplace add alexherrero/crickets` then install by name or via the UI; `agy` equivalent. Best for users browsing the catalog.
3. **Manual pick-and-choose (no marketplace).** For users who want a subset without the marketplace's extra clicks: install a chosen plugin **directly from its committed dir** — Claude `claude --plugin-dir dist/plugins/<group>` (or skills-dir auto-load); Antigravity `agy plugin install` / `link` against the local dir. Simple copy-paste per plugin, no marketplace add. (Integrated plugins still surface their `requires:` so the user grabs the base too.)

The one-liner and the manual path are **documented how-tos** (see Documentation Plan); the marketplace is the default discovery surface.

#### Repo layout + clean break (proof scope)

**Added:** `src/<group>/…` (SoT); `dist/plugins/<group>/…` + the two marketplace manifests (committed generated output); `scripts/generate.py` + tests.

**Deleted (clean break, v3.0 major):** `install.sh` / `install.ps1` dispatch; the crickets copy of `lib/install/`; `sync-lib.sh`; `check-lib-parity.sh`; the old top-level primitive dirs (`skills/`, `agents/`, `hooks/`) — their contents migrate into `src/<group>/`. **agentm keeps its own `lib/install/`**; decoupling means crickets stops mirroring it (the generator is repo-agnostic, so agentm can adopt it later — out of #40 scope).

**Proof scope** *(Decision 3, 2026-06-01).* #40 proves the architecture by emitting crickets' **existing** primitives as real plugins on both hosts and dogfooding install: `pii-scrubber` → a standalone PII plugin; `commit-on-stop` / `kill-switch` / `steer` + the three evaluators → grouped plugins. The **full Developer-base composition and the #36 skill moves** (`design` → Design-docs, `diataxis-author` → Wiki, `ship-release` → Releasing) are **bucket ④** — #40 writes the "#36 partial revision" ADR documenting intent but defers the relocations.

## Alternatives Considered

1. **Keep the custom `install.sh`, lower the parity tax in place.** Rejected: leaves the byte-sync coupling intact and keeps re-implementing dispatch the hosts now do natively; the maintenance tax only grows as the catalog grows.
2. **Extract `lib/install/` into a third shared repo / submodule** (ADR 0006's other named re-audit option). Rejected: solves the coupling but preserves a bespoke installer the native plugin systems have made unnecessary, and adds a third repo to maintain. Going native deletes the installer outright.
3. **Hand-author per-host plugins (no generator).** Rejected: recreates the adapter-tree duplication ADR 0006 split *away from* — two hand-maintained copies that drift. The generator is the single-source discipline.
4. **Generate at install time (repo holds only the SoT, no committed `dist/`).** Rejected: the marketplace must serve static files, and committed artifacts give an auditable CI diff + let users browse the real plugins. (This is the committed-output decision from the earlier round.)

## Dependencies

- **Technical:** Claude Code plugin system (≥ v2.1.110 for dependency semver + marketplace/dev-loop features); Antigravity plugin system (`agy plugin`); Python 3 (generator, stdlib-only).
- **Internal / sequencing:** ADR 0006 (the split this revises); the #36 skill moves (deferred to ④ per Decision 3); roadmap order puts ② Hardening I before ③ (soft); the GitHub Project surface split (deferred until V4 close + #40/#42).
- **Organizational:** operator-only; no team approvals.

## Migrations

- **Clean break — no transition scaffolding** (earlier-round decision 4). The `install.sh` dispatch is deleted in the same release that ships the generator + marketplace.
- **Operator dogfood migration:** existing source-mode symlink installs (crickets primitives symlinked into `~/.claude`) are replaced by native plugin installs (`claude plugin marketplace add` + install; `agy` equivalent). One operator-side step; documented in the v3.0 release notes + a how-to.
- **crickets-side removal:** `lib/install/`, `sync-lib.sh`, `check-lib-parity.sh` deleted; agentm retains its own copy.
- **No persistent data/state to migrate** — crickets ships config, not data.

## Technical Debt & Risks

- **AG `plugin.json` schema + dependency support unconfirmed** (live JS-rendered docs unreadable). Generator emits thin-separate + documents; verify-on-dogfood re-audit trigger (see Composition).
- **AG has no `SessionStart`/`UserPromptSubmit`.** Claude session-boot hooks have no AG analog; the generator marks such hooks Claude-only or maps to `PreInvocation` (no boot semantics). Crickets' own hooks are unaffected; the gap bites only if a future crickets hook needs session-boot on AG.
- **Host plugin schemas are still evolving** (Claude has experimental fields; AG is new). Mitigation: the generator centralizes host-specifics in per-host emitters — one place to fix when a schema shifts. Re-audit on each host major version.
- **Generator/`dist` drift** if someone hand-edits `dist/`. The CI `check` gate catches it; residual risk is a contributor bypassing CI (operator-only repo → low).
- **No manifest-dispatch fallback after the clean break.** If a host's plugin system regresses, the one-line installer can't help (it just calls the host's native `plugin install`, which is what's broken) and there's no v2 dispatch to fall back to — recovery is a git revert to v2 (see Rollback).
- **The one-line installer is a small maintenance surface.** It encodes the default-config plugin set + host-detection; if a host changes its `plugin install` CLI, the wrapper breaks. Mitigation: keep it thin (native commands only), cover it in the dogfood install test, and **emit the default-set list from the generator** (data, not hard-code) so it can't drift from the catalog.

## Quality Attributes

*Proposed below; confirm each in the review pass.*

### Security

**Real.** Installing a plugin grants code execution (hooks, MCP servers, `bin/`). The crickets marketplace must be trusted; plugins ship only the operator's own vetted primitives — no third-party code. crickets is **public** and `dist/` is committed, so the PII guardrails (pii-scrubber skill + pre-push hook + CI scan) must extend to cover generated output, not just `src/`. Primary concern: a generated artifact leaking a personal path/email → the pre-push hook + CI PII scan run over `dist/`.

### Reliability

**Real (modest).** The generator must be deterministic — non-deterministic output would make the CI gate flap. Mitigation: sorted iteration, stable JSON serialization, no timestamps/absolute paths in output. No runtime reliability surface (build-time tool); generator failures are build-time and loud.

### Data Integrity

N/A: build-time tool with no persistent data store. The only integrity property — generated-matches-source — is enforced by the CI gate (see Testability).

### Privacy

**Real (light, overlaps Security).** crickets is public; committed `dist/` + marketplace manifests must not leak operator PII (paths, emails, tokens). The existing PII guardrails extend to generated output; no user data is processed.

### Scalability

N/A: the catalog is ~12 plugins / dozens of primitives; generation is sub-second and has no scale dimension that stresses anything.

### Latency

N/A: build-time tool — generation latency is irrelevant to users; install latency is the host's concern, not crickets'.

### Abuse

N/A: no network surface, no untrusted input, no multi-tenant exposure — a local/CI build script over the operator's own files.

### Accessibility

N/A: no UI; artifacts are config files consumed by host CLIs/IDEs whose own accessibility is the host's concern.

### Testability

**Real (core).** The CI "generated-in-sync-with-SoT" gate is the central test; it's only possible because generation is deterministic (see Reliability). Plus: unit tests for the generator (per-host emitters, the mapping table, the snippet/hook edge cases) and a dogfood install test on both hosts against agentm/crickets/sherwood.

### Internationalization & Localization

N/A: developer tooling, English-only config + docs; no end-user-facing localized content.

### Compliance

N/A: personal developer tooling, no regulated data, no audit/regulatory regime (GDPR/HIPAA/SOC2 inapplicable).

## Project management

### Work estimates

| Piece | Size |
|---|---|
| SoT layout + manifest evolution (migrate existing primitives into `src/<group>/`, add group manifests) | S–M |
| Generator core + per-host emitters + CLI | M |
| CI gate + generator unit tests | S–M |
| Marketplace manifests + distribution wiring | S |
| Clean-break deletion (install.sh, lib/install, sync-lib, parity gate) | S |
| Dogfood proof (emit existing primitives; install both hosts on agentm/crickets/sherwood) | M |
| One-line default installer + manual-install how-tos | S |
| 3 ADRs | S |

Likely **4–6 parts** when translated.

### Documentation Plan

- **ADRs:** "bundles = native host plugins"; "#40 install-decoupling"; "#36 partial revision" (documents the deferred moves).
- **wiki/how-to:** "Install crickets plugins" — covering all three modes (one-line default, marketplace, manual pick-and-choose) per host; "Develop a crickets plugin locally" (the dev loop).
- **wiki/reference:** the SoT manifest schema; the per-host mapping table.
- **wiki/explanation:** this design, published at `Status: final`.
- Update crickets `AGENTS.md` / `README.md` for the new model; remove `install.sh` references.

### Launch Plans

Clean break, single release (**crickets v3.0** major). Dogfood on the operator's own repos first (confidential design → final → publish). No feature flag — it's a dev-tool install-model swap, not a runtime feature. The breaking change is called out loudly in the v3.0 release notes.

## Operations

### SLAs

N/A: internal/personal developer tooling, no external SLA.

### Monitoring and Alerting

The CI gate (generated-in-sync + generator unit tests + PII scan over `src/` and `dist/`) is the monitoring surface — green/red per push. No runtime monitoring (no service). Marketplace availability = GitHub repo availability (GitHub's SLA).

### Logging Plan

N/A: build-time tool; the generator emits human-readable build output to stdout/stderr; no persistent logs or retention policy needed.

### Rollback Strategy

Reversible by git: reverting the v3.0 release commit restores the v2 `install.sh` dispatch + `lib/install/` (kept in history). Plugins install into host config, not crickets, so backing one out is `claude plugin uninstall` / `agy plugin uninstall`. **Flag:** once the operator migrates their own machine to native plugins, rolling back means re-running the old `install.sh` from the reverted commit — reversible, but a deliberate step, not automatic.

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-06-01 | Initial draft created via `/design author`. | draft |
| 2026-06-01 | Drafted Context + Design Overview/Infrastructure from #40 discussion + verified host research. | draft |
| 2026-06-01 | Locked Detailed Design decisions: folder-per-group SoT (D1); thin-separate AG composition (D2); architecture-only + proof scope, #36 moves deferred to ④ (D3). | draft |
| 2026-06-01 | Drafted remaining Detailed Design subsections + Alternatives / Dependencies / Migrations / Risks / Quality Attributes (proposed) / Project management / Operations. | draft |
| 2026-06-01 | Author signaled ready for review. | review |
| 2026-06-01 | Review pass: added three install modes (one-line default installer + marketplace + manual pick-and-choose) per operator feedback. | review |
| 2026-06-01 | Approved as final via /design author review pass. | final |
| 2026-06-01 | Published to wiki/explanation/designs/ (visibility: confidential → published). | final |
| 2026-06-01 | Translated to 6 parts via /design translate: foundations, generator-claude, antigravity-emitter, ci-gate, distribution-clean-break, dogfood-proof-docs. | final |
