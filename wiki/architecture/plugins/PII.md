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
| **`pii-patterns`** | rule | proactive standing instruction: never write real emails, personal paths, API keys, or phone numbers into committed content — use RFC 2606 domains, `$HOME`/`~`, env-var references, and reserved phone ranges (555-01xx) as stand-ins. Fires while composing, before anything reaches a diff. |
| **`pii-scrubber`** | skill | scans the current git diff (or working tree) for PII, surfaces each finding as `file:line` with a redaction suggestion, and loops until clean. Invoke it before any `git push`. |

The rule is the **proactive layer** — it keeps real values out of content from the moment of writing. The skill is the **reactive layer** — it catches anything that slipped through at scan time. The skill drives the detector at `scripts/check-no-pii.sh`; it locates it via `$AGENT_TOOLKIT_PATH` or the sibling-clone convention.

## How it composes

- **Standalone** — `requires: []`; runs on both hosts.
- **A four-layer defense-in-depth stack.** The proactive rule keeps real values out while writing; the scrubber catches anything that slips into a diff; the pre-push hook (`templates/hooks/pre-push`) blocks non-zero at push time; and a CI gate is the final backstop. The layers compose from coarse-grained (rule, always active) to fine-grained (scrubber, operator-invoked) to deterministic enforcement (hook + CI). Pair the rule + scrubber with the hook and CI gate for the full defense crickets uses on its own public repo.

## Why it works

A blocking check alone is adversarial — you hit it at push time and bisect your own diff to find the offending line. Splitting the job into four layers fixes that: the **`pii-patterns` rule** keeps real values out of committed content from the start; the **agent-facing scrubber** catches anything that slipped through and remediates it interactively; the **deterministic pre-push hook** blocks regardless of whether the skill was invoked; and the **CI gate** is the backstop for anything that reaches GitHub. Four layers, one guarantee — the right posture for a public repo where a leaked email or key is permanent.

## Related

- [Install crickets plugins](Install-Into-Project) — all three install modes.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Customization types](Customization-Types) — skill vs the hook/CI enforcers it pairs with.
- [Compatibility](Compatibility) — supported hosts.
