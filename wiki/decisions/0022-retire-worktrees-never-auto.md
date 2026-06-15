# ADR 0022 — Retire `worktrees-never-auto`: worktrees first-class but operator-initiated

> [!NOTE]
> Status: partially superseded by [ADR 0028](0028-worktree-authority-config-opt-in.md) (2026-06-14) — only *how* operator authority is expressed changed; the core invariant (no silent authority-free spawn) is intact
> Date: 2026-06-13

## Context

The V5-10 coordinator-team work introduces a multi-worker model: a coordinator stages and activates named plans ([sibling #1, multi-plan-behavioral](Named-Plans)), then hands each plan to a worker running in its **own git worktree** so several workers progress concurrently without colliding in one checkout. Sibling #2 (`worktree-spawn`) shipped the mechanism for that — the `spawn_worker.py` helper and the [`/spawn-worker`](Spawn-A-Worker-In-A-Worktree) command, which creates a `worker/<name>` worktree pre-bound to its plan. Worktrees are no longer an edge case; they are the load-bearing primitive of the worker model.

That collided with a standing convention. `developer-safety` shipped a `worktrees-never-auto` snippet — *"Never create git worktrees automatically … Only enter a worktree session when the user explicitly asks for one"* — and the same prohibition exists device-globally in the `dev-setup` Claude config (`configs/claude/CLAUDE.md`, the symlink source of `~/.claude/CLAUDE.md`). The blanket framing predates the worker model and now reads in direct tension with it: a coordinator running `/spawn-worker` is *supposed* to create a worktree, yet the rule says "never create worktrees automatically."

**Open questions the decision resolves:**

- Does relaxing the prohibition re-open the door to an agent spawning worktrees on its own — the exact thing the rule existed to prevent?
- One surface or two — is rewriting the crickets `developer-safety` snippet enough, or does the device-global `dev-setup` config also have to change to match?
- What replaces a blanket prohibition without losing the guarantee it actually provided?

## Decision

Retire the blanket prohibition and replace it with **"worktrees are first-class but operator-initiated."** The invariant is restated on the *initiation* axis, not the *existence* axis: an operator-initiated worktree is expected; an autonomously-spawned one is the failure mode.

### 1. The crickets `developer-safety` snippet

Rename `worktrees-never-auto` → `worktrees-operator-initiated` (file + `name:` field, so it stays matched), and reframe its body: worktrees are a first-class part of the workflow (the coordinator flow creates them deliberately via `/spawn-worker`; concurrent workers don't collide), while *autonomous* creation stays prohibited — never spawn one as cleanup, as a convenience for another task, or as a side effect. Creating a worktree is an operator-initiated act: the operator runs `/spawn-worker` (where their invocation **is** the initiation) or explicitly asks. Shipped as `developer-safety` `0.2.0` (sibling #2, Task 3).

### 2. The device-global `dev-setup` surface

The § Worktrees block in the `dev-setup` Claude config (the symlink source of `~/.claude/CLAUDE.md`) gets the same reframe, so the device-wide instruction floor and the plugin convention agree. This is the second removal surface; it commits to `dev-setup`, not crickets, and is applied operator-gated (sibling #2, Task 5).

**Why not fully unguarded (just delete the rule)?** Deleting it outright would license an agent to spawn worktrees on its own initiative — precisely the failure mode the original rule prevented, and *more* dangerous now that worktrees are a real primitive: a stray worktree on a `worker/<x>` branch could collide with a genuine worker or muddy plan resolution. The guarantee worth keeping is "no autonomous spawn." Only the blanket *framing* was wrong, not the underlying guard.

**Why not keep the rule with an exception (e.g. "never, except `/spawn-worker`")?** An exception list is brittle and keeps the default reading "worktrees are suspect": every future sanctioned worktree workflow would need its own carve-out. Reframing on the initiation axis captures the actual invariant — operator-initiated vs autonomous — so it covers `/spawn-worker`, an explicit operator request, and any later operator-initiated workflow without enumeration, while still forbidding the only thing that was ever the real risk.

## Consequences

**Positive**

- The `/spawn-worker` coordinator workflow is no longer in tension with a safety convention — the convention and the command now agree.
- The invariant is stated on the right axis (initiation), so it generalizes to future operator-initiated worktree workflows with no new carve-outs.
- The load-bearing guarantee — no *autonomous* spawn — is preserved verbatim, not weakened.

**Negative / accepted debt**

- **Two prose surfaces must stay in sync** — the crickets `developer-safety` snippet and the device-global `dev-setup` config. A future reframe has to touch both; nothing mechanically couples them.
- **"Operator-initiated" is a semantic line, not a mechanical one.** Nothing in the crickets repo *prevents* a misbehaving agent from running `git worktree add` directly — the snippet is instruction, not enforcement. (The structural backstop, agentm's `check-no-auto-worktree.sh`, lives agentm-side, not here.)
- **Historical prose is superseded, not rewritten.** Design-doc and changelog text naming the old `worktrees-never-auto` convention remains as an append-only record of what was true then; this ADR is the forward-looking correction.

**Load-bearing assumptions + re-audit triggers**

- *Worker-spawn stays operator-initiated* — `/spawn-worker` only ever runs on an explicit operator invocation, never as a side effect of another task. **Re-audit if** any drift toward autonomous worktree creation appears: a solo agent spawning a worktree unprompted, a phase command that creates one without an operator asking, or a workflow that auto-spawns workers. That drift means the reframed rule is being violated in spirit, and the guarantee would need a *mechanical* (gate) backstop on the crickets side rather than prose alone.

## Related

- [Spawn a worker in a worktree](Spawn-A-Worker-In-A-Worktree) — the `/spawn-worker` how-to; the operator-initiated workflow this ADR sanctions.
- [Named plans](Named-Plans) — sibling #1, the named-plan staging a worker binds to.
- `src/developer-safety/snippets/worktrees-operator-initiated.md` — the renamed snippet (first removal surface); the device-global `dev-setup` § Worktrees block is the second.
- The agentm V5-10 coordinator-team design — the source of the multi-worker model and the locked sibling build order (#1 multi-plan-behavioral → #2 worktree-spawn + #3 integration-merge-command → #4 role-agent-defs). Sibling #3 owns the deferred merge/prune of the worktrees this norm now allows.
