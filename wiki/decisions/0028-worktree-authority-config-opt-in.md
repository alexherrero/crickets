# ADR 0028 — Worktree authority broadened: config opt-in is operator authority for auto-spawn

> [!NOTE]
> Status: accepted
> Date: 2026-06-14
> Supersedes: [ADR 0022](0022-retire-worktrees-never-auto.md) (partially — only *how* operator authority is expressed changes; ADR 0023 is untouched)

## Context

[ADR 0022](0022-retire-worktrees-never-auto.md) established the **operator-initiated** invariant for worktree creation: worktrees are first-class in the coordinator flow, but creation requires explicit operator initiation — the operator runs `/spawn-worker` (where the invocation **is** the initiation) or explicitly asks.

The worktree-per-plan design (developer-workflows, 2026-06-14) introduced **config-gated auto-spawn**: when `isolation.mode: worktree-per-plan` is set in `.harness/project.json`, the `/work` and `/bugfix` phase commands auto-spawn a `worker/<slug>` worktree at the start of each plan unit. The operator set this field deliberately — it is a durable, file-backed preference, not a spontaneous agent decision.

**Open questions the decision resolves:**

- Is a durable config opt-in "operator authority," or must authority always be an explicit per-invocation command?
- Does this partial loosening require revisiting the ADR 0023 integration-initiated invariant?
- What is the right statement of the prohibition so it neither blocks config-gated auto-spawn nor licenses silent authority-free spawn?

## Decision

**A durable `isolation.mode: worktree-per-plan` config opt-in in `.harness/project.json` IS operator authority for worktree creation**, on equal footing with an explicit `/spawn-worker` invocation.

The invariant is restated more precisely:

> Worker-tree initiation requires **operator authority** — either an explicit `/spawn-worker` command or a durable `isolation.mode: worktree-per-plan` config opt-in. **Silent authority-free auto-spawn stays forbidden.** `/integrate-worker` stays operator-initiated.

### Why config opt-in counts as operator authority

The operator sets `isolation.mode: worktree-per-plan` in a versioned file they own; they know what it does; it is not set by default by any agent. The semantics are identical to any durable preference: the operator expressed intent once, and the system honors it on every subsequent invocation. The guard ADR 0022 was preserving — *no agent spawning a worktree on its own initiative without the operator asking* — is not violated by honoring a standing operator preference. The config field is the asking.

**Why not keep "explicit command only"?** Config-gated auto-spawn is the entire point of the worktree-per-plan design: the operator should be able to set it once and have every plan unit automatically isolated without repeating `/spawn-worker` manually. Requiring an explicit command every time would defeat the design and create the worst outcome — the feature ships but is unusable without constant operator ceremony.

**Why not the alternative (treat config opt-in as insufficient authority, require an additional flag)?** An additional per-invocation flag is identical to a command in cost and ergonomics — it does not compose with "I set this once in my config." The guard ADR 0022 preserved is about initiation intent, not about invocation mechanics. A durable config setting that says `worktree-per-plan` is as clear an expression of intent as running `/spawn-worker`.

### ADR 0023 is untouched

[ADR 0023](0023-gate-on-integrated-tree.md) governs the integration gate (merging a worker branch and the post-merge gate). That decision is entirely on the integration side: it does not address spawn authority. **`/integrate-worker` stays operator-initiated.** The config opt-in does not auto-integrate; the operator chooses when and what to integrate.

### Revised prohibition

The prohibition in `spawn-worker.md` and the recoverability-gate doctrine block is updated from:
- *"Never spawn a worktree autonomously"*

to:
- *"Never spawn a worktree without operator authority"* (authority = explicit command OR durable config opt-in)

The semantic precision matters: "autonomously" is ambiguous (it could cover config-gated spawn, which is now sanctioned); "without operator authority" is not.

## Consequences

**Positive**

- The worktree-per-plan auto-spawn is consistent with the authority doctrine — no friction between the design and the convention.
- The prohibition is more precise: it names the actual failure mode (spawning without authority) rather than a proxy (spawning autonomously), so it won't need to be re-read every time a new operator-initiated workflow appears.
- The positive case (config opt-in IS authority) is tested by `test_recoverability_gate_carveouts.py` — a future edit removing the config-opt-in reference from `spawn-worker.md` fails the conformance guard.

**Negative / accepted debt**

- **Three prose surfaces must stay in sync** — the recoverability-gate doctrine block (byte-identical across `work.md` / `bugfix.md` / `release.md`), `spawn-worker.md`, and the device-global `~/.claude/CLAUDE.md` § Worktrees block. The drift test pins the first group; the carve-out conformance test pins the second; the global CLAUDE.md is the third (updated via the self-modification gate, not silently).
- **"Without operator authority" is still a semantic line, not a mechanical one.** The only structural backstop against a misbehaving agent is the conformance test + the authority definition; it does not prevent a rogue `git worktree add` directly.

**Load-bearing assumptions + re-audit triggers**

- *Config opt-in is a deliberate operator act* — `.harness/project.json` is operator-owned and versioned; no agent writes `isolation.mode` on its own. **Re-audit if** any agent or installer ever sets this field without explicit operator instruction — that would mean auto-spawn is silently enabled, which is the failure mode this ADR intended to prevent.
- *Integration stays operator-initiated* — the config opt-in does not create a path to auto-integration; the `finalize_unit.py` helper only pushes + opens a PR, not merges. **Re-audit if** a future design proposes auto-merge of the `worker/<slug>` PR — that crosses the ADR 0023 line.
- *Silent (config-absent) spawn is still the failure mode* — the prohibition "without operator authority" still forbids an agent that runs `spawn_worker.py` with no operator preference set. **Re-audit if** any code path calls `spawn_worker.py` outside of the two authorized paths (explicit `/spawn-worker` command; `isolation_config.should_auto_isolate()` returning True with a live config opt-in).

## Related

- [ADR 0022 — Retire `worktrees-never-auto`](0022-retire-worktrees-never-auto.md) — superseded (partially)
- [ADR 0023 — Gate on integrated tree](0023-gate-on-integrated-tree.md) — untouched by this decision
- [`spawn-worker.md`](../../src/developer-workflows/commands/spawn-worker.md) — the explicit-command authority path; updated to "Operator authority required."
- `isolation_config.py` — `should_auto_isolate()` is the config-opt-in authority check; `is_inside_worktree()` is the single-owner guard
- `finalize_unit.py` — pushes + opens PR on unit completion; the post-spawn delivery, not the spawn itself
