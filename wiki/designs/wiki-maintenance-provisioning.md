---
title: Wiki-Maintenance Provisioning Design
status: final
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-10
updated: 2026-06-10
last_major_revision: 2026-06-10
prd:
project: https://github.com/users/alexherrero/projects/5
---

<!--
  Authored 2026-06-10 from the v3.2.0 dogfood feedback (operator) + the live
  ~/.claude shadowing investigation. status: draft — to be refined by the blog
  dogfood (using the shipped plugin against a fresh repo to surface real gaps).
  Status lifecycle: draft → review → final → launched.
-->

# Wiki-Maintenance Provisioning Design

## Context

### Objective

The wiki-maintenance plugin authors and maintains wiki content, but it doesn't set a repo up to *have* a maintainable wiki. A fresh repo still needs the intent-folder structure, the per-folder sidebars, the publish workflow, and the lint gate wired into its CI — all hand-copied today, which drifts. This design adds a one-step provisioning path so a target repo goes from nothing to a self-maintaining wiki in a single action, and retires the pre-v3 standalone skills that shadow the plugin.

### Background

The gap surfaced the moment the plugin shipped (v3.2.0): the next question was "point it at the blog repo and have everything set up," and there's no answer — authoring works, provisioning doesn't. A consumer today hand-copies `check-wiki.py` and `wiki-sync.yml` and builds the intent-folders by hand; each copy drifts from the source the next release moves.

The pieces already exist — they're just not assembled for a target. The plugin **bundles `check-wiki.py`** (reachable at `${CLAUDE_PLUGIN_ROOT}/scripts/check-wiki.py`), the intent-folder IA + per-folder-sidebar conventions are locked ([ADR 0018](0018-per-folder-sidebars) + the [Wiki design](wiki-design)), and crickets' own 72-line `.github/workflows/wiki-sync.yml` is the proven publisher. What's missing is the wiring that drops them into a repo. The constraint that shapes the whole design: a plugin runs *inside an agent session*, so "init" is an agent-driven command, not a host install hook (Antigravity has no install hook at all).

There's also a correctness debt to clear as part of provisioning *correctly*. The v3 plugin model left the pre-v3 install's `~/.claude/` standalones in place, **shadowing the plugin** — confirmed systemic (every plugin, not just wiki: the phase commands, `explorer`, the reviewers, `recent-wiki-changes`, and the wiki trio all had stale symlinks into agentm). Retiring them is selective: remove only what an *installed plugin now supersedes*, never the genuinely-standalone skills (`design`, `memory`, `doctor`, `last30days`). The V5 ⑤ slim deletes agentm's source copies; this design owns the `~/.claude/` symlink side.

## Design

### Overview

Two surfaces. **A `wiki-init` action** (a plugin command) provisions a target repo: it scaffolds the intent-folders + per-folder sidebars + section landings from the template library, drops a parameterized `wiki-sync.yml` into the target's `.github/workflows/`, and wires `check-wiki.py` into the target's CI by **referencing the plugin-bundled gate** rather than copying it. It is preview-first and idempotent — run it on an empty repo to scaffold, or on an existing wiki to fill gaps without clobbering operator content. **An install-time retirement** extends the `reconcile_plugins.py` pattern to the primitive level: for each installed crickets plugin, remove the `~/.claude/` standalone it now provides, and only that.

### Infrastructure

The init runs as a **plugin command in the agent session** (`Read`/`Write`/`Edit`/`Bash`/`Glob`/`Grep`); it reads the plugin's bundled assets and writes into the target repo. Nothing self-hosted; no new runtime.

**What it reads (plugin-bundled) vs writes (target repo):**

| Reads (`${CLAUDE_PLUGIN_ROOT}/…`) | Writes (target repo) |
|---|---|
| `templates/workflows/wiki-sync.yml` (new) | `.github/workflows/wiki-sync.yml` |
| `scripts/check-wiki.py` (already bundled) | a CI step that *invokes* the bundled gate (+ optional vendored copy) |
| the section-template library + page templates | `wiki/<section>/` folders · per-folder `_Sidebar.md` · section landings |

**When what runs:**

| Trigger | What runs |
|---|---|
| `/wiki-init [--sections …] [--preview]` in the target repo | scaffold + workflow drop + gate wiring (preview-first; idempotent) |
| Plugin install / `bootstrap.sh` / a reconcile command | selective standalone retirement (remove superseded `~/.claude/` standalones) |
| Every push to the target (once wired) | the target's own CI runs `check-wiki.py`; `wiki-sync.yml` publishes |

### Detailed Design

#### 1. Ship `wiki-sync.yml` as a template

Add `templates/workflows/wiki-sync.yml` — crickets' own 72-line workflow, parameterized to be repo-agnostic (no hard-coded owner/repo; the default-branch + `wiki/**` trigger + the case-insensitive dupe-check kept verbatim). The init drops it into the target's `.github/workflows/` and fills any per-repo blanks. **The job is opinionated-named `[W] Update Wiki`** — matching crickets' own publish workflow and the `[W]` badge-status convention, so a provisioned repo's Actions list reads consistently with the rest of the catalog. This is the publish half (deployment, documented in the [Wiki design](wiki-design)).

#### 2. The `wiki-init` action

Scaffolds the [intent-folder IA](0018-per-folder-sidebars): the section folders (a sensible default subset — `get-started/ how-to/ reference/ explanation/`, extensible), each with a `_Sidebar.md` and a section-index landing built from the template library. **Idempotent + preview-first**: it detects an existing `wiki/` and fills only what's missing — never overwrites an operator-authored page. `--preview` writes nothing and prints the plan; `--sections` selects the folder set.

**Non-public cost warning.** Before it writes the workflow, the init checks the target's visibility; if the repo **isn't public**, it warns that GitHub Actions minutes are **billed for private repos** — the wiki-sync publish + the `check-wiki` gate both consume them. Public repos run Actions free, so the warning fires only when it's relevant; the operator confirms before the workflow lands.

#### 3. Gate distribution — reference for the agent, vendor for CI

The plugin bundles `check-wiki.py` once; how the target *reaches* it depends on **who runs the gate**, and the two runners differ in what they can resolve — so the distribution is a deliberate **split**, not one mechanism.

- **Agent path (Claude Code / Antigravity).** The plugin runtime exposes `${CLAUDE_PLUGIN_ROOT}`, so an agent-invoked gate references the bundled script directly (`${CLAUDE_PLUGIN_ROOT}/scripts/check-wiki.py`) — an upgrade re-points automatically, nothing to drift. This is the original "reference, don't vendor" win, and it holds *where that variable exists*.
- **CI path (GitHub Actions).** Actions runners have **no `${CLAUDE_PLUGIN_ROOT}`** — it's a plugin-runtime var, not a CI env var — and no plugin checkout to resolve it against. So `wiki-init` **vendors** the gate into the target's `.github/scripts/check-wiki.py` and the `lint-wiki` job runs that copy. Vendoring here is the **rule, not an opt-in**: there is no other way for a runner to reach the script. **`wiki-init --resync-gate`** re-copies it after a plugin upgrade — the drift the agent path dodges for free is paid down on demand here instead.

So "don't vendor" is the agent-path ideal; CI vendors by necessity and keeps the copy fresh via `--resync-gate`. *(Single-source question — raised as open debt in the original draft — now settled: crickets keeps exactly one hand-maintained gate, the plugin's `src/wiki-maintenance/scripts/check-wiki.py`; the repo-root copy is gone, crickets' own `lint-wiki` job invokes the plugin source directly (same checkout), and every provisioned target vendors a copy from it. See §Tech-Debt #1.)*

#### 4. Retire the standalones (selective)

Extend the reconcile to the primitive level. For each **installed** crickets plugin, enumerate the skills/agents/commands it provides; for each, if a `~/.claude/{skills,agents,commands}/<name>` standalone exists that the plugin now supersedes, remove it (preview-first; report each). **Never** touch a `~/.claude/` standalone that no installed plugin provides — `design`, `memory`, `doctor`, `last30days`, `adapt-evaluator`, `memory-idea-researcher` are agentm-native or third-party and must stay. The match is by primitive name *and* provenance (a crickets-plugin primitive), not name alone.

## Alternatives Considered

- **Vendor `check-wiki.py` into every consumer.** Rejected — it's the drift the operator flagged; the next release moves the script and every copy rots. Referencing the plugin-bundled path upgrades for free.
- **Init as a host install hook.** Rejected — plugins have no target-repo install hook, and Antigravity has no install hook at all. An agent-invoked command is the only portable surface.
- **Blow-away scaffold.** Rejected — it would clobber an operator's existing wiki. Idempotent gap-fill is the only safe behavior for a repo that may already have content.
- **Blind standalone removal** (remove every `~/.claude/` symlink into agentm). Rejected, dangerously — it would delete `design`/`memory`/`doctor`, which no plugin provides. Removal must be supersession-gated.
- **Leave provisioning to docs** (a how-to telling the operator to copy files). Rejected — that *is* today, and it drifts; the point is to make it one action.

## Dependencies

- The plugin's **bundled assets** (`scripts/check-wiki.py`, the template library) + the new `templates/workflows/wiki-sync.yml`.
- The **IA conventions** ([ADR 0018](0018-per-folder-sidebars) + the [Wiki design](wiki-design)) the scaffold materializes.
- The **`reconcile_plugins.py`** pattern (shipped 2026-06-10) the retirement extends to the primitive level.
- The **V5 ⑤ slim** — the source-side counterpart (it deletes agentm's baked-in copies; this owns the `~/.claude/` symlink side). Coordinate so the two don't double-handle.
- The target repo: **GitHub Actions** + a wiki enabled for the publish half.

## Migrations

- **Existing consumers** (crickets, agentm) already have hand-built wikis → `wiki-init` is idempotent: it detects the structure, fills gaps (a missing section sidebar, an absent landing), and never clobbers. Running it on crickets itself should be a near-no-op + a good test.
- **The standalone retirement** is the one-time `~/.claude/` cleanup. The wiki four were removed manually 2026-06-10 (operator machine); the install logic generalizes that to all superseded standalones. The agentm *source* copies remain until the ⑤ slim (don't delete them here).

## Technical Debt & Risks

1. **`check-wiki.py` single-sourcing.** ~~Triple-vendored in crickets (`scripts/`, `src/wiki-maintenance/scripts/`, the bundled `dist/` copy).~~ **Resolved (2026-06-10):** the hand-maintained gate now lives in exactly one place — `src/wiki-maintenance/scripts/check-wiki.py`. The repo-root `scripts/check-wiki.py` was removed; crickets' own `lint-wiki` job invokes the plugin source directly, the `dist/` copy is generated (not hand-edited), and provisioned targets vendor from the plugin per §3. *Re-audit if a second hand-maintained copy ever reappears.*
2. **Writing into an unknown target's CI.** The init assumes GitHub Actions; a repo with a different CI shape needs a different wiring. *Mitigation: GH-Actions-first, documented; detect-and-skip with a printed manual step otherwise. Re-audit if a non-Actions target is provisioned.*
3. **The retirement must not false-remove.** Removing a non-superseded standalone is behavior loss. *Mitigation: supersession-gated by name + crickets-plugin provenance; preview-first; dry-run default. Re-audit if any legitimately-standalone skill is ever flagged.*
4. **Init writes a `contents: write` workflow into the target.** Least-privilege + preview-first; the operator sees the workflow before it lands.

## Quality Attributes

*(Only the attributes with real concerns are kept.)*

### Security

The init drops a workflow that holds `contents: write` on the target's wiki, and the retirement deletes files under `~/.claude/`. Both are **preview-first** and operator-confirmed; the workflow is least-privilege (wiki publish only); the retirement is supersession-gated so it can't reach outside the plugin's own primitives.

### Reliability

Idempotent gap-fill is the defining property — `wiki-init` on an existing wiki must converge without clobbering operator content, and re-running it is a no-op. The retirement degrades safely: if it can't confirm supersession, it skips and reports.

### Data Integrity

The hard line: the retirement removes **only** standalones an installed plugin provably supersedes (name + provenance), never operator content or non-superseded skills. The scaffold writes new files and fills gaps; it never edits an existing page's body.

### Testability

The scaffold plan, the gate-wiring, and the supersession reconcile are pure functions over fixtures (empty repo · partial wiki · full wiki · a `~/.claude/` set mixing superseded + standalone) — unit-testable in the battery without a host CLI, exactly like `reconcile_plugins.py`. `--preview` is the e2e dry-run.

## Project management

### Work estimates

| Part | Size |
|---|---|
| `templates/workflows/wiki-sync.yml` (parameterize) + the gate-reference wiring + single-source the script | S–M |
| The `wiki-init` action (scaffold IA + sidebars + landings; idempotent; preview) | M–L (the real new surface) |
| The selective standalone-retirement reconcile (extend `reconcile_plugins.py`) | S–M |
| Docs (how-to + plugin-page + Wiki-design update) + an ADR (vendor-vs-reference · supersession-gated retirement) | S |

Likely **3–4 parts** when translated.

### Documentation Plan

- A how-to: **"Provision a repo's wiki"** (run `wiki-init`, what it drops, the CI wiring).
- Update the [Wiki-Maintenance plugin page](Wiki-Maintenance) (the new init surface) + the [Wiki design](wiki-design) (provisioning joins authoring).
- An **ADR**: the reference-not-vendor gate-distribution call + the supersession-gated retirement.

### Launch Plans

Ships as a crickets v3.x minor. **Dogfood target: the blog repo** — provision its wiki/docs from nothing with the shipped plugin, and let what's awkward there refine this design before the build.

## Operations

*(SLAs / logging omitted — operator tooling, no service.)*

### Monitoring and Alerting

Once `wiki-init` wires the gate, the **target repo's own CI** is the monitor — `check-wiki.py` runs there on every push and the publish workflow reports. No surface of ours beyond that.

### Rollback Strategy

The init is git-reversible in the target (it only adds files); the retirement is reversible (reinstall the plugin or the standalone). Nothing is deleted that can't be regenerated.

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-06-10 | Authored from the v3.2.0 dogfood feedback (provision-not-just-author) + the live `~/.claude` shadowing investigation (systemic, supersession-gated retirement); drafted against the 10-section template with the 2026-06-09 conventions. Operator review: two changes applied — the publish job is opinionated-named **`[W] Update Wiki`** (matching crickets' own), and `wiki-init` **warns about billed Actions minutes when the target isn't public** — and the design **approved → final**. Voice deferred to the #14 dogfood (corpus piece logged). The blog-repo dogfood validates + may amend; approval doesn't wait on it. Translated to **4 parts** via `/design translate` (operator-approved split **B**, honest deps): `wiki-sync-template` · `wiki-init` · `standalone-retirement` · `docs-adr`. Sequenced into 4 plans via `/design sequence` (Kahn topo order: `standalone-retirement` → `wiki-sync-template` → `wiki-init` → `docs-adr`); first active at vault `_harness/PLAN.md`, 3 queued at `_harness/designs/wiki-maintenance-provisioning/queued-plans/`. | final |
| 2026-06-10 | **Dogfood reconciliation** (build-vs-design drift, pre-`docs-adr`). **Drift 1:** the two shipped CI workflows ran independently — a broken wiki published anyway because lint was a tripwire, not a gate. Merged `wiki-lint` into `wiki-sync` as one lint-then-publish workflow (`update-wiki` `needs: lint-wiki`); fixed crickets' own job likewise (commit `c336f37`, CI green). **Drift 2 (this edit):** §3 re-locked from "reference, don't vendor" to the as-built **split** — reference via `${CLAUDE_PLUGIN_ROOT}` on the agent path, vendor-with-`--resync-gate` for CI because GitHub Actions has no such var. Removed the fictional `--vendor` opt-in (CI vendors by necessity). §Tech-Debt #1 single-source debt marked resolved (one hand-maintained gate in the plugin; repo-root copy removed). Status unchanged — reconciliation, not a new decision. | final |
