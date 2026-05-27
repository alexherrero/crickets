# ADR 0012 — Device-wide harness install + vault-backed state by default

> [!NOTE]
> Status: accepted
> Date: 2026-05-26

## Context

The harness started as a phase-gated workflow for a single repo: `bash install.sh <target-project>` drops files into `<project>/.claude/`; gitignored `.harness/` keeps state next to code; per-project memory recall via `MEMORY_VAULT_PATH` env var. This shape worked for one developer with one project. It strains the operator's actual usage:

- Multi-project work: every repo gets its own `.harness/` + `.claude/` + (post-Antigravity-2.0) `.agents/` clutter.
- Cross-project queries ("what was I working on yesterday across all my projects?") require opening each project individually.
- Cross-device continuity doesn't exist — the phone reads the vault but not the per-project `.harness/PLAN.md`.
- Onboarding new repos: re-run `install.sh` per project; easy to forget; install drift between projects.
- The agent's tools (skills, hooks, slash commands) belong to the OPERATOR, not to each project. Today's per-project install model says otherwise.

Plan #18 (V4 architecture design pass) reframed the harness as the operator's **agentic OS** — installed device-wide once, with project-specific state living in the vault. The companion HLD [`device-wide-architecture.md`](../designs/device-wide-architecture.md) ships the full design. This ADR captures the load-bearing decisions + their trade-offs.

**Open questions the decision resolves:**

- Per-repo vs device-wide install — which is default?
- Where does harness state live when not in `<project>/.harness/`?
- How does the agent find the right project given an arbitrary cwd?
- How does a fresh repo get configured? Separate setup script vs implicit auto-detect?
- Does the harness install bundle its sibling toolkit, or are they independent?

## Decision

### 1. Install device-wide by default (`--scope user`)

`bash install.sh --scope user` becomes the default. Drops customizations into `~/.claude/` (skills, agents, hooks, commands, settings.json merge). `bash install.sh --scope project <target>` retained as opt-in for OSS contributors, sandbox dev, special team configurations.

**Why not stay per-project default?** Per-project install model creates clutter in every repo, install drift across projects, and treats the agent's tools as project-scoped when they're actually operator-scoped. Device-wide reflects the operator's actual usage.

**Why not deprecate per-project entirely?** Opt-in remains valuable for: developers who don't want device-wide commitment yet; OSS contributors testing changes; teams shipping their own AGENTS.md + skills that should override device-wide defaults.

### 2. State lives in the vault per [[vault-as-canonical-context]]

`<project>/.harness/<file>` → `<vault>/projects/<slug>/_harness/<file>`. Per-project harness state (PLAN.md, progress.md, ROADMAP.md, FOLLOWUPS.md, features.json, designs/, archived plans) moves to the operator's GDrive-synced Obsidian vault. Multi-device access via Obsidian; cross-project queries are trivial against a centralized store.

**Why `_harness/` subdirectory?** Matches the vault's existing prefix-underscore convention (`_always-load/`, `_meta/`, `_idea-incubator/`); self-documenting (anyone scanning a project dir knows immediately what `_harness/` is); disambiguates from operator-authored content (`_index.md`, `decisions/`, `conventions/`).

**Why not keep state in `<project>/.harness/`?** Defeats cross-project queries; doesn't sync across devices; clutters every repo with gitignored content.

**Why not a database?** Vault stays markdown-canonical + filesystem-only per [[vault-as-canonical-context]]. V5 builds an INDEX on top (vector + graph), but markdown remains source of truth. Reasons: human-readable for operator; scriptable; GDrive-syncable; survives any tooling change.

**One carve-out:** `<project>/.harness/.evidence-reads` (evidence-tracker session-state cache) stays per-cwd. Runtime-ephemeral; not state-of-record; vault-syncing it would create write storms.

### 3. Project resolution defaults to cwd via a future-ready resolver chain

`resolve_project(context) → Optional[Resolution]` returns `{slug, type, vault_path}`. v1 chain (fallback order): explicit override → AGENTS.md frontmatter `vault_slug:` → `.project-slug` file → legacy `.harness/project.json` (transition) → cwd basename inference against `<vault>/projects/<slug>/` → git remote origin basename → `None`. v1 always returns `type: "coding"`.

**Future-ready abstraction:** the chain is composable. V5+ adds resolvers for non-cwd anchors (Obsidian-file-anchored, conversation-anchored, explicit-operator-selected) without breaking v1 code.

**Why not just cwd?** Operator needs explicit override paths (AGENTS.md frontmatter, `.project-slug` file) for cases where cwd basename doesn't match desired vault slug. Future non-coding "projects" (house repairs, vacation planning) don't have a cwd anchor — the resolver chain handles them by plugging in new resolvers.

**Why not require explicit registration?** Friction at every repo entry. The cwd-default + first-run auto-detect bootstrap covers the common case; explicit override handles edge cases.

### 4. Auto-detect bootstrap on first session — no separate setup script

When `resolve_project()` returns `None` for an interactive session, a SessionStart hook runs auto-detect: scans cwd for project signals (wiki/, CHANGELOG.md, .env files, tests/, etc.), proposes a configuration (default-all-enabled with per-skill rationale), operator approves or edits, agent writes `<vault>/projects/<slug>/_index.md` + `_harness/features.json` + offers to add `vault_slug:` line to AGENTS.md. Subsequent sessions resolve via the new registration.

**Why not a separate `setup-project.sh` script?** Friction; easy to forget; redundant given that the agent CAN detect + propose. Implicit bootstrap on first session removes the step.

**Why default-all-enabled?** Per operator preference: minimal-defaults + opt-in misses skills that should obviously be there; rationale-surfaced default-all-enabled lets operator opt out of specific skills if needed but doesn't accidentally suppress useful ones.

### 5. agentm bundles crickets in its one-liner; crickets stands alone

`curl -fsSL .../agentm/install.sh | bash` installs both repos (clones crickets if missing). `curl -fsSL .../crickets/install.sh | bash` installs crickets only. Asymmetric dependency reflects post-V4 #36 reality: agentm depends on crickets's base primitives; crickets is self-contained.

**Why this asymmetry?** Reflects the V4 #36 reorganization (compound skills + agentic memory move to agentm; crickets keeps base primitives). agentm functionality requires crickets's primitives (evaluator, base hooks, pii-scrubber, dependabot-fixer). Crickets's primitives stand alone — useful in any Claude Code project regardless of harness use.

**Why no shared install-bundle repo?** Adds an extra repo + complicates the discovery story. The asymmetric one-liner with a pre-pipe note (*"agentm is designed to work with crickets; this installer sets up both"*) handles discovery cleanly.

### 6. dev-setup is operator-private — invisible to public docs

agentm + crickets installers detect dev-setup presence (operator-personal shell-env layer) and defer to it if present; otherwise they're self-sufficient. No public-facing docs mention dev-setup.

**Why hide it?** dev-setup is the plan-author's personal-machine convenience — not designed for general adoption. Surfacing it in agentm/crickets docs creates expectation that users need it; they don't. Most users install via the one-liner + never know dev-setup exists.

### 7. Hard-cut deprecation of legacy `<project>/.harness/` at agentm v4.0.0

v3.x MINOR releases ship with deprecation warnings on every legacy-path read fallback. v3.9.x ships a strong banner. v4.0.0 removes the fallback entirely. The `--scope project` flag survives v4.0.0 (legitimate opt-in use cases remain).

**Why a hard cut?** Open-ended backward-compat creates maintenance burden + signals that the legacy path is still endorsed when it isn't. A clean cut at a major version is the standard semver contract.

**Why v4.0.0 specifically?** Aligns with the agentm/crickets V4 #36 reorganization release pair. Users migrating to agentm v4.x get one coordinated transition.

## Consequences

### Positive

- **One agentic environment, not 20.** Move the agent forward once; every project benefits.
- **Cross-project visibility.** "What was I working on yesterday across all my projects?" is a single vault query.
- **Cross-device continuity.** Phone + laptop see the same active plans + recent progress via Obsidian sync.
- **Clean repos.** No `.harness/` gitignored clutter, no `.claude/skills/` install drift between projects.
- **Foundation for V5/V6.** Vault-as-canonical-context makes V5 indexed retrieval + V6 dreaming possible.
- **Self-sufficient install.** Operators who don't use dev-setup get a working setup via one-liner.

### Negative

- **Project resolution is load-bearing.** If `resolve_project()` returns the wrong slug, every dispatcher reads/writes the wrong vault path. Resolver chain has 6 fallback levels + explicit override; failure modes documented.
- **Multi-device concurrent writes need handling.** PLAN.md edits from two devices simultaneously can conflict. Cursor + last-modified pre-write check + advisory locks address it; complete elimination is impossible with GDrive-backed sync.
- **Vault becomes a single point of failure.** GDrive sync issue + vault corruption affects every project. Mitigations: GDrive auto-versioning; operator can git-track the vault separately; graceful-skip mode for unavailable vault.
- **Migration burden** for operators on v3.x with multiple per-project installs. Mitigated by `--migrate-existing` single-command flow.
- **Repo install path (`--scope project`) maintenance** continues — two install modes increase test surface.

### Load-bearing assumptions + re-audit triggers

1. **GDrive sync is fast enough** for cross-device continuity to feel real-time. Re-audit if sync lag becomes operationally painful (>30s) OR if a non-GDrive vault host becomes operator-preferred.
2. **Markdown-canonical scales** past the operator's current ~9 projects + ~31 always-load entries. Re-audit at 100+ projects OR 200+ always-load entries OR when retrieval performance degrades.
3. **Single-operator** is the v1 target. Re-audit if multi-operator (team install + shared vault) becomes desired — would require ACL design + concurrency tightening.
4. **Antigravity 2.0 + Antigravity CLI continue to share an agent harness.** Re-audit if Google forks the agent surface across the two products (would invalidate single `antigravity` slug — see [ADR 0011](0011-antigravity-2-host-support)).
5. **`MEMORY_VAULT_PATH` env-var pattern remains the canonical vault-pointer.** Re-audit if Anthropic ships a host-level vault-discovery mechanism (operator-managed env-vars become redundant).
6. **`<vault>/projects/<slug>/` directory layout** holds for V4 + V5 work. Re-audit at V5 lifecycle layer (V5-1) — entries may need state metadata that doesn't fit the current frontmatter contract.
7. **Default-all-enabled auto-detect** doesn't false-positive in painful ways. Re-audit if auto-detect proposals routinely get rejected.

## Related

- [`device-wide-architecture.md`](../designs/device-wide-architecture.md) — the HLD this ADR locks decisions for
- [`agent-memory-evolution.md`](../designs/agent-memory-evolution.md) — the V1 → V6 evolution context
- [ADR 0001](0001-crickets-purpose) — original crickets/agentm split (this ADR shifts the boundary per V4 #36)
- [ADR 0002](0002-evaluator-design) — sub-agent-as-skill pattern preserved per design call
- [ADR 0006](0006-gemini-cli-host-removal) — historical context for the `agentm requires crickets; crickets standalone` asymmetry
- [ADR 0007](0007-memoryvault-discovery) — auto-context dispatcher (`harness_memory.py`) that this design extends
- [ADR 0009](0009-evidence-tracker-hook) — evidence-tracker stays `[claude-code]`-only; per-cwd `.evidence-reads` carve-out preserved
- [ADR 0011](0011-antigravity-2-host-support) — `.agents/` (plural) dispatch path that this design inherits
- agentm `.harness/ROADMAP-AgentMemoryV4.md` — V4 build sequencing (#31 design → #36 reorg → #26 state → #30 install → #35 documenter → #32 auto-detect → #33 cleanup → #34 aesthetic → #25 audit → ...)
- Always-load: [[vault-as-canonical-context]], [[hld-evolution-update-on-major-release]], [[docs-cover-ours-link-theirs]], [[silent-source-influences]], [[pre-approval-batch-pattern]]
