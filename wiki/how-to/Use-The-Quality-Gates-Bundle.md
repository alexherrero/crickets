# How to use the quality-gates bundle

> [!NOTE]
> **Goal:** Install the 4 base operator-control + verification primitives (`evaluator` + `kill-switch` + `steer` + `commit-on-stop` + `evidence-tracker`) into a target project with one command — the set most agentm `/work` sessions want.
> **Prereqs:** `crickets` cloned at a known path (e.g. sibling to your target project); target project exists. See [Manifest-Schema](Manifest-Schema) for the `kind: bundle` contract.

## When to use the bundle vs. individual primitives

| Situation | Reach for |
|---|---|
| New project adopting agentm `/work`; want all the safety nets + verification gates | **bundle** (one command, 5 primitives) |
| Existing project that has 1–2 of these already; want to add the rest | **individual `--hook <name>`** or **`--agent evaluator`** to avoid re-applying ones you already have (though re-install is idempotent via `cp_managed`) |
| Project that explicitly does NOT want one primitive (e.g. no `commit-on-stop` because dirty trees are signal you want to inspect) | install bundle then delete the unwanted `.claude/hooks/<name>.sh` + edit `.claude/settings.json` to remove the registration. Variant bundles are deferred (out of scope for v1). |

Most operators using harness `/work` want all 5. The bundle is the default install path.

## Steps

1. **Confirm the toolkit is cloned + accessible**:
   ```bash
   ls crickets/install.sh   # POSIX
   ls crickets/install.ps1  # PowerShell
   ```
   If missing: `git clone https://github.com/alexherrero/crickets.git` next to your target project.

2. **Run the bundle install** from your shell of choice:
   ```bash
   bash crickets/install.sh <target-project> --bundle quality-gates
   ```
   PowerShell equivalent:
   ```powershell
   pwsh -NoProfile -File crickets/install.ps1 -Bundle quality-gates <target-project>
   ```

3. **Verify the post-install state** (see "What lands post-install" + "Verifying the install" below).

4. **Inspect the merged `settings.json`** in your editor — confirm the 4 hook registrations are there.

5. **Test one hook end-to-end** to confirm enforcement is live. Example for kill-switch:
   ```bash
   cd <target-project> && mkdir -p .harness && touch .harness/STOP
   # Next tool call from Claude Code will be blocked by the kill-switch hook.
   # Remove the sentinel to resume: rm .harness/STOP
   ```

## What lands post-install

```
<target-project>/.claude/
├── agents/
│   └── evaluator.md
├── hooks/
│   ├── kill-switch.sh         + .ps1
│   ├── steer.sh               + .ps1
│   ├── commit-on-stop.sh      + .ps1
│   ├── evidence-tracker.sh    + .ps1
│   └── evidence_tracker.py    ← Python sidecar
└── settings.json              ← merged with 4 hook registrations:
                                   3 PreToolUse (kill-switch + steer + evidence-tracker)
                                   1 Stop (commit-on-stop)
```

The bundle resolves each `contents:` entry against the standalone toolkit primitive — no file duplication. See [ADR 0010](../explanation/decisions/0010-quality-gates-bundle.md) for the sibling-reference design.

## Verifying the install

```bash
# 1. All 6 files present:
ls -la <target-project>/.claude/agents/evaluator.md
ls -la <target-project>/.claude/hooks/{kill-switch,steer,commit-on-stop,evidence-tracker}.sh
ls -la <target-project>/.claude/hooks/evidence_tracker.py

# 2. Settings has 4 registrations:
cat <target-project>/.claude/settings.json | python3 -c "
import json, sys
s = json.load(sys.stdin)
print('PreToolUse:', len(s['hooks'].get('PreToolUse', [])))
print('Stop:', len(s['hooks'].get('Stop', [])))
"
# Expected: PreToolUse: 3, Stop: 1
```

## Troubleshooting

Each primitive has its own how-to with detailed troubleshooting — don't re-debug here, follow the cross-link:

- **kill-switch / steer / commit-on-stop issues** → [Use The Base Hooks](Use-The-Base-Hooks)
- **evidence-tracker blocks a flip you thought was legitimate** → [Use The Evidence-Tracker Hook](Use-The-Evidence-Tracker-Hook)
- **evaluator sub-agent returns unexpected verdicts** → [Use The Evaluator](Use-The-Evaluator)

## See also

- [ADR 0010 — quality-gates bundle](../explanation/decisions/0010-quality-gates-bundle.md) — design rationale + Q1 sibling-reference + Q2 version-bump convention.
- [bundle.md](https://github.com/alexherrero/crickets/blob/main/bundles/quality-gates/bundle.md) — manifest with cross-refs to each primitive.
- [agentm `/work` §5b](https://github.com/alexherrero/agentm/blob/main/harness/phases/03-work.md) — the contract `evidence-tracker` enforces during `/work` task closeouts.
- [example-bundle](https://github.com/alexherrero/crickets/blob/main/bundles/example-bundle/bundle.md) — reference skeleton showing the bundle pattern.
