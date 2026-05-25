# How to use the evidence-tracker hook

> [!NOTE]
> **Goal:** Enforce a default-FAIL evidence contract on `/work` task closeouts — the agent must demonstrably READ relevant spec/test files before flipping a PLAN.md task's `[ ]` → `[x]`.
> **Prereqs:** `crickets` installed into the target project (so `.claude/hooks/evidence-tracker.sh` + `evidence_tracker.py` land + their PreToolUse registration lands in `.claude/settings.json`); the target has a `.harness/PLAN.md` (i.e. the harness has at least run `/plan`). See [Manifest-Schema](Manifest-Schema) for the `kind: hook` fields.

Length justification: this how-to documents 1 hook with 3 task-body conventions × 3 worked scenarios + a 6-row troubleshooting table + dogfood walkthrough. The 1000-word length is acceptable because operators read this end-to-end the first time they adopt the hook + return to specific sections later. Splitting per-scenario would force cross-link chasing for related behavior.

## When the hook fires

The hook registers on Claude Code's `PreToolUse` event with matcher `Read|Write|Edit`. Per-tool behavior:

| Tool | What the hook does | Exit code |
|---|---|---|
| `Read` (path exists on disk) | Records the path to `.harness/.evidence-reads` (per-session JSON, gitignored). | 0 (allow) |
| `Read` (path missing) | No-op — prevents fictitious-path bypass. | 0 (allow) |
| `Write` / `Edit` on `.harness/PLAN.md` that flips a task's `[ ]` → `[x]` | Resolves the task's evidence requirement; checks recorded reads; blocks if unmet. | 0 (allow) **or 2 (block)** |
| `Write` / `Edit` elsewhere, or not flipping a checkbox | Pass-through. | 0 |
| Any other tool (Bash, Glob, Grep, etc.) | Pass-through. | 0 |

State lives at `<project>/.harness/.evidence-reads` (atomic write; reset on `/work` session start per the harness `/work` spec §5b). Reads are recorded under a `__global__` bucket (key `"0"`) because the hook fires on `Read` without knowing which in-flight task the agent is "reading for" — reads count toward any task in the plan.

## Task-body annotations

Tune the contract per task by adding (or omitting) `**Evidence:**` in the task body:

| Annotation | Behavior |
|---|---|
| *(omit — default)* | **HEURISTIC** match — any file under `tests/` / `spec/` / matching `*.spec.*` / `*.test.*` / `*_test.py` / `test_*.py` with a code extension (`.py` / `.ts` / `.js` / etc.; markdown excluded to prevent `tests/README.md` false-positives), OR any path literally in the task's `**Verification:**` text. |
| `**Evidence:** <glob-or-paths>` | **Per-task override** — comma- or whitespace-separated patterns; supports globs. Only matching reads count. Example: `**Evidence:** src/auth/*.py, wiki/explanation/decisions/0012-*.md`. |
| `**Evidence:** none — <rationale>` | **Explicit opt-out** — no reads required; flip always allowed. Rationale is mandatory per the operator-acknowledgment discipline. |

## Three worked scenarios

### Scenario 1 — Heuristic match (the common case)

You're working a task that says:
```markdown
### 5. Add token-refresh logic
- **What:** Refresh access tokens 60s before expiry.
- **Verification:** tests/auth/test_refresh.py covers the 3 cases.
- **Status:** [ ]
```

No `**Evidence:**` annotation → default heuristic. Read `tests/auth/test_refresh.py` (anywhere in the session, before you flip `[x]`) → the read counts; the flip is allowed.

### Scenario 2 — Per-task override (unusual evidence shape)

A docs-grading task:
```markdown
### 11. Audit ADR 0012 against current implementation
- **What:** Confirm the locked design calls still match the shipped code.
- **Verification:** Read ADR 0012 + walk the affected files.
- **Evidence:** wiki/explanation/decisions/0012-*.md, src/affected/*.py
- **Status:** [ ]
```

Heuristic wouldn't catch the ADR file (it's not under `tests/`); the override does. Read either matching path → flip allowed.

### Scenario 3 — Explicit opt-out (genuinely no evidence)

A pure CHANGELOG task:
```markdown
### 14. Append v0.12.0 CHANGELOG entry
- **What:** Add user-visible changes under the v0.12.0 header.
- **Evidence:** none — pure release-notes write; no code paths to verify.
- **Status:** [ ]
```

Flip allowed without any reads. Rationale text after `none —` is mandatory + becomes the audit trail.

## When the hook blocks you

Stderr explains exactly which paths satisfy the requirement + what's already been recorded. Three recovery paths:

1. **Read a file that satisfies the requirement** (use the `Read` tool), then retry the flip.
2. **Add `**Evidence:** none — <rationale>`** to the task body if it's genuinely docs-only, then retry.
3. **Reset state** if reads got out of sync (rare; usually means the hook was installed mid-session):
   ```bash
   python3 .claude/hooks/evidence_tracker.py --mode reset
   ```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Hook silently does nothing | Toolkit not installed, or `evidence_tracker.py` missing from `.claude/hooks/` | Re-run `bash install.sh <project> --hook evidence-tracker` |
| Read recorded but flip still blocks | Path you read doesn't match the task's requirement | Read stderr — it shows the expected patterns + what's recorded |
| "I read the right file but block persists" | State file out of sync (e.g. hook installed AFTER the Read) | `python3 .claude/hooks/evidence_tracker.py --mode reset`; then Read again |
| Hook doesn't fire at all | Settings.json missing the registration | Check `.claude/settings.json` for the `PreToolUse` matcher `Read\|Write\|Edit` → `bash .claude/hooks/evidence-tracker.sh` entry |
| Python error on hook fire | Helper expects Python 3.8+ (uses dataclasses + f-strings) | Verify `python3 --version` is 3.8+ |
| Hook blocks a flip you didn't intend to make | Edit is touching `**Status:**` line inadvertently | Reword the edit to leave the Status line alone, or add `**Evidence:** none` |

## Graceful-skip

The hook is **never** the reason `/work` doesn't run. Silent exit 0 in all these cases:

- `crickets` not installed; hook absent.
- `evidence_tracker.py` helper missing.
- `python3` not on PATH.
- Project has no `.harness/` directory (hook isn't a no-op outside a harness install).
- Tool input JSON malformed (fail-open per Claude Code's contract).

Operators using harness without the toolkit see zero behavior change.

## Dogfood test

After installing into a fresh project:

```bash
# 1. Create a fixture task that should block
echo '### 99. Test task\n- **Verification:** tests/foo.py\n- **Status:** [ ]\n' >> .harness/PLAN.md

# 2. Attempt to flip the checkbox WITHOUT reading anything
# (run this in your Claude Code session)
# Should see: "evidence-tracker: default-FAIL — refusing to flip task 99..."

# 3. Read the expected file, then retry the flip
# (Claude Code Read of tests/foo.py — assuming it exists)
# Flip now succeeds.

# 4. To clean up state: 
python3 .claude/hooks/evidence_tracker.py --mode reset
```

## See also

- [Manifest Schema](../reference/Manifest-Schema.md) — `kind: hook` fields.
- [evidence-tracker hook manifest](https://github.com/alexherrero/crickets/blob/main/hooks/evidence-tracker/hook.md) — fuller technical reference.
- [ADR 0009 — Evidence-tracker hook](../explanation/decisions/0009-evidence-tracker-hook.md) — design rationale + 3 locked design calls.
- [Use The Base Hooks](Use-The-Base-Hooks.md) — sibling hooks (kill-switch, steer, commit-on-stop) from plans #4 + #5.
- [harness `/work` §5b](https://github.com/alexherrero/agentm/blob/main/harness/phases/03-work.md) — the harness-side contract this hook enforces.
