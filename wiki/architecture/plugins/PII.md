<!-- mode: index -->
# PII Guardrail

Scan diffs and the working tree for personal information — emails, personal paths, API keys, phone numbers — before you commit or push. It ships the agent-facing **`pii-scrubber`** skill: the interactive layer that **remediates** findings rather than just blocking on them.

## Install

```bash
claude plugin install pii@crickets
```

On Antigravity, install by path (see [Install crickets plugins](Install-Into-Project)). The skill runs on both hosts.

## What it ships

| Primitive | Kind | What it does |
|---|---|---|
| **`pii-scrubber`** | skill | scans the current git diff (or working tree) for PII, surfaces each finding as `file:line` with a redaction suggestion, and loops until clean. Invoke it before any `git push`. |

The skill drives the detector at `scripts/check-no-pii.sh`; it locates it via `$AGENT_TOOLKIT_PATH` or the sibling-clone convention.

## How it composes

- **Standalone** — `requires: []`; runs on both hosts.
- **The interactive layer of a defense-in-depth stack.** The scrubber fixes PII *before* the deterministic enforcers would block: pair it with the **pre-push git hook** (`templates/hooks/pre-push`) and a **CI gate** for hard enforcement. That three-layer setup — interactive skill · mandatory pre-push hook · CI gate — is how crickets guards its own public repo. The hook is the final, non-negotiable enforcer; the skill is the courtesy layer that keeps you from fighting it in a loop.

## Why it works

A blocking check alone is adversarial — you hit it at push time and bisect your own diff to find the offending line. Splitting the job in two fixes that: the **agent-facing scrubber** catches PII early and helps you redact it once, while the **deterministic hook + CI gate** guarantee nothing slips through even if the skill is skipped. Belt and suspenders — the right posture for a public repo where a leaked email or key is permanent.

## Related

- [Install crickets plugins](Install-Into-Project) — all three install modes.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Customization types](Customization-Types) — skill vs the hook/CI enforcers it pairs with.
- [Compatibility](Compatibility) — supported hosts.
