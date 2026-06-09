# ADR 0007: MemoryVault Discovery + Mining

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-22
> **Related:** [ADR 0001 — crickets purpose](0001-crickets-purpose) · [Parent design — MemoryVault](https://github.com/alexherrero/agentm/wiki/memoryvault) · [Plan #7b discovery-mining part](https://github.com/alexherrero/agentm/wiki/discovery-mining) · [ROADMAP item #7b](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md)

## Context

ROADMAP item #7b (MemoryVault Discovery + Mining) shipped as the natural follow-on to #7a (MemoryVault Core, closed 2026-05-20). #7a populated the vault end-to-end and validated the recall + reflection loop. #7b's mandate: turn the vault from a *static curated store* into a *living surface* by adding three discovery sub-components — transcript reflection over historical Claude Code sessions, personal-skills auto-indexing of installed `SKILL.md` files, and internet skill-discovery against curated sources with the adapt-don't-import principle.

The plan locked four substantive sub-component tasks (1: personal-skills indexer; 2: transcript reflection corpus mode; 3: internet skill-discovery scan; 4: adapt-don't-import workflow + watchlist writes) + three batch tasks (5: watchlist review command; 6: docs + this ADR; 7: paired release). All four substantive tasks needed operator design input on different load-bearing questions:

- Task 1 (personal-skills indexer): how to map a SKILL.md source path back to a `<repo>` slug (auto-detect via .git/AGENTS.md ancestor walk vs. explicit operator flag)
- Task 2 (transcript corpus): default behavior — dry-run-by-default vs. execute-immediately for the firehose-protection question
- Task 3 (skill-discovery scan): which curated sources to seed the whitelist with
- Task 4 (adapt-don't-import): the "is this worth adopting?" rubric design

The decisions here lock the architecture for the discovery + mining surface.

## Decision

**Ship discovery + mining as four discrete sub-commands** (`/memory index-skills` + `/memory reflect corpus` + `/memory discover-skills` + `/memory adapt-skills` + `/memory watchlist`) with a **deterministic Python pipeline + LLM sub-agent two-pass architecture** for the highest-judgment task (adapt-don't-import). All implementations are stdlib-only (no new third-party deps); enrichment via GitHub's unauthenticated API (60/hr rate limit accepted with graceful-skip).

Concretely, the seven locked design calls:

### D1 — Personal-skills indexer auto-detects repo names

`index_skills.py` walks SKILL.md files across configured paths (`--skill-path` repeatable + `MEMORY_SKILL_PATHS` env). For each, derives the `<repo>` slug by walking up the ancestor tree until it finds `.git/` or `AGENTS.md`, then kebab-normalizing the basename. Operator can override via `--repo-name <slug>` for sources that don't sit under a git repo or have a non-kebab dir name. The auto-detect is the common path (works for the toolkit's own `skills/` + sibling `agentm/.claude/skills/` without configuration); explicit override is the escape hatch.

**Why not require explicit operator config**: the canonical clone layout (`~/Antigravity/crickets` + `~/Antigravity/agentm` as siblings) is well-known to the installer, and the auto-detect walks up to find the repo root with high precision. Forcing operator config for the common case adds friction.

### D2 — Transcript corpus mode is dry-run by default

`reflect.py corpus` first invocation prints sessions-to-process + estimated candidate volume without writing entries. Operator re-runs with `--execute` after seeing scope. Mitigates the "transcript backlog produces thousands of inbox candidates" risk flagged in the parent design's Tech Debt #7 and confirmed by the operator's AskUserQuestion answer.

State file at `<vault>/_meta/transcript-reflection-state.json` (schema_version 1) tracks `{session_id, processed_at, message_count, memory_count, idea_count, status}` per processed session. Atomic writes via tempfile + rename; saved after every session for single-session resume granularity (vs. per-batch).

**Why not execute-immediately**: the firehose risk is large + operator-perceptible; the extra command per real-execute run is a cheap safety price. Pattern matches `ideas_promote.py gc`'s never-silent-deletion contract.

### D3 — Skill-discovery whitelist seeds with operator's confirmed v1 set

Four sources in exact priority order (per the operator's task-3 AskUserQuestion answer): Anthropic Cookbook → awesome-claude-code → awesome-mcp-servers → awesome-llm-apps. Operator explicitly accepted "a little noisy" signal for broader coverage. Whitelist lives at `<vault>/personal-private/skill-discovery-sources.md` — operator-editable markdown; auto-seeded on first scan with all four URLs commented + ordered; subsequent scans read as-is.

**Why a vault-side editable file vs. hardcoded list**: per the configure-don't-build philosophy that's threaded through plan #18 (local-only embeddings) and the upcoming #22 (cross-surface protocol). Operator-editable means new sources are added via Obsidian edit, no code change required.

### D4 — Cadence-default 7 days; cadence-check is idle-hook's safety throttle

Default scan cadence is weekly. `discover_skills.py --cadence-check` skips fetch entirely if `last_scan` is within the cadence window. The idle hook (`memory-reflect-idle`) extends to call `discover_skills.py --cadence-check` at end of run, so the hook can fire frequently (every SessionStart) without hammering URLs.

**Why 7 days**: matches the parent design's locked design call; tunable via `--cadence-days N` or `$MEMORY_SKILL_DISCOVERY_CADENCE_DAYS`. Awesome-list READMEs don't change hourly; weekly catches new additions without burning bandwidth.

### D5 — Adapt-don't-import is two-pass: deterministic rubric + LLM judgment

The operator-stated requirement (task 4): "extra thorough 6-rule rubric, and feed that plus more relevant metadata like how popular the skill is, how many stars it's repo has and other indicators of how reliable the repo may be, along with research that confirms it is from a trustworthy source, and use the sub-agent to judge based on that".

Locked architecture:

- **Pass 1 (deterministic Python — `adapt_skills.py`)**: walks cached diff files from `discover_skills.py`; parses candidate patterns (sections + headings + top-level bullets); applies the 6-rule rubric (R1 new-tool +1 / R2 complements-convention +1 / R3 agent-building-context +1 / R4 names-primitive +1 / R5 experimental flag -1 / R6 cross-vendor proprietary -2 → thresholds 3+ HIGH / 1-2 MEDIUM / ≤0 LOW); enriches each candidate with GitHub metadata (stars / last_commit / archived / license SPDX / owner / repo via unauth API, graceful-skip on 403/timeout) + trustworthiness signals (operator-editable trusted-orgs whitelist at `<vault>/personal-private/trusted-sources.md` + cross-citation count across the 4 discovery sources + activity-recent / permissive-license / high-stars / low-stars / archived-warning); writes enriched candidate JSONs to `<vault>/_meta/skill-discovery-cache/adapt-state/<source-slug>/<pattern-slug>.json`.

- **Pass 2 (LLM sub-agent — `adapt-evaluator`)**: reads each enriched JSON; cross-references operator's vault (`personal-skills/` + `_always-load/` + `personal-projects/conventions.md`) for semantic fit; renders final HIGH / MEDIUM / LOW classification + adaptation_notes + recommendation_summary; writes watchlist entry only for HIGH+MEDIUM (LOW dropped silently). Tool allowlist: Read + Glob + Grep + Write (Write scoped to `_skill-watchlist/<source-slug>/<pattern-slug>.md` only — adapt-don't-import architectural enforcement).

**Why two-pass split**: heuristic rubrics are testable + deterministic but blind to semantic nuance (a "workflow" word match doesn't mean it's actually a *workflow worth adopting*). LLM judgment is semantically sharp but expensive + non-deterministic. Pass 1 narrows the surface (drops LOW outright; gates the enrichment + sub-agent dispatch); Pass 2 makes the final decision. Operators can inspect Pass 1's JSON output to verify the rubric is scoring sensibly before paying the LLM cost.

**Why no auto-fork to `crickets/skills/`**: the adapt-don't-import contract is architectural, not advisory. The sub-agent has no write access to skill directories; promotion to a real skill requires the operator's manual authoring outside the script. Watchlist entries are review artifacts, not auto-adopt triggers.

### D6 — Watchlist review uses promote / dismiss / defer (mirroring ideas_promote.py gc)

`watchlist_review.py` exposes `list` / `review` / `promote <slugs>` / `dismiss <slugs>` / `defer <slugs> --until YYYY-MM-DD [--reason]` subcommands. Promote = annotation-only (status: promoted + promoted_at timestamp; entry stays in place). Dismiss = move to `_skill-watchlist/_archive/<source-slug>/` with collision-safe naming. Defer = status: deferred + deferred_until + optional reason; entry stays in place; future passes can filter `deferred_until` to re-surface eligible entries. Non-TTY stdin defaults all interactive prompts to skip (never-silent-action contract — same as `ideas_promote.py gc`).

**Why promote-as-annotation vs. auto-fork**: per D5 — adapt-don't-import is architectural. Promote marks the operator's intent ("yes I want to adopt this"); the actual fork is operator-typed in a separate session.

**Why dismiss-as-archive vs. delete**: archive preserves audit trail. Cross-citation count across sources may surface the same pattern again later (a different source mentions it); the audit trail lets the operator see "we considered this and dismissed it for reason X" rather than re-evaluating from scratch.

### D7 — Stdlib-only Python pipelines

All three new scripts (`index_skills.py`, `discover_skills.py`, `adapt_skills.py`, `watchlist_review.py`) use only Python stdlib — no new third-party deps. GitHub API access via `urllib.request`; markdown parsing via regex; JSON via `json` module; atomic writes via `os.replace`; no `requests` / `pyyaml` / `httpx` / etc.

**Why**: aligns with plan #18's local-first design (no new infrastructure required beyond what `memory` skill already needs). Reduces the install surface; keeps `requirements.txt` lean. The graceful-skip pattern (when GitHub rate-limits or sentence-transformers absent) makes deps-light viable.

## Consequences

### Positive

- **Four discovery sub-commands ship with consistent shape** — same CLI flag conventions (`--vault-path` / `--dry-run` / `--skip-network` / etc.), same atomic state-file pattern, same graceful-skip contracts. Operator learns one pattern, applies it across all four.
- **Adapt-don't-import is architecturally enforced**, not advisory. The sub-agent's write allowlist physically prevents skill-folder pollution; the operator's manual fork step is the only way new skills enter `crickets/skills/`.
- **Pass-1-Python + Pass-2-LLM split** balances determinism + semantic judgment. Operators can tune the rubric in code (testable, fast); LLM only fires for HIGH+MEDIUM (cost-bounded).
- **Operator-editable whitelists** for both discovery sources + trusted orgs mean the system adapts without code change as the operator's tastes evolve.
- **Cadence-check pattern** lets the idle hook fire frequently without hammering URLs — the same self-throttle approach generalizes to any future scheduled-discovery use.
- **Watchlist review action set (promote/dismiss/defer)** mirrors `ideas_promote.py gc` — same operator UX across two surfaces (idea ledger + skill watchlist). Reduces cognitive load.

### Negative

- **GitHub unauthenticated 60/hr rate limit** caps adapt_skills.py's enrichment burst. For a typical scan (4 sources × few-dozen candidates), this is fine; for a one-time backfill over many cached diffs, the rate limit will trip. Acceptable for v1 — graceful-skip means rubric + trust signals still compute without `github_*` enrichment. Future option: authenticated requests via operator-supplied `GITHUB_TOKEN` env.
- **LLM sub-agent latency** for Pass 2 is bounded only by operator attention. For batch contexts (future idle-hook auto-dispatch), a `--limit N` flag will cap per-pass evaluation count (default 5).
- **Markdown-only source fetcher** in `discover_skills.py` — HTML pages get cached as raw HTML; diff still works but downstream `adapt_skills.py` candidate-parsing assumes markdown structure. If operator adds an HTML-only source, candidate extraction degrades. Documented in `/memory discover-skills` anti-patterns.
- **The 6-rule rubric is tuned to v1 fixtures**; real-world signal quality requires dogfooding. Tune-from-real-use pattern (same as `recall.py`'s rank-merge weights in plan #7a part 5 task 6) applies: ship instrumented, tune from real watchlist review.

### Load-bearing assumptions (re-audit triggers)

- **Operator runs Claude Code + Antigravity** (not a different host suite). The discover_skills + idle-hook integration assumes the existing `memory-reflect-idle.sh` hook fires; if operator switches to a host without equivalent hooks, the cadence-check throttle won't kick in. Re-audit triggers: ROADMAP item #17 (Antigravity 2.0 + CLI host support) — verify the new CLI exposes equivalent hook surfaces.
- **GitHub remains the canonical source-of-truth for the 4 default sources** (Anthropic Cookbook + 3 awesome-lists). If any of these moves off GitHub (e.g. to a self-hosted gitea), the slug derivation in `_slug_from_url` falls back to `url-<8-char-hex>` which still works but loses the kebab-readable `<owner>-<repo>` form. Re-audit triggers: any default source mirrors elsewhere or shuts down.
- **Curated `_DEFAULT_TRUSTED_ORGS` list stays current** (anthropics / google / microsoft / hashicorp / openai / etc. — 18 orgs). New trustworthy orgs emerge over time (e.g. ROADMAP #17 may add Antigravity's owner if separate from Google); operator edits the whitelist as needed. Re-audit triggers: any default org in the seed list deprecates or rebrands; new emergent-trustworthy orgs surface in real watchlist review.
- **Adapt-don't-import principle is architectural, not negotiable.** If a future operator decision allows agent-side adoption (e.g. "auto-promote HIGH+trusted-org+stars≥1000"), this ADR is superseded — the architectural enforcement (sub-agent write allowlist) would need explicit revisiting. Re-audit triggers: any operator request to soften the manual-fork-only contract.

## Related

- Parent design: [MemoryVault — permanent agent memory](https://github.com/alexherrero/agentm/wiki/memoryvault)
- Plan #7b part: [discovery-mining](https://github.com/alexherrero/agentm/wiki/discovery-mining)
- ROADMAP: [#7b MemoryVault Discovery + Mining](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md)
- Sibling discovery follow-up: [ROADMAP #21 Harness self-audit skill](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md) — reuses discover_skills.py + adapt-evaluator infrastructure against harness's own conventions
- Sibling discovery follow-up: [ROADMAP #22 Cross-surface AgentMemory protocol](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md) — configure-don't-build vault access across surfaces; uses the same operator-editable-whitelist pattern locked here
- Companion ADR: [0001 — crickets purpose](0001-crickets-purpose) (amended 2026-05-20 for local-only embeddings; this ADR extends the local-first design to discovery + adoption)
