# Gate-battery inventory

Objective house facts, cited by `conventions` rules — not gated itself (no `check-*.sh` enforces this doc staying current; it is descriptive, kept in sync by hand when `scripts/check-all.sh` changes).

The `bash scripts/check-all.sh` battery this repo's own [`ci-battery`](../rules/ci-battery.md) rule requires, as of this writing:

| Gate | What it checks |
|---|---|
| `lint_src` | `src/` tree structural validity — `group.yaml` fields, primitive frontmatter, kind/host expressibility |
| `capability naming` | declared `capabilities:` names follow the naming convention |
| `no-dangling-name` | no plugin/capability name is referenced but never declared |
| `unit tests` | the full `scripts/test_*.py` suite via `unittest discover` |
| `evidence-tracker self-test` | the code-review evidence-tracker hook's own self-test |
| `generate drift` | `dist/` matches what `scripts/generate.py build` would produce from `src/` |
| `dist-references` | every emitted cross-file reference resolves inside its own plugin tree |
| `version bump` | a plugin whose `src/<slug>/**` changed also bumped `group.yaml`'s `version:` |
| `check-wiki` | wiki structural rules (mode declarations, headings, length ceilings, naming, link resolution) |
| `check-slop` | anti-slop prose sweep (banned LLM-tell phrases) |
| `voice-floor-parity` | the always-load voice floor stays a superset of the voice rule pack |
| `check-syntax` | every shell/PowerShell script under `src/` parses cleanly |
| `hook-parity` | every developer-safety hook's `.sh`/`.ps1` twins stay behaviorally paired |
| `check-no-pii` | no personal information (emails, personal paths, API keys, phone numbers) in the tracked tree |
| `board sync` | the vault's `board-items.json` and the GitHub Project board agree |
| `tag-reachability` | every release tag points at a commit reachable from `main` |

CI additionally runs a heavier `smoke-install` + `gitleaks` pass on every push (not part of the local `check-all.sh` battery, since both are slower than a pre-commit run should be).

This table is descriptive, not authoritative — `scripts/check-all.sh` itself is the single source of truth (per the `ci-battery` rule's own framing); re-derive this table from that file's `run "<name>" …` lines if the two ever disagree.
