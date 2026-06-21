# ADR 0011 — Antigravity 2.0 + Antigravity CLI host support

> [!NOTE]
> Status: accepted
> Date: 2026-05-25

## Context

Google released **Antigravity 2.0** (desktop) and the **Antigravity CLI** (Go-built; canonical command `agy`) on 2026-05-19 at I/O. The Antigravity CLI replaces Gemini CLI, which was removed from crickets in v0.9.0 per [ADR 0006](0006-gemini-cli-host-removal). Consumer Gemini CLI sunsets on 2026-06-18 — users migrating during that window will hit crickets's install scripts, and the toolkit must support their new target host cleanly.

Antigravity 2.0 + Antigravity CLI **share the same agent harness** (per the [Google Developers blog post on the transition](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)). The same customization surface works on both. Wave 1 research for [plan #16](https://github.com/alexherrero/agentm/blob/main/.harness/PLAN.md) (operator-local) characterized the surface:

- **Plugins** — JSON-manifested directory packages (`plugin.json` at root + 1-N nested `SKILL.md` skills). Distributed via `agy plugin install <target>`. User-global delivery path: `~/.gemini/config/plugins/<plugin-name>/`. The new primitive vs Antigravity 1.x.
- **Skills** — Same `SKILL.md` shape as Antigravity 1.x (YAML frontmatter with `name` + `description`; markdown body). **Discovery path changed**: agy v1.0.2 scans `<workspace>/.agents/skills/<skill_name>/SKILL.md` (plural `.agents/`), NOT Antigravity 1.x's `.agent/skills/` (singular). Confirmed via binary string inspection of the locally-installed `agy` binary at `~/.local/bin/agy`.
- **Sub-agents** — Spawned dynamically by the parent agent via the built-in `start_subagent` tool, enabled by default via `CapabilitiesConfig(enable_subagents=True)`. No `.subagents/` directory, no file-based subagent manifest. Crickets's sub-agent-as-skill pattern (`kind: agent` → `.agents/skills/<name>/SKILL.md` on Antigravity, treating the SKILL.md as a callable subagent) remains correct.
- **Hooks** — SDK Python decorators registered via `LocalAgentConfig(hooks=[...])`. No file-based authoring surface. Crickets's 8 hooks stay `supported_hosts: [claude-code]`-only; see [ADR 0009](0009-evidence-tracker-hook) re-audit outcome.
- **Triggers (scheduled tasks)** — Python `every(60, callback)` / `on_file_change(...)` registration. No file-based authoring surface.
- **Multi-agent orchestration** — Operator-facing; no plugin-author surface.

## Decision

Crickets adopts Antigravity 2.0 + Antigravity CLI as a **single supported host** under the existing `antigravity` slug (no split into `antigravity` + `antigravity-cli`). Specific implementation calls:

### Single `antigravity` slug for both desktop + CLI

The shared agent harness means a single dispatch path covers both surfaces. Splitting would create parity-check noise without functional benefit. If primitive surfaces diverge meaningfully in the future (e.g. agy adds a hook surface the desktop lacks), revisit by adding `antigravity-cli` slug at that time.

### Skill dispatch path: `.agents/` (plural) for Antigravity

Update installer dispatch:
```diff
- antigravity → <project>/.agent/skills/<name>/SKILL.md     # v1.x convention
+ antigravity → <project>/.agents/skills/<name>/SKILL.md    # 2.0 convention
```

One-letter rename in `crickets/install.sh` `install_skill()` + `install_agent()` functions + `crickets/install.ps1` equivalents. Same path applies to `kind: agent` (sub-agent-as-skill remains the dispatch for `kind: agent` on Antigravity).

**Breaking change for users with crickets v1.0.x installed against Antigravity 1.x's `.agent/` convention.** v1.2.0 release notes call out the migration path: re-run `bash install.sh --update <target-project>` OR manually `mv .agent .agents` in their target project. Antigravity 1.x users who haven't upgraded keep `.agent/` working as long as they stay on 1.x; once they upgrade to 2.0, they need the new path.

### New `kind: plugin` primitive

Add `plugin` to `KIND_ENUM` in `scripts/validate-manifests.py`. Plugin manifest source format: YAML frontmatter on `plugins/<name>/plugin.md` (toolkit-side, for parity with other crickets primitives) + nested skills under `plugins/<name>/skills/<skill-name>/SKILL.md`. Installer generates `plugin.json` JSON at install time from the YAML frontmatter for Antigravity-side delivery.

Plugin delivery path: `~/.gemini/config/plugins/<plugin-name>/plugin.json` + nested skills at `~/.gemini/config/plugins/<plugin-name>/skills/<skill-name>/SKILL.md`. **User-global** (not project-scoped) — matches Antigravity's plugin model.

### Sub-agent-as-skill preserved (no migration)

The 4 existing sub-agents (`evaluator`, `adapt-evaluator`, `diataxis-evaluator`, `memory-idea-researcher`) continue to dispatch to `<project>/.agents/skills/<name>/SKILL.md` on Antigravity (with the path-rename per above). No new directory slot; no breaking change in the SKILL.md authoring shape. The host treats the SKILL.md as a callable sub-agent via its built-in `start_subagent` tool.

[ADR 0002](0002-evaluator-design) gets a follow-up note documenting the 2.0 confirmation. No structural change to the sub-agent-as-skill design.

### File-based hook / trigger / multi-agent surfaces stay deferred

Crickets's 8 hooks stay `supported_hosts: [claude-code]`-only. The hook surface gap is documented in `wiki/reference/Compatibility.md` Known gaps section. A future Python sidecar adapter (translating crickets's file-based hook scripts to SDK decorator registration at agent-author boot time) is captured as a ROADMAP candidate but not in scope for this ADR.

Scheduled tasks (Antigravity triggers) and multi-agent orchestration similarly stay gap-documented; no crickets-side primitive ships for these in v1.2.0.

### `gemini-cli` slug stays removed

[ADR 0006](0006-gemini-cli-host-removal) stands. Antigravity CLI is a new, separate host slug (`antigravity`, sharing with the desktop), not a Gemini CLI revival. Consumer Gemini CLI sunsets 2026-06-18; enterprise tier keeps it indefinitely (out of crickets scope).

## Why not the alternative

### Split `antigravity` + `antigravity-cli` slugs

Considered. Rejected because:
- The shared agent harness means dispatch is identical; splitting doubles the parity-check matrix for no benefit.
- Per-host opt-outs are unlikely to be useful (every customization that works on Antigravity 2.0 desktop also works on agy and vice versa).
- Future divergence (if it materializes) can be handled by adding the second slug at that point without rework.

### Adopt `.subagents/` first-class slot

Originally considered as the locked plan call; **reverted** during Wave 1 research. There is no `.subagents/` slot in agy v1.0.2 or Antigravity IDE — confirmed via binary string inspection + filesystem probes. Community frameworks (`oh-my-antigravity`, `antigravity-subagents`) invented their own subagent file systems; those are not canonical. Sub-agent-as-skill via `.agents/skills/<name>/SKILL.md` remains the correct pattern.

### Plugin-wrap every crickets skill for Antigravity

Considered. Rejected because:
- Plugin delivery is user-global (`~/.gemini/config/plugins/`) — doesn't fit crickets's per-project install model.
- Project-local skill discovery via `.agents/skills/` works directly; plugin-wrapping is unnecessary for project-scoped customizations.
- Plugin authoring is a complementary surface (for shareable bundles distributed via marketplaces or git URLs), not a replacement for project-scoped install.

## Consequences

### Positive

- Crickets supports Antigravity 2.0 + Antigravity CLI from v1.2.0 onward, ahead of the 2026-06-18 Gemini CLI consumer sunset.
- The plugin primitive opens crickets up to Antigravity marketplace distribution (`agy plugin install <url>` against a published crickets plugin).
- Backward-compat surface: `agy plugin import claude` can import Claude Code customizations directly, giving a complementary entry path for users not using crickets's installer.
- ADRs 0002, 0006, 0009 amended with re-audit outcomes documenting the host's evolution.

### Negative

- One-letter `.agent/` → `.agents/` rename is a breaking change for v1.0.x users with active Antigravity installs. Mitigation: clear CHANGELOG migration callout + `bash install.sh --update` smooth-path.
- Crickets's 8 hooks remain `[claude-code]`-only; Antigravity users don't get hook-style behaviors. Documented gap; deferred to a future ROADMAP candidate (Python sidecar adapter).
- Plugin delivery (Antigravity-side) is user-global, not project-scoped. Crickets's installer needs a different invocation mode for plugin dispatch (likely `bash install.sh --plugin <name>` writing to `~/.gemini/config/plugins/`) — different from the project-target invocation it currently uses.
- Operator must keep `agy` installed locally to validate the smoke install (task 13 of plan #16) — adds a dev-environment dependency.

### Load-bearing assumptions

1. **Antigravity 2.0 desktop also uses `.agents/` plural.** Not directly verified (no live Antigravity 2.0 desktop install available during Wave 1 research). Inferred from the shared agent harness with agy v1.0.2. Re-audit trigger: if a user reports Antigravity 2.0 desktop NOT finding skills at `.agents/`, revisit the dispatch.
2. **The `agy` v1.0.2 binary string `{workspace}/.agents/skills/{skill_name}/SKILL.md` is canonical** for the host's project-local discovery path. Re-audit trigger: future agy releases change the binary string OR Google publishes contradicting official docs.
3. **`supported_hosts: [claude-code, antigravity]` semantics** continue: each manifest declares the hosts it works on; the installer dispatches per the per-host paths table. Adding `kind: plugin` doesn't change this — plugins simply declare `supported_hosts: [antigravity]` typically.

## Related

- [ADR 0001](crickets-hld) — the customization manifest schema this ADR extends.
- [ADR 0002](0002-evaluator-design) — sub-agent-as-skill pattern (confirmed unchanged for 2.0).
- [ADR 0006](0006-gemini-cli-host-removal) — Gemini CLI removal; this ADR clarifies that Antigravity CLI is a separate host, not a revival.
- [ADR 0009](0009-evidence-tracker-hook) — hook design; re-audit trigger met by this ADR with outcome "hooks stay claude-code-only."
- Plan #16 (`agentm/.harness/PLAN.md` — operator-local) — implementation plan.
- Wave 1 research artifacts (`agentm/.harness/designs/antigravity-host-support/` — operator-local):
  - `plugin-manifest.md` — plugin schema research.
  - `hook-event-mapping.md` — hook surface gap analysis.
  - `subagent-spec.md` — subagent slot reality.
  - `smoke-test-skill-discovery.md` — `.agents/` (plural) finding.
- [Antigravity 2.0 launch announcement](https://antigravity.google/blog/introducing-google-antigravity-2-0).
- [Gemini CLI → Antigravity CLI transition blog](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/).
