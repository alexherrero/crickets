<!-- mode: index -->
# PII Guardrail

_Scan diffs and the working tree for personal information — emails, personal paths, API keys, phone numbers — before you commit or push. A four-layer defense: rule (proactive) → scrubber (reactive) → pre-push hook (deterministic) → CI gate (backstop)._

Full design detail: [privacy design](crickets-privacy).

## How it composes

- **Standalone** — `requires: []`; runs on both hosts.

## Why it works

A blocking check alone is adversarial — you hit it at push time and bisect your own diff. The `pii-patterns` rule keeps real values out from the moment of writing; the `pii-scrubber` skill catches anything that slipped through and remediates it interactively; the deterministic pre-push hook blocks regardless; and CI is the backstop. Four layers, one guarantee.

## Related

- [Install crickets plugins](Install-Into-Project) — all three install modes.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is + its structure.
- [Compatibility](Compatibility) — supported hosts.

[Architecture](Architecture) · [Plugins](Plugins) · [Home](Home)
