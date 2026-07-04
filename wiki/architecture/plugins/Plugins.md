<!-- mode: index -->
# Plugins

The crickets plugins — what each is and ships. Every one is a native host plugin generated from `src/<group>/`; see [Plugin anatomy](Plugin-Anatomy) for the shared structure, and [Install crickets plugins](Install-Into-Project) to get them.

## What's here

- **[Developer Workflows](Developer-Workflows)** — the phase-gated dev loop (`/setup` … `/bugfix`) + the explorer / evaluator agents; the base the others enhance. Also ships token-efficiency primitives: `terse` output-style, `edit-over-write` rule, `compact-nudge-resume` hook, and phase-aware model defaults on the typed agents.
- **[Developer Safety](Developer-Safety)** — operator control + safety: `kill-switch` · `steer` · `commit-on-stop` + the commit conventions.
- **[Code Review](Code-Review)** — standalone adversarial review of any diff or PR; sharpens `/review`. The `adversarial-reviewer` (+ cross-model) agents · `evidence-tracker`.
- **[GitHub CI](GitHub-CI)** — CI + dependency-update tooling: the `dependabot-fixer` skill (requires `developer-workflows`).
- **[Wiki Maintenance](Wiki-Maintenance)** — Diátaxis-shape, house-voice wiki upkeep: `wiki-author` · `diataxis-author` · `documenter` · `wiki-watch`.
- **[PII Guardrail](PII)** — scan diffs + the working tree for personal info before commit/push: the `pii-scrubber` skill.
- **[Design Docs](Design-Docs)** — design-doc and ADR authoring: the `/design` command (author → translate → sequence) and the ADR skill, with re-audit triggers (requires `developer-workflows`).
- **[GitHub Projects](GitHub-Projects)** — one-way, deterministic board-sync from a vault project's roadmap/plan/progress state onto a GitHub Project board; `project_sync.py` is the single idempotent write path, backed by a vault==board drift gate (requires `developer-workflows`).
- **[Obsidian Vault Backend](Obsidian-Vault-Backend)** — the Obsidian/Google-Drive vault storage backend for the agentm memory engine; ships the `vault` named backend as an agentm-discovered `scripts/` payload. Standalone.
- **[Releasing Conventions](Releasing-Conventions)** — ship-release workflow and release discipline: pre-release checklist, changelog-shape convention, paired cross-repo release coordination (requires `developer-workflows`).
- **[Testing Conventions](Testing-Conventions)** — day-to-day testing principles: tests-are-sacred, verification-first, the 3-layer pyramid (requires `developer-workflows`).
- **Token Audit** (`token-audit`) — deterministic JSONL cost analyzer; the `/token-audit` command reads the session transcript and emits a per-turn cost breakdown. Standalone; declares the `token-audit` capability that `status-line-meter` enhances.
- **Status Line Meter** (`status-line-meter`) — live context/cost meter for the Claude Code status line: used-%, 5h-window cost, and floor-share badge. Reads the session JSONL incrementally; soft-depends on `token-audit`'s `pricing.py` via runtime discovery (graceful-skip when absent). Enhances `token-audit`.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-13 through 2026-06-16** — five more plugins shipped, bringing the roster to 13: `obsidian-vault` (2026-06-13), `github-projects` (2026-06-14), `design-docs` · `releasing-conventions` · `testing-conventions` (2026-06-16).
- **2026-06-14** — `token-audit` and `status-line-meter` plugins shipped (Part C); four token-efficiency primitives added to `developer-workflows` v0.13–0.17 (Part D): `terse` output-style, `edit-over-write` rule, `compact-nudge-resume` hook, phase-aware model routing.
- **2026-06-09** — Plugins section added; Developer Safety is the first per-plugin page (it folds in the retired quality-gates recipe).
- **2026-06-09** — Plugins section complete — all six plugin pages now live (developer-workflows · developer-safety · code-review · github-ci · wiki-maintenance · pii).

## See also

[Reference](Reference) · [Plugin anatomy](Plugin-Anatomy) · [Install crickets plugins](Install-Into-Project) · [Home](Home)
