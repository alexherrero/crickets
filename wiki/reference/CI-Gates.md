<!-- mode: reference -->
# CI gates

"Is it green" has one answer in crickets: the local gate battery passes. This page lists every gate in it, the CI matrix that mirrors it, and where to look when one fails.

A push whose full diff is confined to `wiki/**` and/or `*.md` files skips the CI matrix entirely (`paths-ignore` on each workflow's `push`/`pull_request` triggers) — a diff mixing even one non-doc file with any number of doc files still runs it in full.

## ⚡ Quick Reference

One command runs every deterministic gate locally:

```bash
bash scripts/check-all.sh
```

| Gate | What it checks |
|---|---|
| `lint_src` | `src/` source of truth — `group.yaml` + every primitive's frontmatter (incl. the `standalone ⟺ requires: []` invariant and `enhances:` cross-references) |
| `capability naming` | `check-capability-naming.py` — plugin and capability names obey the AG naming rule |
| `unit tests` | the `scripts/` test suite (`test_*.py` — lint, model, generator, plus the CI-consistency check that enforces the both-places rule) |
| `generate drift` | `generate.py check` — committed `dist/` matches a fresh generation, byte-for-byte |
| `version bump` | each plugin whose `src/<slug>/**` changed must bump its `group.yaml` `version:` (compares against `origin/main`; graceful-skips when that ref is unresolvable) |
| `check-wiki` | the wiki linter, `--strict` (Diátaxis modes, links, sidebars, basename collisions) |
| `check-syntax` | `bash -n` every `.sh` (CI also AST-parses every `.ps1`) |
| `check-hook-parity` | Asserts every `developer-safety` hook keeps its `.sh`/`.ps1` twins behaviorally paired — neither twin may reference a workspace-relative `.harness/…` path without first resolving the workspace from the host's hook-input contract (`workspacePaths` + a `cd`/`Set-Location`). |
| `check-no-pii` | the PII regex scanner over the whole tree (crickets is public) |
| `opinion-snapshot-parity` | `check-opinion-snapshot-parity.py --report` — keeps the committed `scripts/opinion-snapshots/<name>.md` snapshots (what `generate.py` bakes into `dist/` for cross-plugin opinion consumers) honest against agentm's live `opinions/<name>.md`; graceful-skip (exit 0) when no agentm sibling is checked out to diff against. Report-only: drift is surfaced, not blocking, until an automated refresh exists. |
| `opinion-self-provider-drift` | `check-opinion-self-provider-drift.py --report` — for a **self-provider** opinion binding (the caller IS the opinion's `implements:` artifact, e.g. `code-review`→`good`), flags agentm's `opinions/<name>.md` stub if it drifts from curated anchor phrases in the caller's own shipped prose (`adversarial-reviewer.md`) — never the reverse; graceful-skip (exit 0) when no agentm sibling is checked out. Report-only, same posture as `opinion-snapshot-parity`. |
| `cross-repo-script-parity` | `check-cross-repo-script-parity.py --report` — keeps crickets' canonical `src/privacy/scripts/check-no-pii.sh` + `src/wiki/scripts/check-wiki.py` honest against agentm's independently-maintained `scripts/check-no-pii.sh` + `scripts/check-wiki.py`. Not a byte-diff — compares the PII "kind" names and the lettered check-wiki rule identifiers each copy declares, since the two pairs carry legitimate one-sided content (crickets' check-wiki.py has 3 component-overview rules — `m`/`n`/`o` — agentm's wiki has no page-type for, documented in the script's own `ALLOWED_CRICKETS_ONLY_RULES`). Graceful-skip (exit 0) when no agentm sibling is reachable locally; runs for real in CI inside the `obsidian-vault-conformance` job, the one job that already checks out the agentm kernel. Report-only, same posture as the two opinion gates above. |
| `board sync` | `check_project_sync.py` — the vault==board drift oracle: computes the expected GitHub Project board state from `board-items.json` and diffs it against the live board (read-only `gh issue list`), failing on any drift; graceful-skip (exit 0) when there's no `project.json` or no `gh` |
| `tag-reachability` | all git tags must point to commits reachable from `main` — concurrent-release coordination backstop; graceful-skip when `main` doesn't resolve (fresh repos, non-main default-branch names) |
| `conformance-suite` | **Active.** A dedicated `obsidian-vault-conformance` CI job (Linux + Windows) runs the `obsidian-vault` plugin backend's conformance / discovery / doctor suites against a checked-out agentm kernel, on every push; local discovery rides `check-all.sh`'s unit-test gate with graceful-skip when the kernel isn't checked out. |

It prints a PASS/FAIL table and exits non-zero on any failure. Run it before every commit.

## The CI matrix

Three OS workflows run on **every push and every PR**. All three run the toolchain gates (source lint · unit tests · drift · wiki lint); the syntax checks follow each OS's shell surface, and gitleaks rides the Linux leg:

| OS | Workflow | What it runs |
|---|---|---|
| Linux (`ubuntu-latest`) | [`tests-linux.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/tests-linux.yml) | toolchain gates · `.sh` + `.ps1` syntax · PII scan · gitleaks |
| macOS (`macos-latest`) | [`tests-mac.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/tests-mac.yml) | toolchain gates · `.sh` + `.ps1` syntax · PII scan |
| Windows (`windows-latest`, PowerShell 7+) | [`tests-windows.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/tests-windows.yml) | toolchain gates (under `PYTHONUTF8: 1`) · `.ps1` syntax · PII scan |

The single `CI` badge on the README + wiki Home points at [`ci-all.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/ci-all.yml), an aggregate workflow that waits for all three OS workflows and reports a combined result. To drill into a failure, click the badge, open the Actions tab, and pick the failing OS; the failing step names the gate.

## What CI adds beyond the local battery

- **gitleaks** — the industry-standard secret scanner, alongside `check-no-pii.sh` (two independent PII/secret layers; the pre-push git hook is the third, on your machine).
- **PowerShell syntax** — `check-syntax.ps1` AST-parses every `.ps1` (locally this runs only where `pwsh` is installed).
- **`claude plugin validate`** — runs in [`tests-linux.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/tests-linux.yml)'s `validate` job, which installs `@anthropic-ai/claude-code` via npm first, then validates `dist/claude-code/.claude-plugin/marketplace.json` and every `dist/claude-code/plugins/*/` directory non-strict (the marketplace `capabilities:`/`enhances:` fields are soft-composition metadata outside Claude's schema, and `--strict` would flag them as errors instead of the harmless warnings they are).
- *(Not in CI:)* **`agy plugin validate`** — `agy` has no npm/CI-installable distribution, so Antigravity plugin loadability stays proven at dogfood time only.
- **Wiki publish** — [`wiki-sync.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/wiki-sync.yml) (`[W] Update Wiki`) rsyncs `wiki/` to the GitHub wiki on every push to `main`, with a case-insensitive duplicate-basename check.

## Adding a gate

When a new check earns its keep, add it in **both places**: a `run` line in `scripts/check-all.sh` *and* a step in the three `tests-*.yml` workflows — the battery stays the single source of truth for "is it green," and `scripts/test_ci_consistency.py` fails the battery if they drift.

## Related

- [Compatibility](Compatibility) — supported hosts + the per-plugin/hook support matrices.
- [Modify a plugin](Modify-A-Plugin) — the edit → generate → dogfood loop the gates protect.
- [Manifest schema](Manifest-Schema) — the contract `lint_src` enforces.
- [PII Guardrail](PII) — the interactive layer of the PII defense the gates back-stop.
- [Obsidian vault backend](Obsidian-Vault-Backend) — the vault backend plugin (sole vault-backend implementation since V5-3) whose conformance-suite gate is described above.
