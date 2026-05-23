---
name: quality-gates
description: One-command install for the 4 base operator-control + verification primitives that ride alongside agentic-harness `/work`. Bundles the evaluator sub-agent (fresh-context rubric grading) + 3 operator-control hooks (kill-switch, steer, commit-on-stop) + the evidence-tracker hook (default-FAIL enforcement on PLAN.md `[x]` flips). Most projects using harness `/work` want all 5; bundling reduces "I forgot to install commit-on-stop" footguns.
kind: bundle
supported_hosts: [claude-code]
version: 0.1.0
install_scope: project
contents:
  - agent: evaluator
  - hook: kill-switch
  - hook: steer
  - hook: commit-on-stop
  - hook: evidence-tracker
---

# quality-gates — the full operator-control + verification stack for harness `/work`

One-command install for the 4 base primitives that earn their keep on every long-running `/work` session. Pulls 5 primitives into the right `.claude/` paths atomically:

| Primitive | Kind | What it does | Shipped in |
|---|---|---|---|
| [`evaluator`](agents/evaluator.md) | sub-agent | Fresh-context PASS / NEEDS_WORK grading against a caller-supplied rubric. Read-only allowlist (`Read, Glob, Grep`). | [ADR 0002](../../wiki/explanation/decisions/0002-evaluator-design.md), v0.6.0 |
| [`kill-switch`](hooks/kill-switch/hook.md) | hook (PreToolUse) | `touch .harness/STOP` → next tool call halts (exit 2). Operator emergency halt for runaway sessions. | [ADR 0003](../../wiki/explanation/decisions/0003-base-operator-hooks.md), v0.7.0 |
| [`steer`](hooks/steer/hook.md) | hook (PreToolUse) | Write `.harness/STEER.md` → next tool call sees the redirect; file renamed to `STEER.consumed-<ts>.md` for audit trail. | [ADR 0003](../../wiki/explanation/decisions/0003-base-operator-hooks.md), v0.7.0 |
| [`commit-on-stop`](hooks/commit-on-stop/hook.md) | hook (Stop) | Dirty tree at session end → `auto-save/<iso-ts>` safety branch. Recover via `git checkout auto-save/<ts>`. | [ADR 0003](../../wiki/explanation/decisions/0003-base-operator-hooks.md), v0.7.0 |
| [`evidence-tracker`](hooks/evidence-tracker/hook.md) | hook (PreToolUse) | Default-FAIL enforcement: agent must Read evidence files before `[ ]` → `[x]` flip in PLAN.md. Blocks (exit 2) on unmet evidence. | [ADR 0009](../../wiki/explanation/decisions/0009-evidence-tracker-hook.md), v0.12.0 |

## Why this bundle

Each primitive earns its keep individually, but the **set is what makes `/work` durable**:

- `kill-switch` + `steer` give operators precise mid-session control.
- `commit-on-stop` makes any session ending survivable (crashes, accidental closes, mid-task pauses).
- `evidence-tracker` makes the verification step in `/work`'s contract observable + enforced.
- `evaluator` augments `/review` with fresh-context rubric grading alongside `adversarial-reviewer`.

Operators installing one primitive almost always want the others soon after. Bundling reduces the "I forgot to install commit-on-stop and lost an hour of work" failure mode + validates the bundle pattern from `agent-toolkit`'s original design ([ADR 0001](../../wiki/explanation/decisions/0001-agent-toolkit-purpose.md)).

## Install

```bash
bash agent-toolkit/install.sh <target-project> --bundle quality-gates
```

Post-install, the target project has:

```
.claude/
├── agents/
│   └── evaluator.md
├── hooks/
│   ├── kill-switch.sh
│   ├── steer.sh
│   ├── commit-on-stop.sh
│   ├── evidence-tracker.sh
│   └── evidence_tracker.py    ← Python sidecar for evidence-tracker
└── settings.json              ← merged with 4 hook registrations:
                                   3 PreToolUse (kill-switch + steer + evidence-tracker)
                                   1 Stop (commit-on-stop)
```

Plus the matching `.ps1` entries for Windows hosts.

## Version-bump convention

**The bundle's `version:` bumps whenever ANY constituent primitive changes** — even if the change is a single-character fix to one hook's stderr message. Bundle version pins the **set**; operators installing `quality-gates@v0.1.0` get a known frozen quartet (current versions: evaluator 0.1.0, kill-switch 0.1.0, steer 0.1.0, commit-on-stop 0.1.0, evidence-tracker 0.1.0).

Why not version-by-highest-constituent or version-by-substantive-only: the parity-check CI gate (see [`scripts/check-bundle-parity.sh`](../../scripts/check-bundle-parity.sh)) makes drift between bundle copies and standalone primitives **impossible to merge** — so bumping bundle version on every primitive change is the natural cadence. Operators reading the CHANGELOG know exactly what they're getting per bundle release.

Per [ADR 0010 — quality-gates bundle](../../wiki/explanation/decisions/0010-quality-gates-bundle.md) for the locked design calls + 4 load-bearing assumptions with re-audit triggers.

## Maintenance contract — read this before editing a primitive

Per Q1 in [ADR 0010](../../wiki/explanation/decisions/0010-quality-gates-bundle.md), the bundle ships **byte-identical copies** of the standalone primitives. When you edit a standalone primitive (e.g. `agent-toolkit/hooks/kill-switch/kill-switch.sh`), you MUST also update the bundle copy (`agent-toolkit/bundles/quality-gates/hooks/kill-switch/kill-switch.sh`) in the same commit. The CI gate [`scripts/check-bundle-parity.sh`](../../scripts/check-bundle-parity.sh) fails any PR where the two diverge.

The simplest workflow:

```bash
# After editing the standalone primitive:
cp -r hooks/kill-switch/. bundles/quality-gates/hooks/kill-switch/
bash scripts/check-bundle-parity.sh   # local verify (CI also runs this)
```

Future operators may extract this into a `make sync-bundles` helper or a pre-commit hook. For now: manual + parity-gated.

## See also

- [How to use the quality-gates bundle](../../wiki/how-to/Use-The-Quality-Gates-Bundle.md) — operator-facing install + troubleshooting guide.
- [ADR 0010 — quality-gates bundle](../../wiki/explanation/decisions/0010-quality-gates-bundle.md) — design rationale + 2 locked design calls Q1-Q2 + 4 load-bearing assumptions.
- [Use the base hooks](../../wiki/how-to/Use-The-Base-Hooks.md) — per-primitive how-to for kill-switch / steer / commit-on-stop.
- [Use the evidence-tracker hook](../../wiki/how-to/Use-The-Evidence-Tracker-Hook.md) — per-primitive how-to for evidence-tracker.
- [Use the evaluator](../../wiki/how-to/Use-The-Evaluator.md) — per-primitive how-to for the evaluator sub-agent.
- [example-bundle](../example-bundle/bundle.md) — reference skeleton showing the bundle pattern.
