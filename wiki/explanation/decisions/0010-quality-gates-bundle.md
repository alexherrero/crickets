# ADR 0010: quality-gates bundle + sibling-reference dispatch

> [!NOTE]
> **Status:** accepted
> **Date:** 2026-05-23
> **Related:** [ADR 0001 — agent-toolkit purpose](0001-agent-toolkit-purpose) (`kind: bundle` is in the original 11-kind taxonomy) · [ADR 0002 — evaluator design](0002-evaluator-design) (bundled primitive) · [ADR 0003 — base operator-control hooks](0003-base-operator-hooks) (3 of the bundled primitives) · [ADR 0009 — evidence-tracker hook](0009-evidence-tracker-hook) (4th bundled primitive) · [Use The Quality-Gates Bundle how-to](../../how-to/Use-The-Quality-Gates-Bundle.md) · [bundle.md manifest](https://github.com/alexherrero/agent-toolkit/blob/main/bundles/quality-gates/bundle.md) · [agentic-harness ROADMAP item #10](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md)

## Context

ROADMAP item #10 shipped after all 4 base primitives existed as standalone customizations:

| Primitive | Shipped in | Plan |
|---|---|---|
| `evaluator` sub-agent | v0.6.0 (2026-05-13) | #3 |
| `kill-switch` hook | v0.7.0 (2026-05-14) | #4 |
| `steer` hook | v0.7.0 (2026-05-14) | #4 |
| `commit-on-stop` hook | v0.7.0 (2026-05-14) | #5 |
| `evidence-tracker` hook | v0.12.0 (2026-05-23) | #9 |

The gap pre-#10: **operators adopting agentic-harness `/work` had to install each primitive individually** (5 separate `--hook X` / `--agent Y` invocations) AND remember they all wanted the full set. Result: real-world adopters routinely missed one — usually `commit-on-stop`, the safety net you only notice when a session crashes mid-task. The "I forgot to install commit-on-stop and lost an hour" failure mode was predictable + recurring.

**The bundle pattern from ADR 0001's original design** was always intended to package related primitives as one install unit. Until #10, only `example-bundle` (a stub for reference) existed. This ADR captures the design calls for the **first real-substance bundle** — the pattern this validates.

Three honest reasons bundles earn their keep:

| Reason | Strength in quality-gates |
|---|---|
| Atomic install — one command, multiple primitives | strong |
| Version pins the set as a unit | weak today (all primitives are pre-1.0; no real compat constraints between them) |
| Conceptual grouping for discovery — "quality-gates" is the name operators reach for | strong |

Two open design questions surfaced at plan time, both operator-confirmed:

1. **Sync model** — how does the bundle's `contents:` reference the primitives? (Initial plan: COPY + parity gate. Operator pushed back. Pivoted to sibling-reference.)
2. **Version bumping** — when does the bundle's `version:` bump?

The **operator-driven pivot from COPY to sibling-reference is the key design call** in this ADR. The original framing (COPY + parity CI gate) matched the existing `example-bundle` precedent but accepted a permanent maintenance burden: 22 files duplicated forever; every primitive change touches two paths; humans must remember to sync; parity CI catches drift post-hoc. The operator's question — *"wait why did we make a bunch of copies?"* — surfaced that the precedent was set by a stub bundle (one no-op skill, copied once for documentation) and didn't survive contact with a real 5-primitive set.

## Decision

**Ship `quality-gates` as a sibling-reference bundle.** The bundle directory contains ONLY `bundle.md` — the manifest. The 5 primitives are referenced by name in the manifest's `contents:` list and resolved against their standalone toolkit locations at install time. Net 22 file copies removed; net 50 lines of installer dispatch logic added per OS; net zero ongoing maintenance burden.

Two locked design calls:

### Q1 — Sync model: SIBLING-REFERENCE (revised mid-plan after operator pushback)

The bundle is **metadata, not a copy**. `contents:` lists `- agent: evaluator` / `- hook: kill-switch` / etc. The installer's `install_bundles()` / `Install-Bundles` dispatch:

1. Parses `contents:` via inline `python3 -c` (stdlib `yaml`).
2. For each `kind: name` entry, resolves source path:
   - **Standalone-first**: `<TOOLKIT_ROOT>/<kind>s/<name>/` (the canonical standalone location).
   - **Bundle-local fallback**: `<bundle_dir>/<kind>s/<name>/` — preserves `example-bundle`'s stub-only-in-bundle role.
3. Invokes the existing `install_skill` / `install_agent` / `install_hook` dispatch with the resolved source.

`validate-manifests.py check_contents()` accepts either resolution path.

**Why not COPY (original Q1 default)**: duplicates 22 files forever with humans-must-remember sync semantics. Parity CI gate would catch drift post-hoc but doesn't prevent the maintenance burden. The example-bundle precedent set by a one-stub-skill toy didn't survive contact with a real 5-primitive set. **Operator instinct was right; surface design as the better choice.**

**Why fallback to bundle-local**: preserves `example-bundle`'s reference-skeleton role. `example-skill` exists only inside the bundle; without the fallback the example would break. Cost: minimal (one extra path-existence check in the dispatch).

**Why sibling-reference is architecturally correct**: bundles are a **packaging-convenience layer** (atomic install + named set), not a copy of the things they package. Single source of truth = standalone primitive. Bundle is just metadata pointing at it.

### Q2 — Version bumping: bumps when ANY constituent primitive changes

The bundle's `version:` is independent of primitive versions but bumps whenever any constituent primitive changes — even single-character fixes. Operators installing `quality-gates@v0.1.0` get a known-good combination at known primitive versions; the bundle version is a **stamp of approval for the set**.

**Why not semver-sum (highest of constituents)**: obscures intentional versioning + couples bundle ship cadence to primitive churn unhelpfully.

**Why bump-on-any vs. bump-on-substantive-only**: bumping conservatively is safer. Operators tracking the bundle version always know they're getting the latest blessed combo. The cost is bumping for trivial changes; the benefit is operators never get a stale bundle silently.

## Consequences

### Positive

- **Zero ongoing maintenance burden** for bundle/standalone sync — there are no copies. Editing a standalone primitive automatically updates the bundle's install behavior because the bundle resolves to the same source.
- **Adoption friction drops sharply** — operators installing harness `/work` invoke one command instead of five (`--bundle quality-gates` vs. 5 separate `--hook X` / `--agent Y`). The "I forgot to install commit-on-stop" failure mode is closed.
- **First real-substance bundle validates ADR 0001's pattern** — until #10, only `example-bundle` existed (a stub). Now operators can see what a real bundle looks like + future bundles (memory-vault-minimal, documenter-suite, etc.) have a clear pattern to follow.
- **Installer dispatch is contents-driven** — `contents:` order in the manifest defines install order (alphabetical-from-directory-listing replaced). This matches the "alphabetical install order = hook precedence" invariant from ADR 0003 *only if the operator writes the manifest in that order* — which is now explicit, not accidental.
- **Bundle-local fallback preserves backward compat** — `example-bundle` (stub-only-in-bundle) continues to work; future toy bundles can follow the same pattern.
- **-1992 lines net** vs. the COPY pivot — sibling-reference is genuinely smaller AND cleaner.

### Negative

- **Installer extension was scope expansion** vs. the original "matches existing pattern" plan. ~50 lines per OS in `install_bundles()` / `Install-Bundles`. One-time cost; saves recurring maintenance.
- **Inline `python3 -c` in installer scripts** introduces a new pattern (vs. pure-bash `get_field` for simple frontmatter fields). Mitigated: every operator already needs Python 3 for the toolkit; no new dependency. Encoded UTF-8 explicitly to dodge cp1252-on-Windows (caught + fixed mid-plan; lesson logged for future inline-Python additions).
- **Two cross-platform Python gotchas surfaced during smoke-test development** — `Join-Path` constructs path strings but doesn't `mkdir` (pwsh); inline `open()` uses cp1252 on Windows. Both fixed with one-line changes; pattern documented in commit messages + this consequences section so future bundle work doesn't re-discover.
- **No CI parity gate** — but obviated by design: there's nothing to compare. The check that previously would have been "bundle copies match standalone" no longer applies.

### Load-bearing assumptions (re-audit triggers)

1. **Operator stays on the sibling-reference resolution semantics** — standalone-first with bundle-local fallback. Re-audit if a real bundle wants per-bundle customization of a primitive (e.g. "quality-gates ships kill-switch with a longer timeout than the standalone"). At that point, design Q3: how to express per-bundle overrides without resurrecting the COPY problem. v1 deliberately doesn't support this.

2. **`validate-manifests.py` continues to accept either resolution path** — standalone OR bundle-local. If the validator tightens to one or the other, half the existing bundles break. Re-audit if the validator's contract changes for any other reason.

3. **Inline Python in the installer stays small + UTF-8 explicit** — ~30 lines in install.sh + parallel in install.ps1. Re-audit if the inline-Python footprint grows past ~100 lines per OS — at that point, extract to a separate helper script (`scripts/parse-bundle-contents.py` or similar) for testability.

4. **The 4 primitives in quality-gates stay the canonical "quality" set** — evaluator + kill-switch + steer + commit-on-stop + evidence-tracker. Re-audit if a new primitive (e.g. a hypothetical `dry-run-gate` hook) becomes equally fundamental. At that point, decide whether to extend `quality-gates` (operators upgrade get the new primitive automatically) OR create a sibling bundle. v1 keeps the set frozen.

## Related

- [ADR 0001 — agent-toolkit purpose](0001-agent-toolkit-purpose) — `kind: bundle` is in the original 11-kind taxonomy; this ADR ships the first real-substance one.
- [ADR 0002 — evaluator design](0002-evaluator-design), [ADR 0003 — base operator-control hooks](0003-base-operator-hooks), [ADR 0009 — evidence-tracker hook](0009-evidence-tracker-hook) — the 5 primitives this bundle packages.
- [Use The Quality-Gates Bundle how-to](../../how-to/Use-The-Quality-Gates-Bundle.md) — operator-facing install + troubleshooting guide.
- [bundle.md manifest](https://github.com/alexherrero/agent-toolkit/blob/main/bundles/quality-gates/bundle.md) — what + why + install for the bundle itself.
- [example-bundle](https://github.com/alexherrero/agent-toolkit/blob/main/bundles/example-bundle/bundle.md) — reference skeleton; preserved via the bundle-local fallback path.
- [agentic-harness ROADMAP item #10](https://github.com/alexherrero/agentic-harness/blob/main/.harness/ROADMAP.md) — the roadmap entry that triggered this work.
- [agentic-harness `/work` §5b](https://github.com/alexherrero/agentic-harness/blob/main/harness/phases/03-work.md) — the harness-side contract `evidence-tracker` enforces (the primary reason most operators want this bundle).
