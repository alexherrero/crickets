---
name: release
description: Pre-merge gate — verify plan done, gates green, CI passing. Never pushes / merges / tags without explicit approval.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

You are running the **release** phase of the developer-workflows loop. This is a **pre-merge gate**: verify the plan is complete and everything is green, prepare the release, and **wait for explicit human approval** before any high-blast-radius action (push / merge / tag / deploy).

## Non-negotiable constraints

1. **Preconditions** — `PLAN.md` `Status: done`, all tasks `[x]`, `/review` resolved, working tree clean, branch ahead of base. If any fails, **stop and report**.
2. **Re-run the full deterministic gate suite** — the *full* test suite (not a subset), a *production* build (not just dev-server).
3. **Set `features.json` `passes: true` only on verified features** — one feature, one verified test exercise, one clean review, then `true`. Never speculative.
4. **Dispatch the documenter** — probe with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py" wiki-maintenance`; on **exit 0** dispatch the `documenter` with the full plan-to-HEAD diff for a wiki sweep: flip any missed `pending → implemented`, add ADRs for non-obvious decisions, update `Home.md` / `_Sidebar.md`, append to the completed-features log (**block the release** on unresolved `OPEN QUESTIONS` — shipping stale docs poisons the wiki); on **exit 1** (no `wiki-maintenance`, or no `CLAUDE_PLUGIN_ROOT`) skip the sweep silently.
5. **Do NOT push, merge, tag, or deploy.** These require explicit human confirmation per action. Prepare + summarize; wait for the word.
6. **If CI is red, stop.** Do not release past failing checks.
7. **Offer next-release themes to the GitHub Project** (optional) — only a *recurring theme* across sessions (a single deferral is not a theme); batch one preview; **no `gh` without confirmation**; silent-skip if `.harness/project.json` absent, `gh` unavailable, or no theme emerged.

## Process

1. **Check preconditions** (constraint 1). Any miss → stop and report what's outstanding.
2. **Re-run the full gate suite** (constraint 2). Capture results.
3. **Verify CI** if the repo has it — green across the matrix before proceeding (constraint 6). Honor **wake-on-CI**: push the branch, wait for green, *then* tag/release — never tag ahead of a green CI run.
4. **Update `features.json`** — set `passes: true` only on features with a verified test exercise + clean review (constraint 3).
5. **Documenter wiki sweep** (constraint 4 — probe `wiki-maintenance`, dispatch on exit 0).
6. **Prepare release artifacts** — changelog entry + version bump per the project's convention. If a release skill is installed (e.g. crickets `ship-release`), suggest it; otherwise prepare the steps manually. Do **not** execute push / tag / release.
7. **Summarize + wait.** List what's ready and the exact commands the user can run (`git push`, `gh release create`, `gh pr merge`). **Wait for explicit confirmation** before running any of them (constraint 5).

## Failure modes to avoid

- Releasing with the plan not `done` or `/review` unresolved.
- Running a test subset instead of the full suite.
- Setting `passes: true` speculatively.
- Pushing / tagging / merging without explicit per-action confirmation.
- Releasing past a red CI.
