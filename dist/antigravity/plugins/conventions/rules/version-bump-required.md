---
name: version-bump-required
description: Any PR that adds, changes, or removes user-visible primitives requires a group.yaml version bump — the dist-sync gate enforces this, but catch it before the gate.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: version-bump-required

When a diff adds, modifies, or removes **user-visible primitives** (skills, rules, commands, agents, hooks, snippets, MCP server configs) under `src/`, the affected group's `group.yaml` `version` field must be incremented on the same branch before merging.

### Trigger condition

This rule fires when you are reviewing or about to approve/merge a diff that:

- Adds a new file under `src/<group>/skills/`, `src/<group>/rules/`, `src/<group>/commands/`, `src/<group>/agents/`, `src/<group>/hooks/`, or `src/<group>/snippets/`
- Modifies the body or frontmatter of an existing primitive
- Deletes a primitive

### What to check

1. Identify which group the changed primitives belong to (the `<group>` directory under `src/`).
2. Open that group's `src/<group>/group.yaml`.
3. Compare the `version` field against the last released version (from the most recent git tag or the published `dist/` plugin.json). It must be higher.
4. Confirm the bump follows semver: patch for fixes, minor for new primitives or behavioral additions, major for breaking changes.

### What is NOT a bypass

| Stated reason | Why it is not accepted |
|---|---|
| "The integrator will bump it" | True **only** for concurrent worker branches using the Model-A protocol (multi-worker plan where a single integrator runs `/integrate-worker` for the batch). For a solo PR that is not part of a named worker plan, the PR author owns the bump — there is no integrator. |
| "It's just a wording change" | A substantive wording change to a skill body changes the behavior of every installation of that primitive. Bump the patch version. |
| "The version is already 0.1.0" | `0.1.0` is the initial release version. Any modification after the first public release requires a bump. If the primitive has never been released, no bump is needed yet — but confirm the group has not yet been published. |
| "dist/ hasn't been regenerated yet" | The drift gate will catch the dist/ mismatch, but it will also catch a missing version bump. Fix both before the gate runs, not after. |

### Enforcement

Before approving or merging, verify:

1. The diff includes a `group.yaml` version change for every affected group.
2. The version change is a valid semver increment (not a downgrade, not a skip).
3. If this is a worker branch in a named multi-worker plan, confirm with the plan's integration notes that the integrator is expected to own the bump — and that this is documented in the plan.

If all three are satisfied, the bump is compliant. If any is missing, request the bump before merging.
