<!-- mode: reference -->
# CI gates

What "is it green" means for crickets — the local gate battery, the CI matrix it mirrors, and where to look when something fails.

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

The single `CI` badge on the README + wiki Home points at [`ci-all.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/ci-all.yml), an aggregate workflow that waits for all three OS workflows and reports a combined result. **Drill-down:** click the badge → the Actions tab → pick the failing OS → the failing step names the gate.

## What CI adds beyond the local battery

- **gitleaks** — the industry-standard secret scanner, alongside `check-no-pii.sh` (two independent PII/secret layers; the pre-push git hook is the third, on your machine).
- **PowerShell syntax** — `check-syntax.ps1` AST-parses every `.ps1` (locally this runs only where `pwsh` is installed).
- *(Not in CI:)* **host plugin validation** — `claude plugin validate` / `agy` checks need the host CLIs, which GitHub runners don't carry; plugin loadability is proven at dogfood time instead.
- **Wiki publish** — [`wiki-sync.yml`](https://github.com/alexherrero/crickets/blob/main/.github/workflows/wiki-sync.yml) (`[W] Update Wiki`) rsyncs `wiki/` to the GitHub wiki on every push to `main`, with a case-insensitive duplicate-basename check.

## Adding a gate

When a new check earns its keep, add it in **both places**: a `run` line in `scripts/check-all.sh` *and* a step in the three `tests-*.yml` workflows — the battery stays the single source of truth for "is it green," and `scripts/test_ci_consistency.py` fails the battery if they drift.

## Related

- [Compatibility](Compatibility) — supported hosts + the per-plugin/hook support matrices.
- [Modify a plugin](Modify-A-Plugin) — the edit → generate → dogfood loop the gates protect.
- [Manifest schema](Manifest-Schema) — the contract `lint_src` enforces.
- [PII Guardrail](PII) — the interactive layer of the PII defense the gates back-stop.
- [Obsidian vault backend](Obsidian-Vault-Backend) — the vault backend plugin (sole vault-backend implementation since V5-3) whose conformance-suite gate is described above.
