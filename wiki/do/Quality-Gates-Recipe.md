# How to install the quality-gates recipe

> [!NOTE]
> **Goal:** Install the 5-primitive operator-control + verification set (`evaluator` + `kill-switch` + `steer` + `commit-on-stop` + `evidence-tracker`) into a target project — the set most Agent M `/work` sessions want.
> **Prereqs:** Crickets cloned + ([Agent M](https://github.com/alexherrero/agentm) cloned for `evidence-tracker`); target project exists.

## What changed in v2.0.0

In Crickets v1.x this set shipped as the `quality-gates` bundle, installable in one command. In v2.0.0 (V4 #36 reorg) the `bundles/` namespace was removed and the `evidence-tracker` hook moved to Agent M alongside the memory hooks. The five primitives are still the canonical recommended quality-gates configuration — they just install from two repos now:

- **Crickets ships:** `evaluator` (sub-agent) + `kill-switch` + `steer` + `commit-on-stop` (hooks).
- **Agent M ships:** `evidence-tracker` (hook). Also ships the compound skills the quality-gates set was originally built around (`memory`, `design`, `diataxis-author`, `ship-release`).

## When to use the recipe vs. individual primitives

| Situation | Reach for |
|---|---|
| New project adopting Agent M `/work`; want all the safety nets + verification gates | **the recipe** — install both repos (one command each) |
| Existing project that has 1–2 of these already; want to add the rest | individual `--hook <name>` flags on either installer (re-install is idempotent via `cp_managed`) |
| Project that explicitly does NOT want one primitive (e.g. no `commit-on-stop` because dirty trees are signal you want to inspect) | install the recipe, then delete the unwanted `.claude/hooks/<name>.sh` + edit `.claude/settings.json` to remove the registration |

Most operators using Agent M `/work` want all 5. Install both repos with their defaults.

## Steps

1. **Confirm both repos are cloned + accessible.**
   ```bash
   ls ~/Antigravity/crickets/install.sh
   ls ~/Antigravity/agentm/install.sh
   ```
   If either is missing:
   ```bash
   git clone https://github.com/alexherrero/crickets.git ~/Antigravity/crickets
   git clone https://github.com/alexherrero/agentm.git ~/Antigravity/agentm
   ```

2. **Install Crickets** — delivers `evaluator` + `kill-switch` + `steer` + `commit-on-stop`:
   ```bash
   bash ~/Antigravity/crickets/install.sh <target-project>
   ```
   PowerShell:
   ```powershell
   pwsh -NoProfile -File ~/Antigravity/crickets/install.ps1 <target-project>
   ```

3. **Install Agent M** — delivers `evidence-tracker` (plus the compound skill + memory hook stack):
   ```bash
   bash ~/Antigravity/agentm/install.sh <target-project>
   ```
   PowerShell:
   ```powershell
   pwsh -NoProfile -File ~/Antigravity/agentm/install.ps1 <target-project>
   ```

4. **Verify the post-install state** (see "What lands post-install" below).

5. **Inspect the merged `.claude/settings.json`** in your editor — confirm the 4 hook registrations are present (3 from Crickets + 1 from Agent M's `evidence-tracker`).

6. **Test one hook end-to-end** to confirm enforcement is live. Example for `kill-switch`:
   ```bash
   cd <target-project> && mkdir -p .harness && touch .harness/STOP
   # Next tool call from Claude Code will be blocked by the kill-switch hook.
   # Remove the sentinel to resume: rm .harness/STOP
   ```

## What lands post-install

After running both installers (default mode):

```
<target-project>/
├── .claude/
│   ├── agents/
│   │   ├── evaluator.md                  # Crickets
│   │   └── diataxis-evaluator.md         # Crickets
│   ├── hooks/
│   │   ├── kill-switch.sh                # Crickets
│   │   ├── steer.sh                      # Crickets
│   │   ├── commit-on-stop.sh             # Crickets
│   │   ├── evidence-tracker.sh           # Agent M (post-V4 #36)
│   │   └── evidence_tracker.py           # Agent M (post-V4 #36)
│   ├── skills/
│   │   ├── pii-scrubber/                 # Crickets
│   │   ├── dependabot-fixer/             # Crickets
│   │   ├── memory/                       # Agent M (post-V4 #36)
│   │   ├── design/                       # Agent M (post-V4 #36)
│   │   ├── diataxis-author/              # Agent M (post-V4 #36)
│   │   └── ship-release/                 # Agent M (post-V4 #36)
│   └── settings.json                     # merged hooks from both repos
└── .git/hooks/
    └── pre-push                          # Crickets PII guard
```

The Agent M install also lands phase commands + sub-agents under `.claude/commands/` and `.claude/agents/`, plus the Antigravity-side `.agents/skills/` mirrors. See the `agentm` README for the full surface.

## Verifying the install

Run the smoke checks from each repo to confirm install integrity:

```bash
bash ~/Antigravity/crickets/scripts/smoke-install-bash.sh
# crickets-side checks: expected files, idempotent re-run, --update wipe + recreate,
# kill-switch sentinel end-to-end, validate-manifests gemini-cli rejection.

# (Agent M's smoke installer grows the equivalent in plan #19 task 9.)
```

Manual end-to-end test of the recipe:

```bash
cd <target-project>
# 1. Kill switch
mkdir -p .harness && touch .harness/STOP
# Claude Code's next tool call is blocked. Remove to resume:
rm .harness/STOP

# 2. Steer
echo "Use Python 3.11 not 3.12 for this project." > .harness/STEER.md
# Claude Code's next tool call inherits the steer. After absorbing it,
# the file is renamed to .harness/STEER.consumed-<iso>.md for audit.

# 3. Evidence tracker (Agent M hook)
# In a /work session, try to flip a `[ ]` to `[x]` in .harness/PLAN.md
# without first reading the spec/test files. The hook should block the
# Edit and emit a "evidence-tracker: default-FAIL ... never/matched/path"
# message on stderr.

# 4. Commit-on-stop
# Make some local edits, then close the Claude Code session.
# Check for the safety-branch commit:
git branch | grep auto-save/
```

## Why this five-primitive set?

| Primitive | Surface area protected |
|---|---|
| `evaluator` | Fresh-context grader for rubric-driven artifact review at `/review`. Augments the in-session `adversarial-reviewer` with an out-of-session perspective. |
| `kill-switch` | Emergency operator halt for long-running sessions. `touch .harness/STOP` halts the next tool call. |
| `steer` | Mid-run redirect without restart. Write `.harness/STEER.md` with instructions; next tool call inherits the override + the file is renamed for audit. |
| `commit-on-stop` | Safety-branch commit at session end. Dirty tree → `auto-save/<iso-ts>` branch + commit. Recovery via `git checkout auto-save/<ts>`. Never modifies current branch; never pushes. |
| `evidence-tracker` | Default-FAIL evidence enforcement on `/work` task closeouts. Blocks `[ ]` → `[x]` flips in `PLAN.md` unless the agent demonstrably `Read` the spec/test files first. Hybrid resolver (heuristic + per-task override + explicit opt-out). |

Together: operator-controllable (kill-switch + steer), recoverable (commit-on-stop), audit-trail-enforcing (evidence-tracker), and externally-graded (evaluator at phase boundaries).

## Cross-references

- [Evaluator](Evaluator) — the rubric dispatch contract for the evaluator sub-agent.
- [Operator-control hooks](Operator-Control-Hooks) — the three hooks + their trigger files.
- [Add-A-Skill](Add-A-Skill) — authoring new primitives.
- [Install crickets plugins](Install-Into-Project) — installing the plugins these gates ship in.
- [Compatibility](Compatibility) — host coverage per primitive.
- [Agent M wiki — evidence-tracker hook + Antigravity plugins](https://github.com/alexherrero/agentm/wiki) — the evidence-tracker hook and plugin-authoring docs live in Agent M since v2.0.0.
