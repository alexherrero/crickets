# Cross-Repo Memory Protocol

How [agentic-harness](https://github.com/alexherrero/agentic-harness) reads from + writes to the toolkit-side `/memory` skill at phase boundaries.

## Position in the toolkit

The `memory` skill in this repo provides the **vault-side primitives**: `save.py` writes entries, `recall.py` queries them, `reflect.py` periodically mines transcripts, `index_skills.py` keeps the personal-skills index fresh. These run from inside Claude Code via the `/memory` skill or directly as Python CLIs.

The **harness** in [`agentic-harness`](https://github.com/alexherrero/agentic-harness) is a separate repo that shells out to these scripts at deliberate phase boundaries (`/setup`, `/plan`, `/work`, `/review`, `/release`, `/bugfix`). The harness owns the *when*; the toolkit owns the *how*.

This page documents the contract between the two — what the harness expects from the toolkit's scripts, what guarantees the toolkit makes, and how the protocol degrades gracefully when one side isn't installed.

## The contract

### What the harness expects

The harness's dispatcher (`scripts/harness_memory.py` in agentic-harness) calls two toolkit scripts:

| Harness sub-command | Toolkit script | Args passed |
|---|---|---|
| `recall` | `recall.py query` *(planned; v1 reads files directly)* | `<query>` text, `-k 5`, `--vault-path` |
| `offer-save` (silent or post-confirm) | `save.py` | `--vault-path` `--group personal-projects/<slug>` `--body-file -` `<kind>` `<slug>` |

Discovery happens in this priority order:
1. `HARNESS_MEMORY_TOOLKIT_PATH` env (test override + non-standard installs).
2. `<harness-repo>/../agent-toolkit/skills/memory/scripts/` (sibling clone — the canonical setup).
3. `~/Antigravity/agent-toolkit/skills/memory/scripts/` (operator's default install location).

If none resolve, the harness logs `[harness_memory] toolkit not installed — recorded intent only` to stderr + continues. The phase doesn't error.

### What the toolkit guarantees

For the harness contract to hold across releases, the toolkit memory skill must:

1. **`save.py` accepts `--group personal-projects/<slug>` as a valid group path.** The current `_validate_group()` regex (`^[a-z0-9-]+(/[a-z0-9-]+)?$`) permits this; do not narrow it without bumping a MAJOR + amending this doc.
2. **`save.py` accepts body via `--body-file -` (stdin).** The harness streams content via subprocess stdin; if this surface changes, the harness contract breaks.
3. **`save.py` exit code is 0 on success.** Non-zero exits propagate to the harness as a save error (surfaced to operator stderr).
4. **`save.py` deduplicates entries** (per ADR 0007 §5 of this repo's memory skill). Idempotent save semantics mean cursor-deletion recovery in the harness can re-prompt for already-saved candidates without polluting the vault.
5. **`recall.py query` returns markdown-formatted results to stdout** *(planned; not blocking v1 of harness ROADMAP #8 — that release reads vault files directly).*

The harness assumes file-system-level vault layout established by [toolkit ADR 0007 §3](decisions/0007-memoryvault-discovery.md):
- `<vault>/personal-private/_always-load/*.md` — operator-global conventions.
- `<vault>/personal-projects/<slug>/_index.md` — project anchor.
- `<vault>/personal-projects/<slug>/decisions/<date>-<slug>.md` — decisions.
- `<vault>/personal-projects/<slug>/known-issues/<date>-<slug>.md` — gotchas.
- `<vault>/personal-projects/<slug>/open-questions/<date>-<slug>.md` — unresolved.

If any of these paths change, both sides break.

## Phase-boundary integration map

| Harness phase | Toolkit script used | Vault paths read | Vault paths written |
|---|---|---|---|
| `/setup` §1b + §8b | `save.py` | `_always-load/*` | `personal-projects/<slug>/_index.md` |
| `/plan` §1b + §4c | `save.py` | `_always-load/*` + `_index.md` + `decisions/*` + `open-questions/*` | `personal-projects/<slug>/open-questions/<date>-<slug>.md` |
| `/work` §1b + §7b + §7c | `save.py` | `_always-load/*` + `decisions/*` + `known-issues/*` | `personal-projects/<slug>/decisions|gotchas|known-issues/...` |
| `/review` §2b | — (read-only) | `_always-load/*` | none |
| `/release` §1c + §5b + §5c | `save.py` | `_always-load/*` + `decisions/*` | `personal-projects/<slug>/decisions/<date>-<slug>.md` |
| `/bugfix` §2b + §4b | `save.py` | `_always-load/*` + `known-issues/*` | `personal-projects/<slug>/known-issues/<date>-<slug>.md` |

Self-modulating ask (per harness ADR 0007 §Q4) means most saves happen silently with a stderr notice when the agent's confidence is high; only ambiguous cases prompt. The toolkit's `save.py` is unaware of this — it just writes when called.

## Graceful-skip protocol

Either side can be absent and the other continues to work:

- **Toolkit absent, harness present:** harness phases run unchanged. The dispatcher's `available` sub-command returns exit 1; `recall` returns empty; `offer-save` records intent only with stderr notice.
- **Harness absent, toolkit present:** the operator invokes `/memory save`, `/memory search`, etc. directly via the skill. No phase-boundary auto-context, but the manual surface is fully functional.
- **Both present, vault missing:** `MEMORY_VAULT_PATH` unset or directory missing causes the toolkit's `_resolve_vault_path()` to error. The harness dispatcher checks `MEMORY_VAULT_PATH` before invoking the toolkit, so the toolkit-side error never fires — harness graceful-skips at its own boundary.

## Versioning + compatibility

This contract is **soft** — neither repo's CI verifies the cross-repo integration. The harness ships smoke tests against a fixture toolkit stub (see `scripts/test_harness_memory.py` in agentic-harness, `TestOfferSaveBehavior` + `TestOfferSaveToolkitAbsent`). The toolkit's `save.py` interface stability is implicit: it's documented in `SKILL.md`, exercised by `test_save.py`, and changes infrequently.

If you change `save.py`'s CLI flags, body input format, or exit code semantics, the harness's `_invoke_toolkit_save()` function (in `scripts/harness_memory.py`) needs a matching update. The contract is small — 7 flags, one stdin stream, exit-0-on-success — so drift risk is low. But check this page when amending either side.

## Related

- [Memory skill SKILL.md](../../skills/memory/SKILL.md) — the canonical surface this contract calls into.
- [ADR 0007 — MemoryVault Discovery + Mining](decisions/0007-memoryvault-discovery.md) — vault layout + the operator-confirmed save pattern.
- [agentic-harness ADR 0007 — Auto-context into harness phases](https://github.com/alexherrero/agentic-harness/blob/main/wiki/explanation/decisions/0007-auto-context-into-harness-phases.md) — harness-side ADR with all 5 design calls (Q1–Q5).
- [agentic-harness Use Auto-Context how-to](https://github.com/alexherrero/agentic-harness/blob/main/wiki/how-to/Use-Auto-Context-In-Harness-Phases.md) — operator-facing per-phase walkthrough.
- [`scripts/harness_memory.py`](https://github.com/alexherrero/agentic-harness/blob/main/scripts/harness_memory.py) — the harness-side dispatcher implementation.
