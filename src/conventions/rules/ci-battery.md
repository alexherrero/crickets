---
name: ci-battery
description: Always set up a gate battery on a new project, run it before every commit, and add a new check to it as the project grows — check-all.sh (or its equivalent) is the single source of truth for "is it green."
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: ci-battery

Migrated in (crickets-conventions.md's Migrations spec) from agentm `AGENTS.md`'s "Running the checks" section — a re-home, not a rewrite of the underlying standard, generalized from that section's project-specific gate list to the standard itself.

**Always set up CI on a new project.** A project with no gate battery has no deterministic "is it done" signal — everything downstream (`/work`, `/review`) degrades to LLM judgment, which this domain's substrate (the `agentic-engineering` skill's "deterministic verification before LLM judgment" principle) exists to avoid.

**Run the battery before every commit.** Before every commit, run the full local gate battery — the one command that mirrors CI's deterministic checks. For a harness-based project this is `bash scripts/check-all.sh` or its project-specific equivalent; whatever the command, it must run the unit suite plus every project `check-*` gate, print a PASS/FAIL summary, and exit non-zero if any gate fails.

**Add a new check as the project grows.** As the project grows, add new checks to the battery (and a CI step) so the battery stays the single source of truth for "is it green" — a real quality gap discovered by hand and not folded into the battery will regress silently the next time.

### What is NOT an acceptable substitute

| Stated substitute | Why it is not acceptable |
|---|---|
| "I ran the tests manually and they looked fine" | Manual verification is not deterministic, not repeatable, and not what CI re-checks — the battery is the source of truth, not a spot-check. |
| "This change is small, I'll skip the battery this once" | The battery's value is in never being skipped — a "this once" exception is exactly how a real regression ships unnoticed. |
| "I found a gap but didn't add a gate for it" | A gap discovered and not gated is a gap that will resurface — add the check, don't just note it. |

### Enforcement

Before marking any task/commit as done, check:

1. Does the project have a gate battery at all? If not, that's the first thing to build, not a thing to work around.
2. Did the battery actually run (not "should pass" — ran, with output reviewed) before this commit?
3. If a new class of failure was found this session that the battery didn't catch, was a new check added for it?

If all three are yes, the commit is compliant. If any is no, run the battery or add the missing check before proceeding.
