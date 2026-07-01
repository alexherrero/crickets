<!-- mode: reference -->
# PII Guardrail

## Architecture

PII Guardrail keeps personal information — real emails, personal file paths, API keys, phone numbers — out of anything you commit or push. It works in four layers that back each other up, so a value that slips past one is caught by the next, and a value written correctly in the first place never triggers the last.

### Diagram

_None / not needed._

### How it works

The plugin runs a four-layer defense, from proactive to deterministic. The `pii-patterns` rule fires while you compose: it tells the agent to reach for safe stand-ins from the start — RFC 2606 domains like `alice@example.com`, `$HOME` in place of `/Users/<name>/`, env-var references instead of real tokens, and the NANP `555-01xx` range for phone numbers. When something slips through anyway, the `pii-scrubber` skill is the interactive layer: run it before a commit or push and it scans the diff (or the whole tree), surfaces every finding as `file:line` with a proposed redaction, and loops until the range is clean — remediating rather than just failing. Behind the skill sit two deterministic enforcers that live at the repo level: a mandatory `pre-push` hook that blocks a push regardless of whether the agent remembered to scan, and a CI gate that is the final backstop. Together the rule and skill aim to keep the hook from ever needing to fire.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. PII Guardrail is fully standalone. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | — | None. `requires: []` — it runs on its own. |
| Required by (hard) | — | None. |

### Why not

PII Guardrail is opinionated about what a safe stand-in looks like, and that won't suit every project. Reach for something else if:

- Your team already has secret-scanning you trust — a pre-commit framework, a hosted scanner, or your own CI check — and you don't want a second pass with its own opinions.
- You disagree with the prescribed stand-ins. The rule is specific about RFC 2606 domains, `$HOME`, angle-bracket placeholders, and the `555-01xx` range; a project with different conventions would fight it.
- The change is small or throwaway and never leaves your machine. The scan-and-remediate loop is worth it before a push, but can feel heavy on content that will never be committed.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`pii-patterns`](https://github.com/alexherrero/crickets/blob/main/src/pii/rules/pii-patterns.md) | rule | Proactive stand-ins — never write a real email, path, key, or phone number into committed content. |
| [`pii-scrubber`](https://github.com/alexherrero/crickets/blob/main/src/pii/skills/pii-scrubber/SKILL.md) | skill | Scans the diff or working tree for PII, surfaces findings as `file:line`, and loops until clean. |

### Configuration

No configuration — the plugin works out of the box.

## See also

- [Privacy design](crickets-privacy) — the four-layer defense in depth.
- [CI gates](CI-Gates) — the `check-no-pii` gate that backstops the scan.
- [Plugin anatomy](Plugin-Anatomy) — what a crickets plugin is.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)