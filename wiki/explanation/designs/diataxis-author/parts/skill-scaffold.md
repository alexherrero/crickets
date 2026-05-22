---
parent_design: ../../diataxis-author.md
part_slug: skill-scaffold
title: "Skill scaffold — manifest + 5 sub-command stubs + diataxis-evaluator sub-agent stub + installer wiring"
status: pending
visibility: published
author: alex
contributors: []
created: 2026-05-22
updated: 2026-05-22
last_major_revision: 2026-05-22
dependencies: []
estimated_scope: S
plan: "13-part-1"
prd:
project:
---

# Skill scaffold — manifest + 5 sub-command stubs + diataxis-evaluator sub-agent stub + installer wiring

**Parent design:** [diataxis-author](../../diataxis-author.md) — see Detailed Design subsections 1-5 for the 5 sub-commands this scaffold stubs out; subsection 7 for the documenter-as-worker repurposing; subsection 6 for the AgentMemory integration shape this scaffold reserves.

## Scope

Foundational ship for the diataxis-author skill. Lands the skill on disk + in the host install destinations; all 5 sub-commands are stubbed (body says "lands in part N") but the manifest, installer wiring, smoke install tests, and `diataxis-evaluator` sub-agent stub are real. Mirrors plan #7a part 1's shape (`write-primitives` scaffolded the `memory` skill with stubs that filled in across subsequent parts).

**1. Skill manifest** at `agent-toolkit/skills/diataxis-author/SKILL.md`:

- Frontmatter: `name: diataxis-author`, `description: <one sentence per /memory's shape>`, `kind: skill`, `supported_hosts: [claude-code, antigravity]`, `version: 0.1.0`, `install_scope: project`.
- Body sections: "What this skill does" (1 paragraph), "When to reach for which sub-command" (table with 5 rows), "Sub-commands" (5 sub-sections, each a stub with status note + planned invocation shape from the parent design § Detailed Design), "Tool allowlist", "Host scope", "Cross-references", "Status".
- Status: stub-shipped per the established pattern (matches plan #7a part 1's memory skill scaffold).

**2. `diataxis-evaluator` sub-agent stub** at `agent-toolkit/agents/diataxis-evaluator.md`:

- Frontmatter mirroring `adapt-evaluator.md` and `memory-idea-researcher.md` (read-only sub-agent).
- Tool allowlist: `Read, Glob, Grep, WebFetch` (WebFetch for ADR 0004 cross-reference; can drop if not needed in v1).
- Caller-supplies-inline-rubric pattern.
- Body: "What this sub-agent does" + "Caller-supplies-inline-rubric contract" + "Tool allowlist" + "What it never does" + "See also". Body stub status indicates dispatch flow lands in part 3.

**3. Installer wiring**:

- `install.sh` + `install.ps1` add `diataxis-author` to the standalone-skills walk (no special-cased function — handled by the existing skill-walk loop).
- `diataxis-evaluator` sub-agent added to the standalone-agents walk + `.claude/agents/diataxis-evaluator.md` + `.agent/skills/diataxis-evaluator/SKILL.md` (Antigravity wrap; same dual-host pattern as `adapt-evaluator`).
- No new `--no-X` escape hatches needed — skill installs unconditionally per the established convention.

**4. Smoke install tests** (bash + pwsh):

- Expected files list gains 4 new paths: `.claude/skills/diataxis-author/SKILL.md` + `.agent/skills/diataxis-author/SKILL.md` + `.claude/agents/diataxis-evaluator.md` + `.agent/skills/diataxis-evaluator/SKILL.md`.
- Negative-existence assertion: no `agent-toolkit/skills/diataxis-author/scripts/` Python files yet (those land in subsequent parts; verify scaffold doesn't ship empty/broken script files).
- Manifest validation: `validate-manifests.py` runs against the new manifests; passes.

## Verification

- `bash agent-toolkit/install.sh ~/scratch` produces all 4 expected paths.
- `validate-manifests.py` clean on both manifest files.
- Smoke install tests pass on Linux + Mac + Windows.
- Skill `SKILL.md` body renders cleanly in markdown preview (no broken `<!-- -->` blocks).
- Sub-agent allowlist enforced (no Bash, no unexpected tools).

## Out of scope

- Sub-command bodies beyond stubs — those land in parts 2-5.
- `diataxis-evaluator` sub-agent dispatch logic — body has the contract docs but no operational flow until part 3.
- AgentMemory integration code — placeholder mentioned in skill body's Cross-references; lands in part 5.

## Tasks (DRAFT — refine via `/plan` when promoted)

1. Write `skills/diataxis-author/SKILL.md` (manifest + body skeleton + 5 sub-command stubs).
2. Write `agents/diataxis-evaluator.md` (read-only sub-agent stub).
3. Update `install.sh` + `install.ps1` (no new flags; ride the existing skill + agent install loops).
4. Update smoke install tests' expected-files list + negative-existence assertions (bash + pwsh).
5. Local verification (bash + pwsh smoke; manifest validator; `check-syntax.sh`; `check-no-pii.sh`); commit + push + CI wake.

## Verification criteria

1. All 4 expected paths land in scratch install.
2. validate-manifests.py clean.
3. Smoke install + check-syntax + check-no-pii clean on 3-OS CI matrix.
4. Skill body renders cleanly in markdown preview.
5. Sub-agent's tool allowlist matches spec (no Bash; no Write/Edit outside scoped allowlist).
6. No new third-party deps added (stdlib-only per ADR 0007 D7).
7. No `agent-toolkit/skills/diataxis-author/scripts/` directory yet (sub-command Python lands in parts 2-5).

## Locked design calls (inherited)

Per parent design's Design + Alternatives + Detailed Design:

- **Q1**: scope = author + maintain + migrate (subsume `migrate-to-diataxis`).
- **Q2**: AgentMemory depth = read + write conventions (per-repo `.diataxis-conventions.md` overrides).
- **Q3**: skill calls `documenter` as worker.
- **Q4**: single skill with 5 sub-commands.

## Risks / Open questions

- **Sub-command stub language**: should stubs link to the part files (e.g. "lands in part 2") or just say "stub"? Recommend link to part files for discoverability — matches memoryvault parent's pattern.
