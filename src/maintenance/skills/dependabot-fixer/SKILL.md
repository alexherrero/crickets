---
name: dependabot-fixer
description: Fix breakage on a Dependabot PR. Trigger when (a) the current branch matches `dependabot/*` and CI is red, (b) the user asks to "fix the dependabot PR" / "make this dependency update pass", or (c) the user invokes `/dependabot-fix [pr-number]`. Reads failing CI logs and upstream CHANGELOG, applies a bounded fix loop, pushes commits to the Dependabot branch, comments residual risks on the PR. Never merges. Aborts honestly when the fix needs human judgment.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 1.1.0
install_scope: project
---

You are running the `dependabot-fixer` skill. Migrated from `agentm` to `crickets` in toolkit v0.1.0. The body below is the operational version.

## Preconditions (check first, abort if not met)

1. `gh` CLI is authenticated: `gh auth status`.
2. Working tree is clean: `git status --porcelain` returns empty. If not, refuse.
3. `.harness/verify.sh` exists and is executable. If not, warn and fall back to language defaults (`go test ./...`, `npm test`, `pytest`, etc.).

## Identify the target PR

- If current branch matches `dependabot/*` → operate on the PR for that branch (`gh pr view --json number`).
- If user passed a PR number → use it.
- Otherwise → list open Dependabot PRs with red CI and ask which one:
  ```
  gh pr list --author "app/dependabot" --json number,title,headRefName,statusCheckRollup \
    | jq '[.[] | select(.statusCheckRollup[]?.conclusion == "FAILURE")]'
  ```

## Gather context

```
gh pr view <n> --json title,body,headRefName,files,statusCheckRollup
gh run view <latest-failed-run-id> --log-failed > /tmp/dependabot-fix-logs.txt
```

Extract: ecosystem, package, old version, new version, delta (patch/minor/major).

Try to fetch the upstream CHANGELOG for the bump range (GitHub releases of the package's source repo). If unavailable, proceed without it but lower your confidence accordingly.

Read `.harness/known-migrations.md` (if it exists). If the package matches a recipe, that recipe is your first fix attempt.

## Diagnose (call the shared `/diagnose` engine — do not reason inline)

This step no longer produces its own category+confidence judgment from scratch. It calls `diagnostics`' shared entrypoint, feeding it the CI-log text already captured above (`/tmp/dependabot-fix-logs.txt`) as the traceback.

Check availability first (graceful-skip): `python3 "${CLAUDE_PLUGIN_ROOT}/../development-lifecycle/scripts/find_capability.py" diagnostics`.

- **Exit 1** (diagnostics not installed) → fall back to the pre-recast behavior: produce failure category + confidence (high/medium/low) + proposed fix inline, abort on low confidence.
- **Exit 0** → run:
  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/../diagnostics/scripts/diagnose.py" --project <repo-slug> --tool ci /tmp/dependabot-fix-logs.txt
  ```
  One JSON object comes back on stdout: `{"outcome": "layer1_hit"|"written", "path", "fingerprint", "fp_algo", "namespace", [hypotheses]}`.

**The confidence-gate proxy (`/diagnose` has no confidence score — this mapping is the deliberate stand-in for the old high/medium/low gate):**

- `outcome == "written"` with **no** `"Similar to existing incident..."` hypothesis (a cold start / Layer-2 miss — nothing to go on) → **abort**, do not attempt. This is the new low-confidence case.
- `outcome == "layer1_hit"`, or `outcome == "written"` with a `"Similar to existing incident..."` hypothesis (a Layer-2 candidate carrying a real prior fix) → **proceed**, using the recalled prior incident's fix as the proposed-fix seed for the bounded fix loop below.

The bounded fix loop downstream is unchanged — repair stays this skill's own concern; only diagnosis moved to the shared engine.

## Bounded fix loop

Budget: 3 iterations (override with `DEPENDABOT_FIX_BUDGET` env).

```
for i in 1..budget:
  apply the proposed fix (Edit tool)
  bash .harness/verify.sh
  if exit 0: break
  re-read failing output; re-run the Diagnose step above on the new failure (if the proxy gate now says abort → abort)
```

## Hard rules — never violate

- **Never merge the PR.** Human merges.
- **Never modify tests** to make them pass (AGENTS.md rule 5).
- **Never disable lint/type checks** to dodge errors.
- **Never push to the default branch.** Only to the Dependabot branch.
- **Never pin to an older version** to escape the bump. If it can't be fixed, abort.
- **Never claim success unless `verify.sh` exited 0 in the final iteration.**
- **Never touch more than 10 files** in one fix attempt (override with `DEPENDABOT_FIX_MAX_FILES`). Broader changes need a human.

## On success

- Commit each iteration separately: `fix: update call sites for <pkg> v<old>→v<new>`.
- `git push` to the Dependabot branch.
- Comment on the PR via `gh pr comment <n> --body-file -`:
  - Summary + linked CHANGELOG entry.
  - Files touched.
  - **Residual risks** — always include this section, never claim "fully verified".
- Append one line to `.harness/progress.md` (if present): `dependabot-fixer: <pkg> v<old>→v<new> fixed in <N> iterations`.

## On abort

- Comment on the PR: diagnosis, what was tried, what's blocking, concrete next step for the human.
- Discard partial fixes that don't leave the tree in a passing state.
- Append to `.harness/progress.md` (if present): `dependabot-fixer: <pkg> v<old>→v<new> ABORTED — <reason>`.
- Exit with a clear failure message.

## Scope note

This skill exists for the **major-version Dependabot PR where CI failed** case. Green-CI auto-merge is handled by GitHub's native Dependabot auto-merge action — do not try to replicate that here.

## Migration history

Originally shipped in `agentm v0.8.x` as a harness-bundled skill. Migrated to `crickets v0.1.0` (paired with `agentm v2.0.0`) because the skill is host-cross-cutting and not phase-shaped — it earns its keep in any repo with Dependabot + CI, not just harness-installed projects. The `.harness/`-aware paths (`.harness/verify.sh`, `.harness/known-migrations.md`, `.harness/progress.md`) remain because they're soft references — the skill graceful-falls back to language defaults when those files are absent.

**2026-07-07 (v1.1.0, PLAN-wave-d-cross-wiring task 1):** the Diagnose step no longer reasons inline (own category+confidence judgment). It now calls the shared `diagnostics` engine (`diagnose.py`), graceful-skipping back to the pre-recast inline behavior when `diagnostics` isn't installed. The old inline high/medium/low confidence gate is replaced by a proxy mapping over `/diagnose`'s own `outcome` field (no confidence score exists on the shared engine) — see the Diagnose section above for the exact mapping.
