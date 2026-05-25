# Compatibility

Hosts and surfaces Crickets is verified to run with.

## Supported hosts

Crickets customizations declare host compatibility per-manifest via the YAML `supported_hosts:` field. The installer reads that field and dispatches the customization to the right host-specific path.

| Host | Path convention | Status |
|---|---|---|
| **Claude Code** (Anthropic CLI / IDE extension) | `.claude/{skills,agents,hooks,commands}/<name>/` | ✅ first-class — primary development surface, CI-verified on every push |
| **Antigravity** (Google IDE + Antigravity CLI) | `.agent/{skills,agents,hooks,commands}/<name>/` | ✅ first-class — CI-verified on every push |

See [Per-Host-Paths](Per-Host-Paths) for the full per-kind destination matrix.

## Supported operating systems

| OS | Tested via | Frequency |
|---|---|---|
| Linux (`ubuntu-latest`) | [`.github/workflows/tests-linux.yml`](https://github.com/alexherrero/agent-toolkit/blob/main/.github/workflows/tests-linux.yml) | Every push + every PR |
| macOS (`macos-latest`) | [`.github/workflows/tests-mac.yml`](https://github.com/alexherrero/agent-toolkit/blob/main/.github/workflows/tests-mac.yml) | Every push + every PR |
| Windows (`windows-latest`, PowerShell 7+) | [`.github/workflows/tests-windows.yml`](https://github.com/alexherrero/agent-toolkit/blob/main/.github/workflows/tests-windows.yml) | Every push + every PR |

The single aggregate `CI` badge in the README + wiki Home points at a dedicated [`ci-all.yml`](https://github.com/alexherrero/agent-toolkit/blob/main/.github/workflows/ci-all.yml) workflow that waits for all 3 OS workflows then reports a combined success/failure. Diagnostic drill-down: click the badge → Actions tab → pick the OS that's failing.

## Per-customization compatibility

Each customization in the shipped catalog declares its own `supported_hosts` in the manifest:

| Kind | Customization | Hosts |
|---|---|---|
| skill | `pii-scrubber`, `dependabot-fixer`, `ship-release`, `design`, `memory`, `diataxis-author` | `[claude-code, antigravity]` |
| agent | `evaluator` | `[claude-code]` |
| hook | `kill-switch`, `steer`, `commit-on-stop`, `evidence-tracker` | `[claude-code]` |
| bundle | `quality-gates`, `example-bundle` | inherits from contents |

The installer respects each manifest's `supported_hosts` — installing into a target project only writes the customizations declared for the host(s) you're targeting.

## Sibling repo

Crickets pairs with **[Agent M (`agentic-harness`)](https://github.com/alexherrero/agentic-harness)** — the structural backend harness (phase-gated workflow, auto-recall, on-disk state). Agent M is tested on the same OS matrix; both repos ship paired releases per [ADR 0006](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0006-agent-toolkit-split.md).

## Out-of-scope hosts

Hosts that previously had adapters or were considered but are not supported now:

- **Gemini CLI** — dropped in v0.9.0 (2026-05-17). Google replaced Gemini CLI with the new Antigravity CLI; we follow the upstream consolidation. Antigravity CLI adapter work is on the harness roadmap (item #17).
- **Codex** — never had a Crickets adapter; was dropped from the harness in v1.0.0 per harness ADR 0005.

## When a host stops working

If a host's CI starts failing or a customization's adapter goes stale:

1. Check the host's release notes for surface changes (`.claude/` shape, `.agent/` shape, command syntax, etc.)
2. Verify the affected customization's manifest `supported_hosts` field still matches reality
3. Run `bash scripts/smoke-install-bash.sh` locally; if it fails on the affected host, you've reproduced
4. Patch the installer dispatch logic OR the customization's manifest, whichever resolves the surface change at the right layer

For adding new hosts, see [ADR 0006 — Split customizations into agent-toolkit](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0006-agent-toolkit-split.md) for the customization contract + [Manifest-Schema](Manifest-Schema) for the per-customization declaration shape.
