<!-- Status: implemented — the wiki-maintenance wiki-watcher. Config contract: three sources (enablement · run-config · wiki-target), no dedicated config file, run-config never in the vault (the vault holds the cross-device index; the on-host marker holds run config). -->

# Wiki-watch config

The **wiki-watcher** keeps a wiki in sync with its source repo automatically, so docs track the code instead of drifting. It watches the repo's docs and code — `PLAN.md`, `ROADMAP.md`, `designs/`, ADRs, tracked `.md`, source — for **doc-worthy** changes, and dispatches the `documenter` to author the wiki update and open a PR for review. It is an **idempotent single-cycle engine you run on a loop**, not a daemon and not a one-shot: each invocation runs one `detect → judge → author → dispatch` cycle and exits, and something re-invokes it (Claude Code `/loop` or cron) so the wiki keeps up **asynchronously as you work** — cursors and a processed-set make repeated runs safe.

**It's the async path — not run synchronously.** The synchronous path is the phase-boundary dispatch built into the developer-workflows commands: `/plan`, `/work`, `/release`, and `/bugfix` run the same `documenter` in-session the moment a phase completes. The watcher reuses that documenter on a loop for doc-worthy changes that *aren't* tied to a phase boundary — work outside the harness flow, or a repo you aren't driving through the phase commands — which is why it's decoupled, autonomous, and PR-gated rather than synchronous. To drive it, see [How to run the wiki-watcher](Run-The-Wiki-Watcher); for the rationale, [the design](wiki-watcher).

This page is the **config contract**. There is no dedicated config file — the watcher reads three sources, each owned by a different layer, and run config never lives in the vault: the vault holds the cross-device *index*, the on-host marker holds *run config*.

## ⚡ Quick Reference

| Config | Where | Layer | Carries |
|---|---|---|---|
| **Enablement** | `<install-prefix>/.agentm-config.json` | on-host (device) | the device on/off toggle — opt-in |
| **Run config** | `<repo>/.harness/wiki-watch.json` | on-host, per-repo | `watch_sources` + `dispatch_mode`; its **presence** is the per-repo opt-in |
| **Wiki target** | the repo registry (`<vault>/_meta/repos.json`, `wiki_path`) | vault (index) | which wiki a watched repo writes to |

All three are read defensively — an absent, unreadable, or malformed source resolves to its safe default (disabled / skip), never an error.

## Enablement — `.agentm-config.json`

Device-level on/off, read vault-free. The install prefix resolves from `$AGENTM_INSTALL_PREFIX` (default `~/.claude`). Two shapes are recognized — the nested block is canonical, the top-level key an alias:

```jsonc
{ "wiki_watch": { "enabled": true } }   // canonical
{ "wiki_watch_enabled": true }          // alias shorthand
```

The watcher dispatches autonomously, so enablement is **opt-in**: an absent, unreadable, or falsey config resolves to **disabled**.

## Run config — `<repo>/.harness/wiki-watch.json`

A per-repo marker carrying the run config. Its **presence is the per-repo opt-in** — no marker means the watcher skips that repo (a malformed marker also logs to stderr, then skips).

```jsonc
{
  "watch_sources": ["PLAN.md", "designs/"],   // repo-relative paths / globs
  "dispatch_mode": "pr"                         // "pr" | "direct"
}
```

| Field | Values | Default + fallback |
|---|---|---|
| `watch_sources` | list of repo-relative paths / globs | absent / non-list / empty → `["."]` (the whole repo — the significance pre-filter drops noise); non-string entries dropped |
| `dispatch_mode` | `"pr"` \| `"direct"` | absent or unrecognized → `"pr"` (direct-commit is an explicit opt-in only); lowercased before matching |

**Dispatch.** After the documenter authors its changes on a branch, the cycle commits, runs the PII guard, pushes, and dispatches by mode:

| Mode | Behavior |
|---|---|
| `pr` (default) | opens a pull request via `gh` for a human to merge — the async preview boundary. The branch is deterministic (`wiki-watch/<repo-slug>-<token>`), so a re-run reuses it (no duplicate PRs). |
| `direct` | commits straight to the wiki's default branch — an explicit opt-in for a trusted repo. |
| `pr`, `gh` unavailable | **skips** — it never silently downgrades to direct-commit (that would bypass the human-merge boundary). |

Every git / `gh` step graceful-skips on failure.

## Wiki target — the repo registry

Which wiki a watched repo maps to. The registry (`<vault>/_meta/repos.json`) carries an optional per-entry `wiki_path`; the watcher matches the repo by `root_path` (precedence) or `slug`, then resolves:

| Case | Behavior |
|---|---|
| `wiki_path` present | resolve to that path |
| `wiki_path` absent | fall back to `<root_path>/wiki` **only if that dir exists**, else skip |
| repo unregistered | skip — the watcher no-ops for it |

Resolution shells out to agentm's repo registry; when agentm is unreachable it **graceful-skips** (the watcher no-ops rather than failing). The agentm kernel is not folded into crickets.

## State

Run state lives under a `wiki-watch/` leaf — `<vault>/projects/<slug>/_harness/wiki-watch/` in vault mode, falling back to `<repo>/.harness/wiki-watch/` when the vault is unavailable. Three files:

| File | Carries |
|---|---|
| `cursors.json` | per-source high-water mark (git SHA, or a content hash for non-git sources) — advances only after a token is fully processed |
| `pending.json` | the in-flight token + its dispatched paths (no double-dispatch on re-run) + a failures map driving exponential backoff |
| `audit.log` | a JSONL `saw → decided → dispatched` trail with PR links — local, never committed |

## What's watched vs. filtered as noise

Before any candidate reaches the doc-worthiness judge, a coarse **significance pre-filter** drops obvious noise — generated / vendored / transient trees (`.git`, `__pycache__`, `node_modules`, `dist`, `build`, `.venv`, lockfiles, `*.pyc`, `*.min.js`, …) **and the output `wiki/` tree** (watching the documenter's own writes would loop the watcher onto itself). Everything else passes — the filter is permissive; the fine doc-worthiness judgment runs later in the cycle.

## Related

- [How to run the wiki-watcher](Run-The-Wiki-Watcher) — the task-oriented walkthrough.
- [Antigravity limitations](Antigravity-Limitations) — why the scheduling that re-invokes this engine is Claude-first.
- [Compatibility](Compatibility) — supported hosts.
- [Wiki-watcher design](wiki-watcher) — the index-vs-run-config split and the rest of the rationale.
