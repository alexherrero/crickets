# ADR 0019 — Wiki provisioning: gate-distribution split + supersession-gated retirement

> [!NOTE]
> **Status:** accepted · **Date:** 2026-06-10

## Context

The wiki system ([Wiki design](wiki-design), [ADR 0018](0018-per-folder-sidebars)) had a structure, a linter, a publisher, and three maintenance loops — but no **provisioning** step. Standing a new repo's wiki up meant hand-copying files, which is exactly the drift the operator flagged: a moved `check-wiki.py` rots every copy. `wiki-init` makes provisioning one idempotent, preview-first action ([how-to](Provision-A-Repo-Wiki)).

Two of its calls were load-bearing and non-obvious enough to record here: **how the bundled `check-wiki.py` gate reaches a target's CI**, and **how the install retires the `~/.claude/` standalones crickets plugins now supersede** without deleting ones it shouldn't.

Open questions this resolves:

- How does a target repo's CI run the bundled `check-wiki.py` when GitHub Actions runners have no `${CLAUDE_PLUGIN_ROOT}`?
- Should every consumer **vendor** the gate (a copy that can rot) or **reference** it (which a CI runner can't resolve)?
- When the install retires superseded `~/.claude/` standalones, how does it avoid deleting standalones that *no* plugin provides (`design`, `memory`, `doctor`)?

## Decision

### 1. Gate distribution — reference for the agent, vendor for CI (a split)

The plugin bundles `check-wiki.py` once; **how a target reaches it depends on who runs the gate**, and the two runners differ in what they can resolve — so the distribution is a deliberate split, not one mechanism.

- **Agent path (Claude Code / Antigravity).** The plugin runtime exposes `${CLAUDE_PLUGIN_ROOT}`, so the agent runs the gate **by reference** (`${CLAUDE_PLUGIN_ROOT}/scripts/check-wiki.py`) — an upgrade re-points automatically, nothing to drift.
- **CI path (GitHub Actions).** Runners have **no `${CLAUDE_PLUGIN_ROOT}`** and no plugin checkout, so `wiki-init` **vendors** the gate into the target's `.github/scripts/check-wiki.py` and the workflow's `lint-wiki` job runs that copy. `wiki-init --resync-gate` re-vendors it after a plugin upgrade.

- **Why not vendor everywhere.** That's the drift the operator flagged — the next release moves the script and every copy rots. Referencing upgrades for free, so the agent path (which *can* reference) does.
- **Why not reference everywhere.** `${CLAUDE_PLUGIN_ROOT}` is a Claude Code plugin-runtime variable, **absent on GitHub Actions runners**; a referenced CI gate literally can't resolve a path. CI has no choice but to vendor.
- **Why a split, not one mechanism.** The two runners have different capabilities. Forcing one mechanism on both either breaks CI (reference) or rots the agent path (vendor). The split gives each runner the best it can do; `--resync-gate` pays down the vendored copy's only cost (staleness) on demand.

*(This re-locks an earlier "reference, not vendor" call in the design, which described a CI mechanism that couldn't run — reconciled 2026-06-10, [provisioning design](wiki-maintenance-provisioning) §3.)*

### 2. Supersession-gated standalone retirement

Installing crickets plugins should clean up the `~/.claude/` standalones they now supersede — **but only those**. For each *installed* crickets plugin, enumerate the skills/agents/commands it provides; for each, if a `~/.claude/{skills,agents,commands}/<name>` standalone exists that the plugin supersedes — matched by name **and** crickets-plugin provenance — remove it, preview-first, dry-run by default.

- **Why not blind removal** (delete every `~/.claude/` symlink into agentm). Dangerously wrong: it would delete `design`, `memory`, `doctor`, `last30days`, `adapt-evaluator`, `memory-idea-researcher` — agentm-native or third-party primitives no crickets plugin provides. That's behavior loss, not cleanup.
- **Why name + provenance, not name alone.** A bare name match could remove a same-named standalone the plugin doesn't actually provide. Gating on "an installed crickets plugin provides this primitive" keeps removal strictly inside the plugin's own surface.
- **Why preview-first / dry-run default.** Deleting under `~/.claude/` is operator-visible and hard to undo blind; the operator sees the exact list and confirms before anything is removed.

## Consequences

**Positive:**

- Provisioning is one idempotent, preview-first action instead of a hand-copy that drifts.
- The gate **upgrades for free where it can** (agent, by reference) and **stays fixable where it can't** (CI, vendored + `--resync-gate`).
- The retirement **can't reach outside the installed plugins' own primitives** — `design`/`memory`/`doctor` and friends are safe by construction.
- A provisioned repo's wiki can't publish broken (the `lint-wiki` job gates `update-wiki`), and crickets dogfoods the same workflow it ships.

**Negative:**

- The vendored CI copy can go **stale** between upgrades — mitigated by `--resync-gate`, but that's a manual step (no auto-refresh on the runner).
- The split is **two code paths** to maintain (reference + vendor) instead of one.
- The retirement's correctness rests on the **plugin→primitive enumeration being complete**; a mis-enumerated plugin could under- or over-remove.

**Load-bearing assumptions (re-audit triggers):**

- **GitHub Actions has no `${CLAUDE_PLUGIN_ROOT}`.** The entire CI-vendoring half exists because of this. **Re-audit if** GitHub Actions (or the plugin host) ever exposes a runner-visible plugin path, or crickets ships a Marketplace action that checks the plugin out on the runner — then CI could reference too, and the vendor half could retire.
- **`${CLAUDE_PLUGIN_ROOT}` resolves on the agent host.** The reference half assumes the plugin runtime sets it. **Re-audit if** a host stops exporting it — the agent path would have to vendor like CI.
- **Superseded standalones are name-matched *and* crickets-provenance-tagged.** **Re-audit if** any legitimately-standalone skill is ever flagged for removal, or a non-crickets primitive collides by name with a plugin primitive.
- **Targets are GitHub-Actions repos with a wiki enabled.** A different CI shape needs different wiring. **Re-audit if** a non-Actions target is provisioned (today: detect-and-skip with a printed manual step).

## Related

- [Provisioning design](wiki-maintenance-provisioning) — the full design; §3 the gate-distribution split, §4 the retirement.
- [Provision a repo's wiki](Provision-A-Repo-Wiki) — the how-to that walks `wiki-init`.
- [Wiki design](wiki-design) · [ADR 0018 — per-folder sidebars](0018-per-folder-sidebars) — the wiki system + IA this provisions.
- [ADR 0013 — bundles are native host plugins](crickets-v3-native-plugins) — the plugin model the retirement reconciles against the `~/.claude/` standalones.
