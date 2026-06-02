# Compatibility

Hosts and surfaces Crickets is verified to run with.

## Supported hosts

Crickets customizations declare host compatibility per-manifest via the YAML `supported_hosts:` field. The installer reads that field and dispatches the customization to the right host-specific path.

| Host | Path convention | Status |
|---|---|---|
| **Claude Code** (Anthropic CLI / IDE extension) | `.claude/{skills,agents,hooks,commands}/<name>/` | ✅ first-class — primary development surface, CI-verified on every push |
| **Antigravity 2.0** (Google IDE) + **Antigravity CLI (`agy`)** | `.agents/{skills,workflows,rules}/<name>/` (project) + `~/.gemini/config/plugins/<name>/` (user-global, plugin-wrapped) | ✅ first-class as of v1.2.0 — CI-verified on every push. **Migrated from `.agent/` (singular) to `.agents/` (plural) in v1.2.0** per [ADR 0011](decisions/0011-antigravity-2-host-support). Antigravity CLI replaced Gemini CLI 2026-05-19; consumer Gemini CLI sunsets 2026-06-18. |

See [Per-Host-Paths](Per-Host-Paths) for the full per-kind destination matrix.

## Supported operating systems

| OS | Tested via | Frequency |
|---|---|---|
| Linux (`ubuntu-latest`) | [`.github/workflows/tests-linux.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/tests-linux.yml) | Every push + every PR |
| macOS (`macos-latest`) | [`.github/workflows/tests-mac.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/tests-mac.yml) | Every push + every PR |
| Windows (`windows-latest`, PowerShell 7+) | [`.github/workflows/tests-windows.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/tests-windows.yml) | Every push + every PR |

The single aggregate `CI` badge in the README + wiki Home points at a dedicated [`ci-all.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/ci-all.yml) workflow that waits for all 3 OS workflows then reports a combined success/failure. Diagnostic drill-down: click the badge → Actions tab → pick the OS that's failing.

## Per-customization compatibility

Each customization in the shipped catalog declares its own `supported_hosts` in the manifest:

| Kind | Customization | Hosts |
|---|---|---|
| skill (2) | `pii-scrubber`, `dependabot-fixer` | `[claude-code, antigravity]` |
| agent (2) | `evaluator`, `diataxis-evaluator` | `[claude-code, antigravity]` (sub-agent-as-skill on Antigravity) |
| hook (3) | `kill-switch`, `steer`, `commit-on-stop` | `[claude-code]` (Antigravity hook-surface support tracked separately — see Known gaps below) |
| bundle (2) | `quality-gates` (claude-code-only because contents include hooks), `example-bundle` (`[claude-code, antigravity]`) | inherits from contents |
| plugin (1) | `example-plugin` (reference; Antigravity 2.0 + agy) | `[antigravity]` |

The installer respects each manifest's `supported_hosts` — installing into a target project only writes the customizations declared for the host(s) you're targeting.

## Known gaps — Antigravity 2.0 surface

Three Antigravity 2.0 primitive surfaces have **no file-based authoring path** as of crickets v1.2.0. Customizations targeting these surfaces are out of scope for the crickets installer; users must hand-author them in a Python SDK environment if they want to use them.

### Hooks gap

Antigravity 2.0 / agy hooks are **Python decorators** registered at agent-creation time via `LocalAgentConfig(hooks=[...])` (from `google.antigravity.hooks`). The 9 hook types (`on_session_start`, `on_session_end`, `pre_turn`, `post_turn`, `pre_tool_call_decide`, `post_tool_call`, `on_tool_error`, `on_compaction`, `on_interaction`) cover most use cases that Claude Code's file-based hooks cover, but they require Python SDK integration to register — no `.agents/hooks/` directory or `hooks.json` config file exists.

**Crickets's 3 hooks** (`kill-switch`, `steer`, `commit-on-stop`) ship `supported_hosts: [claude-code]`-only. (The memory hooks + `evidence-tracker` are agentm-native, not crickets.) See [ADR 0009 § Antigravity re-audit outcome](decisions/0009-evidence-tracker-hook) for the rationale — note its "no Antigravity file-based hook surface" finding is superseded by Antigravity 2.0 (tracked in the crickets-ADR-overhaul follow-up).

**Future direction (deferred, FOLLOWUP candidate)**: a separate Python sidecar package (`crickets-hooks-py`?) could translate crickets's file-based hook scripts to SDK decorator registration at agent-author boot time. Out of scope for v1.2.0.

> [!NOTE]
> **Gotcha for hook authors — resolve the workspace from the host's hook-input contract, never from `cwd`.** A bash hook that checks `.harness/…` (or any project-relative path) relative to `cwd` works on Claude Code but is silently inert on Antigravity, because the two hosts invoke plugin hooks differently:
> - **Claude Code** — runs hooks with `cwd` = the project root, and also supplies it on stdin (`cwd`) and via `$CLAUDE_PROJECT_DIR`.
> - **Antigravity / agy** — runs plugin hooks with `cwd` = the *plugin dir* (not the workspace), and supplies the workspace **only** on stdin as JSON `{"workspacePaths":["<root>"]}` (no env var).
>
> A host-portable hook reads stdin, parses it with a real JSON parser (`python3 json.load`, top-level keys only — a `sed`/regex parser mismatches nested or pretty-printed payloads), and resolves the root as `workspacePaths[0]` (Antigravity) → stdin `cwd` (Claude) → `$CLAUDE_PROJECT_DIR` → `cwd` (fallback), then `cd`s into it before any relative logic. The shipped `kill-switch`, `steer`, and `commit-on-stop` hooks do this; see `scripts/test_developer_hooks_workspace.py` for the contract cases. (Fixed crickets v3.0 #40 part 6 T2; full plugin-authoring treatment lands in the upcoming "Develop a crickets plugin locally" how-to + ADR 0013/0014.)

### Scheduled tasks (triggers) gap

Antigravity 2.0 / agy triggers — the host's scheduled-task primitive — are **Python registration patterns**: `every(seconds, callback)`, `on_file_change(path, callback)`, custom async functions. Registered via `LocalAgentConfig(triggers=[...])`. No file-based config; trigger callbacks are Python code running in the agent process.

**Crickets doesn't ship trigger primitives** in v1.2.0. The Agent M V6 roadmap (`agentm/.harness/ROADMAP-AgentMemoryV6.md`) contemplates a scheduled-sidecar framework as a future cross-host primitive; if/when that lands, it may also provide an Antigravity-trigger integration path. See agentm V6 for forward-looking context.

### Multi-agent orchestration gap

Antigravity 2.0's multi-agent orchestration is **operator-facing**: the parent agent decides when to spawn subagents via the built-in `start_subagent` tool, enabled by default via `CapabilitiesConfig(enable_subagents=True)`. No plugin-author surface for orchestration policy (which subagents to spawn, when, with what context).

**Crickets's contribution to orchestration** is the sub-agent-as-skill pattern: ship SKILL.md files (via `kind: agent` or `kind: plugin`); the parent agent treats them as callable sub-agents via `start_subagent`. The agents-available-for-spawning surface is what crickets controls; the spawning decisions are the parent agent's.

Deeper orchestration design (e.g. specifying spawn policy via manifest fields) would require a customization kind we don't yet have — and unclear value vs. letting the parent agent reason about it dynamically. Out of scope.

## Sibling repo

Crickets pairs with **[Agent M (`agentm`)](https://github.com/alexherrero/agentm)** — the structural backend harness (phase-gated workflow, auto-recall, on-disk state). Agent M is tested on the same OS matrix; both repos ship paired releases per [ADR 0006](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0006-crickets-split.md).

## Out-of-scope hosts

Hosts that previously had adapters or were considered but are not supported now:

- **Gemini CLI** — dropped in v0.9.0 (2026-05-17). Google replaced Gemini CLI with the new Antigravity CLI (`agy`) on 2026-05-19; consumer Gemini CLI sunsets 2026-06-18 ([transition blog](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)). Enterprise tier keeps Gemini CLI indefinitely (out of scope for crickets). **Antigravity CLI IS supported as of crickets v1.2.0** (shares the agent harness with Antigravity 2.0 desktop; single `antigravity` slug).
- **Codex** — never had a Crickets adapter; was dropped from the harness in v1.0.0 per harness ADR 0005.

## When a host stops working

If a host's CI starts failing or a customization's adapter goes stale:

1. Check the host's release notes for surface changes (`.claude/` shape, `.agent/` shape, command syntax, etc.)
2. Verify the affected customization's manifest `supported_hosts` field still matches reality
3. Run `bash scripts/smoke-install-bash.sh` locally; if it fails on the affected host, you've reproduced
4. Patch the installer dispatch logic OR the customization's manifest, whichever resolves the surface change at the right layer

For adding new hosts, see [ADR 0006 — Split customizations into crickets](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0006-crickets-split.md) for the customization contract + [Manifest-Schema](Manifest-Schema) for the per-customization declaration shape.
