<!-- Status: implemented — the wiki-maintenance wiki-watcher. Config contract: three sources (enablement · run-config · wiki-target), no dedicated config file, run-config never in the vault (the vault holds the cross-device index; the on-host marker holds run config). -->

# Wiki-watch config

The **wiki-watcher** keeps a wiki in sync with its source repo automatically. Your docs track your code instead of drifting. It watches your repo's docs and code for **doc-worthy** changes. It looks at `PLAN.md`, `ROADMAP.md`, `designs/`, ADRs, tracked `.md`, and source files. When it finds a change, it dispatches the `documenter` to author the wiki update and open a PR for review.

It is an **idempotent single-cycle engine you run on a loop**. Each invocation runs one `detect → judge → author → dispatch` cycle and exits. You re-invoke it with Claude Code `/loop` or cron. This keeps your wiki up to date **asynchronously as you work**. Cursors and a processed-set make repeated runs safe.

This is the async path. It is distinct from the synchronous path. The synchronous path is the phase-boundary dispatch built into the development-lifecycle commands. The commands `/plan`, `/work`, `/release`, and `/bugfix` run the same `documenter` in-session the moment a phase completes. The watcher reuses that documenter on a loop for doc-worthy changes outside a phase boundary. This covers work outside the harness flow, or a repo you are not driving through the phase commands. That is why it runs decoupled, autonomous, and PR-gated. To drive it, see [How to run the wiki-watcher](Run-The-Wiki-Watcher). For the rationale, read [the design](crickets-wiki).

There is no dedicated config file. The watcher reads three sources. Each source lives with the layer that owns it. The device config says whether the watcher may run at all. The per-repo marker says how it runs. The vault's repo registry says which wiki it writes to. Run config never lives in the vault. The vault carries the cross-device index. Everything about how this machine runs stays on this machine.

## ⚡ Quick Reference

| Config | Where | Layer | Carries |
|---|---|---|---|
| **Enablement** | `<install-prefix>/.agentm-config.json` | on-host (device) | the device on/off toggle — opt-in |
| **Run config** | `<repo>/.harness/wiki-watch.json` | on-host, per-repo | `watch_sources` + `dispatch_mode`; its **presence** is the per-repo opt-in |
| **Wiki target** | the repo registry (`<vault>/_meta/repos.json`, `wiki_path`) | vault (index) | which wiki a watched repo writes to |

The watcher reads all three defensively. An absent, unreadable, or malformed source resolves to its safe default (disabled / skip). It never throws an error.

## Enablement — `.agentm-config.json`

The device toggle is a plain on/off switch. The watcher reads it without touching the vault. The install prefix resolves from `$AGENTM_INSTALL_PREFIX` (default `~/.claude`). You can use two shapes. The nested block is canonical. The top-level key is an alias:

```jsonc
{ "wiki_watch": { "enabled": true } }   // canonical
{ "wiki_watch_enabled": true }          // alias shorthand
```

The watcher dispatches autonomously. Enablement is **opt-in**. An absent, unreadable, or falsey config resolves to **disabled**.

## Run config — `<repo>/.harness/wiki-watch.json`

The marker is a small per-repo file carrying the run config. Its **presence is the per-repo opt-in**. If you omit the marker, the watcher skips that repo. If you write a malformed marker, the watcher logs to stderr and then skips.

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

**Dispatch.** The documenter authors its changes on a branch. Next, the cycle commits, runs the PII guard, pushes, and dispatches by mode:

| Mode | Behavior |
|---|---|
| `pr` (default) | opens a pull request via `gh` for a human to merge — the async preview boundary. The branch is deterministic (`wiki-watch/<repo-slug>-<token>`), so a re-run reuses it (no duplicate PRs). |
| `direct` | commits straight to the wiki's default branch — an explicit opt-in for a trusted repo. |
| `pr`, `gh` unavailable | **skips** — it never silently downgrades to direct-commit (that would bypass the human-merge boundary). |

Every git / `gh` step graceful-skips on failure.

## Wiki target — the repo registry

The registry says which wiki a watched repo writes to. The registry is located at `<vault>/_meta/repos.json`. It carries an optional per-entry `wiki_path`. The watcher matches the repo by `root_path` (precedence) or `slug`. Then it resolves the path:

| Case | Behavior |
|---|---|
| `wiki_path` present | resolve to that path |
| `wiki_path` absent | fall back to `<root_path>/wiki` **only if that dir exists**, else skip |
| repo unregistered | skip — the watcher no-ops for it |

Resolution shells out to agentm's repo registry. When agentm is unreachable, it **graceful-skips**. The watcher no-ops rather than failing. The agentm kernel is not folded into crickets.

## State

Run state lives under a `wiki-watch/` leaf. In vault mode, this is `<vault>/projects/<slug>/_harness/wiki-watch/`. It falls back to `<repo>/.harness/wiki-watch/` when the vault is unavailable. You will find three files:

| File | Carries |
|---|---|
| `cursors.json` | per-source high-water mark (git SHA, or a content hash for non-git sources) — advances only after a token is fully processed |
| `pending.json` | the in-flight token + its dispatched paths (no double-dispatch on re-run) + a failures map driving exponential backoff |
| `audit.log` | a JSONL `saw → decided → dispatched` trail with PR links — local, never committed |

## What's watched vs. filtered as noise

Candidates face a coarse **significance pre-filter** before they reach the doc-worthiness judge. This filter drops obvious noise. It drops generated, vendored, and transient trees (`.git`, `__pycache__`, `node_modules`, `dist`, `build`, `.venv`, lockfiles, `*.pyc`, `*.min.js`, …). It also drops **the output `wiki/` tree**. Watching the documenter's own writes would loop the watcher onto itself. Everything else passes. The filter is permissive. The fine doc-worthiness judgment runs later in the cycle.

## Related

- [How to run the wiki-watcher](Run-The-Wiki-Watcher) — the task-oriented walkthrough.
- [Antigravity limitations](Antigravity-Limitations) — why the scheduling that re-invokes this engine is Claude-first.
- [Compatibility](Compatibility) — supported hosts.
- [Wiki-watcher design](crickets-wiki) — the index-vs-run-config split and the rest of the rationale.
