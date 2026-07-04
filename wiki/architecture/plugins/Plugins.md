<!-- mode: index -->
# Plugins

These are the plugins crickets ships. Each is a native host plugin generated from `src/<group>/`; see [Plugin anatomy](Plugin-Anatomy) for the shared structure, and [Install crickets plugins](Install-Into-Project) to get them.

## What's here

- **[Developer Workflows](Developer-Workflows)** — the phase-gated dev loop (`/setup` … `/bugfix`) that the other plugins build on, plus the `explorer` and `evaluator` agents it ships with. It also carries token-efficiency primitives: the `terse` output-style, the `edit-over-write` rule, the `compact-nudge-resume` hook, and phase-aware model defaults on the typed agents.
- **[Developer Safety](Developer-Safety)** — the controls that keep an autonomous session safe: a kill switch to stop it, `steer` to redirect it mid-run, and `commit-on-stop` so nothing is lost when it halts, plus the commit conventions.
- **[Code Review](Code-Review)** — adversarial review of any diff or PR, on its own or sharpening `/review`. Its reviewer agents assume there's a bug and go looking; an evidence tracker holds them to specifics.
- **[GitHub CI](GitHub-CI)** — CI and dependency-update tooling built around the `dependabot-fixer` skill, which needs `developer-workflows` installed alongside it.
- **[Wiki Maintenance](Wiki-Maintenance)** — keeps the docs true to the code, in your house voice. Its skills author pages, classify them into the Diátaxis shape, and watch the repo for changes worth writing down.
- **[PII Guardrail](PII)** — scans diffs and the working tree for personal information before you commit or push, through the `pii-scrubber` skill.
- **[Design Docs](Design-Docs)** — authors design docs and ADRs. The `/design` command walks a doc from author through translate to sequence, and the ADR skill captures architectural decisions with re-audit triggers. Requires `developer-workflows`.
- **[GitHub Projects](GitHub-Projects)** — syncs a vault project's roadmap, plan, and progress state onto a GitHub Project board, one way and deterministically. `project_sync.py` is the single idempotent write path, and a vault-equals-board drift gate catches the two silently diverging. Requires `developer-workflows`.
- **[Obsidian Vault Backend](Obsidian-Vault-Backend)** — the Obsidian/Google-Drive vault storage backend for the agentm memory engine. It ships the `vault` named backend as a `scripts/` payload agentm discovers on its own, and it stands alone.
- **[Releasing Conventions](Releasing-Conventions)** — carries the ship-release workflow and release discipline: a pre-release checklist, a changelog-shape convention, and coordination for paired cross-repo releases. Requires `developer-workflows`.
- **[Testing Conventions](Testing-Conventions)** — the day-to-day testing principles: tests are sacred, verify first, and the three-layer pyramid. Requires `developer-workflows`.
- **Token Audit** (`token-audit`) — a deterministic JSONL cost analyzer. Its `/token-audit` command reads the session transcript and produces a per-turn cost breakdown. It stands alone and declares the `token-audit` capability that Status Line Meter enhances.
- **Status Line Meter** (`status-line-meter`) — a live context and cost meter for the Claude Code status line, showing used percentage, five-hour-window cost, and a floor-share badge. It reads the session JSONL incrementally and discovers `token-audit`'s pricing script at runtime when it's installed, skipping gracefully when it isn't. It enhances Token Audit.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-13 through 2026-06-16** — five more plugins shipped, bringing the roster to 13: `obsidian-vault` (2026-06-13), `github-projects` (2026-06-14), `design-docs` · `releasing-conventions` · `testing-conventions` (2026-06-16).
- **2026-06-14** — `token-audit` and `status-line-meter` plugins shipped (Part C); four token-efficiency primitives added to `developer-workflows` v0.13–0.17 (Part D): `terse` output-style, `edit-over-write` rule, `compact-nudge-resume` hook, phase-aware model routing.
- **2026-06-09** — Plugins section added; Developer Safety is the first per-plugin page (it folds in the retired quality-gates recipe).
- **2026-06-09** — Plugins section complete — all six plugin pages now live (developer-workflows · developer-safety · code-review · github-ci · wiki-maintenance · pii).

## See also

[Reference](Reference) · [Plugin anatomy](Plugin-Anatomy) · [Install crickets plugins](Install-Into-Project) · [Home](Home)
