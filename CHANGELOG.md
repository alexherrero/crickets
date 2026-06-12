# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v3.3.0] — 2026-06-11 — The wiki composer: manifests become pages

**MINOR — a net-new `wiki-maintenance` capability (additive; no migration).** The seven-section taxonomy (v3.2.1) split each wiki page-type into a *manifest* — an ordered list of reusable section files — but nothing turned that list into a page: the diataxis-author skill's `/diataxis author` read a manifest verbatim and emitted its scaffolding comment instead of assembled prose. **The composer is that missing transform.** It reads a page manifest, loads each named section, strips the author-facing `<!-- SECTION … -->` opinion comment, applies the house voice and the target language, and concatenates the sections in order under the page H1 into a publishable page. Monoliths stay as a verbatim fallback, so nothing that worked before regresses. Design + rationale: the [Wiki Composer design](https://github.com/alexherrero/crickets/wiki/wiki-composer) (`launched`).

### Added

- **Section file shape v2 (`parse_section`)** — a parser for each reusable section file's frontmatter (`section`, `reusable`, `applies-to`) + scaffold + baked-in `<!-- SECTION … -->` opinion comment. Strictly additive over v1: the existing 25-file section library parses unchanged, proven by an additive-across-the-library test.
- **The composer (`compose_page`)** — loads a manifest's `sections:` list, resolves each name against the section library, strips opinion comments, runs the voice step (reuses the skill's `style_resolver`, graceful-degrades when no style resolves), and concatenates deterministically under the H1. A reserved `lang` seam carries the translate-downstream i18n contract — English-only first cut; the Spanish translate-pass stays deferred to its own design.
- **`author.py` manifest dispatch** — `/diataxis author` now routes a `component-overview` manifest through the composer; the other three manifest page-types (`home`, `plugin-home`, `section-index`) are wired but raise `NotImplementedError` (deferred). Anything that isn't a manifest falls back to the verbatim monolith path.
- **`check-wiki` structural enforcement for composed pages** — rule **(m)** required sections appear in manifest-relative order; rule **(n)** every `##` heading is a required section or a declared optional heading-variant; rule **(o)** a surviving `<…>` placeholder in prose is a finding (hard; `--strict` promotes per DC-4, after stripping inline-code spans + fenced blocks). Rules (m)/(n) emit `soft` on live pages during the taxonomy-migration interim (DC-6); the committed proof-slice fixtures assert all three hard in the unit suite.

### Internal

- **Four-part design pipeline** (`/design author → translate → sequence`, then four `/work` plans): `section-schema → compose-core → author-wiring → enforcement`, shipped in dependency order; all four PLANs completed and archived. 39 section-enforcement tests (`unittest`) + 2 placeholder-free proof-slice fixtures (`scripts/fixtures/component-overview/Sample-Component.md`, `Sample-Guarded-Component.md`).
- Composer logic lands in the diataxis-author skill's `section_schema.py` · `composer.py` · `author.py` and in `wiki-maintenance`'s `check-wiki.py`, and regenerates byte-identically into both host plugins (`generate.py check` drift-gate green); plugins stay `0.1.0` per the repo-level versioning model.
- **Closing docs for the seven-section taxonomy also land in this tag** — [ADR 0020](https://github.com/alexherrero/crickets/wiki/0020-seven-section-wiki-taxonomy) (seven-section wiki taxonomy), the "declare a project's Architecture" how-to, the authoring-spec README §3 reframe, and the [Wiki Section Taxonomy design](https://github.com/alexherrero/crickets/wiki/wiki-section-taxonomy)'s own `final → launched`. These are documentation closers for the scaffolder capability already shipped in v3.2.1 — no new runtime surface — and the paired agentm-wiki migration remains a separate-repo concern (no paired agentm release here).

## [v3.2.1] — 2026-06-11 — The seven-section wiki frame + per-project Architecture manifest

**PATCH — a significant `wiki-maintenance` scaffolder refinement (an existing plugin, no new surface), with one migration note.** `wiki-maintenance`'s scaffolder graduates from the flat `do/` · `why/` · `get-started/` layout to a prescriptive **seven-section frame** — How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational — two of which are *conditional*: **Architecture** renders only when the repo declares a `wiki/architecture.yml`, and **Operational** only for private/internal audiences (public wikis suppress it). The frame is dogfooded the honest way — this repo's own `wiki/` was restructured in place onto it, and `wiki-init` against crickets is now a **proven no-op**: the generator and the hand-built sidebars agree, locked forward by a structural battery check. Architecture + rationale: the [Wiki Section Taxonomy design](https://github.com/alexherrero/crickets/wiki/wiki-section-taxonomy) (`final`). The sibling agentm wiki migration and the closing how-to/ADR are the pipeline's remaining parts — no paired agentm release yet.

### Added

- **The static seven-section frame** — `wiki_init` scaffolds `how-to · reference · architecture · designs · explanation · decisions · operational` (each with a section landing + per-folder `_Sidebar.md`), replacing the old `do`/`why`/`get-started` defaults. `SECTION_META` carries each section's title, landing basename, and folder mode.
- **Per-project Architecture manifest** (`wiki/architecture.yml`) — a `Component {slug, title, summary, overview}` model the scaffolder reads to build the Architecture section. Components are declared in order; recurring shapes toggle as `pillars:` (host-adapters · sibling-interface · distribution) and the rest free-form. Fail-closed: a malformed manifest writes nothing and exits non-zero; the `yaml` import stays lazy so the no-manifest path is dependency-free.
- **Nested Architecture render + conditional sections** — the root sidebar's Architecture bullet expands one sub-bullet per component, in manifest order; `active_sections()` + `renders_operational()` gate the two conditional sections (Architecture on manifest presence; Operational on `--visibility`, public/unknown suppressing it conservatively).
- **A no-op lock** — `TestCricketsDogfoodLock` asserts the full planned scaffold against crickets' real manifest is empty (generator matches the hand-built tree), that the rendered root-sidebar component refs structurally equal the generator's output, and that drift is caught loudly. This is the part of the design that proves the generator and the operator-authored sidebars never silently diverge.

### Changed

- **Migration (restructure + reinstall):** the default frame changed, so an existing wiki on the old `do/`/`why/`/`get-started/` layout will newly fail `check-wiki` until its folders are renamed to the frame (`do→how-to`, `why→explanation`, fold `get-started` into `how-to`). `wiki-init` itself is gap-fill — it never deletes — so the migration is a rename, not a rebuild. Reinstall `wiki-maintenance` from the updated marketplace to pick up the new scaffolder.
- **This repo's wiki, restructured in place** — `do/`→`how-to/`, `why/`→`explanation/`, standalone `plugins/`→`architecture/plugins/` (all `git mv`, history preserved); a new Architecture section with five component landings (Plugins · Customization model · Build & distribution · Host adapters · Harness interface) that link out to Reference rather than duplicating it; root + per-folder sidebars reordered to the frame; Home brought into frame order.
- **`check-wiki`** — `_FOLDER_MODE` reshaped to the new intent-folders (every page under `architecture/` is index-mode, including nested component-detail pages). A cross-design `docs-adr` basename collision (GitHub Wiki resolves links by flat basename) was resolved by namespacing the colliding part file.

### Internal

- **Four-part dogfood pipeline** (parts 1–4 of the wiki-section-taxonomy design): static frame → architecture manifest → nested render + visibility gate → crickets dogfood. Generator surfaces (1–3) are unit-tested; part 4's proof is the e2e crickets no-op plus the structural sidebar-equals-generator battery check.
- Generator/scaffolder changes land in `src/wiki-maintenance/scripts/{wiki_init.py,check-wiki.py}` and regenerate byte-identically into both host plugins (`generate.py check` drift-gate green); plugins stay `0.1.0` per the repo-level versioning model.

## [v3.2.0] — 2026-06-10 — The wiki-maintenance plugin + the wiki overhaul

**MINOR — one breaking rename (the `wiki` stub → `wiki-maintenance`), with migration.** Bucket ④'s second critical plugin: a wiki maintainer that authors and repairs pages against a prescriptive template library in the operator's voice — and **gets closer to that voice every time it's used**, via an operator-in-the-loop learning loop. The plugin shipped across five parts and was validated the honest way: its own dogfood finale rewrote this repo's entire wiki (two waves, ~40 pages), with every lesson the operator taught captured into the voice overlay and the first proven lesson **promoted into the committed base**. Architecture + rationale: the [Wiki-Maintenance design](https://github.com/alexherrero/crickets/wiki/wiki-maintenance-design) (`launched`) + the new [Wiki](https://github.com/alexherrero/crickets/wiki/wiki-design) and [Continuous Integration](https://github.com/alexherrero/crickets/wiki/continuous-integration) designs. No paired agentm release — the docs portion of the V5 ⑤ slim is unblocked but not performed.

### Added

- **The `wiki-maintenance` plugin, complete** (8 primitives): the `diataxis-author` authoring/learning engine + `wiki-author` dispatch skill; the `documenter` write-executor wired to the developer-workflows phase boundaries via a `documentation` capability probe; the **wiki-watcher (W1)** — `wiki-watch` skill + command, one idempotent cooldown-gated cycle, PR-default; the `diataxis-evaluator` + `style-scope-evaluator` read-only agents; `recent-wiki-changes`.
- **The style layer**: a committed base style guide ⊕ learned voice overlays (global / per-project / per-repo, on-demand), **edit-driven lesson capture** from operator diffs, and the operator-gated **`/diataxis promote`** that graduates a proven overlay lesson into the committed base (preview-first, `src/`-only, never auto-commits). The first real promotion shipped in this release: the llm-tell-vocabulary lesson (+5 machine-checkable banned terms).
- **The Plugins wiki section** — a per-plugin page for all six plugins (plugin-home shape: install · what it ships · how it composes · why it works).
- **New references**: [CI gates](https://github.com/alexherrero/crickets/wiki/CI-Gates) · [Troubleshooting](https://github.com/alexherrero/crickets/wiki/Troubleshooting) (symptom-first) · [Repo layout](https://github.com/alexherrero/crickets/wiki/Repo-Layout) · the [Add-A-Plugin](https://github.com/alexherrero/crickets/wiki/Add-A-Plugin) how-to.
- **Two codified designs**: [Continuous Integration](https://github.com/alexherrero/crickets/wiki/continuous-integration) + [Wiki](https://github.com/alexherrero/crickets/wiki/wiki-design) (both `draft`, operator-review lifecycle).

### Changed

- **BREAKING (migration: reinstall):** the `wiki` stub group is renamed **`wiki-maintenance`** and its composition flips to `standalone: true` + `enhances: developer-workflows` (capability-targeted). Operators with the old `wiki` plugin install `wiki-maintenance` from the updated marketplace.
- **The wiki's information architecture** ([ADR 0018](https://github.com/alexherrero/crickets/wiki/0018-per-folder-sidebars)): intent-grouped folders with per-folder sidebars (collapse/expand nav on GitHub's nearest-sidebar rendering), section landing pages, and a **case-insensitive basename guard** (two silently-shipped page collisions found + fixed; user-facing pages own clean names, design pages take `-design`).
- **Every user-facing page rewritten** for the v3 model and the house voice; the Agent-M memory-architecture design docs relocated to the agentm wiki; the README rebuilt capabilities-first (five sections); stale v2.x how-tos (Add-A-Skill, Purpose-And-Scope, …) rewritten or retired.
- The base style guide gains the promoted banned-terms class (`first-class`, `seamless`, `robust`, `leverage`, `comprehensive`).

### Internal

- **CI hardening (from the new CI design's review):** `test_ci_consistency.py` mechanically enforces the battery↔workflow both-places rule + the aggregate's filename coupling; all third-party actions **SHA-pinned**; the **toolchain gates extended to all three OSes** (`PYTHONUTF8` pinned on Windows) — and Windows' first `validate` run immediately caught a real bug: `Path.write_text()` newline translation made the generator non-byte-deterministic, fixed structurally with byte writes (`write_utf8`, all 11 emit sites).
- `check-no-pii.sh` gains a separate **line-level allowlist** (scoped to SHA-pinned `uses:` lines) so context patterns can't mask real findings.
- `check-wiki.py` grows per-folder mode defaults, the `index` landing mode, case-insensitive rule-g, and rule-l README governance; `wiki-sync.yml` ships per-folder sidebars with a case-insensitive dupe-check.
- Twelve design-doc authoring conventions codified into the `/design` template + skill (plain titles, 3–4-sentence objectives, platform-first infrastructure charts, omit-N/A sections, one history row per day, …).

## [v3.1.0] — 2026-06-04 — The developer-plugin suite + `enhances:` soft composition

**MINOR — one breaking removal (the transitional `developer` seed), with migration.** v3.0 stood up the generator and a single seed `developer` plugin; this wave (bucket ④, the first build step of the V5 "unbundling") extracts the operator's opinionated developer process into a **suite of composable native plugins**. Where v3.0 modelled only *hard* dependencies (`requires:` / `standalone:`), v3.1 adds **soft composition** — a new `enhances:` manifest field so a plugin can *augment* another when both are installed while staying fully usable alone. The monolithic `developer` seed splits into three standalone plugins that compose through `enhances:`, and a deterministic capability probe makes the composition engage at runtime. Architecture + rationale: the [Developer Plugin Suite design](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/developer-plugin-suite.md) (`launched`) + [ADR 0017](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0017-enhances-soft-composition.md). Dogfood-proven on Claude Code + Antigravity across `agentm` / `crickets` / `sherwood`.

### Added

- **`developer-workflows`** — the phase-gated loop as a standalone plugin: the six phase commands `/setup` `/plan` `/work` `/review` `/release` `/bugfix` (self-contained — the agentm-kernel plumbing is stripped to graceful-skip per the memory↔process seam) + the `explorer` and `evaluator` sub-agents + the `harness-context` SessionStart hook (Claude-only). Declares `capabilities: [setup, plan, work, review, release, bugfix]`.
- **`developer-safety`** — the universal control layer (usable in any session): the `kill-switch` / `steer` / `commit-on-stop` hooks + the `commit-no-coauthor` / `worktrees-never-auto` conventions; `enhances: [developer-workflows]`.
- **`code-review`** — standalone adversarial review of any diff/PR: the `adversarial-reviewer` + cross-model `adversarial-reviewer-cross` agents + the `evidence-tracker` hook + a new **`/code-review <diff|PR>`** command; `enhances: [{group: developer-workflows, capability: review}]`.
- **`enhances:` + `capabilities:`** soft-composition manifest fields (orthogonal to `requires:`/`standalone:`), lint-validated and carried into both hosts' marketplaces; `bootstrap.sh` suggests installing a declared enhancer.
- **Runtime composition** — a deterministic local capability probe (`capability_probe.py`) wires the thin `/review` to dispatch the adversarial reviewers when `code-review` is installed, else gates-only (the interim fallback for the agentm V5-8 capability-discovery API).
- **Generator capabilities** — discovery of `command` and `snippet` primitives, and group-level `scripts/` verbatim asset-bundling (e.g. `cross-review.sh`).

### Changed

- **Breaking (only for `developer` adopters): the `#40 developer` seed plugin is retired.** Its contents moved into the new plugins (the `evaluator` agent → `developer-workflows`; the control hooks → `developer-safety`). `github-ci` and `wiki` now `requires: [developer-workflows]`. The recommended set is now **six** plugins: `developer-workflows`, `developer-safety`, `code-review`, `github-ci`, `pii`, `wiki`.
- `capabilities`/`enhances` are emitted to the **marketplace entry only** on both hosts (Claude's `plugin.json` rejects unrecognized keys); only `requires`→`dependencies` lands in `plugin.json`.

### Migration

If you installed the v3.0 `developer` plugin, migrate to the suite:

```bash
claude plugin marketplace update crickets
claude plugin install developer-workflows@crickets --scope user
claude plugin install developer-safety@crickets --scope user
claude plugin install code-review@crickets --scope user
claude plugin uninstall developer@crickets
```

(`github-ci` / `pii` / `wiki` are unchanged; after installing `developer-workflows` their dependency resolves.) Antigravity: `agy plugin install <plugin>@crickets` for the three new plugins.

### Internal

- Host limitations carried + documented (not worked around): Antigravity plugin hooks are observe/side-effect-only (`kill-switch`/`steer`/`evidence-tracker` are Claude-only-effective; `commit-on-stop` works on both); Claude drops `snippet` instruction files (conventions reach Antigravity `rules/` + the operator-global config).
- agentm's baked-in workflow/agent/hook copies are **untouched** (parallel-run) — removing the duplicates is the V5 ⑤ slim, gated on this wave's dogfood proof.
- Two dogfood/CI-caught fixes: the `plugin.json` unrecognized-keys rejection (above); a `__pycache__` leak into bundled `scripts/` assets (the asset copy now excludes it).

### Cross-references

- [Developer Plugin Suite design](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/developer-plugin-suite.md) (`launched`) + its six part files.
- [ADR 0017](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0017-enhances-soft-composition.md) — `enhances:` soft composition + the three-way split + the local-probe→agentm-V5-8 hand-off.
- agentm `ROADMAP-AgentMemoryV5.md` — **V5-8** (the host capability-discovery API that retires the local probe) + the **⑤ V5 slim** (the dev-loop portion is unblocked by this wave; bucket ④'s Wiki/docs + project-management plugins still precede the full V5 split).

## [v3.0.0] — 2026-06-02 — Native host plugins from a single source of truth

**MAJOR — breaking.** Crickets stops shipping a bespoke installer. For two years the toolkit dispatched customizations into host paths with a custom `install.sh` that parsed per-primitive YAML and copied files, and it kept its `lib/install/` layer byte-identical with `agentm` via `sync-lib.sh` + a `check-lib-parity` gate. Both target hosts have since shipped native plugin systems that already do dispatch, dependency resolution, and distribution. v3.0 (#40) retires the dispatcher entirely: every customization is authored once under `src/<group>/`, and a deterministic generator emits **committed native plugins** — a Claude Code plugin *and* an Antigravity plugin per functional group — plus each host's marketplace. Installation moves onto the hosts' own machinery in three modes (one-liner / marketplace / manual). This also **decouples `agentm` and `crickets`**: the shared `lib/install/` byte-sync is gone, closing the re-audit [ADR 0006](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0006-gemini-cli-host-removal.md) anticipated — the two repos now release independently. Proven by dogfooding the generated plugins on Claude Code + Antigravity across `agentm` / `crickets` / `sherwood`. Architecture + rationale: the [native-plugins HLD](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/crickets-v3-native-plugins.md) (`launched`) + ADRs [0013](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0013-bundles-native-plugins.md) / [0014](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0014-install-decoupling.md) / [0015](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0015-partial-revision-36.md).

### Added

- **Source-of-truth tree (`src/<group>/`)** — folder-per-group layout; each group carries a `group.yaml` (`name` / `description` / `category` / `requires` / `standalone`) and its primitive folders (`skills/`, `agents/`, `hooks/`, …). Four groups, seven primitives: **developer** (evaluator agent + kill-switch / steer / commit-on-stop hooks), **github-ci** (dependabot-fixer), **pii** (pii-scrubber), **wiki** (diataxis-evaluator).
- **The generator (`scripts/generate.py`)** — deterministic, stdlib-only `src/ → dist/`. Per-host emitters (`emit_claude.py`, `emit_antigravity.py`) write committed native plugins under `dist/<host>/plugins/<group>/` + each host's marketplace. `generate.py check` is a CI drift gate that fails if committed `dist/` diverges from a fresh build (replaces `check-lib-parity.sh`). `lint_src.py` validates the `src/` tree.
- **Three install modes** — (1) one-line `bootstrap.sh` (`curl … | bash`, detects hosts, installs the generator-emitted default set); (2) marketplace, including the one-word `claude plugin marketplace add alexherrero/crickets` from GitHub, backed by a **repo-root marketplace pointer** that the `check` gate covers so it can't drift; (3) manual `claude --plugin-dir` / `agy plugin install <path>`.
- **Docs** — ADRs 0013 (bundles = native plugins) / 0014 (#40 install-decoupling) / 0015 (#36 partial-revision); how-tos [Install crickets plugins](https://github.com/alexherrero/crickets/wiki/Install-Into-Project) + [Develop a crickets plugin locally](https://github.com/alexherrero/crickets/wiki/Develop-A-Plugin-Locally).

### Changed

- **Hooks resolve the workspace from the host's hook-input contract, not cwd.** Claude Code runs hooks from the project root; Antigravity runs them from the plugin dir and passes the workspace on stdin as `workspacePaths[]`. The developer hooks (`kill-switch` / `steer` / `commit-on-stop`) now read that contract (stdin JSON via `python3`, falling back to `$CLAUDE_PROJECT_DIR` / cwd) so they operate on the real workspace on both hosts. Regression-tested; fixed mid-release (`5c307a6`).
- **Antigravity composition is thin-separate** (confirmed at dogfood — `agy` 1.0.2 exposes no native cross-plugin `dependencies`): Claude plugins carry native `dependencies`; AG plugins carry only their own primitives with `requires` documented in the marketplace.

### Removed

- **`install.sh` / `install.ps1`** (the per-host dispatch installer) and its smoke/integrity tests.
- **`lib/install/`** and the `agentm`↔`crickets` byte-sync — `check-lib-parity.sh` + the CI `lib-parity` job + the `install-smoke` CI job. Parity is now `generate.py check`.
- **`validate-manifests.py`** (vestigial after the dir migration; `lint_src.py` validates `src/`).
- **The old top-level `skills/` / `agents/` / `hooks/` / `commands/` dirs** — migrated into `src/<group>/`.

### Known limitations

- **Antigravity plugin hooks are observe/side-effect-only** in this host build (`agy` 1.0.2 ignores a hook's exit code *and* never reads its stdout). So `kill-switch` / `steer` fire but cannot veto/inject on Antigravity — they are Claude-Code-only-effective there; `commit-on-stop` (a side-effect hook) works on both. Shipped + documented ([ADR 0013](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0013-bundles-native-plugins.md), [Compatibility](https://github.com/alexherrero/crickets/wiki/Compatibility)). Re-audit if Antigravity ships hook-veto support.

### Migration

- **From a v2.x `install.sh` install →** install the native plugins (`bash ~/Antigravity/crickets/bootstrap.sh`, or `claude plugin marketplace add alexherrero/crickets` + `claude plugin install <group>@crickets`; `agy plugin install <path>` on Antigravity), then remove any old `~/.claude/{skills,agents,hooks}` symlinks that pointed into the crickets clone. The pre-push PII hook is no longer installed by an installer — copy it in (`cp templates/hooks/pre-push .git/hooks/ && chmod +x .git/hooks/pre-push`).

### Deferred (bucket ④, per ADR 0015)

- The #36 skill relocations (`design` / `diataxis-author` / `ship-release`), the full Developer-base composition, and the new bundles (Testing / Releasing / knowledge). #40 proves the architecture on the existing primitives; the catalog build is the next bucket.

### Cross-references

- **`agentm` decoupled independently** (no paired release required — that's the point of this one): the auto-clone+bootstrap block removed from agentm's installer + `sync-lib.sh` patched local-only ([`9dc4189`](https://github.com/alexherrero/agentm/commit/9dc4189)); docs pointed at native install ([`21ab3ea`](https://github.com/alexherrero/agentm/commit/21ab3ea)). agentm keeps its own `lib/install/` and releases on its own cadence.
- A cwd-portability hook bug found during the both-hosts dogfood was fixed via the full bugfix pipeline (`5c307a6`, two adversarial review passes).

## [v2.2.0] — 2026-05-30 — commit-on-stop: non-disruptive snapshot model

**MINOR.** Behavior change (not a bug fix) to the `commit-on-stop` Stop hook: it no longer mutates the working tree or switches branches to record a safety commit. The v0.7.0 design stashed the dirty tree, created an `auto-save/<ts>` **branch**, checked out to it, committed, then checked back — which parked in-flight edits off the current branch on every Stop (multi-turn agents saw it as "my edits got reverted") and switched the branch for the *whole* working tree, making it unsafe the instant two agents — or an orchestrator and its sub-agents — share one tree. It could also abort mid-checkout when two Stop events collided in the same second. The rewrite records a **snapshot** instead: it builds a tree from the full dirty state (tracked + untracked, `.gitignore` honored) in a temporary index, `commit-tree`s it parented on HEAD, and publishes to the hidden side ref `refs/auto-save/<iso-ts>` via `update-ref` — never touching HEAD, the current branch, the index, or the working tree. Snapshots are concurrency-safe (independent Stop events write independent refs, even in a shared tree), stay out of `git branch`, auto-prune to the most recent 10, and recover via `git checkout refs/auto-save/<ts> -- .`. The fix is already live on source-mode installs (the hook is symlinked from this clone), so this release is distribution + release hygiene rather than an urgent functional change.

### Changed

- **`commit-on-stop` hook rewritten to a non-disruptive snapshot model** (manifest `0.1.0 → 0.2.0`; `commit-on-stop.sh`, `commit-on-stop.ps1`, `hook.md`). Drops the stash → branch → checkout → commit → checkout-back flow for a temporary-index + `commit-tree` + `update-ref` flow that writes a snapshot to `refs/auto-save/<ts>` and leaves HEAD, the current branch, the real index, and the working tree byte-identical. Fixes three problems with the old design at once: **working-tree mutation** (in-flight edits now survive across turns — no park-and-clean surprise), **branch switching** (a ref write can't yank the tree out from under a concurrent agent), and **same-second collision** (independent refs instead of a branch-name race that aborted the hook). Also removes a possible gpg-signing hang — `commit-tree` ignores `commit.gpgsign`, unlike `commit`. Verified in a temp repo: tree byte-identical after the hook, snapshot captures tracked+untracked while honoring `.gitignore`, clean-tree no-op, prune-to-10.

- **ADR 0003 amended** ([`0003-base-operator-hooks.md`](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0003-base-operator-hooks.md)) — decision §3 (commit-on-stop safety-branch strategy) is now superseded by a dated **branch → snapshot redesign** amendment carrying the three-problem rationale, the multi-agent-safety motivation, "why not the alternative" for each call (side refs vs branches, temp-index vs stash, `commit-tree` vs `commit`), and re-audit triggers. The original v0.7.0 decision is preserved as rationale-of-record. This also resolves the original ADR's open "safety-branch sprawl / auto-cleanup is a future improvement" question (now auto-pruned to 10).

### Migration

- **Old installs keep their `auto-save/*` branches.** Sessions that ran the v0.1.0 hook left real branches under `refs/heads/auto-save/`; they are not migrated automatically. Delete them with `git branch | grep auto-save/ | xargs git branch -D`. New snapshots live under the hidden `refs/auto-save/` namespace and never appear in `git branch`. The hook.md carries the same migration note.

### Cross-references

- Local source commit [`eb86e90`](https://github.com/alexherrero/crickets/commit/eb86e90) (`feat(commit-on-stop): non-disruptive snapshot model for multi-agent safety`).
- The paired `agentm`-local cleanup deletes the 4 stale `auto-save/*` **branches** that the old hook design left in that repo — purely local housekeeping, no `agentm` release.

## [v2.1.2] — 2026-05-29 — gitignore `.harness/` ephemeral state

**PATCH.** Single-line `.gitignore` fix surfaced during a `/doctor` dogfood audit. The `memory-recall-session-start` hook writes a `.harness/session-id-<uuid>.start` marker on every session boot, and that marker carries a personal transcript path (`/Users/<name>/.claude/projects/…`). agentm already gitignores `.harness/`; crickets didn't — so in this **public** repo the marker showed up as untracked and was sweepable into `git add -A`. Mirrors agentm's `.gitignore`; the pre-push PII hook stays the enforcing backstop. No code changes.

### Fixed

- **`.gitignore` now excludes `.harness/`** — closes the one path by which a SessionStart hook could leak a personal home path into the public repo. Matches the agentm `.gitignore` entry.

### Cross-references

- [agentm v4.7.0](https://github.com/alexherrero/agentm/releases/tag/v4.7.0) — companion release from the same `/doctor` audit; among other installer hardening it stops symlinking the loose `harness/skills/*.md` specs that surfaced the cruft alongside this marker.
- **lib-parity follow-up** — agentm v4.7.0's `install_symlinks.py` loose-`.md` fix is not yet mirrored into crickets's byte-identical `lib/install/`; a `sync-lib.sh` pass is the separate follow-up (no functional impact on crickets-as-toolkit, which installs *from* agentm).

## [v2.1.1] — 2026-05-29 — Catch-up + wiki hygiene + CI gate

**PATCH.** Cross-repo lib-parity catch-up (5 `sync-lib.sh` passes since v2.1.0 carrying agentm's installer evolution into crickets, including the Windows-symlink normalization fix surfaced during dev-machine-setup dogfood), CI hygiene (`check-wiki --strict` gate now runs in crickets's `validate` job, mirroring agentm; gitleaks shallow-checkout fragility on multi-commit pushes fixed), wiki cleanup (5 stub how-tos for skills that moved to Agent M in v2.0.0 deleted with inbound refs cleaned), and multi-subsection HLD updates tracking agentm's V4.5 → V4.7 arc. No public-API changes — entirely catch-up work bringing crickets to parity with the agentm-side primitive evolution that's been landing since v2.1.0.

### Added

- **`check-wiki --strict` CI gate** — new `Lint wiki (Diátaxis)` step in `.github/workflows/tests-linux.yml`'s `validate` job, mirroring agentm's pattern. Linux-only (the lint is deterministic; no per-OS variance). Closes the pre-existing crickets-side gap that let 23 structural errors accumulate in the wiki unnoticed before this gate landed.

- **`install_migrate` primitive** (via `sync-lib.sh` from agentm V4 #30 plan 3 tasks 2+3) — `lib/install/python/install_migrate.py` now ships byte-identical between agentm + crickets; covers the install-mode migration recipe operators run when promoting a release-mode install to source-mode (or vice-versa).

- **Orphan-symlink reaping** in `install_symlinks.symlink_customizations()` (via sync from agentm `8c5af42`) — when a skill / agent / command / hook is deleted upstream from a source clone, the prior install's dangling symlink under `<install-prefix>/` is now reaped on the next run. The result dict gains a `reaped: []` key alongside the existing `created` / `repointed` / `skipped` / `conflicts`. Operator-placed real files and external symlinks left untouched (DC-8 preserved).

### Changed

- **5 wiki stub how-tos removed** (`wiki/how-to/Add-A-Plugin.md`, `Use-Diataxis-Author.md`, `Use-The-Design-Skill.md`, `Use-The-Evidence-Tracker-Hook.md`, `Use-The-Memory-Skill.md`). Each was a "moved-to-Agent-M" pointer note for a skill / hook / authoring flow that relocated to Agent M in v2.0.0 (V4 #36 reorg). The pages were genuinely explanation-mode content — move rationale + cross-refs, not step-by-step recipes — so adding placeholder Steps would have either duplicated Agent M's docs (drift risk) or been degenerate. Deletion + inbound-reference cleanup (~23 refs across 11 files) was the right shape; ADR/HLD narrative references replaced with Agent M wiki URLs so cross-references still resolve to canonical operational docs.

- **`Home.md` + `_Sidebar.md` nav** — added `device-wide-architecture` to the Explanation sections. `Home.md`'s How-to section gained a generic "moved to Agent M" pointer block covering plugin authoring + the 3 skills + the hook, replacing per-page redirect entries.

- **HLD subsections published**: V4.5 (`agentm v4.4.0` wiki I/O foundation), V4.6 (`agentm v4.5.0` migration tooling), V4.7 (`agentm v4.6.0` documenter vault-context resolution). Each subsection tracks a paired-pair release arc that materially extended the device-wide-architecture model.

- **`install_state.py` schema v2** + filename rename (via sync from agentm) + persisted `--fragments-file` CLI flag for hook-fragment-tracking install state.

- **Windows-path normalization** in `_reap_orphan_symlinks` (via sync from agentm) — the orphan-reap path-comparison logic now handles `\\?\` extended-path prefix asymmetry, Windows case-insensitivity, and separator mixing via a new `_normalize_path_str` helper. Closes a silent failure where dead symlinks were never reaped on Windows even though the symlink-creation side worked correctly.

### Internal

- **`gitleaks` shallow-checkout fragility fixed** in `tests-linux.yml`'s `pii-guardrails` job — `actions/checkout@v4`'s default `fetch-depth: 1` couldn't resolve the parent commit needed for gitleaks's `git log <parent>^..<HEAD>` range scan; multi-commit pushes failed deterministically. Job now uses `fetch-depth: 0`. Other jobs keep their fast shallow clones.

- **Cross-repo lib parity** — `lib/install/python/install_symlinks.py` + `install_state.py` + `install_migrate.py` synced byte-identically with agentm (5 `sync-lib.sh` passes this release cycle); `lib/install/.checksums.txt` regenerated on each pass.

### Cross-references

- Paired with agentm v4.4 → v4.6.x (multiple agentm releases since crickets v2.1.0; sync-lib.sh passes track each).
- Wiki cleanup driven by plan `<vault>/projects/crickets/_harness/PLAN.md` ("crickets wiki cleanup — close the check-wiki gap"), planned 2026-05-28, executed + closed 2026-05-29.
- [HLD V4.5/V4.6/V4.7 subsections](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/agent-memory-evolution.md#v4-release-milestones).

## [v2.1.0] — 2026-05-27 — Global install + `--scope user` (paired with agentm v4.3.0)

**MINOR.** ROADMAP-V4 item #30 (plan 1 of 3). Paired pair #12 with [agentm v4.3.0](https://github.com/alexherrero/agentm/releases/tag/v4.3.0). Toolkit-first ordering per `[[paired-pair-toolkit-first-ordering]]`. The first install-model overhaul: `--scope user` flag added to `install.sh` (pwsh dispatch deferred). When `--scope user` is passed, customizations install into `~/.claude/` once, drawn by every operator-repo on the device — no more per-project `<project>/.claude/{skills,hooks,agents,commands}/` footprint. Default scope stays `--scope project` for v2.1.0 backward compat; flips to `--scope user` in a future release once real-use validates. The locked operator insight from 2026-05-24: "the only thing repos need is to be aware of them and how to interact/write/read plans from them" — anything else lives globally. See [HLD § V4.4 release milestones](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/agent-memory-evolution.md#v4-release-milestones) + [device-wide-architecture v0.4](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/device-wide-architecture.md#lifecycle) for the architectural arc.

### Added

- **`lib/install/python/` subdir** — 3 new cross-repo Python helpers byte-identical between agentm + crickets (sync via `scripts/sync-lib.sh`; parity enforced via `lib/install/.checksums.txt`):
  - `install_state.py` — probe canonical source-clone paths; persist `{mode, source_clones, installed_at, harness_version, installer_source}` to `<install-prefix>/.agentm-install-state.json`. CLI: `detect`/`persist`/`read`.
  - `install_symlinks.py` — source-mode primitive. Symlinks the customizations subset per locked DC-7 (skill dirs + agent .md + command .md + hook bundles). Cross-platform: `os.symlink` with Windows junction fallback (`cmd /c mklink /J`). Idempotent + `--force` for conflict replacement.
  - `install_copy.py` — release-mode primitive. SHA256-aware copy with conservative divergence detection — never silently overwrites operator-edited content.

- **`install.sh` `--scope user` dispatch** — install prefix = `$AGENTM_INSTALL_PREFIX` or `$HOME/.claude`; probes mode; source mode → symlinks; release mode → copies from crickets's own source tree; persists install-state with `installer_source` recorded. Pwsh `-Scope` parameter dispatch deferred to follow-up.

- **`lib/install/CONTRACT.md`** updated with `python/` subdir entries.

### Changed

- **`install.sh` + `install.ps1`** invoke `lib/install/python/install_state.py persist` at end-of-install. Silent best-effort.

- **`scripts/check-no-pii.sh`** SELF_SKIP_PATHS includes `lib/install/.checksums.txt` (generated SHA256 file; hex substrings false-positive on phone-us regex).

- **Wiki sweep — dev-setup mentions** — 5 wiki design + ADR files rephrased to remove explicit `dev-setup` references from new-user-facing surfaces. ADR 0012 (the policy doc itself) preserved per FOLLOWUPS exemption.

### Internal

- **Cross-repo lib parity** — `sync-lib.sh` now propagates `lib/install/python/` byte-identically; `check-lib-parity.sh` verifies 6 files (was 3): bash + pwsh primitives + 3 new Python helpers + CONTRACT.md.

- **Mid-build dogfood findings from paired agentm plan #22 task 11**: install_symlinks bundle-walk gap (agentm harness/skills + harness/hooks missing); Windows path-handling fixes (POSIX-normalize + samefile compare); bash-only tests Windows-skipped.

### Backward-compat

- **Default scope = `project`** for v2.1.0. Existing per-project install unchanged; the default flip is queued for a future release once real-use confirms the new path.

### Cross-references

- Paired with [agentm v4.3.0](https://github.com/alexherrero/agentm/releases/tag/v4.3.0) (toolkit-first ordering).
- [HLD V4.4 subsection](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/agent-memory-evolution.md#v4-release-milestones).
- [device-wide-architecture v0.4](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/device-wide-architecture.md#lifecycle).
- ADR 0012 § 6 (dev-setup invisibility policy — preserved).
- FOLLOWUPS 2026-05-27 (auto-stay-in-sync default-on; no `--dev` flag).

### Deferred

- Full `--scope user` default flip — future release.
- `install.ps1` `-Scope user` dispatch in crickets — minimal scaffold only.
- Settings.json hook-registration migration to user-scope — per-repo `.harness/hooks/` references intact so safe to defer.
- Pwsh launcher + hook test coverage.
- Bundle-walk unit test fixture (mapping gap surfaced only at real-vault smoke).

## [v2.0.0] — 2026-05-27 — V4 #36 reorg: catalog narrowed to base primitives

**MAJOR — BREAKING.** V4 #36 reorganization. Compound skills (`memory`, `design`, `diataxis-author`, `ship-release`), memory hooks (`memory-recall-session-start`, `memory-recall-prompt-submit`, `memory-reflect-stop`, `memory-reflect-idle`), the `evidence-tracker` hook, the `memory-idea-researcher` sub-agent, the `plugins/` tree (including `example-plugin` and the `install-plugin.sh` user-global plugin installer), and the `bundles/` namespace (including `quality-gates` + `example-bundle`) **all moved to [Agent M](https://github.com/alexherrero/agentm) v4.0.0**. Crickets v2.0.0 is base primitives only — the toolkit-cricket split now mirrors the design call locked in ADR 0012 (device-wide-by-default): Crickets owns universal primitives any project can use; Agent M owns the agentic memory + compound flows + plugins that make the harness a full agentic learning environment. Paired with **agentm v4.0.0** — see the [Agent M v4.0.0 release notes](https://github.com/alexherrero/agentm/releases/tag/v4.0.0) for the full V4 device-wide context.

### Added

- **`wiki/how-to/Quality-Gates-Recipe.md`** — operator-facing recipe documenting which primitives form the quality-gates set (`evaluator` + `kill-switch` + `steer` + `commit-on-stop` + `evidence-tracker`, the last sourced from Agent M post-reorg). `bash install.sh <target>` default install gives all of Crickets's contribution to that set.

### Changed [BREAKING]

- **Catalog narrowed to base primitives.** Public surface shrinks from 6 skills / 1 sub-agent / 4 hooks / 2 bundles (v1.x) to **2 skills + 3 sub-agents + 3 hooks** (v2.0.0):
  - **Skills (2):** `pii-scrubber`, `dependabot-fixer`.
  - **Sub-agents (3):** `evaluator`, `adapt-evaluator`, `diataxis-evaluator`.
  - **Hooks (3):** `kill-switch`, `steer`, `commit-on-stop`.
- **`kind: bundle` + `kind: plugin` reserved-future.** Both kinds remain in the manifest enum (manifest schema unchanged from v1.2.0; still 13 kinds total) but no bundles or plugins ship in v2.0.0. The `quality-gates` bundle pattern moved to a docs-only how-to recipe per design call Q of plan #19. The `--bundle <name>` installer flag still parses but no-ops when no bundles are present.
- **`install.sh` + `install.ps1` python-deps section slimmed.** `requirements.txt` is now `pyyaml` only. `sqlite-vec` + `sentence-transformers` (with their transitive `torch`/`transformers`/`tokenizers` chain — the ~1.3GB BGE-large download nag in the v1.x install log) moved to Agent M's `requirements.txt` since they were memory-skill deps.
- **`install.sh` + `install.ps1` `index_personal_skills` removed.** The personal-skills auto-indexer's script (`skills/memory/scripts/index_skills.py`) moved with the memory skill to Agent M. Agent M's installer owns this step post-reorg. The `--no-skill-index` / `-NoSkillIndex` flag is preserved as a backward-compat no-op so existing CI invocations don't break.
- **Smoke install tests rewritten.** `scripts/smoke-install-bash.sh` + `scripts/smoke-install-pwsh.ps1` were ~95% memory-skill functional tests (`/memory save`, `/memory evolve`, recall engine, embedding queue, reflection mining, ideas surfacing, permeable boundary, Diátaxis classify/author/check/repair/migrate, etc.) — all of which moved to Agent M with the skill. New shape covers only what Crickets still ships; expected-files arrays, idempotent re-run, `--update` wipe + recreate, `--no-pre-push-hook`, `--no-legacy-cleanup`, kill-switch sentinel end-to-end, validate-manifests gemini-cli rejection, and post-install integrity all preserved.

### Internal

- **`bundles/` namespace removed.** `bundles/quality-gates/` + `bundles/example-bundle/` both deleted. The `install_bundles` function in both installer scripts is retained (no-ops over an empty `bundles/*` glob); kept for forward-compat if the catalog ever grows enough to warrant bundles again.
- **`plugins/` namespace + `scripts/install-plugin.sh` moved to Agent M** (now at `agentm/harness/plugins/` + `agentm/scripts/install-plugin.sh`). The Crickets-side plugin documentation cross-links to Agent M's location.
- **ADR 0010 (quality-gates-bundle) deleted.** Per design call Q of plan #19, no supersession marker — the decision was project-internal and the recipe replaces it. ADR audit confirmed no other ADRs reference 0010 inbound.
- **HLD V4.2 subsections added** to both `wiki/explanation/designs/agent-memory-evolution.md` (Architecture section) and `wiki/explanation/designs/device-wide-architecture.md` (Lifecycle section). The V4.x evolution chain so far: V4.1 was crickets v1.2.0 (Antigravity 2.0 host support); V4.2 is this reorg; V4.3+ will be Agent M's continuing state migration + auto-detect work.

### Migration

**For v1.x users with compound skills installed (`memory`, `design`, `diataxis-author`, `ship-release`) or memory hooks running:**

The compound surface moved to Agent M. The simplest upgrade path:

1. Install Agent M (if you don't already have it):
   ```bash
   git clone https://github.com/alexherrero/agentm.git ~/Antigravity/agentm
   bash ~/Antigravity/agentm/install.sh <target-project>
   ```
2. Re-install Crickets at v2.0.0:
   ```bash
   cd ~/Antigravity/crickets && git pull && git checkout v2.0.0
   bash install.sh --update <target-project>
   ```

Agent M's installer dispatches the compound skills + memory hooks to your target's `.claude/skills/`, `.claude/hooks/`, and `.agents/skills/` paths — the same destinations Crickets v1.x used. Your vault content (`<vault>/personal-private/`, `<vault>/_meta/embedding-queue.jsonl`, the vec-index database) is untouched; the skill scripts that read/write it just live at a different on-disk source path now. Re-running the SessionStart hook on first invocation under v4.0.0 re-anchors the recall loop without any vault-side migration.

**For v1.x users with `--bundle quality-gates`:** the bundle is gone but the recipe lives on. See [Quality-Gates-Recipe.md](https://github.com/alexherrero/crickets/blob/main/wiki/how-to/Quality-Gates-Recipe.md). Default `bash install.sh <target>` installs Crickets's contribution to the set (evaluator + kill-switch + steer + commit-on-stop); pair with `bash agentm/install.sh <target>` to add the evidence-tracker hook that completes the set.

### Cross-references

- **Paired sibling release:** [Agent M v4.0.0](https://github.com/alexherrero/agentm/releases/tag/v4.0.0) — the "device-wide era" opens.
- **HLD updates:** `agent-memory-evolution.md` (Architecture § V4.2), `device-wide-architecture.md` (Lifecycle § V4.2).
- **ADRs referenced:** ADR 0012 (device-wide-by-default — locked the decision; this release implements it on the Crickets side).
- **Plan:** `agentm` `.harness/PLAN.md` plan #19 — coordinated paired release pair #11.

---

## [v1.2.0] — 2026-05-25 — Antigravity 2.0 + Antigravity CLI (agy) host support + `kind: plugin`

Minor — **Antigravity 2.0 + Antigravity CLI host support**. Google launched Antigravity 2.0 (desktop) + Antigravity CLI (`agy`, Go-built) on 2026-05-19 at I/O. Antigravity CLI replaces Gemini CLI (which we removed in v0.9.0); consumer Gemini CLI sunsets 2026-06-18. Paired with `agentm` v3.2.0 (harness-side doctor probes for new primitives) — see [agentm v3.2.0 release notes](https://github.com/alexherrero/agentm/releases/tag/v3.2.0).

The new CLI and 2.0 desktop **share the same agent harness** — single `antigravity` slug in crickets manifests, but the dispatch path and primitive surface have evolved.

### Added

- **New `kind: plugin` customization type** — Antigravity-2.0-style bundle (JSON `plugin.json` manifest at root + 1-N nested `SKILL.md` skills). Adds the 13th customization kind to the toolkit catalog.
- **Reference plugin** at `plugins/example-plugin/` showing the manifest format + nested skill layout.
- **New `scripts/install-plugin.sh`** — installs crickets plugins to Antigravity's user-global plugins directory (`~/.gemini/config/plugins/<name>/`). Generates `plugin.json` from the toolkit-side YAML frontmatter at install time. Modes: install (default), `--uninstall <name>`, `--list`.
- **New wiki how-to**: `Add-A-Plugin.md` — full plugin authoring walkthrough.
- **New ADR 0011** — Antigravity 2.0 + Antigravity CLI host support (the umbrella decision record).
- **Compatibility.md "Known gaps" section** — documents the 3 Antigravity 2.0 surfaces (hooks / scheduled-tasks / multi-agent orchestration) that have no file-based authoring path; FOLLOWUP candidates captured for future Python sidecar integration.

### Changed

- **Antigravity dispatch path moved from `.agent/` (singular) to `.agents/` (plural)** — agy v1.0.2 binary scans `{workspace}/.agents/skills/<skill_name>/SKILL.md`. **Breaking change for v1.0.x users** with Antigravity 1.x installs: re-run `bash install.sh --update <target-project>` to migrate. The installer's `legacy_cleanup` detects pre-existing `.agent/skills/` from Antigravity 1.x installs and offers backup-then-remove with operator confirmation; new install populates `.agents/skills/`. Same path applies to `kind: agent` dispatch (sub-agent-as-skill).
- **Sub-agent-as-skill pattern preserved** — Antigravity 2.0 still has no `.subagents/` first-class slot; subagents remain SDK runtime constructs spawned via the built-in `start_subagent` tool. `kind: agent` continues to dispatch to `.agents/skills/<name>/SKILL.md` on Antigravity (path updated; pattern unchanged). See ADR 0002 v1.2.0 amendment.
- **Updated `Per-Host-Paths.md`** with the new `.agents/` convention + new `kind: plugin` row.
- **Updated `Manifest-Schema.md`** with `kind: plugin` in the enum (now 13 entries) + plugin frontmatter schema section.
- **Updated `Compatibility.md`** with Antigravity 2.0 + Antigravity CLI as first-class hosts; out-of-scope hosts section notes Gemini CLI consumer sunset 2026-06-18; per-customization compatibility table refreshed (6 skills + 4 agents + 8 hooks + 2 bundles + 1 plugin).
- **Updated wiki tutorials, how-tos, and references** (`Use-The-Evaluator.md`, `Add-A-Skill.md`, `Use-The-Base-Hooks.md`, `Use-The-Memory-Skill.md`, `Customization-Types.md`, `Installer-CLI.md`, `01-First-Customization.md`) to reflect the new `.agents/` path convention.
- **ADR 0002 (evaluator-design)** amended with v1.2.0 confirmation: sub-agent-as-skill pattern still correct; only the install destination path moved.
- **ADR 0009 (evidence-tracker-hook)** re-audit trigger met; outcome captured: hooks stay `[claude-code]`-only because Antigravity hooks are Python SDK decorators with no file-based surface. Python sidecar adapter tracked as FOLLOWUP candidate.

### Internal

- `validate-manifests.py` accepts `kind: plugin` (added to `KIND_ENUM`).
- `install.sh` + `install.ps1` updated: skill / agent dispatch for Antigravity host moved from `.agent/skills/` to `.agents/skills/`; `legacy_cleanup_gemini_cli` detection switched from `.agents/skills/` (the v0.8.x Gemini-CLI path that coincidentally matches the new agy path) to `.agent/skills/` (the Antigravity 1.x path). `MANAGED_PARENTS` updated.
- `install-plugin.sh` reads YAML frontmatter from `plugins/<name>/plugin.md` (via pyyaml), generates `plugin.json`, copies nested `skills/` + optional `references/` / `examples/` / `policies/` dirs. Writes `installed_version.json` for parity with agy-installed plugins.
- Smoke install verified: fresh install to `/tmp/crickets-smoke` populates `.agents/skills/` (plural) for 11 skills + 4 sub-agents-as-skill; `.agent/` (singular) NOT created (correctly absent post-migration).

### Cross-references

- Paired sibling release: [agentm v3.2.0](https://github.com/alexherrero/agentm/releases/tag/v3.2.0) — harness-side doctor probes for new primitives.
- Plan #16 (operator-local; `agentm/.harness/PLAN.md`) — the implementation plan.
- [Gemini CLI → Antigravity CLI transition](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) — upstream announcement. Consumer Gemini CLI sunsets 2026-06-18.

### Migration for v1.0.x users with Antigravity 1.x installs

If you have crickets v1.0.x installed against an Antigravity project with `.agent/` (singular) layout:

```bash
cd <your-target-project>
bash /path/to/crickets/install.sh . --update
```

The installer prompts to back up the old `.agent/skills/` directory (move to `.agent/skills.crickets-bak.<timestamp>/`) and populates the new `.agents/skills/` path. Pass `--no-legacy-cleanup` to skip the prompt; the new path gets populated either way.

## [v1.1.0] — 2026-05-25 — Repo rename agent-toolkit → crickets + cross-ref sweep

Minor — **repo rename release**. The GitHub repo for this project is now `alexherrero/crickets` (was `alexherrero/agent-toolkit`). Brand name (Crickets) was always the operator-facing label; the rename brings the URL slug + clone path in line with the brand. Paired with `alexherrero/agentm` v3.1.0 (the harness, was agentic-harness) — see [agentm v3.1.0 release notes](https://github.com/alexherrero/agentm/releases/tag/v3.1.0).

GitHub installs HTTP redirects from the old URLs to the new ones automatically — existing clones, links, and bookmarks keep working without action. New clones should use `https://github.com/alexherrero/crickets.git`.

### Changed

- **Repo URL** github.com/alexherrero/agent-toolkit → github.com/alexherrero/crickets. Old URL 301-redirects to new permanently.
- **Recommended local sibling-clone path** ~/Antigravity/agent-toolkit/ → ~/Antigravity/crickets/. Operators with the old path can `mv` locally + `git remote set-url origin` to migrate.
- **All cross-references** to the old name swept across the repo: README.md, wiki/ pages, AGENTS.md, CLAUDE.md, CONTRIBUTING.md, scripts/, lib/, templates/, .github/workflows/, CHANGELOG.md historical entries, extensionless files (templates/hooks/pre-push, wiki/.diataxis, .gitleaks.toml, requirements.txt). ~640+ occurrences across ~145 files; zero remaining post-sweep verification.
- **One ADR file renamed**: 0001-agent-toolkit-purpose.md → 0001-crickets-purpose.md (via `git mv`).
- **CI badge URLs** still resolve correctly (point at new URL + GitHub's auto-redirect handles the old).
- **Manifest schema** unchanged; `supported_hosts:` field semantics unchanged; no API-shape changes.

### Internal

- Mass sed sweep `s/agent-toolkit/crickets/g` + `s/agentic-harness/agentm/g` across all text files in both repos.
- `lib/install/` resynced via the canonical `scripts/sync-lib.sh` from the agentm side (propagates byte-identical lib + regenerates parity checksums on both sides).
- Sibling repo's `~/.claude/CLAUDE.md` global Claude Code import paths updated to point at `~/Antigravity/agentm/AGENTS.md` + `~/Antigravity/crickets/AGENTS.md` (operator-local; lives in `dev-setup/configs/claude/CLAUDE.md` via symlink).
- Vault dirs `personal-projects/agentic-harness/` + `personal-projects/agent-toolkit/` renamed to `agentm/` + `crickets/` respectively; ~43 vault files / 157 occurrences swept.
- Pre-push PII hook (templates/hooks/pre-push) updated to search `~/Antigravity/crickets/scripts/check-no-pii.sh` instead of the old `agent-toolkit` path.

### Cross-references

- Paired sibling release: [agentm v3.1.0](https://github.com/alexherrero/agentm/releases/tag/v3.1.0) — the harness (was agentic-harness)
- Plan #15 task 11 — README refresh closing task (final task of plan)

## [v1.0.2] — 2026-05-24 — Fix Crickets transparent-variant assets (toolkit-only PATCH)

Patch — **hotfix for the v1.0.1 Crickets logo hero**. The 6 `crickets-transparent-{64 / 128 / 256 / 512 / 1024 / 2048}.png` files shipped in v1.0.1 had the design-tool's transparency-indicator checker pattern **baked into the PNG itself** (visible by inspecting the asset directly; visible on the live GitHub README hero as a grey checker around the disc). Operator flagged the mismatch with Agent M's clean visual after v1.0.1 shipped.

**Fix:** regenerated all 6 transparent variants from the clean `crickets-disc-2048.png` source via PIL high-quality resize. New transparent set has real transparent surround (bbox padding matches Agent M's `clean-transparent` ratio at ~10%). README hero reference stays `crickets-transparent-512.png` — file content replaced in place; live render auto-corrects on push.

### Changed

- **`assets/crickets/crickets-transparent-{64 / 128 / 256 / 512 / 1024 / 2048}.png`** — regenerated. File sizes shrunk ~3× (e.g. 512px went from 282KB → 96KB; no more checker overlay inflating the file). Visual now matches Agent M's clean-silhouette-on-transparent-surround pattern.

### Internal

- 1 commit on this side: this v1.0.2 release commit (combined: regenerated PNGs + CHANGELOG entry).
- **Source for regeneration**: `crickets-disc-2048.png` (the largest clean disc variant). PIL `Image.LANCZOS` resampling for each target size.
- **Not regenerated** (intentionally left alone): the 9 `crickets-{16 / 32 / 48 / 64 / 128 / 256 / 512 / 1024 / 2048}.png` standard variants have the same checker-baked-in issue, but no README currently references them. Operator can re-export from Claude design at their convenience; not blocking.
- **Diagnosis trail**: live GitHub render still showed checker artifact → PIL bbox analysis confirmed content reached all canvas edges (bbox = (0,0,512,512)) → contrast with clean disc variant (bbox = (75,75,437,436)) confirmed the checker was baked into the broken files, not a rendering artifact. Fix regenerates from the clean source.

## [v1.0.1] — 2026-05-24 — Crickets logo hero + brand-name clarification (toolkit-only PATCH)

Patch — **first visual brand iteration on the Crickets side**, mirroring the [`agentm v3.0.1`](https://github.com/alexherrero/agentm/releases/tag/v3.0.1) Agent M logo pass from earlier today. Adds the Crickets logo asset set and refreshes `README.md` + `wiki/Home.md` with the brand-aligned visual hero. Toolkit-only PATCH (no paired harness release this round — harness already shipped v3.0.1 with the Agent M hero; this matches it on the Crickets side).

**Brand-name clarification — singular "Cricket" → plural "Crickets" across all surfaces.** The brand was always meant to be plural (per the asset directory `assets/crickets/` shipped here and `<title>Crickets — Asset Set</title>` in the operator's brand artifacts); earlier CHANGELOG entries / READMEs introduced the singular form by typo. This release corrects retroactively — CHANGELOG entries for `v1.0.0` (and harness v3.0.0 / v3.0.1 on the harness side) read "Crickets" consistently end-to-end. **GitHub release pages preserved as-shipped** (those are immutable in practice).

### Added

- **`assets/crickets/`** — Crickets logo asset set in 4 treatments (standard / transparent / on-black / disc) × multiple PNG sizes (16 / 32 / 48 / 64 / 128 / 256 / 512 / 1024 / 2048) + SVG wrapper. ~33 asset files.
- **`assets/crickets/banner-1600.png`** + **`banner-3200.png`** — wide banner format (1600×640 — common GitHub README banner ratio).
- **`assets/crickets-index.html`** — brand-asset preview page showing all variants on light / dark / checkered backgrounds.
- **`assets/banner.html`** — preview page for the banner format.

### Changed

- **Brand name clarified Cricket → Crickets** everywhere in this repo's `CHANGELOG.md` (v1.0.0 entry retroactively), `README.md`, `wiki/Home.md`. Asset directory was already `assets/crickets/` (plural) — the rename aligns text with directory.
- **`README.md` hero** — centered logo hero (`assets/crickets/crickets-transparent-512.png` at displayed 256px), italic tagline (*"Small agent primitives that punch above their weight."*), and reorganized badge layout into two centered blocks (test/release/license + host-compat). H1 swapped from markdown `#` to `<h1 align="center">` for visual coherence with the centered hero. Rest of the README untouched.
- **`wiki/Home.md`** lead paragraph updated for Crickets branding (singular → plural).

### Internal

- 1 commit on this side: `<pending>` (assets + rename + README hero + wiki Home) + this v1.0.1 release commit.
- **Toolkit-only PATCH** — harness reference cleanup (singular Cricket → plural Crickets in harness README + CHANGELOG + Completed-Features) rides as a separate harness docs commit (no harness version bump this round; harness already shipped v3.0.1).
- **Same brand palette + typography as Agent M** — `--ink: #0a0a0a` + `--paper: #f4efe6` + Inter Tight + JetBrains Mono. Brand-system coherence is real; operator delivered both sets from Claude.ai Artifacts.
- Establishes `assets/` as the brand-asset convention on the Crickets side (matches the convention already established on the Agent M side).
- **Operator-review-gated** per [[docs-prose-style]] workflow; explicit approve-and-ship green-light received before push.

## [v1.0.0] — 2026-05-24 — Crickets 1.0 (paired with agentm v3.0.0 — Agent M V3 close-out)

Major — **1.0 commitment** after the V3 arc validates the customization surface. The toolkit is now **Crickets** — the noisy cricket of the system, small primitives that punch above their weight. Paired with [`agentm v3.0.0`](https://github.com/alexherrero/agentm/releases/tag/v3.0.0) which ships **Agent M V3** — the agentic memory system that the harness + Crickets + vault folder together compose.

**What 1.0 commits to** (stable public API surface):

- **Manifest schema** — YAML frontmatter contract (`name` / `kind` / `description` / `supported_hosts` / `version` / `install_scope` / `deprecated` / `contents`). Stable. Breaking changes require a 2.0.
- **Installer flags** — `--skill <name>`, `--agent <name>`, `--hook <name>`, `--bundle <name>`, `--update`, `--hooks` (verification hooks), `--no-pre-push-hook`. Stable.
- **`bundles/` namespace** — bundles are manifests pointing at standalone primitives (sibling-reference dispatch); the `contents:` schema is stable.
- **11 customization kinds** — `skill` / `command` / `agent` / `hook` / `mcp-server` / `bundle` / `status-line` / `output-style` / `workflow` / `rule` / `snippet` / `settings-fragment`. Adding kinds is non-breaking; removing or renaming is a 2.0.
- **Per-host install paths** — destinations per kind per host (see [wiki/reference/Per-Host-Paths](wiki/reference/Per-Host-Paths.md)). Stable.

**What stays pre-1.0 in spirit** (internal surface, may evolve):

- **`scripts/`** — `validate-manifests.py`, `check-lib-parity.sh`, `check-syntax.sh`, `check-no-pii.sh`, `check-wiki.py`, etc. Used by Crickets' own CI; not part of the public contract.
- **`lib/install/`** — shared install plumbing copied byte-identical between Crickets + `agentm`. Internal to both repos.

### What shipped across the V3 arc (v0.5.0 → v1.0.0)

13 paired releases over ~12 days. Headline customizations:

| Layer | What Crickets ships today |
|---|---|
| **Skills** (6) | `pii-scrubber`, `dependabot-fixer`, `ship-release`, `design`, `memory`, `diataxis-author` |
| **Sub-agents** (1) | `evaluator` (+ `adapt-evaluator` write-allowlist-scoped helper) |
| **Hooks** (4) | `kill-switch`, `steer`, `commit-on-stop`, `evidence-tracker` |
| **Bundles** (2) | `quality-gates` (real-substance), `example-bundle` (reference skeleton) |
| **ADRs** (9) | 0001 purpose, 0002 evaluator, 0003 base hooks, 0004 design skill, 0006 Gemini-CLI removal, 0007 MemoryVault Discovery + Mining, 0008 diataxis-author, 0009 evidence-tracker, 0010 quality-gates |

Plus the wiki — Diátaxis four-mode (tutorials / how-to / reference / explanation) with the V3 retrospective + Agent M evolution HLD shipped fresh in this release pair.

### Added

- **`README.md`** — Crickets brand-framed rewrite. Lead paragraph names Crickets, the catalog table covers what ships today, install commands paired with Agent M, architecture-history pointers go to the HLD + V3 retrospective.
- **`wiki/Home.md`** — Crickets lead paragraph above the Diátaxis nav.
- **`wiki/explanation/v3-retrospective.md`** (new, 1749 words) — what shipped across the V3 arc, what we learned, what's deferred. 7 sections: scope / what shipped / architecture themes that crystallized / repeat lessons / operator-driven mid-plan pivots / deferred items + rationale / TBD frontiers heading into V4.
- **`wiki/explanation/designs/agent-memory-evolution.md`** (new, ~3000 words) — Agent M V1→V4 HLD. 8 sections: Goals / Background / Architecture / Constitutional Schema / Autonomous Workflows / Background Automations / Commands Reference + See also. Forward-looking V4 framing covers role split (raw yours / wiki agent's / schema joint), three-stage pipeline (raw / inbox / wiki), file-back compile loop, multi-domain scope (Agent M for coding, vacation, cooking, crafting, research, learning), universal sub-dirs, first-class binary assets, domain-as-tag, cross-project layers, entry content rule, synthesis primitive, auto-save default, tighter guardrails. V4.5 (harness rework for any domain) noted as separate future design.

### Changed

- **Brand**: the toolkit is now **Crickets** in operator-facing prose. The `crickets` repo name + `crickets/` path literal stay as code-side names (renaming the repo would break every existing install). Per the locked branding convention.

### Internal

- **4 commits on this side** since v0.13.0: `6cea91d` (V3 retrospective), `33dc752` (Agent M HLD + Home/Sidebar/retrospective back-links), `e30fbef` (cross-ref fix — `.harness/` paths are gitignored, so GitHub URLs to them resolve to 404; demoted to inline path mentions), `d22ea0d` (Crickets README + wiki Home rewrite), plus this v1.0.0 release commit.
- **Paired-release ordering**: this toolkit release tagged first; harness v3.0.0 release notes URL-link this release per `[[coordinated-release-order]]` convention.
- **8th consecutive paired-release pair** (after v0.9.0/v0.9.2/v0.10.0/v0.11.0/v0.11.1/v0.12.0/v0.13.0). First MAJOR.

## [v0.13.0] — 2026-05-23 — quality-gates bundle (paired with agentm v2.6.1)

Minor — **first real-substance bundle** in the toolkit after the `example-bundle` stub. Ships [`quality-gates`](bundles/quality-gates/bundle.md) — one-command install for the 4 base operator-control + verification primitives that earn their keep on every agentm `/work` session: `evaluator` sub-agent + `kill-switch` / `steer` / `commit-on-stop` / `evidence-tracker` hooks. Paired with [`agentm v2.6.1`](https://github.com/alexherrero/agentm/releases/tag/v2.6.1) (paired-doc-only — bundle is pure toolkit packaging).

**Why this earns its keep**: pre-#10, operators adopting harness `/work` had to install each of the 5 primitives individually + remember they all wanted the full set. Real-world adopters routinely missed one — usually `commit-on-stop`, the safety net you only notice when a session crashes mid-task. The "I forgot to install commit-on-stop and lost an hour" failure mode was predictable + recurring. The bundle closes that gap: one `--bundle quality-gates` install lands all 5 primitives at the right `.claude/` paths + merges all 4 settings.json registrations (3 PreToolUse + 1 Stop) atomically.

**Notable design call — operator-driven mid-plan pivot from COPY to sibling-reference.** Initial plan (matching the existing `example-bundle` precedent) was to copy each primitive's files into `bundles/quality-gates/{agents,hooks}/` + add a CI parity gate to catch drift. Operator pushed back: *"wait why did we make a bunch of copies?"* The example-bundle precedent was set by a one-stub-skill toy + didn't survive contact with a real 5-primitive set. Pivoted to **sibling-reference**: bundle directory contains only `bundle.md`; the installer's `install_bundles()` / `Install-Bundles` dispatch resolves each `contents:` entry against the standalone toolkit primitive location (`<TOOLKIT_ROOT>/<kind>s/<name>/`), with bundle-local fallback preserving example-bundle's stub-only-in-bundle role. Net: -1992 lines vs. the COPY pivot; zero ongoing maintenance burden; bundle is metadata pointing at standalone primitives, single source of truth.

Decision rationale + 2 locked design calls Q1-Q2 + 4 load-bearing assumptions with re-audit triggers in the new [ADR 0010 — quality-gates bundle](wiki/explanation/decisions/0010-quality-gates-bundle.md).

### Added

- **`bundles/quality-gates/bundle.md`** (~85 lines) — manifest with `contents:` listing 5 entries (1 agent + 4 hooks); `kind: bundle`; `supported_hosts: [claude-code]`; `version: 0.1.0`; body documents what / why / install / version-bump convention / sibling-reference invariant + how-it-works section.
- **`install.sh` `install_bundles()` extension** (~50 lines) — contents-driven dispatch: parses `bundle.md` `contents:` via inline `python3 -c` + for each `kind: name` entry, resolves source path (standalone-first; bundle-local fallback); invokes the existing per-kind `install_*` dispatch.
- **`install.ps1` `Install-Bundles` extension** (~50 lines) — PowerShell mirror of the bash logic.
- **`scripts/validate-manifests.py` `check_contents()` update** — accepts either standalone OR bundle-local path resolution for bundle contents.
- **Smoke install tests (bash + pwsh)** — `==> quality-gates bundle install test` block in both `scripts/smoke-install-bash.sh` + `smoke-install-pwsh.ps1`. 3 assertions per OS: [a] 6 expected files land (1 agent + 4 hook .sh/.ps1 + evidence_tracker.py sidecar); [b] settings.json shape — exactly 3 PreToolUse + 1 Stop with correct script references; [c] kill-switch sentinel works end-to-end against the bundle-installed `.sh` (touch `.harness/STOP` → exit 2).
- **New [ADR 0010 — quality-gates bundle](wiki/explanation/decisions/0010-quality-gates-bundle.md)** (~1500 words) — full Status block + Context + Decision Q1-Q2 + Consequences positive/negative/load-bearing with re-audit triggers + Related. Documents the COPY→sibling-reference pivot as the key design call.
- **New [`wiki/how-to/Use-The-Quality-Gates-Bundle.md`](wiki/how-to/Use-The-Quality-Gates-Bundle.md)** (~570 words, under 600 soft ceiling) — operator-facing: when-to-use guide; install command for bash + pwsh; post-install state tree; verification commands; troubleshooting that cross-links to per-primitive how-tos rather than duplicating.
- **`wiki/Home.md` + `wiki/_Sidebar.md`** references added for both new entries.

### Changed

- **`install.sh` + `install.ps1`** — bundle dispatch is now contents-driven (was alphabetical-from-directory-listing). Install order = `contents:` order in the manifest. For bundles like quality-gates this is deterministic + explicit.
- **`validate-manifests.py`** — bundle `contents:` entries validate against either standalone or bundle-local primitive paths.

### Internal

- **6 commits across plan #10** on this side: `325481c` (initial COPY pivot — reverted) + `62a38a7` (COPY→sibling-reference pivot; -1992 lines) + `62230ca` (smoke tests) + `2667348` (pwsh `mkdir` fix — Windows CI failure) + `16d55e4` (UTF-8 fix — Windows cp1252 failure) + `45a23e9` (how-to + ADR 0010) + this v0.13.0 release commit.
- **2 cross-platform Python gotchas caught + fixed mid-plan**: (a) `Join-Path` constructs path strings but doesn't `mkdir` on pwsh — bash `mktemp -d` implicitly creates the dir, so tests passed locally but Windows failed. (b) Inline `python3 -c "open(file)..."` uses cp1252 on Windows → `UnicodeDecodeError` on UTF-8 bundle.md (em dashes + arrows). Same family as the plan #13 `→`-arrow + cp1252 stdout bugs; defensive fix in both install.sh + install.ps1. Lesson logged: when extending toolkit installers with inline Python, audit for `encoding='utf-8'` explicit on every `open()`.
- **Paired-release ordering**: this toolkit release tagged first; harness v2.6.1 release notes URL-link this release per `[[coordinated-release-order]]` convention.
- **7th consecutive paired-release pair** (after v0.9.0/v0.9.2/v0.10.0/v0.11.0/v0.11.1/v0.12.0). First real-substance MINOR since v0.12.0.

## [v0.12.0] — 2026-05-23 — evidence-tracker hook (paired with agentm v2.6.0)

Minor — **4th base hook** in the toolkit after kill-switch / steer / commit-on-stop (ADR 0003). Ships [`evidence-tracker`](hooks/evidence-tracker/hook.md) — a `PreToolUse` hook that enforces a **default-FAIL evidence contract** on harness `/work` task closeouts. The agent must demonstrably *read* (via the `Read` tool, which the hook observes) a spec/test/evidence file matching the task's requirement *before* a `Write`/`Edit` that flips PLAN.md `[ ]` → `[x]` is allowed. Hook blocks (exit 2) otherwise with a helpful stderr message + 3 recovery paths. Paired with [`agentm v2.6.0`](https://github.com/alexherrero/agentm/releases/tag/v2.6.0) which ships the corresponding `/work` §5b spec amendment.

**Why this matters**: today's `/work` trusts the agent to *verify* before flipping a task `[x]`. The verification step is in the contract but not *observable* — sometimes the agent claims completion based on partial signals (passing tests that didn't cover the new code; "looks good" judgments on diffs the agent didn't actually read against the spec). The cwc-long-running-agents pattern, paraphrased: *"The only evidence that counts is a file matching the patterns."* This hook makes that observable + enforced.

**Evidence resolution is HYBRID** (per Q1 in the new ADR 0009):
- **HEURISTIC** by default — file under `tests/` / `spec/` / matching `*.spec.*` / `*.test.*` / `*_test.py` / `test_*.py` with a code extension (markdown explicitly excluded — `tests/README.md` does NOT satisfy evidence), OR any path literally named in the task's `**Verification:**` text.
- **Per-task override** via `**Evidence:** <glob-or-paths>` task-body annotation.
- **Explicit opt-out** via `**Evidence:** none — <rationale>` (rationale mandatory; becomes audit trail).

**Granularity** (Q2): per-task PLAN.md `[ ]` → `[x]` flips only; `features.json passes:true` is `/release`'s domain.
**Bypass** (Q3): explicit opt-out only; no auto-detection (would let lazy refactor commits dodge via .md-only-touch).

Decision rationale + 3 locked design calls (Q1-Q3) + 4 load-bearing assumptions with re-audit triggers in the new [ADR 0009 — evidence-tracker hook](wiki/explanation/decisions/0009-evidence-tracker-hook.md).

### Added

- **`hooks/evidence-tracker/evidence_tracker.py`** (~720 lines, stdlib-only) — core resolver + state-file management + checkbox-flip detector. 5 core functions (parse_plan / resolve_evidence_requirement / matches_heuristic / matches_list / state-file-mgmt + check_evidence_met + would_flip_checkbox) + CLI dispatcher (`--mode check|reset|self-test`). **61 unit tests** across 9 classes covering all paths including the negative blocking case. Fictitious-path bypass blocked at CLI level (only existing files recorded).
- **`hooks/evidence-tracker/{hook.md, evidence-tracker.sh, evidence-tracker.ps1, settings-fragment-bash.json, settings-fragment-pwsh.json}`** — manifest + thin shell + pwsh entry points (just shell out to the Python helper via stdin pipe-through) + settings registrations for PreToolUse on `Read|Write|Edit` matcher.
- **Smoke install tests (bash + pwsh)** — 6 evidence-tracker sub-tests in both `scripts/smoke-install-bash.sh` + `smoke-install-pwsh.ps1` covering happy path / opt-out / heuristic / per-task override / state reset / blocking-with-helpful-stderr.
- **CI step** added to all 3 OS workflows (`tests-linux.yml`, `tests-mac.yml`, `tests-windows.yml`): `python3 hooks/evidence-tracker/evidence_tracker.py --mode self-test`.
- **New [ADR 0009 — evidence-tracker hook](wiki/explanation/decisions/0009-evidence-tracker-hook.md)** — full Status block + Context + Decision Q1-Q3 + Consequences positive/negative/load-bearing with re-audit triggers + Related. Matches ADR 0007/0008 shape.
- **New [`wiki/how-to/Use-The-Evidence-Tracker-Hook.md`](wiki/how-to/Use-The-Evidence-Tracker-Hook.md)** — operator-facing per-hook walkthrough: when-it-fires per-tool table + 3 worked scenarios + 3 recovery paths + 6-row troubleshooting table + dogfood walkthrough. Length-justified inline.
- **`wiki/Home.md` + `wiki/_Sidebar.md`** references added for the new how-to + ADR.

### Changed

- **`install.sh` + `install.ps1`** — `install_hook` / `Install-Hook` extended to copy any sibling `*.py` files in the hook source dir to `.claude/hooks/` alongside the `.sh`/`.ps1` entry. Lets hooks ship a Python helper without requiring it to live in a separate skill dir. Plan #9 introduced this pattern; ~7 lines per installer.
- **`scripts/check-integrity-bash.sh` + `check-integrity-pwsh.ps1`** — `.claude/hooks/` integrity assertion updated to permit `.py` files (previously only `.sh`/`.ps1` allowed; would reject the new sibling helper layout).

### Internal

- **8 commits across plan #9 on this side**: `8c6419f` (evidence_tracker.py + 61 tests) + `6e875d5` (hook scaffolding + installer + integrity-check extension) + `e6f4411` (integrity-check fix for sibling-.py pattern caught by CI) + `83fb3e7` + `a3100ab` (smoke tests + variable-name fix caught by CI) + `4569c20` (how-to) + `8793237` (wiki baseline drift cleanup — 21 → 0 structural errors) + `ecd8d6c` (ADR 0009) + this v0.12.0 release commit.
- **2 in-flight scope expansions caught + fixed mid-plan**: (a) installer needed to copy sibling `.py` helpers (not original scope; necessary for the new hook design) + corresponding integrity-check update; (b) toolkit-side check-wiki baseline drift accumulated from plans #7b/#13/#8 not refreshing Home.md/Sidebar.md — surfaced when adding the new how-to + ADR; fixed in `8793237`. Both expansions were necessary for the task; documented in commit messages.
- **Paired-release ordering**: this toolkit release tagged first; harness v2.6.0 release notes URL-link this release per `[[coordinated-release-order]]` convention.
- **6th consecutive paired-release pair** (after v0.9.0/v0.9.2/v0.10.0/v0.11.0/v0.11.1). First real-substance toolkit MINOR since v0.11.0 (intervening v0.11.1 was wiki-only).

## [v0.11.1] — 2026-05-22 — Cross-Repo Memory Protocol doc (paired with agentm v2.5.0)

Patch — wiki-only release paired with [`agentm v2.5.0`](https://github.com/alexherrero/agentm/releases/tag/v2.5.0). Substantive change ships entirely on the harness side: new `scripts/harness_memory.py` dispatcher + phase-spec amendments wire MemoryVault read + write into every harness phase command (`/setup` `/plan` `/work` `/review` `/release` `/bugfix`) at natural boundaries.

This toolkit-side release adds the **companion documentation** describing the cross-repo contract: what the harness expects from `skills/memory/scripts/save.py` (+ planned `recall.py query`), what stability guarantees the toolkit makes, and how graceful-skip works in both directions when one side isn't installed.

**5th consecutive paired-release-as-documentation pair** (after v2.4.0/v2.4.1/v2.4.2/v2.4.3) — but **first non-doc-only pair** in the run when measured from the harness side (harness ships real new phase behavior, not just docs).

### Added

- **New `wiki/explanation/Cross-Repo-Memory-Protocol.md`** (~80 lines) — documents the harness↔toolkit memory contract:
  - **What the harness expects** from `save.py` — CLI flag stability (`--vault-path` / `--group` / `--body-file -`), body-via-stdin, exit-0-on-success, deduplication contract.
  - **What the toolkit guarantees** — 5 stability points that anchor the harness's `_invoke_toolkit_save()` function in `scripts/harness_memory.py`.
  - **Phase-boundary integration map** — table showing which toolkit script each harness phase calls + which vault paths get read vs. written.
  - **Graceful-skip protocol** — both directions: toolkit-absent + harness-present (manual `/memory save` still works), harness-present + toolkit-absent (phases run unchanged with stderr `[harness_memory] toolkit not installed — recorded intent only` notice), and vault-missing (harness short-circuits before invoking toolkit).
  - **Versioning + compatibility note** — explicit "soft contract" framing; neither repo's CI verifies the cross-repo integration. Harness ships smoke tests against a fixture toolkit stub (`TestOfferSaveBehavior` + `TestOfferSaveToolkitAbsent` in `scripts/test_harness_memory.py`).

- **`wiki/Home.md`** reference added under "Want to know why?" → Cross-Repo Memory Protocol.

### Changed

- None — no skill code, no installer changes, no manifest schema changes. Toolkit `skills/memory/` is byte-identical to v0.11.0.

### Internal

- **1 commit** (`9176bc2`) — wiki-only addition.
- **No CI changes** — wiki page lints clean against the toolkit's `check-wiki.py`; the 22 pre-existing soft errors in toolkit-side check-wiki output are unchanged baseline drift (not gated in toolkit CI).
- **Paired-release ordering**: this toolkit release tagged first; harness v2.5.0 release notes URL-link this release per `[[coordinated-release-order]]` convention.

## [v0.11.0] — 2026-05-22 — diataxis-author skill (paired with agentm v2.4.3)

Minor — second major skill in the toolkit after `memory`. Ships [`diataxis-author`](skills/diataxis-author/SKILL.md) — one skill, five sub-commands covering the full Diátaxis-wiki lifecycle (author + maintain + migrate). Encodes the operator's preferred conventions from [agentm ADR 0004](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0004-diataxis-documentation-spec.md) into proactive authoring guidance + ongoing drift detection + repair + one-shot migration. Subsumes harness's `migrate-to-diataxis` predecessor (deprecated 2026-05-22; predecessor file removal in follow-up harness PATCH after dogfood). Second real dogfood of plan #6's `/design` skill (after MemoryVault). Paired with [`agentm v2.4.3`](https://github.com/alexherrero/agentm/releases/tag/v2.4.3) (paired-doc-only on harness side — 4th consecutive paired-release-as-documentation pair after v2.4.0/v2.4.1/v2.4.2).

**Why this shape**: the operator maintains three Diátaxis-shaped wikis (agentm + crickets + dev-setup) plus the just-shipped MemoryVault parent design — Diátaxis discipline is real, ongoing, but previously supported only by `check-wiki.py --strict` (catch violations post-write) + `documenter` sub-agent (sweep at `/release`) + `migrate-to-diataxis` (one-shot legacy migration). The gap: live authoring guidance + ongoing drift detection + repair. This skill ships the missing layer + subsumes the predecessor + repurposes `documenter` as the skill's mechanical-write worker (same orchestration-skill + worker-sub-agent pattern as `/memory adapt-skills` + `adapt-evaluator` from #7b task 4).

Decision rationale + 4 locked design calls (Q1-Q4) + 4 load-bearing assumptions with re-audit triggers in the new [ADR 0008 — diataxis-author skill](wiki/explanation/decisions/0008-diataxis-author.md). Parent design at [wiki/explanation/designs/diataxis-author.md](wiki/explanation/designs/diataxis-author.md) (Status: launched as of this release per `/design` lifecycle).

### Added

- **`skills/diataxis-author/SKILL.md`** (~700 lines) — manifest + body covering all 5 sub-commands (`/diataxis author`, `/diataxis check`, `/diataxis repair`, `/diataxis migrate`, `/diataxis classify`). Cross-refs to parent design + ADR 0004 + predecessor + sibling `memory` skill + `adapt-evaluator` as design precedent.
- **`skills/diataxis-author/scripts/classify.py`** (~250 lines) — Tier-1 heuristic mode-classification engine: regex + heading-shape rules mirroring `check-wiki.py` + ADR 0004's machine-enforceable rules. Per-mode scoring (tutorial 0.0-0.95 / how-to 0.0-0.85 with rationale-section penalty / reference 0.0-0.9 with quickref + table-ratio signals / explanation = 1.0-max(others)). Mode-mixed detection: ≥1 other mode within 0.2 + above 0.5. `--threshold` (default 0.7; AgentMemory-tunable) / `--no-subagent` / `--stub` flags.
- **`skills/diataxis-author/scripts/author.py`** (~200 lines) — invocation entry for `/diataxis author`. Resolves mode (`--mode` > `--intent` → classify.py > error); loads template; applies filename style (AgentMemory-tunable; default `CamelCase-With-Dashes`); writes skeleton via `write_bytes` (LF-only Windows portability). Mode-to-dir mapping: `tutorial → tutorials/` (plural per Diátaxis); others singular. Collision-refuse by default.
- **`skills/diataxis-author/scripts/check.py`** (~270 lines) — drift detection. Wraps `check-wiki.py` (harness-side) as subprocess via auto-detect sibling-clone; adds 4 skill-side heuristics: `mode-mixed` (catches both `mode_mixed:true` + `needs_subagent:true` to handle penalty-masked cases), `stale-cross-ref` (wiki-link resolution), `template-shape-drift` (page lives in mode-dir X but classifies as Y with confidence ≥0.7), `convention-drift` (v1 stub; full handling part 5 with AgentMemory). Structured JSON report grouped by rule.
- **`skills/diataxis-author/scripts/repair.py`** (~270 lines) — interactive fix-application loop; preview-first per finding. Dispatches `documenter` sub-agent for mode-mixed splits (CLI emits marker; skill body dispatches; `--stub` mode for CI). Non-TTY defaults to skip (never-silent-action). `--limit N` caps; `--findings <json>` replays.
- **`skills/diataxis-author/scripts/migrate.py`** (~360 lines) — ports harness's `migrate-to-diataxis` predecessor. 6 classification rules + precondition checks (clean tree + wiki exists + no `.diataxis` marker + ≥1 legacy mode-dir) + `--skip-precheck` testing escape. `git -C <repo_root>` cwd-independent invocation. Never `git commit`. `.diataxis-conventions.md` auto-seeded with operator-editable conventions.
- **`skills/diataxis-author/scripts/agentmemory_conventions.py`** (~200 lines) — AgentMemory read + write integration. 3-tier fallback chain: per-repo `<wiki>/.diataxis-conventions.md` > vault `_always-load/diataxis-*.md` > ADR 0004 hardcoded defaults. Recognizes both plain + `**bold**`-wrapped convention keys via shared `_parse_conventions_text()` helper. `confirm_save_convention()` routes through `permeable_boundary` for operator-confirmed write-back. Falls back to direct write if `save.py` import fails.
- **`skills/diataxis-author/templates/{tutorial,how-to,reference,explanation}.md`** — 4 Diátaxis templates per ADR 0004 mode definitions. Tutorial has mandatory `## What you learned` + `## Next`. How-to excludes `## Rationale|Why|Background|Context`. Reference leads with `## ⚡ Quick Reference`. Explanation is prose-heavy with `## Context` + `## Tradeoffs`.
- **`agents/diataxis-evaluator.md`** (~135 lines) — read-only sub-agent stub with caller-supplies-inline-rubric pattern. Tool allowlist `Read, Glob, Grep, WebFetch` with **NO Write/Edit** (zero filesystem write scope — stricter than `adapt-evaluator`'s scoped-write).
- **[ADR 0008 — diataxis-author skill](wiki/explanation/decisions/0008-diataxis-author.md)** — 4 locked design calls Q1-Q4 (scope = author+maintain+migrate; AgentMemory = read+write conventions; documenter = worker via dispatch; single skill with 5 sub-commands) + 4 load-bearing assumptions with re-audit triggers.
- **[`wiki/how-to/Use-Diataxis-Author.md`](wiki/how-to/Use-Diataxis-Author.md)** — comprehensive how-to covering all 5 sub-commands + 5 worked scenarios + AgentMemory integration walkthrough + per-repo `.diataxis-conventions.md` override pattern + troubleshooting (8 entries including Windows UnicodeEncodeError fixed in this release).
- **Parent design** at [wiki/explanation/designs/diataxis-author.md](wiki/explanation/designs/diataxis-author.md) — Status: final (operator-approved 2026-05-22 via `/design author` fast-path); transitions to `launched` post-release per `/design` skill lifecycle.
- **5 part files** at [wiki/explanation/designs/diataxis-author/parts/](wiki/explanation/designs/diataxis-author/parts/) — `skill-scaffold` + `author-classify` + `check-repair` + `migrate-subsume` + `agentmemory-docs-release`.
- **Smoke install tests (bash + pwsh)**: ~30 new sub-tests across 4 test blocks (author+classify: 10; check+repair: 7; migrate: 5; AgentMemory integration verified via existing test fixtures + dry-run testing).

### Changed

- **`scripts/smoke-install-bash.sh` + `smoke-install-pwsh.ps1`** — expected-files list grew with 17 new paths (`.claude/skills/diataxis-author/{SKILL.md,scripts/*,templates/*}` + `.agent/skills/diataxis-author/{...same...}` + `.claude/agents/diataxis-evaluator.md` + `.agent/skills/diataxis-evaluator/SKILL.md`). Rerun-log regex extended for new sub-agent.

### Internal

- **8 commits across plan #13**: `095b688` (Part 1 scaffold) + `9d619db` (Part 2 author + classify + 4 templates) + `caf3c5a` (Part 2 Windows pwsh Start-Process fix) + `45eecd6` (Part 3 check + repair) + `c5b32fd` (Part 4 migrate) + `d4d4adf` (Part 4 harness deprecation) + `79cf283` (Part 4 Windows UTF-8 stdout fix) + this v0.11.0 release commit (Part 5 AgentMemory + docs + ADR + CHANGELOG).
- **3 Windows-specific CI failures caught + fixed mid-plan** per `[[wake-on-ci-pattern]]` scope-expansion convention: (1) `caf3c5a` — pwsh `Start-Process -ArgumentList` splits multi-word args; switched to `& python3` direct invocation. (2) `79cf283` — Windows Python `cp1252` stdout encoding can't encode `→` arrow in migrate preview; switched to `sys.stdout.reconfigure(encoding='utf-8')` at module load. (3) prior `ead1f8d` from v0.9.2 set the pattern (CRLF line endings → `write_bytes` for operator-facing files). Pattern locked: cross-platform Python scripts must defensively configure encoding + line endings + invocation patterns.
- **Subsumes `migrate-to-diataxis` predecessor** (harness-side); harness commit `d4d4adf` adds NOTE-WARNING deprecation block + redirect. Predecessor file stays through v1 dogfood; removal in follow-up harness PATCH release.

## [v0.10.0] — 2026-05-22 — MemoryVault Discovery + Mining (paired with agentm v2.4.2)

Minor — second roadmap item under the MemoryVault parent design closes (ROADMAP item #7b). **Four new sub-commands** turn the vault from a static curated store into a living surface: `/memory index-skills` (auto-indexer for installed SKILL.md files), `/memory reflect corpus` (historical-transcript-backlog mining), `/memory discover-skills` (cadence-checked internet skill-discovery scan), `/memory adapt-skills` (Pass 1 Python rubric + Pass 2 LLM sub-agent judgment), `/memory watchlist` (promote/dismiss/defer review surface). All implementations are stdlib-only (no new third-party deps); GitHub API access via unauthenticated `urllib.request` with graceful-skip on the 60/hr rate limit. Paired with [`agentm v2.4.2`](https://github.com/alexherrero/agentm/releases/tag/v2.4.2) (paired-doc-only on the harness side).

**Why this shape**: plan #7a (MemoryVault Core, closed 2026-05-20) shipped the static curation surface — auto-recall via hooks + reflection sidecar + tri-modal routing + idea ledger + seed-pass. #7b's mandate was the *living* surface: indexing installed skills as recall context, mining the historical transcript backlog for durable patterns the manual seed pass missed, scanning curated internet sources for skill-shaped patterns, and gating adoption through a deterministic Python rubric + LLM sub-agent judgment with **adapt-don't-import architectural enforcement** (sub-agent write allowlist physically prevents auto-fork to `crickets/skills/`).

Decision rationale + 7 locked design calls + 4 load-bearing assumptions with re-audit triggers in the new [ADR 0007 — MemoryVault Discovery + Mining](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0007-memoryvault-discovery.md). The parent [MemoryVault design doc](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/memoryvault.md) gets Document History row 11 covering the additive layer.

### Added

- **`skills/memory/scripts/index_skills.py`** (~440 lines) — walks SKILL.md files across `--skill-path` (repeatable) + `MEMORY_SKILL_PATHS` env. Writes one `kind: skill-pointer` entry per skill to `<vault>/personal-skills/<repo>/<skill-name>.md`. Repo-name auto-detect via `.git/` or `AGENTS.md` ancestor walk (kebab-normalized); override via `--repo-name`. Idempotent: `_entry_needs_refresh()` no-ops when `skill_version` + description match.
- **`skills/memory/scripts/reflect.py corpus` subcommand** (~404 net new lines) — batched paced walk over `~/.claude/projects/*/<session>.jsonl` with skip-resume state file. **Dry-run by default** — first invocation counts + estimates without writing. Atomic state writes; single-session resume granularity. Subcommand dispatch via `argv[0]=="corpus"` preserves existing single-transcript CLI path.
- **`skills/memory/scripts/discover_skills.py`** (~380 lines) — periodic fetcher over operator-editable source whitelist at `<vault>/personal-private/skill-discovery-sources.md`. Auto-seeds 4 sources in operator's confirmed priority order: Anthropic Cookbook → awesome-claude-code → awesome-mcp-servers → awesome-llm-apps. Per-source dated snapshot + diff cache. `--cadence-check` (default 7d) self-throttles for idle-hook integration. Stdlib-only urllib; graceful-skip on 4xx/5xx/timeout/DNS.
- **`hooks/memory-reflect-idle/{memory-reflect-idle.sh,.ps1}` extension** — appends `discover_skills.py --cadence-check` call. Restructured early-exit so the discover call still fires when there's no orphan work.
- **`skills/memory/scripts/adapt_skills.py`** (~480 lines) — Pass 1 of adapt-don't-import. Parses candidates from cached diffs; applies 6-rule rubric (R1 new-tool +1 / R2 complements-convention +1 / R3 agent-building-context +1 / R4 names-primitive +1 / R5 experimental-flag -1 / R6 cross-vendor-proprietary -2; thresholds 3+ HIGH / 1-2 MEDIUM / ≤0 LOW). Enriches with **GitHub metadata** (owner/repo/stars/archived/last_commit/license SPDX/html_url via unauth API) + **trustworthiness signals** (operator-editable trusted-orgs whitelist + cross-citation count + activity-recent / permissive-license / high-stars / low-stars / archived-warning). Writes enriched candidate JSONs for Pass 2.
- **`agents/adapt-evaluator.md`** (~120 lines) — read-only Pass 2 sub-agent. Tool allowlist Read+Glob+Grep+Write; **write allowlist physically scoped to `_skill-watchlist/<source-slug>/<pattern-slug>.md` only** — adapt-don't-import architectural enforcement. Caller-supplies-inline-rubric pattern. Renders final HIGH/MEDIUM/LOW + adaptation_notes; writes watchlist entry only for HIGH+MEDIUM.
- **`skills/memory/scripts/watchlist_review.py`** (~350 lines) — review surface. Subcommands: `list` / `review` (interactive) / `promote <slugs>` / `dismiss <slugs>` / `defer <slugs> --until YYYY-MM-DD [--reason]`. **Promote = annotation-only**; **dismiss = archive** (never rm); **defer = snooze** with deferred_until + optional reason. Non-TTY stdin defaults all prompts to skip (never-silent-action contract).
- **Trusted-sources whitelist** at `<vault>/personal-private/trusted-sources.md` — operator-editable in Obsidian. Auto-seeded with 18 default orgs (anthropics / google / microsoft / hashicorp / openai / github / modelcontextprotocol / huggingface / pytorch / etc.). Used by `adapt_skills.py` for `+1 trustworthiness` flag.
- **Sub-command bodies** for all 5 new commands in `skills/memory/SKILL.md` (~500 lines net). At-a-glance + when-to-use tables grow 5→10 rows.
- **`install.sh` + `install.ps1` wiring** for `index_skills.py`: `--no-skill-index` / `-NoSkillIndex` escape hatch; runs after `install_python_deps`; silently skipped when `MEMORY_VAULT_PATH` unset.
- **Installer dispatch** for `adapt-evaluator` agent → `.claude/agents/adapt-evaluator.md` (Claude Code) + `.agent/skills/adapt-evaluator/SKILL.md` (Antigravity skill-wrap).
- **[ADR 0007 — MemoryVault Discovery + Mining](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0007-memoryvault-discovery.md)** — 7 locked design calls + 4 load-bearing assumptions with re-audit triggers.
- **`wiki/how-to/Use-The-Memory-Skill.md` discovery + mining section** (~200 lines) — worked invocations for all 5 new sub-commands + cache layouts + trustworthiness signal table + cadence + idle-hook integration.
- **27 new smoke install sub-tests** (bash + pwsh) across 5 test blocks: index-skills 7 / reflect-corpus 6 / discover-skills 6 / adapt-skills 7 / watchlist-review 7. Local stdlib `http.server` fixture for discover-skills lifecycle managed via `trap "kill -9 $PID; rm -rf $DSTMP" EXIT INT TERM`.

### Changed

- **`skills/memory/SKILL.md`** — at-a-glance + when-to-use tables grow 5→10 rows + 5 new sub-command bodies appended.
- **MemoryVault design doc** Document History row 11 captures the discovery + mining additive layer; cross-links ADR 0007.

### Internal

- **8 commits across plan #7b**: `76ec580` (task 1 index_skills + 7 smoke sub-tests) + `bf8ccbb` (task 2 reflect corpus + 6 smoke sub-tests) + `a911ce0` (task 3 discover_skills + 6 smoke sub-tests + idle-hook extension) + `8c9402c` (task 4 adapt_skills + adapt-evaluator + 7 smoke sub-tests) + `ead1f8d` (task 4 Windows CRLF fix per `[[wake-on-ci-pattern]]` scope expansion) + `5d9474c` (task 5 watchlist + 7 smoke sub-tests) + this v0.10.0 release commit (task 6 docs + ADR 0007 + CHANGELOG).
- **First Windows-specific CRLF bug** caught by CI on `8c9402c`: `_seed_trusted_sources` used `Path.write_text` which on Windows translates `\n` → `\r\n`; pwsh `(?m)^${org}$` regex didn't match CRLF lines. Fixed in `ead1f8d` by switching to `write_bytes` for LF-only output (matches established convention in `save.py` + `ideas_surface.py`).

## [v0.9.2] — 2026-05-20 — Local-only embeddings; BGE-large default (paired with agentm v2.4.1)

Patch — embedding-mode collapse + default model upgrade. **Drops the Voyage/Anthropic API embedding mode entirely; local `sentence-transformers` is now the only production mode.** Default model upgraded from `all-MiniLM-L6-v2` (384-d, MTEB English 56.3) to `BAAI/bge-large-en-v1.5` (1024-d, MTEB English 64.2). `EMBEDDING_DIM` bumped 384 → 1024. Triggered by [ROADMAP item #18](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md) (inserted mid-flight of plan #7a part 5 / seed-pass on 2026-05-20). Implemented as plan #18 (7 tasks across 8 toolkit commits). Paired with [`agentm v2.4.1`](https://github.com/alexherrero/agentm/releases/tag/v2.4.1) (doc-only on the harness side).

**Why this shape**: the primary operator is a Claude Ultra subscriber without a separate Anthropic / Voyage API key — the API path was unreachable for the toolkit's actual user. Dual-mode added surface area (mode resolution, env-var contract, dim-truncation, two test paths) without value for the personal-dev-env use case. Modern small-to-mid local models (BGE-large family, mxbai, nomic-embed) deliver near-SOTA MTEB results on desktop-class hardware (M-series + 64GB RAM) — the quality gap that motivated dual-mode is no longer load-bearing. Plan #18 was inserted mid-flight of plan #7a part 5 (seed-pass) because task 6 (validate via sample recalls) needs a worthwhile embedding model for validation signal to be meaningful; seed-pass resumes at task 6 with the new model after this release pair ships.

Decision rationale + 4 load-bearing assumptions with re-audit triggers in [ADR 0001's 2026-05-20 amendment](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0001-crickets-purpose.md#amendment-2026-05-20) (operator decision: amend rather than write new ADR 0007). The parent [MemoryVault design doc](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/designs/memoryvault.md) body was rewritten in-place across 12 substantive references to match the v0.9.2 state; Document History row 10 captures the rewrite scope.

### Added

- **`AGENT_TOOLKIT_EMBEDDING_MODEL` env var escape hatch** in `skills/memory/scripts/embed.py` — operators on low-spec hosts swap the BGE-large default for a smaller local model (e.g. `all-MiniLM-L6-v2`) without code changes. Still local-only — no API option ever.
- **`rebuild` subcommand** in `skills/memory/scripts/vec_index.py` — drops `entries` virtual table + `entry_meta` table + recreates at current `EMBEDDING_DIM`. Preserves the embedding queue file. Returns stats dict (`old_dim`, `new_dim`, `entries_dropped`, `queue_preserved`) or `{skipped: true, ...}` for graceful-skip. Exit 0 on success / exit 2 on graceful-skip (matches `size` pattern).
- **Dim-mismatch detection** in `vec_index.py`'s `_open_index()` — introspects existing virtual-table schema via `sqlite_master` + the new `_DIM_REGEX`; on mismatch prints `[vec_index] dim mismatch ... rebuild required: python3 vec_index.py rebuild --vault-path <path>` to stderr + closes conn + returns None (graceful-skip; never blocks the prompt). Same path fires from `drain_queue` so dim-mismatch surfaces there too.
- **`requirements.txt`** at repo root with the canonical Python dep list: `pyyaml>=6.0`, `sqlite-vec>=0.1.0`, `sentence-transformers>=2.0`. Comments document manual install + PEP 668 escape (`--break-system-packages`) + virtualenv pattern.
- **`--no-python-deps` / `-NoPythonDeps` flag** in `install.sh` + `install.ps1` — operator escape hatch for operators who manage Python deps via virtualenv / conda / system packages, or for CI to avoid the ~1.3GB sentence-transformers download per workflow run.
- **`install_python_deps()` function** in `install.sh` (+ `Install-PythonDeps` in `install.ps1`) — best-effort pip-install of `requirements.txt` after the customization install loop. Idempotent quick-path checks importability before attempting install. Non-fatal failure with operator-facing hint for PEP 668 systems.
- **Local-mode integration test** in `scripts/smoke-install-{bash.sh,pwsh.ps1}` guarded by `SKIP_LOCAL_MODE_INTEGRATION` env var (set by all 3 OS CI workflows to skip the BGE-large download). Operators with sentence-transformers installed run the test locally — invokes `embed.py --mode local`, asserts 1024-d JSON list, asserts all numeric values.
- **[ADR 0001's 2026-05-20 amendment](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0001-crickets-purpose.md#amendment-2026-05-20)** (43 new lines) — the v0.9.2 amendment block following the existing 2026-05-17 amendment shape. WHY narrowing + WHY NOT 4 alternatives + 5 operational changes + 4 load-bearing assumptions with re-audit triggers.

### Changed

- **`skills/memory/scripts/embed.py` rewrite** (109 ins / 115 del; 216 lines net). Removed: `_embed_api()` function + `_VOYAGE_ENDPOINT` / `_VOYAGE_MODEL` constants + dim-truncation logic + `_resolve_mode()`'s API branch + `MEMORY_USE_API_EMBEDDINGS` / `VOYAGE_API_KEY` / `ANTHROPIC_API_KEY` env var reads. Added: `_DEFAULT_LOCAL_MODEL = "BAAI/bge-large-en-v1.5"`, `EMBEDDING_DIM = 1024`, `_resolve_model()` with `AGENT_TOOLKIT_EMBEDDING_MODEL` env var override, informative `ValueError` for `"api"` invocations pointing at v0.9.2 + ADR amendment. CLI `--mode` choices reduced from `["api","local","stub"]` to `["local","stub"]`.
- **`skills/memory/scripts/vec_index.py`** (209 ins / 18 del). Schema dim 384 → 1024. `_open_index()` extended with dim-mismatch detection. `drain_queue()` switched to use `_open_index()` as gating probe so dim-mismatch surfaces from drain. New `rebuild_index()` function + `rebuild` CLI subcommand.
- **`skills/memory/scripts/recall.py` + `vec_index.py` CLI `--mode` choices** reduced from `["api","local","stub"]` to `["local","stub"]` (alignment with embed.py).
- **`install.sh` + `install.ps1`** install Python deps from `requirements.txt` by default (was: not installed at all; operators followed wiki docs to install manually). Same default-on-with-opt-out pattern as `--no-pre-push-hook`.
- **MemoryVault design doc body rewritten in-place** across 12 substantive references (overview, infrastructure, recall engine, dependencies, tech debt #2 + #9, security network surface, reliability, privacy opt-out, latency budgets, project management § DD #7, operations monitoring). Each rewritten section cross-links to ADR 0001's amendment. Document History row 10 captures the rewrite scope. Old dual-mode narrative preserved only in the pre-existing 2026-05-15 / 2026-05-16 / 2026-05-17 Document History rows as historical record.
- **`wiki/how-to/Use-The-Memory-Skill.md` updates** — Prereqs callout updated; § Embedding mode (was "Embedding modes" plural) rewritten with BGE-large + model swap escape hatch; troubleshooting entries for "embedding skipped" + "embedding unavailable" updated for local-only state; offline-capable recall paragraph updated.
- **Design doc parts files** (`write-primitives.md`, `recall-loop.md`) updated to match v0.9.2 state — references to `memory.use_api_embeddings` flag + Anthropic API replaced with single-mode local sentence-transformers narrative + ADR amendment cross-refs.

### Internal

- **Smoke install bash + pwsh tests updated**: all 5 install.sh + 5 install.ps1 invocations pass `--no-python-deps` / `-NoPythonDeps` so CI doesn't pay the ~1.3GB sentence-transformers download × 5 install scenarios × 3 OS per workflow run. Default-mode-resolution test changed from `'api'` expectation to `'local'`; new tests for v0.9.2 `--mode api` ValueError, `EMBEDDING_DIM=1024`, `AGENT_TOOLKIT_EMBEDDING_MODEL` escape hatch, stub-mode 1024-d output, `rebuild` subcommand happy + graceful-skip paths, `_DIM_REGEX` parse correctness.
- **8 commits across plan #18**: `222fea6` (embed.py refactor) + `6f0383b` + `ce5b110` (task-1 CI fixups) + `18941ae` + `fb83437` (task-2 vec_index.py + CI fixup) + `4a9c74a` (task-3 local-mode integration test) + `6633943` (task-4 install scripts) + `1b956f2` (task-5 ADR amendment) + this v0.9.2 release commit.

## [v0.9.0] — 2026-05-17 — Gemini-CLI host removal (host-scope reduction)

Minor — host-scope reduction. **Drops standalone Gemini CLI from supported hosts.** Keeps Claude Code + Antigravity (Gemini-in-Antigravity is a different surface — IDE-level integration, not standalone CLI). Triggered by [ROADMAP item #15](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md). Implemented as plan #15 (7 tasks across 5 toolkit commits + 1 harness commit). Paired with [`agentm v2.4.0`](https://github.com/alexherrero/agentm/releases/tag/v2.4.0) (doc-only on the harness side).

**Why this shape**: in practice the operator (one person) runs Claude Code + Antigravity. Standalone Gemini CLI was added defensively in v0.1.0 but never grew into the workflow; the Gemini usage that does happen lives inside Antigravity's IDE-level integration. Maintaining a third host destination, dispatch arms in `install.{sh,ps1}`, a third column in `Per-Host-Paths.md`, and three case-arms in every dispatch function was carrying maintenance cost without observed payoff. Plan #7a part 1 (memory skill scaffold, shipped 2026-05-16) was the first new skill that opted out of the three-host scope from day 1; v0.9.0 sweeps the rest of the toolkit to match.

Decision rationale + 4 load-bearing assumptions with re-audit triggers in the new [ADR 0006 — Gemini CLI host removal](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0006-gemini-cli-host-removal.md). ADRs 0001 + 0002 also get amendments (preserve original text + audit trail per the convention established by ADR 0004's 2026-05-16 external-review-handoff amendment).

### Added

- **[ADR 0006 — Gemini CLI host removal](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0006-gemini-cli-host-removal.md)** (1652 words) — full host-scope-reduction rationale with Context (4 forces), Decision (concrete sub-decisions with why-not-the-alternative for each), 5+/4- consequences, 4 load-bearing assumptions with re-audit triggers (Antigravity covers Gemini use cases; operators distinguish toolkit-managed vs unmanaged content; backup-not-hard-delete pattern; Gemini-CLI successor doesn't ship within ~6 months).
- **Legacy `.agents/skills/` + `.gemini/agents/` auto-cleanup primitive** in `install.sh` + `install.ps1`. Detects pre-existing toolkit-managed legacy entries from prior installs (matched against current manifest names); prompts operator with N default (`"Move to backup .agents/skills.crickets-bak.<ts>/ and remove from active install path? [y/N]"`); on opt-in moves (not hard-deletes) to timestamped backups per the pre-push hook backup convention. Non-interactive stdin auto-defaults to N with explanatory notice. New `--no-legacy-cleanup` / `-NoLegacyCleanup` flag suppresses for CI / scripted installs.
- **Validator `REMOVED_HOSTS` dict** in `scripts/validate-manifests.py` — keyed by removed host name → actionable error message that points operator at the v0.9.0 CHANGELOG and clarifies Antigravity (Gemini-in-IDE) stays supported. `require_supported_hosts()` surfaces removed-host errors before unknown-host errors for better next-step text.
- **Smoke install negative-existence assertions** (`scripts/smoke-install-{bash.sh,pwsh.ps1}`) — `.agents/` + `.gemini/` MUST NOT exist after install. Catches regressions if the gemini-cli dispatch arms ever come back. Two new automated tests: `--no-legacy-cleanup` flag suppression + validator-rejects-gemini-cli with v0.9.0 message (bypasses normal walk via importlib inline driver for in-isolation testing).
- **ADR amendments** preserving original ADR text + audit trail: [0001-crickets-purpose](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0001-crickets-purpose.md) (Amendment 2026-05-17) + [0002-evaluator-design](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0002-evaluator-design.md) (Amendment 2026-05-17). Same shape as ADR 0004's 2026-05-16 amendment for external-review-handoff.
- **MemoryVault parent design Document History row 8** noting the fleet-wide sweep is done — closes the row-7 thread opened 2026-05-16 ("until #15 sweeps them in one coordinated patch" → "v0.9.0 swept them"). Memory skill's architecture is unchanged; host-scope correction is operator-driven implementation detail, not a parent-design pivot.

### Changed

- **Every customization manifest** now ships with `supported_hosts: [claude-code, antigravity]`: 4 skills (`pii-scrubber`, `dependabot-fixer`, `ship-release`, `design`) + 1 agent (`evaluator`) + 1 bundle (`example-bundle`) + `AGENTS.md` schema example. Memory skill was already correct (shipped post-#15-decision in plan #7a part 1 task 1). Hooks (`kill-switch`, `steer`, `commit-on-stop`) were already `[claude-code]`-only — no change.
- **Validator `HOST_ENUM`** tightened: `{claude-code, antigravity, gemini-cli}` → `{claude-code, antigravity}`. Any manifest still listing `gemini-cli` errors with the v0.9.0 CHANGELOG-pointer message.
- **Installer dispatch arms** in `install_skill` / `install_hook` / `install_agent` (both `install.sh` + `install.ps1`) dropped the `gemini-cli` case-arms; collapsed `antigravity|gemini-cli` no-hook-surface arms to `antigravity` only.
- **Managed parents** (`MANAGED_PARENTS` / `$ManagedParents`) dropped `.agents/skills` + `.gemini/agents` — `--update` true-sync no longer touches those paths.
- **`Per-Host-Paths.md`** Quick Reference table dropped the 3rd column; revisit-triggers updated.
- **`Manifest-Schema.md`** allowed-values description tightened to `[claude-code, antigravity]`; 2 example manifests updated.
- **`Customization-Types.md`** Hosts column dropped gemini-cli across all rows; implementation-status table notes the v0.9.0 removal per row.
- **`Installer-CLI.md`** `--update` wipe-set updated; new `--no-legacy-cleanup` flag documented; sibling-tool collision note narrowed; legacy-cleanup [!NOTE] block added.
- **How-tos swept**: `Add-A-Skill.md` + `Add-A-Bundle.md` (manifest examples) + `Install-Into-Project.md` (`ls` verifications + `--update` narrative) + `Use-The-Design-Skill.md` ("three hosts" → "both supported hosts") + `Use-The-Evaluator.md` (rubric example).
- **Tutorial** `01-First-Customization.md` swept: manifest example + installer output + `ls` verifications + `--update` output + "what you learned" summary all aligned with 2-host scope.
- **MemoryVault parent design + 3 part files** (`memoryvault.md` + `write-primitives.md` + `recall-loop.md` + `reflection-and-recovery.md`) updated: manifest examples + "3 host destinations" → "2 host destinations" + cross-links to ROADMAP #15 + ADR 0006.
- **`README.md`** mermaid diagram dropped `.agents/skills/` box; "What's inside" version bumped `v0.8.1 → v0.9.0`; ROADMAP #15 + ADR 0006 cross-link added.
- **`skills/memory/SKILL.md` body** host-scope-rationale paragraph updated to past-tense post-#15 framing.
- **Wiki Sidebar + Home** gained ADR 0006 link in the Decisions section.

### Removed

- **Standalone Gemini CLI host support** entirely. The toolkit no longer dispatches to `.agents/skills/<name>/` (skills) or `.gemini/agents/<name>.md` (agents). Antigravity (Gemini-in-IDE) stays as a supported host — different surface than standalone CLI.
- **`.agents/skills/` + `.gemini/agents/` install destinations**. Pre-existing user installs with these dirs trigger the interactive legacy-cleanup-with-confirmation flow at next install time.

### Internal

- First **dogfood-driven host-scope reduction** in toolkit history. Pattern: surface the gap during real work (memory skill plan #7a part 1 task 1 chose 2-host scope; #15 added to ROADMAP same session); plan + execute the cross-cutting sweep across installer + manifests + tests + wiki + ADRs; ship as coordinated cross-repo MINOR release pair. 7-task plan, 5 toolkit commits (e1b477e + 5af1a59 + b216043 + 13109fa + 7a4162f) + 1 harness commit (the paired v2.4.0 doc-only update).
- **Defense-in-depth against regressions** active across multiple layers: validator's `REMOVED_HOSTS` dict catches manifest re-additions; smoke-install negative-existence assertions catch installer dispatch re-additions; `--no-legacy-cleanup` flag test catches flag-plumbing regressions; HOST_ENUM tightening catches enum re-admissions.
- **5 ADR amendments total** since toolkit shipped — pattern: append amendment at the bottom of the existing ADR rather than rewriting (per ADR 0004's 2026-05-16 amendment shape). This commit's amendments (0001 + 0002) bring the total to ADR 0001 amended × 1, ADR 0002 amended × 1, ADR 0004 amended × 1.
- **Operators with pre-v0.9.0 installs** see the interactive cleanup prompt at next install. Backup directories accumulate at `.agents/skills.crickets-bak.<ts>/` if operator opts in repeatedly across multiple install runs; GC recipe (`find .agents/ -name 'skills.crickets-bak.*' -mtime +30 -exec rm -rf {} \;`) documented in ADR 0006 + the Installer CLI reference. Auto-deletion of user filesystem is deliberately deferred — operators validate the backup before manually `rm -rf`ing.

## [v0.8.1] — 2026-05-16 — `/design` external-review-handoff option (dogfood-driven amendment)

Patch — additive only, no breaking changes. Adds an **external-review-handoff option** as an alternative to the block-by-block inline review in the `/design` skill. Dogfood-driven amendment from plan #6's first real design exercise (MemoryVault, design doc at `wiki/explanation/designs/memoryvault.md`): the 6-chunk inline walk of a ~7200-word design surfaced a real UX gap. Antigravity IDE's native inline-comment UI + Gemini-applies-comments pattern is dramatically better for review-style work on long content; the new option lets operators hand off to that workflow.

Three skill points get the option:

- `/design author` Step 5 (alternative to "Ready for review" inline transition)
- `/design author` Step 6 (alternative to per-section Approve/Revise/Skip walk on `Status: review` docs)
- `/design translate` Step 4 (alternative to inline Reshape commands on proposed part split)

Paired with [`agentm v2.3.1`](https://github.com/alexherrero/agentm/releases/tag/v2.3.1), which adds the same external-review-handoff option to the harness's `/plan` phase. Shared template, shared workflow shape, shared cleanup discipline across both repos.

### Mechanics

1. **Pre-handoff snapshot** at `<target-doc>.pre-handoff-<YYYYMMDDhhmmss>.md` — full copy of the doc as it stands when the operator picks "Hand off". Claude uses this on resume to diff against the externally-revised version.
2. **Transfer-context file** at `<project>/.harness/transfer/<doc-slug>-<YYYYMMDDhhmmss>.md` from the new template at `skills/design/templates/transfer-context.md`. Inlines: operator intent, recent decisions to honor, dev-flow conventions (since Antigravity-Gemini won't see device-global `~/.claude/CLAUDE.md`), doc-type-specific guardrails (10-section template lock, 11 QA sub-attrs N/A-with-rationale discipline, Status lifecycle, Visibility routing, Document History append-only), and explicit MUST-NOT rules to prevent silent drift.
3. **Handoff prompt** output to the operator with explicit Antigravity steps: open target doc + transfer-context, add inline comments via Antigravity's native UI, ask Gemini to apply per the transfer-context. Gemini revises + writes a change-summary log at `<target-doc>.diff.md`.
4. **Resume flow** (`/design author <slug> --resume-external-review` or natural "review complete on <slug>"): Claude reads revised doc + change-summary log, diffs against pre-handoff snapshot, surfaces findings (applied changes / frontmatter modifications / "Recent decisions" overrides / Gemini's adjacent-issue suggestions), asks Accept / Iterate / Discard. Accept archives snapshot + transfer-context to `.harness/transfer/_archive/`; Iterate regenerates transfer-context for another round; Discard restores from snapshot.

Decision rationale captured in the new [ADR 0004 amendment (2026-05-16)](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0004-design-skill.md#amendment--2026-05-16-v081-external-review-handoff-option) covering: rejection of the comment-marker-convention alternative (Antigravity has native inline-comment UI; inventing a marker convention adds friction); pre-handoff snapshot as the silent-drift safety net; multi-round iteration support via transfer-context regeneration. Includes 4 load-bearing assumptions with explicit re-audit triggers.

### Added

- **`skills/design/SKILL.md`** — new `#### External-review handoff (alternative to inline block-by-block review — added in v0.8.1)` section (~80 lines) under `/design author` documenting when the option is offered, what the skill does on handoff, the transfer-context generation, the handoff prompt output, and the resume flow with diff-on-resume + Accept/Iterate/Discard. `/design author` Step 5 + Step 6 + `/design translate` Step 4 each gain the new option as an alternative branch.
- **`skills/design/templates/transfer-context.md`** — NEW template (~110 lines) defining the handoff artifact's structural shape. Placeholders for `DOC_TITLE` / `DOC_TYPE` / `OPERATOR_INTENT_PARAGRAPH` / `RECENT_DECISIONS_BULLETS` / `INLINED-CONVENTIONS-dev-flow` / `INLINED-GUARDRAILS-FOR-{DOC_TYPE}` get filled at handoff time. Includes explicit MUST-NOT list (don't change frontmatter; don't add new sections; don't remove sections; don't modify pre-handoff Document History rows; don't revert "Recent decisions to honor" without explicit override comment; don't apply silent improvements beyond inline comments).
- **`wiki/how-to/Use-The-Design-Skill.md`** — new "Scenario 4 — External-review handoff (long-doc Antigravity-Gemini workflow, v0.8.1+)" walked end-to-end. Includes decision rubric (when to pick external vs. inline) + 5-step worked flow + trade-offs (context-switch overhead; silent-drift risk; artifacts to manage).
- **[ADR 0004 amendment (2026-05-16)](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0004-design-skill.md#amendment--2026-05-16-v081-external-review-handoff-option)** — captures the dogfood-driven framing, the decision + rationale + alternatives-rejected, 5+/5- consequences, 4 load-bearing assumptions with re-audit triggers (Gemini respects MUST-NOT list / regeneration prevents stale-context drift / snapshot+diff catches silent drift / operators tolerate context-switch overhead).

### Changed

- `README.md` "What's inside" — version bump `v0.8.0 → v0.8.1` (no row change; the new option is captured under the existing `/design` skill row).

### Internal

- Implementation lives entirely in skill body documentation + template content + how-to + ADR. No script changes, no manifest changes, no installer changes. The skill body documents what the agent does at handoff time; the agent reads the skill body + executes the flow.
- First dogfood-driven amendment to a shipped toolkit skill. The pattern: ship v1, dogfood on a real exercise, surface gaps, ship a small patch with the amendment captured in the ADR. Re-audit triggers in the amendment fire after the next 3-5 real external-review handoffs.

## [v0.8.0] — 2026-05-15 — `/design` skill: human-facing design pipeline → agent execution handoff

The first toolkit skill that ships its own custom multi-stage workflow. The `/design` skill walks a human through a precise 10-section design-doc template, gates on review approval, splits the approved design into structural parts, and generates one `PLAN.md` per part for the harness's `/work` + `/review` flow to execute. Published designs surface in `wiki/Home.md` as the canonical "Why we built X" entry point.

Three sub-commands:

- **`/design author <slug> [--visibility]`** — interactive section-by-section authoring of the 10-section template (Frontmatter + Context + Design + Alternatives Considered + Dependencies + Migrations + Tech Debt & Risks + Quality Attributes [11 sub-attrs] + Project management + Operations + Document History). Forces explicit N/A-with-rationale on each Quality Attribute sub-attr. Drives Status `draft → review → final`.
- **`/design translate <slug>`** — consumes a `Status: final` design doc and proposes a structural-part split (one part per Detailed Design subsection by default; grouping rule for tightly-coupled subsections; ~6-part soft cap with `--allow-large-design` override). Human approves via table with Reshape (merge/split/rename/reorder) sub-loop. Writes `<doc-dir>/parts/<part-slug>.md` per part with inherited frontmatter + part-specific fields (`parent_design`, `part_slug`, `dependencies`, `estimated_scope`).
- **`/design sequence <slug>`** — topologically sorts parts (Kahn's BFS with deterministic alphabetical tie-breaking; cycle detection) and generates one `PLAN.md` per part using the harness's existing `templates/PLAN.md` shape. First part activates at `<project>/.harness/PLAN.md`; subsequent parts queue at `<project>/.harness/designs/<doc-slug>/queued-plans/<part-slug>.PLAN.md`. Until v2.3.0 of the harness installs alongside, operators manually promote next queued plan via `mv`; v2.3.0's `/release` §1b auto-promotes.

Stage 5 (per-part execution) reuses the harness's existing `/work` + `/review` flow — no new execution primitives. The harness's deterministic gates + adversarial-reviewer + evaluator (v0.6.0) + kill-switch/steer/commit-on-stop (v0.7.0) all participate in the per-part execution loop.

Paired with [`agentm v2.3.0`](https://github.com/alexherrero/agentm/releases/tag/v2.3.0), which lands the harness-side `/release` §1b lifecycle hook (plan promotion + design `final → launched` Status transition + `wiki/Home.md` + `_Sidebar.md` surfacing for launched published designs) and `/setup` §7 scaffolding for the `wiki/explanation/designs/` landing dir.

Decision rationale captured in the new [ADR 0004 — Design skill design](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0004-design-skill.md): 7 locked design calls with rationale + "why not the alternative" + 5 positive / 5 negative consequences + 4 load-bearing assumptions with explicit re-audit triggers.

### Added

- **`skills/design/SKILL.md`** — full skill spec (692 lines) covering all three sub-commands with input contracts / step-by-step flows / tool allowlists / hard gates / worked examples / failure modes / anti-patterns. Manifest: `name: design`, `kind: skill`, `supported_hosts: [claude-code, antigravity, gemini-cli]`, `version: 0.1.0`, `install_scope: project`.
- **`skills/design/templates/design-doc.md`** — locked 10-section template (299 lines). User-provided structure codified verbatim 2026-05-14, with Alternatives Considered added same day. Each section has an italic prompt + HTML-comment guidance covering "what goes here" + "what N/A looks like" per the locked design call that Quality Attributes force explicit N/A.
- **`wiki/how-to/Use-The-Design-Skill.md`** — practical recipe (1741 words). At-a-glance table; when-to-reach-for-`/design`-vs-`/plan` decision table; three worked scenarios end-to-end (blank-slate feature design with Reshape demo; mid-execution revision with `--force-replace`; confidential design routing to `.harness/designs/`); Status lifecycle table; wiki integration explanation; manual-equivalents for Antigravity + Gemini CLI; 5 troubleshooting scenarios.
- **[ADR 0004 — Design skill design](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0004-design-skill.md)** — captures Context (4 forces driving the new primitive + 7 open design questions resolved 2026-05-14), Decision (7 locked design calls: hybrid decomposition; 10-section template locked verbatim; design doc as canonical wiki entry; Status lifecycle 4-state machine; Visibility routing; one-PLAN.md-per-part; skill ships in toolkit not harness; tool allowlist; mid-execution audit-trail via Document History), Consequences (5+/5-/4 load-bearing assumptions with re-audit triggers tied to plans #7 + #8 first-dogfood-surfacing-gaps + retrospective #12).
- **First real consumer of multi-stage skill workflow** in the toolkit. Earlier skills (`pii-scrubber`, `dependabot-fixer`, `ship-release`) ship a single workflow; the `evaluator` agent ships a single grading contract; the base hooks ship single-event triggers. `/design` is the first toolkit customization with multiple sub-commands that hand off between each other to drive a multi-stage workflow.

### Changed

- **README.md** — `What's inside (v0.7.0)` → `(v0.8.0)`; new row in the inventory table for the `design` skill with input → output one-liner noting the three sub-commands + the wiki surfacing trigger; new bullet in "Adding your own customizations" for Use-The-Design-Skill.
- **`wiki/Home.md`** — `🔧 Trying to do something specific?` section gains a Use-The-Design-Skill row; `💡 Architecture decisions` gains ADR 0004 row.
- **`wiki/_Sidebar.md`** — `🔧 How-to` + Decisions lists both extended with new entries.
- **`wiki/reference/Customization-Types.md`** — "When to use a skill vs. command vs. agent" table's skill row gains `design` + `pii-scrubber` as concrete example links.
- **`scripts/smoke-install-{bash,pwsh}.{sh,ps1}`** — expected-files list +6 entries (design/SKILL.md + design/templates/design-doc.md × 3 host destinations); idempotent re-run assertions extended.

### Internal

- **6-task implementation in `agentm/.harness/PLAN.md` plan #6** (crickets-side): task 1 (lock template + scaffold skill home); task 2 (`/design author` 192-line body); task 3 (`/design translate` 240-line body); task 4 (`/design sequence` 201-line body); task 6 (docs pass — how-to + ADR + cross-refs). Task 5 landed in the harness (`/release` §1b lifecycle hook). Task 7 is this release pair.
- **First real consumer of `kind: skill` with templates/ subdir.** Earlier skills don't ship templates because they don't author files at runtime. The design skill's `/design author` consumes `templates/design-doc.md` to seed new design docs. The skill dir's `cp_managed_dir` install handles the templates/ subdir transparently — no installer changes needed.
- **All five toolkit gates green on every commit** in the v0.7.0..v0.8.0 range. Soft length warnings on the new how-to (1741w) and ADR (2266w) explicitly accepted per the codified dev-flow convention from `~/.claude/CLAUDE.md`: comprehensive content (three worked scenarios + Quality Attributes guidance + Operations guidance + troubleshooting) is load-bearing for design-skill discoverability; splitting would fragment the reader experience.

[v0.8.0]: https://github.com/alexherrero/crickets/releases/tag/v0.8.0

## [v0.7.0] — 2026-05-14 — Three base operator-control hooks + first-class `kind: hook` installer support

Three new hook customizations for long-running Claude Code sessions, lifted from the cwc-long-running-agents pattern:

- **`kill-switch`** — `touch .harness/STOP` to halt all tool calls; `rm` to resume. PreToolUse hook, exit 2 + halt-message stderr.
- **`steer`** — write `.harness/STEER.md` with a "do it this way instead" instruction; next tool call picks it up (contents → agent context); file renamed to `STEER.consumed-<iso-ts>.md` for audit trail.
- **`commit-on-stop`** — Stop-event hook; if working tree is dirty at turn-end, creates `auto-save/<iso-ts>` branch and commits the work there. Returns HEAD to original branch with a clean tree. Never modifies the current branch; never pushes to remote.

Paired with [`agentm v2.2.0`](https://github.com/alexherrero/agentm/releases/tag/v2.2.0), which adds new optional sections to `/work` and `/release` phase specs documenting how to dispatch the three hooks alongside the existing phase workflow. The harness still works standalone without the toolkit — the new sections graceful-skip when crickets is absent.

**First real consumer of `kind: hook`** in the toolkit's manifest schema. This release lands first-class `kind: hook` installer support: per-host paths dispatch (`.claude/hooks/<name>.{sh,ps1}`) **plus** idempotent deep-merge of each hook's `settings-fragment-{bash,pwsh}.json` into `.claude/settings.json` via a new Python helper. Same dogfood pattern as `kind: agent` in v0.6.0 — building real hooks forces the installer + validator + per-host paths machinery end-to-end.

Decision rationale captured in the new [ADR 0003 — base operator-control hooks](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0003-base-operator-hooks.md): per-repo file locations (device-scope deferred); STEER.md audit-trail rename (not delete); safety-branch (not current-branch) for commit-on-stop; Stop-event-only triggers for v0.7.0 (N-consecutive-errors deferred); alphabetical-install-order hook ordering (kill-switch fires before steer in PreToolUse — load-bearing invariant); claude-code-only host scope (Antigravity + Gemini CLI documented as manual equivalents); Python helper for settings.json merge (not jq — reuses python3 prereq).

### Added

- **`hooks/kill-switch/`** — operator emergency halt. PreToolUse, matcher `.*`, timeout 5s. Manifest + bash + pwsh scripts + bash/pwsh settings fragments. `touch .harness/STOP` → exit 2 + halt-message stderr (Claude Code surfaces to agent + blocks tool call). `rm` to resume.
- **`hooks/steer/`** — mid-run redirect. PreToolUse, matcher `.*`, timeout 5s. Writes `.harness/STEER.md` → contents on stdout (Claude Code injects into next tool call's context) + file renamed to `.harness/STEER.consumed-<iso-ts>.md` for audit trail.
- **`hooks/commit-on-stop/`** — safety-branch commit at session end. Stop event, matcher `.*`, timeout 30s. Dirty tree → stash → create `auto-save/<iso-ts>` branch → switch + pop + commit with greppable message `auto-save: stop at <ts> on branch <original-branch>` → switch back to original branch with clean tree. Identity scoped to single commit via `git -c user.email=commit-on-stop@crickets.local`; gpg signing disabled.
- **First-class `kind: hook` installer dispatch** across both installers (`install.sh` + `install.ps1`). New `--hook` / `-Hook` flag (mirrors `--skill` / `--agent`); `install_hook` / `Install-Hook` helper dispatches per host (claude-code only in v0.7.0; antigravity + gemini-cli warn-and-skip — no first-class hook surface today); `install_standalone_hooks` / `Install-StandaloneHooks` walker iterates `hooks/*/hook.md`; bundle loops extended to dispatch inner-bundle hooks from `bundles/<b>/hooks/<n>/hook.md`.
- **`scripts/merge-settings-fragment.py`** — new Python helper for idempotent deep-merge of hook settings fragments into target `.claude/settings.json`. Reads existing settings.json (or `{}` if missing); for each `hooks.<event>` in the fragment, dedups on the first inner hook's `command` field; appends only new entries to the existing array; preserves all other top-level keys (user's `permissions`, third-party hooks, etc.). Uses `Path.as_posix()` for cross-platform output normalization. Idempotent on re-run.
- **MANAGED_PARENTS extended** with `.claude/hooks` in both bash + pwsh installers for true-sync `--update` orphan cleanup. **`.claude/settings.json` is NOT a managed parent** — it's user-state-merged; the toolkit re-merges its fragments idempotently each install run.
- **`validate-manifests.py` knows hooks** — new `validate_standalone_hook` walker; `hooks/*/hook.md` discovery; bundle `check_contents` handles `kind=hook` (resolves to `bundle_dir/hooks/<n>/hook.md`); for claude-code in `supported_hosts`, asserts four companion files exist (`<name>.sh` + `<name>.ps1` + `settings-fragment-bash.json` + `settings-fragment-pwsh.json`); summary line counts hooks.
- **[ADR 0003 — base operator-control hooks](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0003-base-operator-hooks.md)** — captures Context (3 forces driving the new primitives + 7 open design questions resolved), Decision (7 locked design calls), Consequences (5 positive + 6 negative + 5 load-bearing assumptions with explicit re-audit triggers).
- **[How to use the base hooks](https://github.com/alexherrero/crickets/blob/main/wiki/how-to/Use-The-Base-Hooks.md)** — practical recipe with at-a-glance reference table, when-to-reach-for-each decision table, three worked scenarios (halt runaway loop, mid-run redirect, crash recovery with 3 recovery options), hook-ordering invariant, file conventions, cleanup patterns, manual equivalents for Antigravity + Gemini CLI, and a 5-section troubleshooting guide.
- **`--hook <name>` / `-Hook <name>` flag** for selective install. Mirrors the existing `--skill` / `--agent` flags. Documented in the [Installer-CLI reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Installer-CLI.md).
- **`smoke-install-{bash,pwsh}.{sh,ps1}` + `check-integrity-{bash,pwsh}.{sh,ps1}`** extended for the hook kind: expected-files list gains 4 new destinations (`.claude/hooks/{kill-switch,steer,commit-on-stop}.{sh,ps1}` + `.claude/settings.json`); idempotent re-run + `--update` assertions extended (re-running settings.json merge reports "kept (fragment entries already present)", treating "merged on re-run" as a regression); new integrity sections validate `.claude/hooks/` shape (only `.sh`/`.ps1` files; `.sh` scripts executable on POSIX) and `.claude/settings.json` parses + hooks shape valid.

### Changed

- **[Customization Types reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Customization-Types.md)** — `hook` row in the implementation-status table flipped from ⚠️ "not yet supported" to ✅ "v0.7.0 supported (claude-code only)"; bundle row notes `skill`, `agent`, and `hook` kinds are all wired inside bundles as of v0.7.0; "What it is" column links to the new how-to with the three concrete examples.
- **[Installer CLI reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Installer-CLI.md)** — Quick Reference + Synopsis + Flags table gain `--hook` / `-Hook`; Installed-paths table gains 3 new rows (`.claude/hooks/<name>.sh` POSIX + `.claude/hooks/<name>.ps1` Windows + `.claude/settings.json` idempotent-merge entry); `--update` parent list extended with `.claude/hooks`; sibling-tool collision note updated for hooks.
- **[Home](https://github.com/alexherrero/crickets/blob/main/wiki/Home.md) + [Sidebar](https://github.com/alexherrero/crickets/blob/main/wiki/_Sidebar.md)** — new how-to row + ADR 0003 row in their reader-intent sections.
- **README "What's inside" table** — bumped from `v0.6.0` framing to `v0.7.0`; three new hook rows added with one-line descriptions of trigger + effect; "Adding your own customizations" list gains Use-The-Base-Hooks link.

### Internal

- **4-task implementation in `agentm/.harness/PLAN.md`** plan #4 (crickets-side): task 1 (kind=hook installer + settings.json merge with fixture); task 2 (author the three hooks, replacing the fixture); task 4 (documentation pass — how-to + ADR + cross-refs). Task 3 landed in the harness (the `/work` + `/release` graceful-skip sections + `EXTERNAL_CUSTOMIZATIONS` extension).
- **Two real cross-platform bugs surfaced + fixed via CI** during plan #4: (1) commit b9d8c79 passed Linux + Mac but failed Windows because Python's `Path.__str__()` returns native-separator paths on Windows (`.claude\settings.json` not `.claude/settings.json`); fix in commit 8918967 uses `Path.as_posix()` for display output. (2) PII guardrail caught `commit-on-stop@crickets.local` synthetic commit identity as a false-positive email match in commit b9d8c79's pre-push; added `@crickets\.local` to both `scripts/check-no-pii.sh` allowlist patterns and `.gitleaks.toml` allowlist regexes. Third such cross-platform-byte-difference fix in project history (after LC_ALL=C sort + CRLF/sha256sum from plan #1).
- **commit-on-stop scope reduction from plan**: ships **Stop event only** for v0.7.0; the N-consecutive-errors trigger (`PostToolUse` with state-tracking + `COMMIT_ON_STOP_ERROR_THRESHOLD` env var) is deferred to a follow-up plan. Stop covers the load-bearing case (session end with uncommitted work); the N-errors variant requires hook-side state machinery that's significantly more complex.
- **First real consumer of `kind: hook`** in the toolkit's manifest schema. Future hook customizations drop into the same installer + validator + per-host paths machinery; the hook kind is no longer a future-proofing stub.

[v0.7.0]: https://github.com/alexherrero/crickets/releases/tag/v0.7.0

## [v0.6.0] — 2026-05-13 — `evaluator` agent + first-class `kind: agent` installer support

First customization beyond skills: the `evaluator` sub-agent — a read-only fresh-context grader that takes an artifact reference and an explicit rubric, returns a structured `PASS` / `NEEDS_WORK` verdict with per-rubric-item reasoning. Tool allowlist is `[Read, Glob, Grep]` only (no `Bash`, no `Write`, no `Edit`) so the "fresh context that never saw the build" framing is structurally protected.

Paired with [`agentm v2.1.0`](https://github.com/alexherrero/agentm/releases/tag/v2.1.0), which adds a new optional §3b "evaluator augmentation" section to `/review` documenting how to dispatch the evaluator alongside the existing `adversarial-reviewer`. The two are complementary, not competing: adversarial finds defects ("the code contains bugs"); evaluator grades against an explicit rubric ("did this satisfy claims 1–5?"). The harness still works standalone without the toolkit installed — the §3b section graceful-skips when `crickets` is absent.

Decision rationale captured in the new [ADR 0002 — evaluator design](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0002-evaluator-design.md): standalone agent in the toolkit (not a harness primitive); tight read-only allowlist (no `Bash` → caller pre-runs tests and supplies output as artifact); caller-supplied inline rubric (no `rubric.md` file convention); coexist with adversarial-reviewer rather than replacing; structured PASS/NEEDS_WORK output mirroring adversarial-reviewer's structured-output convention.

### Added

- **`agents/evaluator.md`** — the fresh-context grader. Frontmatter (`kind: agent`, `supported_hosts: [claude-code, antigravity, gemini-cli]`, `version: 0.1.0`, `install_scope: either`); body with Purpose / When to reach / Tool allowlist + rationale / Input contract (ARTIFACT + RUBRIC labeled sections) / Output contract (PASS or NEEDS_WORK header + per-rubric-item PASS/FAIL line + Verdict line) / Workflow (5 steps) / 4 Failure modes with literal output templates (input contract violation / artifact unreadable / rubric item unfalsifiable / rubric item out of scope) / 7 Anti-patterns / 2 Worked examples (one PASS with 4-item rubric against parser code/tests/spec, one NEEDS_WORK finding scope creep + untested code path).
- **First-class `kind: agent` installer dispatch** across both installers (`install.sh` + `install.ps1`). New `--agent` / `-Agent` flag mirrors `--skill`; new `install_agent` / `Install-Agent` helper dispatches per the locked per-host paths table — claude-code → `.claude/agents/<name>.md` (single file via `cp_managed`); antigravity → `.agent/skills/<name>/SKILL.md` (sub-agent-as-skill wrap); gemini-cli → `.gemini/agents/<name>.md` (single file). New `install_standalone_agents` / `Install-StandaloneAgents` walker iterates `agents/*.md`. Bundle loops extended to dispatch inner-bundle agents from `bundles/<bundle>/agents/*.md`.
- **`MANAGED_PARENTS` extended** with `.claude/agents` + `.gemini/agents` (symmetric with the harness's managed-parents list) for true-sync `--update` orphan cleanup of toolkit-managed agent files. Sibling-tool collision note added to [Installer-CLI reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Installer-CLI.md): when both repos are installed into the same target, the later-run installer's `--update` wins the parent dir per the existing pattern (which already applied to `.claude/skills/` etc.).
- **`validate-manifests.py` knows agents** — new `validate_standalone_agent` checker; `agents/*.md` walk in main; bundle `check_contents` handles `kind: agent` (resolves to `bundle_dir/agents/<name>.md`); inner-bundle agents validated with relaxed schema (name + description only); summary line counts agents alongside bundles and skills.
- **[ADR 0002 — evaluator design](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0002-evaluator-design.md)** — captures Context (3 forces driving the new primitive), Decision (5 locked design calls), Consequences (5 positive + 4 negative + 3 load-bearing assumptions with re-audit triggers).
- **[How to use the evaluator](https://github.com/alexherrero/crickets/blob/main/wiki/how-to/Use-The-Evaluator.md)** — practical recipe with the dispatch prompt template, three worked rubrics (code-change for `/review`, docs-rubric for `/release`, release-readiness pre-tag check), output interpretation, four common failure modes with symptoms + fixes, and the tool-allowlist rationale.
- **`--agent <name>` / `-Agent <name>` flag** for selective install. Mirrors the existing `--skill` / `-Skill` flag. Documented in [Installer-CLI reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Installer-CLI.md).
- **`scripts/smoke-install-{bash,pwsh}.{sh,ps1}` + `check-integrity-{bash,pwsh}.{sh,ps1}`** extended for the agent kind: expected-files list gains 3 new destinations (`.claude/agents/evaluator.md`, `.agent/skills/evaluator/SKILL.md`, `.gemini/agents/evaluator.md`); new integrity section validates agent `.md` frontmatter; new integrity section catches stray subdirs / non-`.md` files under agent managed parents; idempotent re-run + `--update` assertions extended to the agent path.

### Changed

- **[Customization Types reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Customization-Types.md)** — `agent` row in the implementation-status table flipped from ⚠️ "not yet supported" to ✅ "v0.6.0 supported"; bundle row notes both `skill` and `agent` kinds are now wired inside bundles. "When to use" table's evaluator example now links to the how-to.
- **[Installer CLI reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Installer-CLI.md)** — Quick Reference + Synopsis + Flags table gain `--agent` / `-Agent`; Installed-paths table gains rows for `.claude/agents/<name>.md` + `.gemini/agents/<name>.md`; sibling-tool collision note added.
- **[Home](https://github.com/alexherrero/crickets/blob/main/wiki/Home.md) + [Sidebar](https://github.com/alexherrero/crickets/blob/main/wiki/_Sidebar.md)** — new how-to and ADR 0002 rows in their reader-intent sections.
- **README "What's inside" table** — bumped from `v0.1.0` framing to `v0.6.0`; new evaluator agent row added with one-line description noting its role at `/review` + feed to design skill + quality-gates bundle.

### Internal

- **4-task implementation in `agentm/.harness/PLAN.md`** plan #3 (crickets-side): task 1 (installer + validator + smoke/integrity scripts for `kind: agent`); task 2 (author the evaluator body, replacing the task-1 fixture); task 4 (documentation pass — how-to + ADR + cross-refs). Task 3 landed in the harness (the `/review` §3b section + `EXTERNAL_SKILLS` → `EXTERNAL_CUSTOMIZATIONS` rename).
- **First real consumer of `kind: agent`** in the toolkit's manifest schema. Future agent customizations drop into the same installer + validator + per-host paths machinery; the agent kind is no longer a future-proofing stub.

[v0.6.0]: https://github.com/alexherrero/crickets/releases/tag/v0.6.0

## [v0.5.0] — 2026-05-12 — Initial public release: sibling toolkit for `agentm`

First public release of `crickets` — a sibling repo to [`agentm`](https://github.com/alexherrero/agentm) holding personal agent customizations (skills, sub-agents, hooks, MCP servers, slash commands, bundles, etc.) that ride on top of the harness's phase-gated workflow. Released alongside [`agentm v2.0.0`](https://github.com/alexherrero/agentm/releases/tag/v2.0.0), which migrated `dependabot-fixer` + `ship-release` here as part of the split. Version chosen as `v0.5.0` (rather than a fresh `v0.1.0`) because the first cut already ships substantial scope — full Diátaxis wiki, three skills, an example bundle, three-OS CI matrix, byte-identical shared install plumbing, and three-layer PII guardrails — so `v0.5.0` signals the toolkit's actual maturity at launch.

The split decision and its rationale are captured in two parallel ADRs: [crickets ADR 0001](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0001-crickets-purpose.md) (this repo, purpose + scope framing) and [agentm ADR 0006](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0006-crickets-split.md) (harness side, parity-tax + harness-identity rationale).

### Added

- **Repo scaffold** — 12 customization-type subdirs (`skills/`, `commands/`, `agents/`, `hooks/`, `mcp-servers/`, `bundles/`, `status-line/`, `output-styles/`, `workflows/`, `rules/`, `snippets/`, `settings-fragments/`) covering every primitive the three supported hosts know about. Plus `lib/install/` (shared install plumbing), `scripts/` (validators + CI helpers + PII detector), `templates/hooks/` (pre-push hook template), `wiki/` (Diátaxis-shaped dogfood docs), and `.github/workflows/`. Top-level files: `LICENSE` (MIT), `.gitignore`, `.gitleaks.toml` (gitleaks config with allowlist for the `alexherrero` public handle + RFC 2606 reserved domains + NANP fiction phone numbers + placeholder strings), `README.md`, `AGENTS.md` (universal entry), `CLAUDE.md` (Claude Code overlay), `CONTRIBUTING.md` (full PII guardrails section + local-gate commands + override protocol), and this `CHANGELOG.md`.
- **Working installers** — `install.sh` (POSIX bash) and `install.ps1` (PowerShell 7+). Flags: `--bundle <name>`, `--skill <name>`, `--all` (default), `--update`, `--no-pre-push-hook`, `--help`. Both source the shared install primitives from `lib/install/` (byte-identical with `agentm/lib/install/`). Discovery walks `bundles/*/bundle.md` + `skills/*/SKILL.md`, reads each manifest's YAML frontmatter, dispatches each primitive to the right host-specific path per the [Per-Host Paths reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Per-Host-Paths.md). `--update` mode runs `sync_managed_parents` (true-sync wipe-and-recreate) on `.claude/skills/`, `.agent/skills/`, `.agents/skills/`. Pre-push hook installation is on by default; `--no-pre-push-hook` opts out. Backs up existing non-matching `.git/hooks/pre-push` to `.crickets-bak.<timestamp>` rather than clobbering.
- **Manifest schema + validator** — every customization carries YAML frontmatter with required fields `name`, `description`, `kind`, `supported_hosts`, `version`; optional fields `install_scope` (`user` | `project` | `either`) and `deprecated`. Bundles additionally require `contents`. The `kind` enum has 12 entries covering every customization type. `scripts/validate-manifests.py` walks the repo, parses each manifest, asserts schema conformance + that bundle `contents` resolve inside the bundle dir, exits non-zero with `file:line` on first failure. See the [Manifest Schema reference](https://github.com/alexherrero/crickets/blob/main/wiki/reference/Manifest-Schema.md).
- **PII guardrails (three enforcement layers, since this repo is public).**
  - **`scripts/check-no-pii.sh`** — bash regex scanner catching email addresses, personal paths (`/Users/<name>/`, `C:\Users\<name>\`, `/home/<name>/`), API key shapes (OpenAI, GitHub, GitLab, AWS), and US phone numbers. Configurable allowlist for known-safe matches (e.g. the public `alexherrero` handle). Modes: `--all` (whole tree), `--staged` (staged diff), `--diff <range>` (pre-push range). Exits 0 on clean, 1 with `file:line` per finding.
  - **`skills/pii-scrubber/SKILL.md`** — agent-facing interactive skill. Scans the current diff before commit, presents each finding as `file:line: <kind> match: <redacted-snippet>`, proposes redactions, offers remediate/allowlist/override choices, logs every override with reason to `.harness/.pii-overrides.log`. Loops until clean. Hard rule: cannot silently bypass findings.
  - **`templates/hooks/pre-push`** — mandatory enforcer. Runs the detector against every push range; blocks non-zero. Installed into target projects' `.git/hooks/pre-push` by `install.sh` unless `--no-pre-push-hook` is passed. Multi-path lookup for the detector script (`$AGENT_TOOLKIT_PATH` env → `~/Antigravity/crickets/` → `~/dev/crickets/` → sibling-of-current-repo) so the hook works regardless of where the toolkit lives.
  - **CI gate** (defense in depth) — `tests-linux.yml` runs both `check-no-pii.sh` and the official `gitleaks/gitleaks-action@v2` on every push.
- **Three skills shipping in v0.5.0.**
  - **`pii-scrubber`** (new in this release) — see above.
  - **`dependabot-fixer`** — migrated from `agentm` v1.x. Interactive harness for Dependabot PR migration recipes; reads per-project `.harness/known-migrations.md`. Carried over as `version: 1.0.0` since it's a mature skill, not a fresh one.
  - **`ship-release`** — migrated from `agentm` v1.x. Auto-sized semver releases from conventional commits; writes CHANGELOG, tags, pushes, creates the GitHub release. Aborts on dirty tree, unpushed default branch, or existing tag. Carried over as `version: 1.0.0`.
- **`example-bundle/`** — dogfood reference content showing how to package a multi-primitive customization (bundle.md + inner `skills/example-skill/SKILL.md`). Explicitly framed as "safe to delete in your fork" to prevent rot.
- **Shared install plumbing** — `lib/install/bash/primitives.sh` (6 functions: `ensure_boundary_src`, `cp_user`, `cp_managed`, `cp_user_walk`, `cp_managed_dir`, `sync_managed_parents`), `lib/install/pwsh/primitives.ps1` (8 functions; pwsh equivalents + `Copy-AdapterFiles`/`Copy-AdapterDirs` for the harness-side use case), `lib/install/CONTRACT.md` (caller-contract docs: `UPDATE_MODE`/`$Update` flag + `BOUNDARY_ROOTS`/`$BoundaryRoots` array + six behavior invariants), `lib/install/.checksums.txt` (SHA-256 manifest). Byte-identical with `agentm/lib/install/` — cross-repo updates flow through `agentm/scripts/sync-lib.sh`, and `scripts/check-lib-parity.sh` in each repo asserts self-consistency in CI.
- **Cross-platform CI** — three per-OS workflows (`tests-linux.yml`, `tests-mac.yml`, `tests-windows.yml`) running install-smoke + validate-manifests + check-syntax + check-lib-parity + check-no-pii + gitleaks on every push. Plus `wiki-sync.yml` mirroring the harness's wiki-publish pattern. The cross-platform debugging surfaced four real cross-platform issues (case-insensitive `sort` on Mac, `$host` collision in PowerShell, missing `shasum` in Git Bash on Windows, autocrlf + binary-mode SHA-256 difference) — all fixed before this release tag.
- **Diátaxis-shaped wiki** — 12 pages covering all four modes. Tutorials (1): hello-world walkthrough of a first customization. How-to (3): install into project, add a skill, add a bundle. Reference (4): manifest schema, customization types (12-kind subdir/host mapping), per-host paths (the full dispatch table), installer CLI (flag reference + exit codes + pre-push hook behavior). Explanation (1): purpose and scope, with sibling-repo ASCII diagram. Decisions (1): [ADR 0001 — crickets purpose](https://github.com/alexherrero/crickets/blob/main/wiki/explanation/decisions/0001-crickets-purpose.md), capturing the sibling-repo decision from the toolkit's side. `scripts/check-wiki.py` (copied from agentm) enforces the 11-rule Diátaxis lint in CI.
- **`no-Co-Authored-By` convention** documented in `AGENTS.md` + `CLAUDE.md`. Host-agnostic rule: agents do not append `Co-Authored-By:` trailers naming the model or host. Mirrors the harness's convention.

### Internal

- **7-task plan (#1)** tracked in `agentm/.harness/PLAN.md`: task 1 (repo scaffold + PII guardrails), task 2 (shared `lib/install/` + byte-identity gate), task 3 (real installers + manifest validator + per-host paths), task 4 (CI matrix + PII gate), task 5 (migrate `dependabot-fixer` + `ship-release` from harness), task 6 (full Diátaxis wiki + cross-repo ADRs), task 7 (this release pair).
- **End-to-end dogfooding** — the pre-push hook ran on every crickets push during development and reported clean; the byte-identity flow was exercised across nine commits between the two repos; manifest validator + check-syntax + check-lib-parity gates all green from task 4 onward.

[v0.5.0]: https://github.com/alexherrero/crickets/releases/tag/v0.5.0
