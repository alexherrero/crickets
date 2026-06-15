# How to configure `main` branch protection

> [!NOTE]
> **Goal:** Enable the four GitHub branch-protection controls that the worktree-per-plan isolation loop assumes — required CI status checks, PR-only merges with squash/rebase, no force-push, and linear history — so concurrent plan workers cannot race on tags or merge order.
> **Prereqs:** GitHub repository admin access (Settings → Branches); at least one push to `main` so the branch exists; the repo's CI workflows set up (so you can add them as required status checks). See [CI gates](CI-Gates) for the full gate list.

The worktree-per-plan loop creates one `worker/<slug>` branch per plan and merges it into `main` via a PR. Two concurrent plan workers can both create a tag pointing to a branch tip — the force-push-on-shared-tag trap — unless `main` is protected. The four controls below make that trap structurally unreachable.

## Steps

### 1. Open branch protection settings

In your GitHub repository: **Settings → Branches → Add branch protection rule** (or edit the existing `main` rule). Set **Branch name pattern** to `main`.

### 2. Require status checks before merging

- Enable **"Require status checks to pass before merging"**.
- Search for and add each CI job as a required status check. For a repository running the standard CI matrix (see [CI gates](CI-Gates)), add:
  - `validate`
  - `syntax`
  - `pii-guardrails`
- Enable **"Require branches to be up to date before merging"** so the merge target is current when CI runs.

*Why:* The loop's pre-tag CI wait and `check_tag_reachability.py` gate enforce "CI green before tag." If CI checks aren't required at merge, a broken worker branch can land and a tag can be created from that commit.

### 3. Require a pull request before merging (squash or rebase only)

- Enable **"Require a pull request before merging"**.
- Under **Allowed merge methods**, enable only **Squash merging** and/or **Rebase merging**. Disable **Merge commits**.

*Why:* The loop pushes each plan unit as a `worker/<slug>` branch and merges it via PR. Allowing direct pushes to `main` bypasses the per-plan CI gate. Merge commits produce non-linear history that makes reachability checks ambiguous when two plans land concurrently.

### 4. Disallow force pushes

- Ensure **"Do not allow force pushes"** is enabled (it is the default for protected branches; verify it has not been overridden).

*Why:* Force-pushing `main` rewrites published history — the unrecoverable case the recoverability gate explicitly stops on. It would also make existing tags unreachable, breaking the `tag-reachability` gate and the release serialization guarantee.

### 5. Require linear history

- Enable **"Require linear history"**.

*Why:* Linear history means every commit on `main` has exactly one parent. The `check_tag_reachability.py` gate uses `git merge-base --is-ancestor` to check reachability; with merge commits, two unrelated histories can pass that check even though they were never serialized — hiding the interleave the loop prevents.

### 6. Save and verify

Save the rule. Confirm the four controls are active:

```bash
gh api repos/{owner}/{repo}/branches/main/protection \
  --jq '{required_status_checks: .required_status_checks.contexts,
         allow_force_pushes: .allow_force_pushes.enabled,
         linear_history: .required_linear_history.enabled}'
```

Expected: `allow_force_pushes: false`, `linear_history: true`, status checks listed.

## See also

- [CI gates](CI-Gates) — the full gate battery the required status checks reference
- [ADR 0029: Concurrent-release coordination](../decisions/0029-concurrent-release-coordination.md) — why this model was chosen and the re-audit trigger if plan concurrency grows past a handful of simultaneous landers
- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — how the loop creates the `worker/<slug>` branch this protection applies to
