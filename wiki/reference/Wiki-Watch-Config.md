<!-- Status: implemented — wiki-watcher (W1). Plan: .harness/PLAN.md (The wiki-watcher (W1) — wiki-maintenance part 4/5), tasks 1 + 3 + 4. Task 1 landed the three config resolvers (wiki_watch_config.py); task 3 the dispatch_mode consumption (wiki_watch_dispatch.py); task 4 the single-cycle driver (wiki_watch_cycle.py) that consumes all three resolvers, making the engine end-to-end usable. Every field/section below is confirmed against those diffs. Honors DC-W2 (no new config file) + DC-8 (vault index vs on-host run config). -->

# Wiki-watch config reference

How the `wiki-watch` engine is configured. There is **no new config file** (DC-W2) — the watcher reads config through **three sources**, each owned by a different layer, and config never lives in the vault (DC-8: the vault holds the cross-device *index*; the on-host marker holds *run config*).

> [!NOTE]
> **Status:** implemented — `wiki-maintenance` part 4. The three config **resolvers** landed in task 1 (`wiki_watch_config.py`); their files, shapes, and opt-in semantics below are confirmed against that diff. Task 3 added the **dispatch plumbing that consumes `dispatch_mode`** (`wiki_watch_dispatch.py`). Task 4's single-cycle driver (`wiki_watch_cycle.py`) consumes all three resolvers — `read_enablement`, `read_run_config`, `resolve_wiki_target_for_repo` — so the engine is now end-to-end usable. See [How to run the wiki-watcher](Run-The-Wiki-Watcher) for the run flow.

## ⚡ Quick Reference

| Config | Source file | Layer | Carries | Resolver entry point |
|---|---|---|---|---|
| **Enablement** | `<install-prefix>/.agentm-config.json` | on-host (device) | host on/off toggle — **opt-in** | `read_enablement()` · CLI `enabled` |
| **Run config** | `<repo>/.harness/wiki-watch.json` (net-new marker) | on-host, per-repo | `watch_sources` + `dispatch_mode` — **presence = per-repo opt-in** | `read_run_config(repo_root)` · CLI `run-config <repo_root>` |
| **Wiki target** | `repo_registry` (`<vault>/_meta/repos.json`) `wiki_path` | vault (index) | watched repo → which wiki to write | `resolve_wiki_target_for_repo(...)` · CLI `wiki-target <repo_root> [--slug X]` |

All three resolvers live in the group script `wiki_watch_config.py` (bundled to both hosts at `<plugin>/wiki-maintenance/scripts/`). The pure resolvers take explicit inputs and are deterministically unit-tested (38 tests, `test_wiki_watch_config.py`); the registry shell-out is a best-effort, graceful-skip seam.

## Enablement — `<install-prefix>/.agentm-config.json`

Device-level on/off, read **vault-free**. The install prefix resolves from `$AGENTM_INSTALL_PREFIX` (default `~/.claude`), mirroring the agentm convention. Two shapes are recognized — the nested block is canonical (extensible), the top-level key an alias shorthand:

```jsonc
// <install-prefix>/.agentm-config.json
{
  "wiki_watch": { "enabled": true }   // canonical (nested, extensible)
}
// — or the alias shorthand —
{
  "wiki_watch_enabled": true          // top-level alias
}
```

The watcher dispatches autonomously, so enablement is **OPT-IN**: an absent config, an unreadable / malformed file, or any falsey value all resolve to **disabled**. The CLI `enabled` subcommand exits `0` when enabled, `1` when disabled.

## Run config — `<repo>/.harness/wiki-watch.json` (net-new marker)

A **net-new** per-repo marker carrying the run config. It is JSON (it holds structure), modeled on agentm's flat `.project-mode` marker. This is on-host, per-repo run config and is **never written to the vault** (DC-8).

```jsonc
// <repo>/.harness/wiki-watch.json
{
  "watch_sources": ["PLAN.md", "designs/"],   // repo-relative paths/globs
  "dispatch_mode": "pr"                         // "pr" | "direct"
}
```

The marker's **presence is the per-repo opt-in**: an absent, unreadable, empty, or malformed marker (or one that isn't a JSON object) means *this repo is not configured for watching → skip it*. A malformed marker also logs to stderr so a typo stays visible, then skips. Parsing is defensive:

| Field | Values | Default + fallback behavior |
|---|---|---|
| `watch_sources` | list of repo-relative paths / globs | Absent / non-list / empty → `["."]` (the whole repo; the task-2 significance pre-filter drops noise). Non-string entries are dropped. |
| `dispatch_mode` | `"pr"` \| `"direct"` | Absent or any unrecognized value → `"pr"` (DC-W1: direct-commit is an explicit opt-in only). Value is lowercased before matching. |

**How `dispatch_mode` is acted on** (task 3, `wiki_watch_dispatch.py`). After the documenter authors its changes on a branch, the cycle commits, runs the **PII guard, then pushes** (the in-engine pre-check; the repo's pre-push hook is the hard enforcer), and dispatches per mode:

| Mode | Dispatch behavior |
|---|---|
| `pr` (default) | Opens a pull request via the `gh` CLI for a human to merge — the PR is the async preview boundary (DC-W1). Branch is deterministic (`wiki-watch/<repo-slug>-<short-token>`), so a re-run reuses it (no duplicate PRs). |
| `direct` | Commits straight to the wiki's **default branch** — explicit per-repo opt-in for a trusted repo. |
| `pr`, but `gh` unavailable / unauthenticated | **Skips** the dispatch. It does **not** silently downgrade to direct-commit — that would bypass the human-merge boundary. |

Every git/`gh` step graceful-skips on failure (no hard-fail).

The CLI `run-config <repo_root>` subcommand prints the normalized `watch_sources` + `dispatch_mode` (exit `0`), or a `{"skipped": true, ...}` reason (exit `1`) when the marker is absent / unreadable.

## Wiki target — `repo_registry` `wiki_path`

Which wiki a watched repo maps to. The registry (`<vault>/_meta/repos.json`) already carries an optional per-entry `wiki_path`, but shipped **no lookup**; task 1 adds the net-new resolver. It matches the watched repo by `root_path` (path-normalized, precedence) or `slug`, then resolves the target:

| Case | Behavior |
|---|---|
| `wiki_path` present | Resolve to that path (normalized). |
| `wiki_path` absent | Fall back to `<root_path>/wiki` **only if that dir exists**, else skip. |
| repo unregistered (no matching entry) | Skip — the watcher no-ops for that repo. |

Resolution reaches the registry through a **path-fallback shell-out** to agentm's `repo_registry.py` (`$AGENTM_SCRIPTS_DIR/repo_registry.py` → co-located → `../lib/install/python/`). The agentm kernel is **not folded into crickets** (parent Dependencies bucket B); when agentm is unreachable the resolver **graceful-skips** (returns `[]`), so the watcher no-ops rather than hard-failing. Entry points: `resolve_wiki_target_for_repo(...)`, `list_repos_via_registry(...)`. The CLI `wiki-target <repo_root> [--slug X]` prints the resolved `wiki_target` (exit `0`), or a `{"skipped": true, ...}` reason (exit `1`).

## State and audit (not config, but config-adjacent)

State lives under a `wiki-watch/` leaf — resolved by `resolve_state_dir(repo_root)` via a shell-out to `harness_memory.py vault-state-path wiki-watch` to `<vault>/projects/<slug>/_harness/wiki-watch/` in vault mode, falling back to `<repo>/.harness/wiki-watch/` when agentm is unreachable or the vault is unavailable (DC-W6). Two files back idempotency:

| File | Carries |
|---|---|
| `cursors.json` | per-source high-water mark (git SHA, or sha256 content hash for non-git sources) — advances only after a token is fully processed |
| `pending.json` | the token mid-processing + its `dispatched` paths (no double-dispatch on re-run) + a `failures` map driving exponential backoff |

The audit log is a JSONL file, `audit.log`, alongside these under the same `wiki-watch/` leaf (task 3 added `append_audit` / `read_audit`). It records each cycle's `saw → decided → dispatched` trail with PR links, and is **local and never committed**. The detection feed reads `watch_sources` as the inclusion filter, then drops noise (generated / vendored / transient trees and the output `wiki/`) via the significance pre-filter before judging doc-worthiness — see [§ What gets watched vs. filtered as noise](#what-gets-watched-vs-filtered-as-noise) below.

## What gets watched vs. filtered as noise

Before any candidate reaches the doc-worthiness judge, a deterministic, coarse **significance pre-filter** drops obvious noise: generated/vendored/transient trees (`.git`, `__pycache__`, `node_modules`, `dist`, `build`, `target`, `.venv`, lockfiles, `*.pyc`, `*.min.js`, `.DS_Store`, …) — **and the output `wiki/` tree**, since watching the documenter's own writes would loop the watcher back onto itself. Everything else is kept (the filter is permissive by design): code, `PLAN.md`/`ROADMAP.md`, and design docs all pass through. This is only the coarse gate — the fine, doc-worthiness judgment runs later in the cycle (see [How to run the wiki-watcher](Run-The-Wiki-Watcher) for the run flow).

## Related

- [How to run the wiki-watcher (W1)](Run-The-Wiki-Watcher) — the task-oriented walkthrough.
- [Antigravity limitations](Antigravity-Limitations) — why scheduling (the loop that re-invokes this engine) is Claude-first.
- [Compatibility](Compatibility) — supported hosts + per-manifest `supported_hosts` contract.
- [Wiki-watcher (W1) design](../explanation/designs/wiki-maintenance/parts/wiki-watcher.md) — the index-vs-run-config split (DC-8) and the rest of the rationale.
