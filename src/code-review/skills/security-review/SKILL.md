---
name: security-review
description: "Structured security review via the three-tier boundary model: LLM API boundary (prompt injection / untrusted model output), persistence boundary (durable writes that are hard to roll back), and system execution boundary (shell commands, lateral movement risk). Work each tier in order; visual scanning is not this skill."
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# security-review

Structured threat modeling and vulnerability detection. Security review is **boundary-oriented**, not visual: the question for each piece of code is "which trust boundary does this cross, and is the crossing validated?"

## When to Invoke

- Before merging code that calls an external LLM API, executes shell commands, or writes to persistent storage.
- When reviewing agent code that handles untrusted input (user prompts, external API responses, file contents).
- When a diff adds a new integration point (a new API call, a new database write path, a new subprocess invocation).
- When the adversarial-reviewer surfaces a security concern but without enough depth to assess exploitability.

**Do NOT use as a substitute for a lint rule or a static analyzer.** Those tools catch the mechanical layer; this skill catches the architectural layer — the boundary that shouldn't be crossed without validation, not the individual line that violates a pattern.

## Threat Tiers

Work the tiers in order. A finding at any tier is a hard stop — document it before moving to the next tier.

### Tier 1 — LLM API boundary

**Risk:** the external model is attacker-controlled via prompt injection; its output is untrusted data, not a trusted instruction.

Any code that passes user-supplied content to an LLM API call, or that acts on LLM output without sanitization, crosses this boundary. Check: does the caller treat the model's response as a trusted command? Does user input reach the prompt without isolation? Does the model's output reach an execution context (shell, eval, database write) without validation?

### Tier 2 — Persistence boundary

**Risk:** vault writes, database mutations, and file overwrites are durable state — hard to roll back, especially under concurrent writes or partial failure.

Any code path that writes to persistent storage crosses this boundary. Check: is the write path idempotent? Is there a race condition between read and write? Is the rollback path tested? Does a failed write leave the store in a consistent state?

### Tier 3 — System execution boundary

**Risk:** shell command execution opens lateral movement — arbitrary commands, path traversal, privilege escalation.

Any `subprocess`, `exec`, `eval`, `os.system`, or shell interpolation crosses this boundary. Check: is user-controlled data interpolated into a shell string? Is the command constructed from untrusted input? Is the working directory or environment sanitized? Could the output of the command be used to pivot to a further execution?

## Process

### Step 1 — Map the diff to boundary crossings

Read the diff. For each change, classify which tier(s) it touches. Changes that touch no boundary tier are out of scope for this review — do not invent findings.

### Step 2 — Work each tier in order

For each tier that the diff touches, apply the tier's check questions above. For each check question: yes (validated) / no (unvalidated, finding) / not applicable.

### Step 3 — Report findings

For each finding: `VULNERABILITY <file>:<line> [Tier N]` — one sentence stating what is unvalidated and what an attacker can do with it. For each tier that passes: one sentence confirming what was checked and why it passes.

If no tier-relevant code was found: `NO ISSUES FOUND` — state which tiers were checked and why each was not applicable or passed.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "I reviewed the code, I didn't see any obvious issues." | Security review is structured threat modeling per boundary, not a visual scan. Work the tiers. "No obvious issues" after a visual pass is not a security finding — it is the absence of having looked. |
| "This is internal code, it won't be reached by attackers." | The LLM API boundary applies regardless of whether the attacker reaches it directly — prompt injection exploits the trusted internal path. |
| "I'll add input validation later." | An unvalidated boundary crossing is a vulnerability now. "Later" is not a mitigation. |

## Verification checklist

Before reporting complete:

- [ ] All three tiers were checked, or explicitly marked not applicable with a reason.
- [ ] Every finding is `VULNERABILITY file:line [Tier N]` with a one-sentence exploit path.
- [ ] `NO ISSUES FOUND` includes explicit tier-by-tier confirmation.
- [ ] No prose-only findings ("consider sanitizing input") — every finding names the specific line.
