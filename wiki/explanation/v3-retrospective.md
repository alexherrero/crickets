# V3 Retrospective — what we shipped, what we learned, what's next

> [!NOTE]
> **Status:** historical record, closed
> **Period:** 2026-04-19 → 2026-05-23
> **Paired with releases:** `agentm` v3.0.0 + `crickets` v1.0.0

The V3 arc took `agentm` from v1.0.0 (Codex-removal sweep) to v3.0.0 (V3 close-out), and `crickets` from inception (v0.5.0 split-out) to v1.0.0 (public-API commitment). This page is the focused-survey retrospective of that arc.

It exists so the next arc starts from a settled answer to "what V3 was," so future maintainers read the design themes once instead of re-deriving them, and so the operator has a record ready for the later vault archive of V3 material.

## 1. Scope

V3 begins with plan #0 (the Codex-removal sweep that shipped harness v1.0.0 on 2026-05-11) and ends with this plan (the V3 close-out that ships harness v3.0.0 + toolkit v1.0.0). Every plan in between executed under the phase-gated workflow established in harness ADR 0001 and the toolkit-split architecture established in harness ADR 0006 / toolkit ADR 0001.

Pre-V3 work (harness v0.x) is out of scope. So is anything in the AgentMemoryV4 roadmap — that's the next arc, not this one.

## 2. What shipped

**Plans:** 23 total. 22 archived under `.harness/PLAN.archive.*.md`, plus this active plan (#14) which closes V3.

**Paired releases:** 12 paired pairs (harness × toolkit), chronologically:

| Harness | Toolkit | Date | Theme | Substantive side |
|---|---|---|---|---|
| v2.0.0 | v0.5.0 | 2026-05-12 | crickets repo split (BREAKING migration) | both |
| v2.1.0 | v0.6.0 | 2026-05-13 | `evaluator` sub-agent + `/review` §3b | both |
| v2.2.0 | v0.7.0 | 2026-05-14 | base hooks: kill-switch / steer / commit-on-stop | both |
| v2.3.0 | v0.8.0 | 2026-05-15 | `/design` skill v1 + `/release` §1b | both |
| v2.3.1 | v0.8.1 | 2026-05-16 | external-review-handoff option (dogfood patch) | both |
| v2.4.0 | v0.9.0 | 2026-05-17 | Gemini-CLI host removal | toolkit-substantive |
| v2.4.1 | v0.9.2 | 2026-05-20 | local-only embeddings + BGE-large default | toolkit-substantive |
| v2.4.2 | v0.10.0 | 2026-05-22 | MemoryVault Discovery + Mining | toolkit-substantive |
| v2.4.3 | v0.11.0 | 2026-05-22 | `diataxis-author` skill | toolkit-substantive |
| v2.5.0 | v0.11.1 | 2026-05-22 | auto-context into harness phases | **harness-substantive** |
| v2.6.0 | v0.12.0 | 2026-05-23 | evidence-tracker hook for `/work` | both |
| v2.6.1 | v0.13.0 | 2026-05-23 | quality-gates bundle | toolkit-substantive |

V3 closes with paired pair #13 — harness v3.0.0 + toolkit v1.0.0.

**Primitives shipped (toolkit):**

- 1 sub-agent: `evaluator`.
- 4 hooks: `kill-switch`, `steer`, `commit-on-stop`, `evidence-tracker`.
- 3 skills: `memory` (with `/memory save|recall|evolve|reflect|index-skills|discover-skills|adapt-skills|watchlist`), `design`, `diataxis-author`.
- 1 real-substance bundle: `quality-gates` (packages the evaluator + 4 hooks via sibling-reference dispatch).

**Architecture decisions:** 7 harness ADRs (0001–0007) + 9 toolkit ADRs (0001–0010 with an intentional gap at 0005). All `accepted`; three carry dated amendments (toolkit 0001 / 0002 / 0004).

**Versioning shape:** harness V3 release matches the AgentMemory implementation V-versioning (V3 = merged Obsidian+GDrive vault auto-loaded into every phase). Toolkit v1.0.0 commits to a stable public API surface: bundle/manifest schema + installer flags + `bundles/` namespace + the 11 customization kinds. Internal surface (`scripts/`, `lib/install/`) remains pre-1.0 in spirit.

## 3. Architecture themes that crystallized

**Paired-release cadence.** Twelve consecutive paired releases established that harness changes and toolkit changes ship together — even when one side is doc-only, the paired CHANGELOG entry on the other side keeps version cadences readable. Toolkit-first ordering (toolkit release notes URL-link the harness release, then the harness release URL-links the toolkit release) became the locked convention.

**Sibling-reference over copy-with-parity.** Plan #10 shipped the `quality-gates` bundle after an operator-driven mid-plan pivot from COPY to sibling-reference. A bundle is now a manifest pointing at standalone primitives; the installer resolves `contents:` entries against the toolkit's standalone layout. Net effect: zero file duplication, zero drift surface, single source of truth (ADR 0010).

**Evidence-tracking default-FAIL contract.** Plan #9 shipped a hook that blocks `[ ]` → `[x]` flips in `PLAN.md` unless the agent has demonstrably `Read` a spec-shaped file in this session. The resolver is a hybrid: it looks for `**Evidence:**` task-body annotations or files named in the task, allows a per-task override, and permits an explicit opt-out with mandatory rationale (ADR 0009).

**Auto-recall in every harness phase.** Plan #8 wired `harness_memory.py recall` into every phase, `/setup` through `/bugfix`, at each one's natural boundary. The offer-save prompt modulates itself — it asks only when its confidence clears the threshold, so saving never becomes a nag. Promotion is tracked by a cursor at `.harness/.promoted-progress-cursor`, so a finished plan gets its end-of-plan reflection exactly once (ADR 0007).

**Sub-letter spec amendment convention.** Adding §5b instead of inserting a new §6 preserves integer §-numbering — incoming wiki refs that cite "§N" stay valid. Established in plan #3, reinforced across plans #4 / #8 / #9. Line-range anchors still need manual updating, but the §-level contract is stable.

**`.py`-sidecar installer pattern.** Plan #9 introduced the convention that a hook can ship a Python helper alongside its `.sh`/`.ps1` entry script. The installer extension was ~7 lines per OS; the integrity check had to be extended in parallel to allow `.py` files in `.claude/hooks/`. The pattern is now reusable for future hooks that need stdlib-only Python helpers.

**Permeable A3 write boundary.** MemoryVault writes default to `personal-private/` but agents can write anywhere on explicit operator instruction or after confirmation. Read is universal; write is constrained-by-default. Established plan #7a part 4; reinforced by the adapt-don't-import sub-agent write allowlist in plan #7b.

## 4. Repeat lessons

These surfaced multiple times and are now part of the muscle memory:

1. **`LC_ALL=C sort` for deterministic line order.** macOS uses case-insensitive collation vs. Linux byte-order; breaks SHA-256 byte-identity in `lib/install/.checksums.txt`.
2. **`$host` is a read-only PowerShell built-in.** Loop-variable collisions in installers; always rename.
3. **Git Bash on Windows ships `sha256sum`, not `shasum`.** Runtime detection with fallback in `lib-parity` checks.
4. **Git `autocrlf=true` on Windows breaks SHA-256 byte-identity.** `.gitattributes` forcing LF + sed pattern normalizing binary-mode and text-mode `sha256sum` output.
5. **`Path.__str__()` returns native separators on Windows.** Use `Path.as_posix()` for display output and cross-platform comparisons.
6. **`ConvertTo-Json` single-element array unwrap.** A single hook event stored as object instead of `List[object]` breaks Claude Code's hook loader schema; use `ConvertFrom-Json -AsHashtable` throughout.
7. **`Start-Process -ArgumentList` splits multi-word args.** Switched to `& python3` direct invocation.
8. **Windows Python `cp1252` stdout encoding can't encode `→` or em-dashes.** `sys.stdout.reconfigure(encoding='utf-8')` at module load; inline `python3 -c open(file)` needs explicit `encoding='utf-8'`.
9. **`Join-Path` constructs strings but doesn't `mkdir`.** Bash's `mktemp -d` hides this — Windows CI catches it.
10. **`Path.write_text` translates `\n` → `\r\n` on Windows.** pwsh `(?m)^${org}$` regex won't match CRLF lines; switch to `write_bytes` for LF-only.
11. **PII scanner false-positives on synthetic identities.** Synthetic test emails + SSH-form URLs + file-path-shaped strings in fixtures trip the scanner. Allowlist must be maintained; **even narrative describing prior scrubs trips the scanner** — v2.5.0 hit itself, fixed forward.
12. **Sub-letter spec amendments preserve §-numbering.** §5b not §6; preserves external "§N" refs.
13. **Wake-on-CI: never mark `[x]` speculatively.** Push → schedule ~90s wake → close out only when CI is green across 3-OS. Six distinct Windows-only failures caught this way.
14. **Operator-driven mid-plan pivots are normal.** Build the ADR around the locked decision, not the first sketch.
15. **ADR numbering is per-repo, not global.** Harness ADRs 0001–0007; toolkit ADRs 0001–0010 (gap at 0005). Conflating numbering breaks cross-references at scale.

## 5. Operator-driven mid-plan pivots

Six plans had substantive mid-flight design changes initiated by the operator:

- **Plan #7a part 4 — A3 permeable boundary.** Initial sketch was "memory writes only to vault." Revised to "writes default to vault; explicit operator instruction or confirmation unlocks anywhere." Locked the read-universal / write-constrained pattern.
- **Plan #8 Q4/Q5 mid-flight revision.** Flat-ask offer-save → self-modulating (confidence-thresholded). Release-only promotion → dual-trigger cursor-tracked (plan-done in `/work` + tail-scan in `/release`).
- **Plan #10 Q1 COPY → sibling-reference.** Operator's "wait why did we make a bunch of copies?" caught a design smell labeled "invasive" but actually ~50 lines per OS. Net: -1992 lines, zero ongoing maintenance burden, single source of truth.
- **Plan #11 explicit deferral.** Operator chose option 1 (defer formally with 4 revisit triggers) rather than build speculatively. First explicit "skip this item formally" decision in the arc.
- **Plan #9 Q1 evidence resolver.** Hybrid heuristic + override + explicit opt-out instead of strict path-list.
- **Plan #14 (this plan) HLD constraint.** Operator-locked: HLD must stand on its own, no overt external prior-art references; operator review-and-approve gate before commit/push.

The recurring lesson: don't anchor on existing precedent, and sanity-check any "invasive alternative" framing against its actual cost.

## 6. Deferred items + rationale

- **#11 Wake-from-state** ⏸️ deferred 2026-05-23. Implicit `state on disk` already covers ~95%; no real crash has lost recoverable data through the 10-plan arc. Revisit triggers: (i) real crash loses data; (ii) #26 ships and reshapes WHERE state lives; (iii) #28 ships and absorbs the wake surface; (iv) #24 cross-device hits state-recovery friction.
- **#16 Personal-knowledge consolidation** — gated on V4 vault architecture. Out of scope for V3 because the V3 vault tree is now stable but the full content-curation pass is a 2-3 session co-creation project, not a code-shipping plan.
- **#18 Local-only embeddings** — already shipped mid-flight as a plan; no longer "deferred." Listed here for completeness.

## 7. TBD frontiers heading into V4

V4 carries the memory line forward; non-V4 backlog stays on the slimmed ROADMAP. The full V4 design space lives in the [AgentMemory evolution HLD](https://github.com/alexherrero/agentm/wiki/agentm-hld) (shipped alongside this retrospective) and the new `.harness/ROADMAP-AgentMemoryV4.md`. Headlines:

- **Vault-backed harness state (#26).** Move `PLAN.md` / `progress.md` / `ROADMAP.md` / `project.json` into the vault. Universal cross-repo development. Reshapes the state model that #11 (wake-from-state) was originally going to formalize.
- **FRIDAY-style natural-extension-of-memory (#28).** Agent + harness + memory as a personal-knowledge-management OS. Vision item; absorbs explicit-wake-surface in favor of higher-abstraction "open the file for X."
- **AgentMemory evolution audit (#25).** Read prior-art memory architectures (Karpathy LLM Wiki + GBrain + others); 4-bucket classification (adopt as-is / adopt with adaptation / deliberately reject / incompatible).
- **Cross-surface AgentMemory protocol (#22).** Configure-don't-build vault access for Claude.ai / Gemini / Antigravity / etc.
- **Auto-orchestration (#23).** Chain MemoryVault skills (recall + reflect + idea-ledger + index-skills + discover-skills + adapt-skills + watchlist + promote) into natural automatic invocations.

Non-V4 frontiers: #17 Antigravity 2.0 + CLI host support; #19 Ideas.md format redesign; #21 harness self-audit skill; #24 portable harness (Claude Code Web / NAS Docker remote); #30 public-consumption-ready release.

---

**Cross-references:**

- [`agent-memory-evolution`](https://github.com/alexherrero/agentm/wiki/agentm-hld) — the AgentMemory evolution HLD (V1 → V4), shipped alongside this retrospective in plan #14
- [`memoryvault`](https://github.com/alexherrero/agentm/wiki/memoryvault) — the parent MemoryVault design (V3 implementation)
- [`agentm/.harness/ROADMAP-AgentMemoryV4.md`](https://github.com/alexherrero/agentm/blob/main/.harness/ROADMAP-AgentMemoryV4.md) — V4 roadmap (lands in plan #14 task 3)
- `agentm/.harness/ROADMAP.archive.20260523-v3-complete.md` — full V3-era ROADMAP snapshot (operator-local; `.harness/` is gitignored — archive preserved for eventual vault migration)
