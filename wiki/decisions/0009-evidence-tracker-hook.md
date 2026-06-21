# ADR 0009: evidence-tracker hook

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-22
> **Related:** [ADR 0003 — base operator-control hooks](0003-base-operator-hooks) (precedent for the `kind: hook` installer pattern + Claude-Code-only scope) · [ADR 0001 — crickets purpose](crickets-hld) (stdlib-only / no-new-third-party-deps convention D7) · [ADR 0007 — MemoryVault Discovery + Mining](crickets-hld) (precedent for the architectural-enforcement-via-write-allowlist pattern this hook mirrors at the tool-input gate level) · [Use The Evidence-Tracker Hook how-to (Agent M wiki)](https://github.com/alexherrero/agentm/wiki/Use-The-Evidence-Tracker-Hook) · [agentm `/work` §5b spec amendment](https://github.com/alexherrero/agentm/blob/main/harness/phases/03-work.md) · [agentm ROADMAP item #9](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md) · [cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents) (upstream pattern source — "The only evidence that counts is a file matching the patterns")

## Context

ROADMAP item #9 (agentm) shipped as a follow-on to plans #4 + #5 (the three base operator-control hooks: kill-switch / steer / commit-on-stop) and complementary to plan #6's `/design` skill + plan #7a/7b's MemoryVault. The locked execution-order placed it after the MemoryVault parent design finished (#7a + #7b ✅ 2026-05-22) and ROADMAP #8's auto-context-into-harness-phases shipped (toolkit v0.11.1 + harness v2.5.0).

**The gap this addresses.** Today's `/work` phase trusts the agent to *verify* before flipping a PLAN.md task `[x]`. The verification criterion lives in the task body (`**Verification:** <executable check>`), but there's no enforcement that the agent actually opened the relevant files before claiming the task is done. In practice: agents sometimes flip tasks `[x]` based on partial signals (a passing test run that didn't actually cover the new code; a "looks good" judgment on a diff they didn't read against the spec). The verification step exists in the contract but isn't *observable*.

The cwc-long-running-agents pattern, paraphrased: *"The only evidence that counts is a file matching the patterns."* Translated to the harness: every task starts with `evidence-met=false`; the agent must demonstrably *read* (via the `Read` tool, which the hook observes) a spec/test/evidence file matching the task's requirement *before* a `Write`/`Edit` that flips the task `[ ]` → `[x]` is allowed. Hook blocks otherwise.

This is the 4th base hook in `crickets/hooks/` after kill-switch, steer, and commit-on-stop (ADR 0003). Same Claude-Code-only scope, same graceful-skip discipline, same PreToolUse event surface — but where the prior three are *operator-precision controls* (halt / redirect / safety-net), evidence-tracker is *enforced discipline* (default-FAIL contract on a specific tool-input pattern).

**Three open design questions surfaced at plan time** (#9 PLAN.md):
1. What counts as evidence?
2. Granularity — per task in PLAN.md, or per `passes` flag in features.json?
3. Bypass for genuinely-no-evidence cases (docs-only tasks)?

This ADR captures the operator-confirmed resolutions + 4 load-bearing assumptions with re-audit triggers.

## Decision

**Ship `evidence-tracker` as a single base hook** in `crickets/hooks/evidence-tracker/`: PreToolUse on Claude Code's `Read|Write|Edit` matcher; Python helper (`evidence_tracker.py`, ~720 lines, stdlib-only, 61 unit tests) does the substantive work; thin `.sh` + `.ps1` entry scripts shell out to the helper via stdin pipe-through. **Default-FAIL contract** enforced by exit code: 2 to block, 0 to allow. Graceful-skip in every direction (Python missing, helper missing, project has no `.harness/`, malformed input) — the hook *never* prevents `/work` from running, only specific `[ ]` → `[x]` flips with unmet evidence.

Three locked design calls Q1–Q3 (operator-confirmed at /plan time, 2026-05-22):

### Q1 — What counts as evidence: HYBRID (heuristic + per-task override + explicit opt-out)

- **HEURISTIC** by default: any file under `tests/` / `spec/` / `test/` / `specs/` / `__tests__/`, OR matching `*.spec.*` / `*.test.*` / `*_test.py` / `test_*.py`, **with a code extension** (markdown explicitly excluded — `tests/README.md` does NOT satisfy evidence for a coding task), OR any path that appears literally in the task's `**Verification:**` text in PLAN.md (literal-path match not gated by code-ext since operator-stated paths can be anything).
- **Per-task override** via `**Evidence:** <glob-or-paths>` task-body annotation (comma- or whitespace-separated; supports globs).
- **Explicit opt-out** via `**Evidence:** none — <rationale>` (case-insensitive; rationale stripped after `—` or `-`).

**Why not pure heuristic** (no per-task override): would miss tasks whose evidence isn't conventionally test-shaped (ADR-grading work; cross-file refactor audits where the evidence is `docs/architecture/*.md`). Per-task override is the tail-case escape hatch.

**Why not per-task only** (no heuristic default): would force operators to annotate every single task, including the 95% common case where reading `tests/foo.py` is the obvious evidence. Heuristic catches the bulk with zero operator effort.

**Why exclude markdown from the heuristic** (`tests/README.md` doesn't satisfy): the heuristic targets "evidence the agent read the actual test logic", not "evidence the agent read prose about tests". Markdown in `tests/` is a legitimate prose-about-tests case, but counting it as evidence creates a trivial bypass.

### Q2 — Granularity: per-task PLAN.md `[ ]` → `[x]` flips ONLY (not features.json `passes:true`)

Hook fires on Write/Edit operations that would mutate the PLAN.md task's checkbox from `[ ]` → `[x]`. Detection: for `Write`, compare current PLAN.md against proposed new content; find any task whose checkbox went `[ ]` → `[x]`. For `Edit`, scan `old_string` for `**Status:** [ ]` + `new_string` for `**Status:** [x]`, then walk backwards in the current PLAN.md from the edit position to find the most recent task H3 header.

**Why not features.json `passes:true` too**: that flip happens at `/release`, not `/work`. `/release` already has its own adversarial review (`adversarial-reviewer` + `evaluator` augmentation per ADR 0002 + ADR 0003). Layering evidence-tracking on top of those would be redundant for `/release`-time enforcement.

**Why per-task and not per-feature**: most plans have ~10 tasks per feature; per-task is the finer-grained safety net. A feature-level gate would let the agent flip 9/10 tasks `[x]` without evidence as long as the 10th had it.

### Q3 — Bypass for docs-only tasks: EXPLICIT OPT-OUT (`**Evidence:** none — <rationale>`)

Task body declares opt-out with a mandatory rationale. No silent bypasses.

**Why not auto-detect** (e.g. "if the task only touches `.md` files, exempt it"): would let lazy refactor commits that "happen to only touch .md files" slip through. Some operators would route otherwise-evidence-requiring work through doc-only-shaped tasks to dodge the gate. Auto-detection optimizes for the wrong thing.

**Why not strict** (every task requires at least one read): forces operators to fabricate an evidence read for legitimately-no-evidence tasks (CHANGELOG entries, ADR writes, README updates). Fabricated reads train the operator + agent to circumvent the gate, eroding the trust the gate is supposed to build.

**Explicit opt-out preserves the discipline**: operator acknowledges deliberately; rationale becomes the audit trail (git blame on the PLAN.md line shows when + why the opt-out was added).

## Consequences

### Positive

- **Default-FAIL is observable + enforced.** Verification stops being a contract item that's trusted-but-unchecked; becomes a gate the agent must pass. Operators see the agent's reads (`.harness/.evidence-reads` is inspectable) and the hook's block messages directly.
- **Hybrid evidence resolution covers the 95/5 split.** Heuristic handles common test-shaped evidence with zero operator effort; per-task override handles the unusual tail; explicit opt-out handles legitimate no-evidence cases. Each operator workflow has a clean path.
- **Graceful-skip is total.** Hook missing, Python missing, project not a harness install, malformed input — every failure mode exits 0. Harness installs without the toolkit see zero behavior change. Same pattern as ADR 0003's three base hooks; operators upgrading paths-incrementally are never blocked.
- **First Python-sidecar hook in the toolkit.** Pattern documented inline in `install.sh` + `install.ps1` as "Plan #9 introduced this pattern" — future hooks can ship a Python helper alongside their `.sh`/`.ps1` entry without separate skill-dir scaffolding. Extension is ~7 lines per OS installer.
- **Fictitious-path bypass blocked.** PreToolUse on `Read` records only paths that *exist on disk* — agent can't claim to have read `tests/fake.py` to satisfy a requirement. Combined with the explicit-opt-out discipline, the gate stays meaningful.
- **State is per-session ephemeral.** `.harness/.evidence-reads` resets on `/work` start; gitignored; atomic-write via tmp+rename. No cross-session contamination; no `git status` noise.

### Negative

- **Hook latency on every Read/Write/Edit.** Adds Python-process invocation + PLAN.md parse + state-file I/O on every relevant tool call. Mitigation: fast-path early-exit when `would_flip_checkbox` detects the Write/Edit target isn't PLAN.md (no parse + no diff cost). Read recording is cheap (single JSON append).
- **Heuristic-vs-override calibration risk.** First weeks of dogfood will surface whether the heuristic's code-extension set is right, whether the test-dir list is complete, whether literal-verification-path match catches the operator's actual conventions. Mitigation: ship-instrumented + tune-from-real-use pattern (same precedent as `recall.py` rank-merge weights from plan #7a + `adapt_skills.py` 6-rule rubric from plan #7b). The 61 unit tests anchor the current behavior so changes are deliberate.
- **Block messages are the operator-facing surface.** If the message is unclear, operators will reflex-disable the hook rather than understand why it fired. Mitigation: block message includes the expected requirement + the recorded reads + the 3 recovery paths (read evidence / add opt-out / reset state). Tested locally + in CI smoke tests (the [f] sub-test verifies the message contains both "evidence-tracker: default-FAIL" + the expected path).
- **Self-hosting awkwardness.** This repo (crickets) doesn't itself have a harness install — so the hook can't dogfood against this repo's own development. First real dogfood happens when an operator installs both `crickets` + `agentm` into a target project + the next `/work` task there. The harness repo (agentm) is the natural first dogfood target.

### Load-bearing assumptions (re-audit triggers)

1. **Operator runs Claude Code as the primary host for `/work`** (not Antigravity-IDE-as-driver). The hook fires on Claude Code's PreToolUse event with the specific JSON shape (`tool_name` + `tool_input.file_path` + `tool_input.old_string` / `new_string` for Edit; `tool_input.content` for Write). Other hosts have different hook surfaces; the `supported_hosts: [claude-code]` constraint is deliberate. **Re-audit triggers**: ROADMAP item #17 (Antigravity 2.0 + Antigravity CLI host support) lands AND the new host exposes a comparable PreToolUse-style primitive — at that point, port the hook surface (probably as a sibling entry script per host). **Re-audit outcome 2026-05-25** (Plan #16, [ADR 0011](0011-antigravity-2-host-support)): Antigravity 2.0 + Antigravity CLI v1.0.2 host support shipped, but the new host **has no file-based hook surface** — hooks are Python decorators registered via `LocalAgentConfig(hooks=[...])` (from `google.antigravity.hooks`). The 9 hook types (`on_session_start`, `pre_turn`, `pre_tool_call_decide`, `post_tool_call`, `on_tool_error`, etc.) semantically map to PreToolUse/Stop/UserPromptSubmit/SessionStart from Claude Code, but the host requires SDK Python integration to register — there's no `.agents/hooks/` directory or `hooks.json` config file to dispatch to. **Decision**: the `supported_hosts: [claude-code]` constraint is preserved; evidence-tracker hook stays Claude-Code-only. **Future direction**: a Python sidecar adapter (`crickets-hooks-py` or similar) could translate file-based hook scripts to SDK decorator registration at agent-author boot time. Tracked as a FOLLOWUP candidate (`agentm/.harness/FOLLOWUPS.md`); not in scope for any current crickets release. **Next re-audit trigger**: if Google adds a file-based hook surface to agy / Antigravity 2.x in a future release, OR if the Python sidecar adapter ships as its own ROADMAP item.

2. **PLAN.md task headers stay at H3 with the `### N. <title>` shape**. The `_TASK_HEADER_RE` regex is `^### (\d+)\. (.+)$`. Status lines stay at `**Status:** [ ]` / `[x]`. **Re-audit triggers**: harness `/plan` spec amendment that changes task-header shape (would require parser update + a one-time migration of in-flight PLAN.md files); operator preference shift toward sub-tasks or nested task hierarchies.

3. **Reads through Claude Code's `Read` tool are the canonical evidence signal**. The hook ignores Bash `cat`, `grep`, `head` — those produce content the agent sees but the hook doesn't observe. **Re-audit triggers**: operator dogfood surfaces that the agent legitimately uses Bash-based reads for evidence + the hook blocks too often. At that point, extend to PreToolUse on `Bash` with input-pattern matching (more complex; deferred to follow-up).

4. **Verification-quality grading is out of scope for v1**. The hook checks that *some* matching file was read; doesn't grade whether the agent actually understood what they read. A future follow-up could escalate ambiguous cases to the `evaluator` sub-agent (ADR 0002 — fresh-context grading with caller-supplied rubric). **Re-audit triggers**: dogfood shows the hook accepts "the agent read tests/foo.py but didn't actually check what it asserts"; at that point, design Pass 2 LLM grading on top of the deterministic Pass 1 heuristic (same two-pass pattern as `adapt-evaluator` from plan #7b).

## Related

- [ADR 0003 — base operator-control hooks](0003-base-operator-hooks) — precedent for `kind: hook` installer pattern + Claude-Code-only scope + graceful-skip discipline.
- [ADR 0001 — crickets purpose](crickets-hld) — D7 stdlib-only convention (no new third-party deps; the 720-line helper uses only `argparse` / `fnmatch` / `json` / `os` / `pathlib` / `re` / `tempfile`).
- [ADR 0007 — MemoryVault Discovery + Mining](crickets-hld) — precedent for the architectural-enforcement-via-write-allowlist pattern (adapt-evaluator's scoped write boundary mirrors evidence-tracker's tool-input gate — both physically prevent a class of failure rather than relying on operator vigilance).
- [Use The Evidence-Tracker Hook how-to (Agent M wiki)](https://github.com/alexherrero/agentm/wiki/Use-The-Evidence-Tracker-Hook) — operator-facing guide. The hook moved to Agent M in v2.0.0 (V4 #36 reorg) along with its operational docs.
- [evidence-tracker hook manifest](https://github.com/alexherrero/crickets/blob/main/hooks/evidence-tracker/hook.md) — technical reference (manifest + entry-point docs).
- [`evidence_tracker.py`](https://github.com/alexherrero/crickets/blob/main/hooks/evidence-tracker/evidence_tracker.py) — implementation (~720 lines, stdlib-only, 61 unit tests).
- [agentm `/work` §5b](https://github.com/alexherrero/agentm/blob/main/harness/phases/03-work.md) — the harness-side contract this hook enforces.
- [agentm ROADMAP item #9](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP.md) — the roadmap entry that triggered this work.
- [cwc-long-running-agents](https://github.com/anthropics/cwc-long-running-agents) — upstream pattern source for the default-FAIL philosophy.
