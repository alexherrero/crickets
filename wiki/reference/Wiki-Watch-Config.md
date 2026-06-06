<!-- Status: pending — wiki-watcher (W1). Plan: .harness/PLAN.md (The wiki-watcher (W1) — wiki-maintenance part 4/5), tasks 1 + 3. Field names, marker filename, and exact JSON shapes are placeholders until the task-1/task-3 resolvers land; fill the table from the implementation diff at /work. Honors DC-W2 (no new config file) + DC-8 (vault index vs on-host run config). -->

# Wiki-watch config reference

How the `wiki-watch` engine is configured. There is **no new config file** — the watcher reads from **three existing sources**, each owned by a different layer (honors DC-W2 + DC-8: the vault holds the cross-device *index*, the on-host marker holds *run config*, never config in the vault).

> [!NOTE]
> **Status:** pending — `wiki-maintenance` part 4. Field names and exact shapes below are placeholders to be confirmed against the task-1 and task-3 diffs at `/work`. Marked `_Filled by human._` where the source has not yet landed.

## ⚡ Quick Reference

| Config | Source | Layer | Carries | Resolver |
|---|---|---|---|---|
| **Enablement** | `.agentm-config.json` | on-host | `wiki_watch_enabled` toggle (host-level on/off) | `_Filled by human._` (modeled on `harness_memory.py:_read_config_state_mode()`) |
| **Run config** | `<repo>/.harness/` marker (new, per-repo) | on-host, per-repo | watch sources + dispatch mode `pr` \| `direct` | `_Filled by human._` (modeled on `_read_mode_marker()`) |
| **Wiki target** | `repo_registry` (`<vault>/_meta/repos.json`) `wiki_path` | vault (index) | watched repo → which wiki to write | net-new repo→wiki resolver (task 1) |

## Enablement — `.agentm-config.json`

Host-level on/off. A `wiki_watch_enabled` toggle (or nested block) read without touching the vault. Off or absent → the watcher no-ops for this host. Mirrors the existing config-state read path; **no new file**.

```jsonc
// .agentm-config.json (shape pending task 1)
{
  "wiki_watch_enabled": true
  // _Filled by human._ — confirm nesting + any sub-keys from the task-1 diff.
}
```

## Run config — the per-repo `.harness/` marker

A **new** per-repo marker under `<repo>/.harness/` carrying the run config: which sources to watch (the repo plus the active `PLAN.md` / design / `ROADMAP.md` — the *source* files, not the output wiki) and the **dispatch mode**. This is on-host, per-repo run config — it is **never written to the vault** (DC-8).

| Field | Values | Meaning |
|---|---|---|
| dispatch mode | `pr` (default) \| `direct` | `pr` opens a pull request a human merges; `direct` commits straight to the wiki — **opt-in per trusted repo only**. |
| watch sources | `_Filled by human._` | The repo + active `PLAN.md` / design / `ROADMAP.md` to diff since the cursor. |

An absent marker, a malformed marker, or an unknown dispatch mode is handled defensively (skip / safe default) — confirm the exact behavior from the task-1 diff. `_Filled by human._`

## Wiki target — `repo_registry` `wiki_path`

Which wiki a watched repo maps to. The registry (`<vault>/_meta/repos.json`) already carries an optional `wiki_path` per entry; the resolver (net-new in task 1) maps a watched path/slug → registry entry → `wiki_path`.

| Case | Behavior |
|---|---|
| `wiki_path` present | Resolve to that path. |
| `wiki_path` absent | Fall back to `<root>/wiki`, or skip. `_Filled by human._` (confirm from task-1 diff) |
| repo unregistered | Skip — the watcher no-ops for that repo. |

Cross-repo resolution shells out to agentm's `repo_registry.py` via path-fallback (mirroring `recent-wiki-changes.sh`) and **graceful-skips** if agentm is absent — the watcher no-ops, never hard-fails.

## State and audit (not config, but config-adjacent)

Cursors, the processed-set, and the audit log live under `_harness/wiki-watch/` — resolved via `harness_memory.py vault-state-path wiki-watch/<file>` to `<vault>/projects/<slug>/_harness/wiki-watch/` in vault mode, or `<repo>/.harness/wiki-watch/` in local mode (DC-W6). The audit log is **local and never committed**.

## Related

- [How to run the wiki-watcher (W1)](Run-The-Wiki-Watcher) — the task-oriented walkthrough.
- [Antigravity limitations](Antigravity-Limitations) — why scheduling (the loop that re-invokes this engine) is Claude-first.
- [Compatibility](Compatibility) — supported hosts + per-manifest `supported_hosts` contract.
- [Wiki-watcher (W1) design](../explanation/designs/wiki-maintenance/parts/wiki-watcher.md) — the index-vs-run-config split (DC-8) and the rest of the rationale.
