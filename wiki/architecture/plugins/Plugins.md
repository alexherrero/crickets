<!-- mode: index -->
# Plugins

These are the plugins crickets ships. Each is a native host plugin generated from `src/<group>/`; see [Plugin anatomy](Plugin-Anatomy) for the shared structure, and [Install crickets plugins](Install-Into-Project) to get them.

## What's here

- **[Development Lifecycle](Developer-Workflows)** (`development-lifecycle`) — the phase-gated dev loop (`/setup` … `/bugfix`) that the other plugins build on, plus the `explorer` and `evaluator` agents it ships with. It also carries token-efficiency primitives: the `terse` output-style, the `edit-over-write` rule, the `compact-nudge-resume` hook, and phase-aware model defaults on the typed agents.
- **[Developer Safety](Developer-Safety)** (`developer-safety`) — the controls that keep an autonomous session safe: a kill switch to stop it, `steer` to redirect it mid-run, and `commit-on-stop` so nothing is lost when it halts, plus the commit conventions.
- **[Code Review](Code-Review)** (`code-review`) — adversarial review of any diff or PR, on its own or sharpening `/review`. Its reviewer agents assume there's a bug and go looking; an evidence tracker holds them to specifics.
- **[Maintenance](GitHub-CI)** (`maintenance`) — CI and dependency-update tooling built around the `dependabot-fixer` skill, which needs `development-lifecycle` installed alongside it.
- **[Wiki](Wiki-Maintenance)** (`wiki`) — keeps the docs true to the code, in your house voice. Its skills author pages, classify them into the Diátaxis shape, and watch the repo for changes worth writing down.
- **[Privacy](PII)** (`privacy`) — scans diffs and the working tree for personal information before you commit or push, through the `pii-scrubber` skill.
- **[Design](Design-Docs)** (`design`) — authors design docs and ADRs. The `/design` command walks a doc from author through translate to sequence, and the ADR skill captures architectural decisions with re-audit triggers. Requires `development-lifecycle`.
- **[GitHub Projects](GitHub-Projects)** (`github-projects`) — syncs a vault project's roadmap, plan, and progress state onto a GitHub Project board, one way and deterministically. `project_sync.py` is the single idempotent write path, and a vault-equals-board drift gate catches the two silently diverging. Requires `development-lifecycle`.
- **[Diagnostics](crickets-diagnostics)** (`diagnostics`) — deterministic-first failure diagnosis: `/diagnose` classifies a failure, recalls it via a fingerprint-first exact-match ladder (semantic fallback only on a miss), ranks two or three hypotheses, and writes one scrubbed `kind:failure-incident` memory entry. It also shares its diagnose engine with `maintenance`'s dependabot-fixer. Requires `development-lifecycle`.
- **[Research](crickets-research)** (`research`) — discovery-to-watchlist research primitives: `idea-search` scans the agentm recall engine for existing vault and codebase entries relevant to a question, `learn-forward` mines operator-configured sources onto the watchlist through agentm's forward-learning pipeline, and `codebase-improvement` applies a research insight's stale pattern against your own repo. All three only ever surface a watchlist finding — nothing is auto-adopted. Requires `development-lifecycle`.
- **[Obsidian Vault](Obsidian-Vault-Backend)** (`obsidian-vault`) — the Obsidian/Google-Drive vault storage backend for the agentm memory engine. It ships the `vault` named backend as a `scripts/` payload agentm discovers on its own, and it stands alone.
- **Conventions** (`conventions`) — day-to-day testing and release discipline in one plugin: [Testing Conventions](Testing-Conventions) hold the line on tests-are-sacred, verify-first, and the three-layer pyramid; [Releasing Conventions](Releasing-Conventions) carry the pre-release checklist, the changelog-shape convention, and coordination for paired cross-repo releases. Requires `development-lifecycle`.
- **Tokens** (`tokens`) — token-efficiency tooling in one plugin: [Token Audit](Token-Audit) is a deterministic JSONL cost analyzer whose `/token-audit` command reads the session transcript and produces a per-turn cost breakdown, and the [Status Line Meter](Status-Line-Meter) reads the same session JSONL incrementally to show used percentage, five-hour-window cost, and a floor-share badge on the Claude Code status line, discovering the pricing script at runtime. Stands alone.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-07-11** — roster reconciled against the completed AG Wave A renames and mergers, which this page had never picked up: `developer-workflows` → `development-lifecycle`, `design-docs` → `design`, `github-ci` → `maintenance`, `wiki-maintenance` → `wiki`, `pii` → `privacy`, `obsidian-vault-backend` → `obsidian-vault`; `testing-conventions` + `releasing-conventions` merged into `conventions`; `token-audit` + `status-line-meter` merged into `tokens`; the previously undocumented `diagnostics` and `research` plugins added. Roster holds at 13.
- **2026-06-13 through 2026-06-16** — five more plugins shipped, bringing the roster to 13: `obsidian-vault` (2026-06-13), `github-projects` (2026-06-14), `design-docs` · `releasing-conventions` · `testing-conventions` (2026-06-16).
- **2026-06-14** — `token-audit` and `status-line-meter` plugins shipped (Part C); four token-efficiency primitives added to `developer-workflows` v0.13–0.17 (Part D): `terse` output-style, `edit-over-write` rule, `compact-nudge-resume` hook, phase-aware model routing.
- **2026-06-09** — Plugins section added; Developer Safety is the first per-plugin page (it folds in the retired quality-gates recipe).
- **2026-06-09** — Plugins section complete — all six plugin pages now live (developer-workflows · developer-safety · code-review · github-ci · wiki-maintenance · pii).

## See also

[Reference](Reference) · [Plugin anatomy](Plugin-Anatomy) · [Install crickets plugins](Install-Into-Project) · [Home](Home)
