---
name: privacy-review
description: "Structured privacy-engineering review of a diff/PR, adapted from OWASP ASVS V8 Data Protection, the OWASP Top 10 Privacy Risks, the NIST Privacy Framework, and ICO data-protection-by-design guidance. Runs a deterministic Semgrep pre-pass for the four mechanizable checks (PII-in-URL, PII-in-client-storage, plaintext-columns, third-party-sinks), then LLM-judges the non-mechanical practices (consent scoping, retention adequacy, erasure completeness, purpose limitation). Reports falsifiable PRIVACY-RISK <file>:<line> [ASVS-id] findings; never fixes."
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
---

# privacy-review

Adversarial review of a diff/PR for **privacy-engineering practice** — the structural mistakes a string scanner can't catch: a personal field flowing into a logger, a store with no deletion path, data collected beyond its consented purpose, PII sent to a third-party SDK. `pii-scrubber` catches a leaked secret in the diff; this skill catches a defect in the *shape* of the code. Modeled on its sibling `security-review` — same falsifiable-finding contract, same "assume a gap exists" framing.

**Deterministic-first.** The four mechanizable checks (PII-in-URL, PII-in-client-storage, plaintext-columns, third-party-sinks) run through the bundled Semgrep taint pack — regex/pattern, not LLM judgment. The LLM reasons only over the practices that genuinely require judgment: consent scoping, retention adequacy, erasure completeness, purpose limitation, data minimization. Semgrep can't express "was consent obtained for this purpose" — don't try to force it there.

## When to invoke

- Before merging a diff that introduces a new data-collection point, a new logger/telemetry call, a new database write of a personal field, or a new third-party SDK integration.
- When the adversarial-reviewer or `security-review` surfaces a privacy-shaped concern but without ASVS-anchored depth.
- As part of a `privacy-review`-gated release check for any change touching user data.

**Do NOT use as a substitute for `pii-scrubber`.** `pii-scrubber` catches a leaked secret/PII literal already in the diff — a detect-and-redact loop. This skill catches a privacy-engineering *defect in the design of the code itself*, whether or not any literal PII appears in the diff.

## What it checks

Nine practices, each keyed to a standard so every finding cites a concrete requirement, not a vibe:

| Practice | Anchor | Mechanized? |
|---|---|---|
| PII in a log / telemetry / third-party sink | ASVS-8.3.6 | Semgrep (third-party-sinks) + LLM (log/telemetry calls Semgrep can't enumerate) |
| No retention or deletion path | NIST Privacy Framework — Disassociate/Protect | LLM |
| Incomplete erasure (right-to-be-forgotten) | ICO data-protection-by-design | LLM |
| Purpose-limitation + consent reuse | OWASP Top 10 Privacy Risks — P1/P8 | LLM |
| Data minimization (over-collection + over-return) | OWASP Top 10 Privacy Risks — P2 | LLM |
| PII in URLs | ASVS-8.3.4 | Semgrep |
| PII in client storage | ASVS-8.2.3 | Semgrep |
| Plaintext personal data at rest | ASVS-8.2.1 | Semgrep |
| Production data in test fixtures | ASVS-8.3.1 | LLM |
| Unscoped access to personal data | ASVS-8.1.1 | LLM |

## Process

### Step 1 — Run the deterministic Semgrep pre-pass

```bash
semgrep --config "${CLAUDE_PLUGIN_ROOT:-src/privacy}/scripts/privacy-taint-pack.yml" --json <path-or-diff-range>
```

If `semgrep` isn't installed, note it explicitly ("Semgrep pre-pass skipped — binary not found; the four mechanizable checks were not run") and proceed to Step 2 anyway — the LLM pass still covers everything it can, but never silently claim the mechanized checks ran when they didn't.

Each Semgrep finding already carries the `PRIVACY-RISK <category> [ASVS-id]` shape (see the pack's own `message:` field) — pass these through into the final report unchanged, don't re-derive them.

### Step 2 — Read the diff for the five LLM-judged practices

For each of retention/deletion, erasure completeness, consent/purpose-limitation, data minimization, test-fixture production-data, and unscoped access: read the diff and ask the practice's anchor question directly. A change that touches none of these practices is out of scope for that row — do not invent a finding.

### Step 3 — Report findings

For each finding: `PRIVACY-RISK <file>:<line> [<ASVS-id or OWASP-P#>]` — one sentence naming the specific practice violated and why. Never prose-only ("consider adding a retention policy") — name the file:line.

If nothing is found across every practice checked: `NO PRIVACY ISSUES FOUND` — state which practices were checked (mechanized + LLM-judged) and why each passed or was not applicable.

**This skill never fixes.** Report findings; the caller (or a follow-up task) remediates.

## Opinions it consumes

`privacy-review` is designed to consume `opinion_resolve("good")` (what good privacy practice looks like) and `opinion_resolve("how-we-engineer")` (the review discipline) — the same by-name Opinion-registry request pattern `diagnostics`' `writer.py` uses (`PLAN-wave-d-opinion-wiring` task 1).

**Deferred, not wired, in this build.** `writer.py` can call `opinion_resolve()` because it has a genuine code-level render step (`_build_body()`, real Python assembling a written entry) to inject the resolved text into. `privacy-review` has no such render step — like its own shape-model `security-review`, it is a static markdown prompt file loaded verbatim; there is no code path that assembles this skill's system-prompt text at runtime. Injecting resolved opinion text into a markdown prompt file is exactly the grammar gap `PLAN-wave-d-opinion-wiring` found and deliberately left unbuilt (tracked as `task_a2bed2b9`, a follow-up design task for the markdown/skill-prompt consumer grammar). Wiring it here would mean inventing a one-off fix the sibling plan explicitly declined to improvise — so this binding stays a documented intent, not a working connection, until that grammar lands.

## Common Rationalizations

| Excuse | Why it's wrong |
|---|---|
| "The Semgrep pass came back clean, so privacy is fine." | Semgrep only covers the four mechanizable checks. Five more practices (retention, erasure, consent, minimization, fixtures, access scope) are never checked by a pattern — a clean Semgrep run is not a clean privacy review. |
| "This data is already public, so PII rules don't apply." | Data minimization and purpose-limitation apply regardless of a field's public/private classification elsewhere — the question is whether *this* collection point is within *this* feature's consented purpose. |
| "We'll add a deletion path later." | An unscoped, undeletable personal-data store is a finding now, keyed to the erasure-completeness practice — "later" is not a mitigation. |

## Verification checklist

Before reporting complete:

- [ ] The Semgrep pre-pass ran (or its absence was explicitly noted, never silently skipped).
- [ ] All five LLM-judged practices were checked, or explicitly marked not applicable with a reason.
- [ ] Every finding is `PRIVACY-RISK file:line [ASVS-id]` with a one-sentence violation statement.
- [ ] `NO PRIVACY ISSUES FOUND` includes explicit per-practice confirmation (mechanized + LLM-judged).
- [ ] No prose-only findings — every finding names the specific line.

## See also

- [`privacy-taint-pack.yml`](../../scripts/privacy-taint-pack.yml) — the bundled Semgrep pack backing Step 1.
- `pii-scrubber` (same plugin) — catches a leaked secret/PII literal already in the diff; this skill catches a design-shaped defect instead.
- `security-review` (code-review plugin) — the shape-model this skill is modeled on: same falsifiable-finding contract, same deterministic-first discipline.
