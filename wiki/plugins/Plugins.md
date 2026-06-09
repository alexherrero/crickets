<!-- mode: index -->
# Plugins

The crickets plugins — what each is and ships. Every one is a native host plugin generated from `src/<group>/`; see [Plugin anatomy](Plugin-Anatomy) for the shared structure, and [Install crickets plugins](Install-Into-Project) to get them.

## What's here

- **[Developer Workflows](Developer-Workflows)** — the phase-gated dev loop (`/setup` … `/bugfix`) + the explorer / evaluator agents; the base the others enhance.
- **[Developer Safety](Developer-Safety)** — operator control + safety: `kill-switch` · `steer` · `commit-on-stop` + the commit conventions.
- **[Code Review](Code-Review)** — standalone adversarial review of any diff or PR; sharpens `/review`. The `adversarial-reviewer` (+ cross-model) agents · `evidence-tracker`.
- **[GitHub CI](GitHub-CI)** — CI + dependency-update tooling: the `dependabot-fixer` skill (requires `developer-workflows`).
- **[Wiki Maintenance](Wiki-Maintenance)** — Diátaxis-shape, house-voice wiki upkeep: `wiki-author` · `diataxis-author` · `documenter` · `wiki-watch`.
- **[PII Guardrail](PII)** — scan diffs + the working tree for personal info before commit/push: the `pii-scrubber` skill.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-09** — Plugins section added; Developer Safety is the first per-plugin page (it folds in the retired quality-gates recipe).
- **2026-06-09** — Plugins section complete — all six plugin pages now live (developer-workflows · developer-safety · code-review · github-ci · wiki-maintenance · pii).

## See also

[Reference](Reference) · [Plugin anatomy](Plugin-Anatomy) · [Install crickets plugins](Install-Into-Project) · [Home](Home)
