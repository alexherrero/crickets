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
- **Token Audit** (`token-audit`) — deterministic JSONL cost analyzer; the `/token-audit` command reads the session transcript and emits a per-turn cost breakdown. Standalone; declares the `token-audit` capability that `status-line-meter` enhances.
- **Status Line Meter** (`status-line-meter`) — live context/cost meter for the Claude Code status line: used-%, 5h-window cost, and floor-share badge. Reads the session JSONL incrementally; soft-depends on `token-audit`'s `pricing.py` via runtime discovery (graceful-skip when absent). Enhances `token-audit`.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-14** — `token-audit` and `status-line-meter` plugins shipped (Part C); four token-efficiency primitives added to `developer-workflows` v0.13–0.17 (Part D): `terse` output-style, `edit-over-write` rule, `compact-nudge-resume` hook, phase-aware model routing.
- **2026-06-09** — Plugins section added; Developer Safety is the first per-plugin page (it folds in the retired quality-gates recipe).
- **2026-06-09** — Plugins section complete — all six plugin pages now live (developer-workflows · developer-safety · code-review · github-ci · wiki-maintenance · pii).

## See also

[Reference](Reference) · [Plugin anatomy](Plugin-Anatomy) · [Install crickets plugins](Install-Into-Project) · [Home](Home)
