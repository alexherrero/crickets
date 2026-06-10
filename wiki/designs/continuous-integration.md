---
title: Continuous Integration Design
status: draft
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-09
updated: 2026-06-09
last_major_revision: 2026-06-09
prd: <none — codified retroactively from the shipped CI surface: check-all.sh + the 5 workflows + the ci-gate part of crickets-v3-native-plugins + the PII guardrail layers>
project:
---

<!--
  Codification design (2026-06-09): the CI architecture shipped piecemeal across
  plans (v0.x guardrails → the v3.0 ci-gate part → the v3.1 wave gates) and had
  no holistic design doc. This codifies the system as built so future changes
  have a design to amend. Status lifecycle: draft → review → final → launched
  per /design author; the operator drives transitions.
-->

# Continuous Integration Design

## Context

### Objective

crickets is a public repo that generates everything it ships and has to work on two agent hosts and three operating systems. All of that can break quietly: generated files drift from their source, a script fails only on Windows, a personal detail slips into a public commit. CI is the safety net that catches these automatically, on every change. This design records how that system works and why it's built the way it is.

### Background

The ways this repo breaks are mechanical — generated output drifting from source, an OS-specific script failure, a personal detail in a public commit, a wiki link rotting — and mechanical failures are exactly what scripts catch best. Hand-run checks get skipped; an automatic gate doesn't. That's the project's standing posture: deterministic checks decide whether something ships, and LLM judgment only advises. The battery grew gate by gate as each failure class showed up — the drift gate arrived with the v3.0 generator ([crickets-v3-native-plugins](crickets-v3-native-plugins), replacing the old byte-parity check that died with the v2 installer), and the PII gates date back to the repo going public ([ADR 0001](0001-crickets-purpose)).

The same checks run in two places: locally as `bash scripts/check-all.sh` before each commit, and on GitHub on every push and pull request. Running in both places drives two of the design's rules. The battery can't depend on anything that exists only on one machine — it's plain Python and bash, no host CLIs — and a new check is always added to both places at once, so a local green means the same thing as a CI green. The flip side: work isn't *done* on a local pass; it's done when GitHub agrees (the wake-on-CI convention).

GitHub Actions is free for public repos, so there's no cost pressure to trim anything: all three operating systems run the toolchain gates on every push and every PR. The matrix has paid for itself — in the v0.x era the Windows leg alone caught three real failures (argument splitting, working-directory dependence, console encoding) that Linux and macOS would never have surfaced. That coverage narrowed during the v3 rebuild and was restored on 2026-06-09, with the Windows job pinning UTF-8 stdio against the encoding class outright.

## Design

### Overview

One set of checks, run in two places. On your machine, `bash scripts/check-all.sh` runs all six in sequence — source lint, unit tests, generated-output drift, wiki lint, shell syntax, PII scan — and prints a PASS/FAIL table. On GitHub, **all three operating systems run the toolchain gates** (source lint, unit tests, drift, wiki lint) on every push and pull request; the per-OS differences are small — each OS checks the script syntax its shells can parse, and a second secret scanner (gitleaks) runs on Linux. A small aggregate workflow waits for all three OS runs and reports one combined result — that's the `CI` badge on the README and the wiki Home. The rule that holds it all together: a new check lands in the local battery and the CI workflows together, or not at all. (The repo has one more workflow, the wiki publisher — that's deployment, not CI; it's covered in the [Wiki design](wiki-design).)

### Infrastructure

CI runs on **GitHub's Actions framework**: four CI workflows under `.github/workflows/`, each a set of jobs on GitHub-hosted runners (`ubuntu-latest` / `macos-latest` / `windows-latest` with PowerShell 7+). Nothing is self-hosted. (A fifth workflow in the same directory, `wiki-sync.yml`, **deploys** the wiki on commits — it isn't CI and is documented in the [Wiki design](wiki-design).)

**The workflows and their jobs:**

| Workflow | Job | What runs in it |
|---|---|---|
| `[T] Linux Tests` (`tests-linux.yml`) | `validate` | `lint_src.py` · `unittest` over `scripts/test_*.py` (incl. the CI-consistency check) · `generate.py check` · `check-wiki.py --strict` |
| | `syntax` | `check-syntax.sh` (`bash -n` every `.sh`) · `check-syntax.ps1` (AST-parse every `.ps1`) |
| | `pii-guardrails` | `check-no-pii.sh --all` · gitleaks (`.gitleaks.toml`) |
| `[T] Mac Tests` (`tests-mac.yml`) | `validate` | same toolchain gates as Linux's `validate` |
| | `checks` | `check-syntax.sh` · `check-syntax.ps1` · `check-no-pii.sh --all` |
| `[T] Windows Tests` (`tests-windows.yml`) | `validate` | same toolchain gates, under `PYTHONUTF8: 1` (the cp1252 guard) |
| | `checks` | `check-syntax.ps1` (PowerShell 7+) · `check-no-pii.sh --all` |
| `[T] CI All` (`ci-all.yml`) | aggregate | waits for the three OS workflows **by filename**; reports one combined result — the badge target |

**When what runs:**

| Trigger | What runs |
|---|---|
| Push to `main` | the 3 OS test workflows + `CI All` |
| Every pull request | the 3 OS test workflows + `CI All` |
| Locally, before each commit | `bash scripts/check-all.sh` — the same six gates, no host CLIs needed |
| Locally, on every `git push` | the pre-push PII hook (`templates/hooks/pre-push` installed into `.git/hooks/`) |

**What the scripts guarantee.** Each gate proves one thing and proves it deterministically: the source tree is well-formed (`lint_src`), the toolchain behaves (`unit tests`), committed `dist/` is byte-identical to a fresh generation (`generate.py check`), the wiki's structure and links hold (`check-wiki --strict`), every script parses (`check-syntax`), and nothing personal is anywhere in the tree (`check-no-pii` + gitleaks). The per-gate breakdown is the table in Detailed Design §1.

**Coverage.** There is no line-coverage percentage — coverage is tracked **by failure class**: each way the repo can break has a dedicated gate, and the unit suite covers the toolchain itself (lint rules, the source model, both emitters) via `unittest` discovery. The honest gap: nothing measures how much of `scripts/` the tests exercise; if that starts to matter, `coverage.py` is the standard answer.

**Third-party surface:** `gitleaks` (CI secret scanner) and `pyyaml` (the one pip install) — everything else is stdlib per the repo convention.

### Detailed Design

#### 1. The gate battery (what each gate proves)

| Gate | Script | Proves |
|---|---|---|
| `lint_src` | `scripts/lint_src.py` | the `src/` source of truth is well-formed: `group.yaml` contracts (`standalone ⟺ requires: []`; `enhances` targets exist, no self-enhance, `enhances ∩ requires = ∅`, capability declared) + every primitive's frontmatter |
| unit tests | `scripts/test_*.py` (unittest discovery) | the toolchain itself — lint rules, the src model, both generator emitters, mapping tables, determinism |
| generate drift | `generate.py check` | committed `dist/` is byte-identical to a fresh generation — the gate that makes committing generated output safe |
| `check-wiki` | `check-wiki.py --strict` | wiki integrity: Diátaxis mode discipline, link resolution, sidebar/index coverage, case-insensitive basename uniqueness |
| `check-syntax` | `check-syntax.sh` / `.ps1` | every `.sh` passes `bash -n`; every `.ps1` AST-parses (pwsh) |
| `check-no-pii` | `check-no-pii.sh --all` | no personal paths / emails / phone numbers / key-shaped strings anywhere in the tree, `dist/` included |

Gate scripts are deterministic and exit-code-honest — a gate that can flap (e.g. a non-deterministic generator) is treated as a bug in the gate's subject, not tolerated in the gate.

#### 2. The matrix + the aggregate badge

All three OSes run the toolchain gates on every push and PR (since 2026-06-09 — restoring the v0.x-era cross-OS coverage that caught the Windows-only failures); the syntax checks differ per shell surface, and gitleaks rides the Linux leg. The aggregate `ci-all.yml` exists because a README can carry only one badge: it waits for all three **by workflow filename** (`tests-linux.yml` …) and reports the conjunction — a rename of a workflow *file* breaks it, which is why the files carry warning comments and `test_ci_consistency.py` asserts the list. Diagnostic drill-down is badge → Actions tab → the failing OS → the failing step (steps are named after gates).

#### 3. Host plugin validation (outside both the battery and CI today)

`claude plugin validate` / the `agy` equivalent verify that each generated `dist/<host>/plugins/<group>/` is loadable by the real host. These need the host CLIs, so they are deliberately **outside** `check-all.sh` (which must run anywhere) — and as of this writing they are **not in the CI workflows either**: GitHub runners don't carry the host CLIs, so loadability is proven at **dogfood time** (the operator installs and exercises the generated plugin). The gap is recorded as the last entry in Technical Debt & Risks.

#### 4. The 3-layer PII defense

1. **`pii-scrubber` skill** (interactive, agent-facing) — scans the diff before commit, surfaces `file:line` findings with redactions, loops until clean. The courtesy layer: fix it once instead of fighting the enforcer.
2. **The pre-push git hook** (mandatory, client-side) — runs the detector on every push; blocks on findings. Catches whatever bypassed the skill.
3. **CI** (`check-no-pii.sh --all` + **gitleaks**) — defense in depth on the server side, over the full tree including generated `dist/`. Two independent scanners reduce single-pattern blind spots.

#### 5. Operating conventions — how the agent (LLM) works with CI

These conventions are about **agent behavior**: CI produces the signals, and the LLM running the session is the one acting on them.

- **Wake-on-CI:** after the agent pushes, it doesn't sit idle or declare victory — it schedules a wake (or polls `gh run list`) while continuing other work, reads the per-OS results when the runs finish, and only then closes out the task (`[x]`, progress append, "done" claims). Green locally is never treated as done; done is when the matrix agrees.
- **The both-places rule:** when the agent adds a gate, it adds it to `check-all.sh` *and* the CI workflows in the same change, so local and CI never diverge on what "green" means — and since 2026-06-09 that's **mechanically enforced**: `scripts/test_ci_consistency.py` (itself a battery test) fails if a battery gate is missing from the Linux workflow or a toolchain gate from any of the three.
- **Full-output feedback:** on a gate failure — local or CI — the agent reads the **full** failing log (check-all `cat`s it; in CI the agent pulls the failing step's log), never a summary. Failures are information to be read, not noise to be retried.

## Alternatives Considered

1. **Single-OS CI (Linux only).** Rejected on evidence: plan #13 caught three Windows-specific failures mid-plan that a Linux-only matrix would have shipped. The repo's scripts ship as `.sh` + `.ps1` pairs; both must be exercised.
2. **Generate `dist/` in CI instead of committing it (no drift gate needed).** Rejected in the v3.0 design: the marketplaces must serve static files, and committed output gives an auditable diff. The drift gate is the price, and it's cheap.
3. **One mega-workflow instead of three OS workflows + an aggregator.** Rejected: per-OS workflows give independent signal (which leg failed) and retry granularity; the aggregator exists solely because the README carries one badge.
4. **Putting host `plugin validate` into `check-all.sh`.** Rejected: the battery must run on any machine (and on contributors' machines) without `claude`/`agy` installed; host-dependent checks are CI-resident by design.
5. **LLM-based review as a CI gate.** Rejected per the harness principles: LLM judgment is non-deterministic and sycophantic under pressure; it augments (e.g. `/review`, adversarial reviewers) but never gates a merge. Gates are scripts with exit codes.
6. **A single PII layer (CI only).** Rejected: by the time CI fails, the secret is already in the pushed history. The pre-push hook blocks before publication; the skill fixes before the hook; CI back-stops both.

## Dependencies

- **GitHub Actions** (ubuntu/macos/windows hosted runners) + the GitHub wiki surface (`wiki-sync.yml`'s target).
- **gitleaks** — the CI secret scanner (third-party action).
- **Python 3 + pyyaml** — the gate scripts (pyyaml is the single non-stdlib dependency, installed per-run in CI).
- **PowerShell 7+** — the Windows leg + `.ps1` AST parsing.
- **The generator** (`generate.py`) — the drift gate is only meaningful because generation is deterministic (sorted iteration, stable JSON, no timestamps — a reliability property owned by the v3.0 design).
- **Host CLIs (`claude`, `agy`)** — the plugin-validation CI step only.

## Migrations

- **v2 → v3.0:** `check-lib-parity.sh` + `sync-lib.sh` deleted with the installer clean break; `generate.py check` replaced parity as the integrity gate (the ci-gate part). The PII scan widened from `src/`-only to the full tree including `dist/`.
- **v3.1 wave:** `lint_src` grew the `enhances:`/`capabilities:` cross-reference rules; the unit suite grew with each generator capability (commands, snippets, group scripts).
- **Wiki IA restructure (2026-06-08):** `check-wiki.py` (the gate) gained per-folder modes, the index landing mode, and case-insensitive rule-g. (The publish-side changes ride with the [Wiki design](wiki-design).) No operator-side migration — CI changes ride the repo.

## Technical Debt & Risks

*(Four earlier entries were **paid down on 2026-06-09**: `scripts/test_ci_consistency.py` enforces battery↔workflow consistency and the aggregate's filename list; the workflow files carry coupling warnings; every third-party action is SHA-pinned with its tag in a trailing comment; and the toolchain gates were extended to all three OSes — closing the Linux-only unit-suite gap, with `PYTHONUTF8` pinned on the Windows job against the cp1252 class.)*

1. **gitleaks/regex false positives.** Documentation examples — and now SHA pins, whose digit runs can mimic a phone number — can trip the scanners. The relief valves are the match-level allowlist and the **line-level allowlist** (added 2026-06-09 for `uses:`-pinned lines; kept separate so broad context patterns can't mask a real finding). Every allowlist addition must be justified in the commit. *Risk: allowlist rot — re-audit if it grows past a screenful.*
2. **CI minutes scale with the matrix.** 3 OS × every push, now with the toolchain gates everywhere; acceptable at current volume (and free on a public repo). *Re-audit if queueing becomes noticeable.*
3. **The pre-push hook is opt-in by nature** (a clone doesn't auto-install hooks). The skill + CI layers cover the gap, but a fresh clone pushing PII reaches the public repo before CI flags it. *Standing mitigation: bootstrap docs instruct installing the hook; re-audit if a real leak ever reaches `main`.*
4. **Host plugin validation is not automated.** `claude plugin validate` / `agy` checks need the host CLIs, which neither the battery nor the GitHub runners have — loadability rests on dogfood discipline. *Re-audit trigger: a generated plugin that passed every gate but failed to load on a host — then either install the CLIs in a CI job or add a schema-level validator to the battery.*
5. **SHA pins need deliberate upgrades.** Pinned actions no longer float with their major tag; security fixes in the actions arrive only when we re-pin. *Convention: re-pin (and re-verify the tag comment) when bumping; re-audit pins quarterly.*

## Quality Attributes

*(Only the attributes with real concerns are kept — N/A / low-relevance ones are omitted per the design convention.)*

### Security

Real, and the dominant concern — two distinct surfaces:

- **What CI protects:** crickets is public, so the PII/secret defense (Detailed Design §4) is the privacy story too. Three independent layers (interactive skill, mandatory pre-push hook, CI scanners ×2) with allowlist discipline; `check-no-pii` also keeps operator-machine paths out of the repo, so CI logs only ever contain repo content.
- **Protecting CI itself (supply chain):** the workflows execute third-party actions with repo access, so every action is **pinned to a full commit SHA** (the tag kept as a trailing comment, e.g. `actions/checkout@34e11487… # v4`) — a re-pointed or compromised tag can't execute in our CI. Upgrades are deliberate re-pins (Technical Debt & Risks #5). CI runs with default GitHub token scopes and the gate scripts need no secrets.

### Reliability

The battery must be deterministic to be trustworthy: gate scripts are exit-code-honest, the generator's determinism keeps the drift gate from flapping, and a flaky gate is treated as a bug, not retried into green. The aggregate workflow makes partial signal (one OS green) impossible to mistake for full green.

### Data Integrity

The drift gate **is** the integrity property: committed `dist/` provably matches `src/`. No other durable state is owned by CI.

### Latency

Real but modest: the battery is the developer's inner loop (`check-all.sh` before every commit), so it must stay fast — currently well under a minute locally. CI wall-time (~minutes across the matrix) sets the agent's wake-on-CI cadence (~90s polls).

### Testability

Self-referential and real: the gates are themselves unit-tested (`test_*.py` covers lint rules, the model, the emitters), and gate failures reproduce locally by construction (same battery). The CI-only pieces (gitleaks, the runners) are the exception — verifiable only in CI.

## Project management

*(Shipped system — work estimates omitted per the design convention.)*

### Documentation Plan

Every wiki page documenting this system:

- **[CI gates](CI-Gates)** (reference) — the operator-facing "is it green" page: the battery table, the matrix, the drill-down.
- **[Compatibility](Compatibility)** (reference) — the supported hosts/OSes the matrix verifies; points here for the workflow detail.
- **[PII Guardrail](PII)** (plugin page) — the interactive layer of the PII defense CI back-stops.
- **[Why deterministic gates run first](Why-Deterministic-Gates)** (explanation) — the principle behind the whole posture.
- **[Wiki design](wiki-design)** — the deploy-side sibling (the wiki publisher that is *not* CI).
- **This design** — the why/architecture record; future CI changes amend it together with CI-Gates.

### Launch Plans

Already launched: the PII guardrails since **v0.1.0** ([ADR 0001](0001-crickets-purpose), 2026-05-12); the drift gate + the battery's current core since **v3.0.0** (2026-06-01); the system in the shape described here since **v3.1.0** (2026-06-04).

## Operations

*(SLAs and a logging plan are omitted — GitHub's availability and Actions logs are the whole story; nothing of ours on top.)*

### Monitoring and Alerting

The aggregate badge is the at-a-glance monitor. The active monitoring is done **by the agent (LLM)**: after every push it polls the run set (wake-on-CI), reads the per-OS conclusions when they land, reports them to the operator, and treats a red `main` as the alert — pulling the failing step's full log rather than summarizing. There is no paging; the agent's next session surfaces anything missed.

### Rollback Strategy

CI config is repo-versioned: a bad workflow or gate change reverts by git like any other change. A red gate never auto-blocks anything beyond merging — rollback of the *checked* artifact is the normal git revert of the offending commit.

## Document History

| Date | Change | Status |
|---|---|---|
| 2026-06-09 | Codified retroactively from the shipped CI surface (check-all.sh · the 5 workflows · the ci-gate part · the PII layers · the wake-on-CI + both-places conventions). Authored directly against the 10-section template; operator to drive the review pass. | draft |
| 2026-06-09 | Operator review round 1 applied: title plain ("Continuous Integration Design"); Objective cut to 4 plain sentences; Background reshaped to 3 paragraphs (why · GitHub+local · free-for-public-repos); Overview de-jargoned; Infrastructure restructured platform-first (Actions framework → jobs chart → triggers chart → guarantees → coverage). Accuracy fix surfaced by the rework: host `plugin validate` is **not** a CI step (check-all.sh's comment was stale) — §3 corrected + new risk. Lessons codified into the design template prompts + a global voice-lesson overlay. | draft |
| 2026-06-09 | Operator review round 2 applied: wiki publishing reclassified as **deployment, not CI** — moved to the new [Wiki design](wiki-design) (cross-linked); operating conventions + Monitoring made **agent-explicit** (the LLM polls, reads, closes out); supply-chain **SHA-pinning** added under Security + Risks (tag-pins are mutable); cheap-paydown annotations on risks 1–3; N/A quality attributes omitted (new convention); Project management slimmed to Documentation Plan (all pages) + launch dates; Operations slimmed to Monitoring + Rollback. Conventions codified into the template + overlay. | draft |
| 2026-06-09 | **Hardening landed + accuracy pass.** The three cheap paydowns shipped: `test_ci_consistency.py` (the both-places rule + the aggregate's filename list, mechanically enforced from inside the battery), SHA-pinned actions (tags as comments), filename-coupling warning comments. Risks rewritten accordingly (+ a new deliberate-re-pin entry). Accuracy findings fixed: the aggregate couples by workflow **filename**, not display name; and **only Linux runs the full battery** — macOS/Windows run portability checks (new Risk #1 records the Linux-only unit-suite gap + the cheap extension). | draft |
| 2026-06-09 | **3-OS coverage restored** (operator call): the `validate` job (toolchain gates) extended to macOS + Windows, with `PYTHONUTF8: 1` pinned on the Windows job against the historical cp1252 class; the consistency test now asserts the toolchain gates on all three OSes (+ the UTF-8 pin). The Linux-only-unit-suite risk retired (4 paydowns total); fallout from the SHA pins (a digit run mimicking a phone number) fixed with a separate **line-level PII allowlist** scoped to pinned `uses:` lines — recorded under Risk #1. | draft |
