---
title: "The wiki-watcher (W1): continuous watch-loop documentation"
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-04
updated: 2026-06-04
last_major_revision: 2026-06-04
prd:
project: https://github.com/users/alexherrero/projects/5
parent_design: ../../wiki-maintenance.md
part_slug: wiki-watcher
dependencies: [scaffold-fold-in, documenter-wiring]
estimated_scope: L
---

# The wiki-watcher (W1): continuous watch-loop documentation

## Scope

The most net-new surface: a session-level continuous mode that runs the `documenter` on a **watch loop** instead of one-shot at a phase boundary (parent Detailed Design §7).

- **What it watches.** A repo (GitHub) and/or the active `PLAN.md` / design / `ROADMAP.md`. On each change it decides whether the change is doc-worthy, and dispatches the `documenter` to author the update.
- **Dispatch mode — PR is the default autonomous boundary.** Updates go out **directly or by PR**, configurable per repo. PR-default means a human merges; **direct-commit is opt-in per trusted repo**.
- **Hosting ships as W1.** A self-scheduling session using the host's loop/wakeup, to prove the loop end-to-end. **W2 (cron-headless) and W3 (external-poll → trigger) + a scheduled-routine mode are the documented follow-ons** — surfaced as a roadmap/Project backlog item at `/plan` (Technical Debt & Risks #3 in the parent).
- **Config rides the existing architecture — no new file.** `.agentm-config.json` carries host enablement; a **per-repo marker** carries run config (watch + dispatch mode); the `repo_registry` index (`<vault>/_meta/repos.json`) resolves which wiki a watched repo maps to. Honors the locked **DC-8 index-vs-run-config split** (cross-device *indexes* in the vault; *run config* on-host/per-repo). No standalone `.wiki-watch.yml`.
- **Correctness rests on durable state.** Per-source **cursors** + a **processed-set** make dispatch idempotent (never drop a change, never double-dispatch); a **significance gate** decides whether a diff warrants a doc update (filters noise → bounds PR volume); an **audit log** (`saw → decided → dispatched`, with PR links) is the monitoring surface.
- **Reuses the `documenter`** for the authoring itself — the watcher adds the trigger / config / dispatch / idempotency scaffolding around it, not a second writer.

## Dependencies

- **`scaffold-fold-in`** — the `documenter` must be present in `wiki-maintenance` for the watcher to dispatch it.
- **`documenter-wiring`** — the watcher reuses the deterministic probe → documenter dispatch plumbing built for the phase-boundary path.

## Verification criteria

- The watcher detects changes to a watched repo + the active `PLAN.md` / design / `ROADMAP.md` and dispatches the `documenter` only on doc-worthy changes (significance gate filters noise).
- **Idempotency:** durable cursors + a processed-set guarantee no dropped change and no double-dispatch across watcher restarts.
- **PR-default:** dispatch opens a PR by default; direct-commit engages only where opted-in per repo.
- **Config:** the watcher reads enablement from `.agentm-config.json`, run config from the per-repo marker, and the wiki target from `repo_registry` — no new config file introduced.
- **Audit log** (`saw → decided → dispatched`, with PR links) is written to the durable store (`_harness/wiki-watch/`), **local, never committed**.
- **Graceful-skip** where `gh`/auth or a scheduler is unavailable — the watcher mode no-ops, never hard-fails a session.
- Public-repo **PII guardrails** (pre-push hook + `pii-scrubber`) gate anything the watcher pushes.
- The watch loop is mockable (inject deltas); deterministic plumbing (cursors, dispatch, config resolution) is unit-tested under `bash scripts/check-all.sh`.

## Parent design

This part implements one slice of [Wiki-Maintenance — an opinionated, template-driven wiki maintainer](../../wiki-maintenance.md) (`Status: final`). See the parent for Context, Alternatives Considered, Quality Attributes overview, and Operations strategy. Mid-execution changes to this part's scope must be appended to the parent's Document History.
