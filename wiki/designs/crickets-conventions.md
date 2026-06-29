---
title: conventions — design
status: launched
kind: design
scope: feature
area: crickets/conventions
governs: [src/releasing-conventions/, src/testing-conventions/]
parent: crickets-hld.md
seeded: 2026-06-20
approved: 2026-06-23
---

> [!NOTE]
> **LAUNCHED (lifted 2026-06-24, AG Phase 3; originally approved 2026-06-23) · locked 2026-06-28 (final AG design sweep).** child-design — **the `conventions` capability** (the base set of standards a plugin consumes before opinions weigh in). `status: launched` (lifted into tracked `wiki/designs/` 2026-06-24, AG Phase 3). Points *up* at the [crickets HLD](crickets-hld.md).

# conventions

## Objective

`conventions` is the **base set of standards a plugin consumes directly — before any opinion weighs in**. They are objective, house-standard facts a tool reads and acts on with **no judgment call**:

- bump the version when a primitive changes;
- set up CI on a new project;
- run the gate battery before every commit;
- a skip needs a named blocker;
- keep state on disk.

Each enforceable convention is backed by a deterministic gate (`scripts/check-*.sh`) — shipped, or **gate-targeted** (`[PENDING-IMPL]`) when a newly-folded rule's gate isn't built yet. That gate, present or pledged, is what makes it a *convention* and not an *opinion*. Conventions are the substrate the agentm opinions cite, and the arrow runs one way: opinions, personas, and workflows read conventions; conventions never ask an opinion.

## Overview

`conventions` is an extensible shell holding **base-standard domains** in three shapes — **rules** (enforceable, gate-backed), **skills** (practice), and **reference** (objective house facts) — detailed under Design. The domains:

| Domain | Holds | Status |
|---|---|---|
| **testing** | tests-are-sacred · verification-first · the 3-layer pyramid · `no-skip-tests` *(rule shipped; `check-no-skip-tests.sh` gate `[PENDING-IMPL]`)* | delivered |
| **releasing** | `ship-release` · `version-bump-required` · changelog + paired-release discipline | delivered |
| **ci** | always set up CI · `check-all.sh` is the source of truth · run-the-battery-before-commit · add-new-checks | partial |
| **code-quality** | evidence-to-flip-a-task · no-change-detector tests · design-conformance (the seam invariants) · Beyoncé-rule · simplicity-first · `skill-quality` + `check-slop` *(the skill-shape gate, `[PENDING-IMPL]`)* | partial |
| **agentic-engineering** | phase-gated sessions · state-on-disk · single-threaded + read-only fan-out · the PLAN.md shape · wake-on-CI · no-parallel-implementers | partial *(mostly homeless today)* |
| **reliability** | deterministic-checks-gate-LLM-judgment · prefer-deterministic-over-agentic verification · resolve-don't-cache-paths | partial |
| **coding** | the day-to-day base (naming · error-handling · structure) under testing + quality — no home today | new |
| **documentation** | the Diátaxis structure (four modes · single-mode-per-page · intent-group layout · length ceilings · naming) — enforced by [wiki](crickets-wiki.md)'s `check-wiki.py` | partial |

![The conventions hub: phase workflows probe it by name through the resolver and personas lean on it, while opinions cite it one-way; its rules are enforced by the check-all.sh gate battery, and it cites — never re-owns — the standards held by developer-safety, privacy, maintenance, and code-review](diagrams/crickets-conventions.svg)

*Consumers (workflows, personas) read `conventions` by name through the resolver; opinions **cite** it one-way (it is their substrate); its rules are enforced by the **`check-all.sh` gate battery** — the can't-forget floor; and it **cites, never re-owns**, the standards held by `developer-safety` / `privacy` / `maintenance` / `code-review`.*

## Design

### The line — conventions vs opinions

A **convention** is an *objective, house-standard fact* a plugin reads and acts on with **no judgment** ("bump the version on any primitive change"; "a skip needs a named blocker"; "tests are a 3-layer pyramid"). An **opinion** is an agentm *stance* asked for **by name** that requires judgment (`done` / `good` / `efficient` / `how-we-engineer`).

Conventions are what an opinion cites: the `done` opinion is literally *"the check battery + the written conventions for shape."* So an opinion is the **named question** ("is this done?"); conventions are part of the **deterministic answer** it cites. One convention can be cited by several opinions; an opinion cites conventions across domains. The arrow is one-way: conventions stay dumb and objective, consumed directly (**crickets-side**); opinions are the judgment surface on top (the **agentm pillar**).

### The three shapes

| Shape | Path | What it is | How it holds |
|---|---|---|---|
| **rule** | `rules/<name>.md` | an enforceable standard — trigger condition · "what is NOT a bypass" table · enforcement checklist (the `no-skip-tests` / `version-bump-required` template) | **names its `scripts/check-*.sh` gate** (shipped or `[PENDING-IMPL]`) — the gate is what makes it objective and un-forgettable |
| **skill** | `skills/<name>/SKILL.md` | standing day-to-day practice prose | consulted by the workflow; owns the *practice*, not the *audit* (that's `code-review`'s `testing-strategy`) |
| **reference** | `reference/<name>.md` | objective house facts (the gate-battery inventory, the `features.json` schema) the rules cite | *objective facts only* — cited, not gated; subjective tradeoff knowledge is excluded (below) |

### Cite, don't duplicate

`conventions` holds the objective, gate-backed, house-standard conventions and **migrates in the homeless ones** (the agentic-engineering harness discipline, the ci-battery rules, the no-change-detector quality rule, the coding base). It does **not re-own** a standard another capability already owns — it **cites** it:

- the **recoverability gate** is [developer-safety](crickets-developer-safety.md)'s.
- the **deterministic PII / secret scan** is [privacy](crickets-privacy.md)'s.
- **dependency repair** is [maintenance](crickets-maintenance.md)'s.
- the **adversarial-review contract** is [code-review](crickets-code-review.md)'s (the `good` opinion's framing) — a judgment stance, not a gate-backed convention, so it stays there.

### The domains

- **testing** *(delivered)* + **releasing** *(delivered)* — the two existing plugins, folded in (Migrations). Consumed by `/work` + `/release` and `code-review`'s `testing-strategy`.
- **ci** *(partial)* — `check-all.sh` is the single source of truth for "green"; the rules: always set up CI on a new project · run the battery before every commit · add a new check to the battery as the project grows. The **both-places consistency is mechanically enforced** — `scripts/test_ci_consistency.py` (itself a battery test) fails if a battery gate is missing from the Linux workflow or a toolchain gate from any of the three OS workflows, and the aggregate `ci-all.yml` couples to the three OS workflows by filename (a rename trips the test). The gate inventory is a `reference/` doc. Consumed by every pre-commit and by `maintenance`'s CI-repair.
- **code-quality** *(partial)* — evidence-required-to-flip-a-task, no-change-detector tests, design-conformance to the seam invariants (import-direction, no-Path-leak, one-port), the Beyoncé-rule, simplicity-first. Each is gate-backed (`check-*.sh`) or a skill. Consumed by `/review` and the Tech-Lead persona.
- **agentic-engineering** *(partial — mostly homeless)* — the harness discipline: phase-gated sessions, state-on-disk-not-conversation, single-threaded implementation with read-only sub-agent fan-out, the PLAN.md shape (locked design calls + narrative Status), wake-on-CI, no parallel implementers. Today these live only in `AGENTS.md` / `principles.md` / `CLAUDE.md`; they migrate in. Consumed by every phase workflow and every persona.
- **reliability** *(partial)* — deterministic-checks-gate-LLM-judgment, prefer-deterministic-over-agentic verification when both achieve the same thing, resolve-don't-cache vault paths. Consumed by the gate battery and the `good` opinion.
- **coding** *(new)* — the general day-to-day base (naming, error-handling, structure) that sits under testing + quality and has no dedicated home; the umbrella skill for the expanded shell. Consumed by every `/work` session.
- **documentation** *(partial)* — the **Diátaxis structure**: every page is exactly one of four modes (tutorials · how-to · reference · explanation), single-mode-per-page, with length ceilings and a naming style. The tree is the **fixed seven-section frame** in fixed order — How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational — with two **conditional** sections (Architecture on a `wiki/architecture.yml` declaration; Operational on audience/visibility). The **naming rule:** every page basename is unique across the tree case-insensitively; when a user-facing page and a design page collide, the user-facing page owns the clean name and the design page takes a `-design` suffix (`check-wiki` rule (g)). Index/landing pages (`<!-- mode: index -->`) are **shape-exempt** from the single-mode rule. The objective structure standard lives here; **[wiki](crickets-wiki.md) consumes and enforces it** — `check-wiki.py` is the gate (mode · length · vendor · structure), its templates and `diataxis-author` skill author against it, and a per-repo `.diataxis-conventions.md` can override. The prose *voice* is a separate agentm opinion (subjective, learned), not a convention.

### Opinions — conventions are the substrate they cite

`conventions` consumes no opinion; it is the **inverse** — the deterministic substrate the opinions point at. `done` = the check battery + these written shape conventions; `good` cites testing + code-quality; `how-we-engineer` cites agentic-engineering + ci; `efficient` cites the objective performance gates. The arrow is one-way — opinions read conventions; conventions never ask an opinion. *(The subjective tradeoff knowledge an opinion adds — language choice, platform tradeoffs, per-language performance tuning — lives in the [Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates) pillar or learned memory, **not here**: it is contextual judgment that decays, not a house standard.)*

### The extensible shell

One `conventions` plugin, domains as sub-folders:

```
src/conventions/
├── group.yaml          # requires: [development-lifecycle] · capabilities: [conventions]
│                       #   (resolver-aliases the old testing-conventions + releasing-conventions)
├── rules/              # enforceable — each names a check-*.sh gate
│   ├── no-skip-tests.md
│   ├── version-bump-required.md
│   ├── always-setup-ci.md
│   └── …
├── skills/             # standing practice
│   ├── testing-conventions/
│   ├── ship-release/
│   └── coding/
└── reference/          # objective house facts the rules cite
    ├── gate-inventory.md
    └── …
```

Adding a domain = drop a `rules/` file (+ its `check-*.sh` gate), a `skills/` folder, or a `reference/` doc, then bump the version — no new plugin, no new wiring.

### How others call it in

A consumer — a command, skill, persona, or opinion — reaches `conventions` the one-way way everything reaches a capability: **by name through the resolver** (`find_capability` → `capability_resolver.py`, version-matched, graceful-skip), then reads the relevant domain's `rules` / `skills` / `reference`. The harder problem is making sure a consumer **doesn't forget** — handled in two tiers:

- **Gate-backed conventions can't be forgotten.** Every `rule` names a `scripts/check-*.sh` gate, and the gate runs in the **`check-all.sh` battery at every commit** — independent of whether any plugin remembered to consult it. A violation fails the commit, not a code review. (The `ci` convention "run the battery before every commit" is what closes this loop.) This is the strong floor.
- **Practice + reference conventions are surfaced, not just available.** A skill / reference standard has no gate, so a consumer must read it — and a standard nobody reads is dead. So the applicable conventions are **surfaced at the point of work**: each phase workflow consults its domain (`/work` reads coding + testing, `/release` reads releasing). The set a project is governed by is surfaced at session start — the pattern the always-load memory already uses. A consumer **declares** the conventions it depends on, and the **Phase-2 conformance gate** can check that a plugin which should consult one actually declares it — so "forgot to call conventions" becomes a gate finding, not a silent gap.

The principle: **prefer the gate.** A convention that can be made gate-backed should be — the battery is the only mechanism that survives forgetfulness; surfacing is the fallback for the genuinely judgment-shaped ones.

## Dependencies

- **requires [development-lifecycle](crickets-development-lifecycle.md)** — `/work`, `/review`, `/release` run the rules + skills.
- **consumed by** the phase loop, [code-review](crickets-code-review.md) (the `testing-strategy` audit draws on the testing standard), **[wiki](crickets-wiki.md)** (enforces the `documentation` convention via `check-wiki.py`), the personas (Engineer / Reviewer / Maintainer / Tech-Lead lean on it), and the **opinions** (which cite it — the inverse clause above).
- **cites, does not own** — [developer-safety](crickets-developer-safety.md) (recoverability) · [privacy](crickets-privacy.md) (the PII scan) · [maintenance](crickets-maintenance.md) (dependency repair) · [code-review](crickets-code-review.md) (the adversarial contract).
- Points up at the [crickets HLD](crickets-hld.md); the requires/enhances mechanics are in [crickets-composition](crickets-composition.md).

## Migrations

Two structural lifts at the Phase-3 / v6.0 pass:

1. **Merge** — `testing-conventions` + `releasing-conventions` consolidate to one `src/conventions/`, the `group.yaml` merges, and `capabilities: [conventions]` replaces the two transitional declarations (the merged group declares both the old and new capability names, so the old ones keep resolving — the [composition](crickets-composition.md) rename mechanism). The four existing primitives don't change.
2. **Migrate the homeless conventions in** — the objective base standards that live only in `AGENTS.md` / `principles.md` / `~/.claude/CLAUDE.md` (the agentic-engineering discipline, the ci-battery rules, the no-change-detector quality rule, the coding base) become standalone `rules/` + `skills/`; `AGENTS.md` keeps a pointer, `conventions` owns the standard. The cite-don't-duplicate boundary keeps it from re-owning what `developer-safety` / `privacy` / `maintenance` / `code-review` already hold.

## Risks & open questions

- **The line is the standing risk** — a convention must be objective and (ideally) gate-backed; a judgment stance is an opinion. Grey-zone principles (simplicity-first, adversarial-review-assumes-bugs) resolve by the rule: **gate-backed → conventions; pure judgment-framing → the opinion**.
- **Subjective knowledge-refs are explicitly OUT** — language-selection, platform-selection, per-language performance tuning belong in the Opinions pillar or learned memory (contextual, decaying); putting them behind a gate would be a category error.
- **The de-dup must hold** — `conventions` cites, never duplicates, a standard another capability owns; a re-owned convention drifts from its source.
- **The `reference/` shape is new** — objective house facts only; the rules cite it, no gate enforces a reference doc.
- **`self-correction-loop` is not a conventions concern** — the evaluate→grade→re-run improvement loop is the agentm **Experience → Opinions** loop ([agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates)), not a gate-backed standard; conventions only folds in the *skill-shape* gate (`skill-quality` + `check-slop`).
- **Re-audit triggers:** land the merge + the homeless-migration at the Phase-3 lift; add the `reference/` shape; confirm each new rule names its `check-*.sh` gate; **ship `check-no-skip-tests.sh`** + a **`check-conventions-cite-not-duplicate`** portfolio lint (fails on a standard duplicated rather than cited — the structural boundary the residual bucket rests on); keep the subjective knowledge-refs routed to opinions/memory.

## References

- crickets `src/testing-conventions/` + `src/releasing-conventions/` (live; → `src/conventions/`) — rules (`no-skip-tests`, `version-bump-required`) · skills (`testing-conventions`, `ship-release`)
- **Homeless conventions to migrate in:** agentm `AGENTS.md` (the non-negotiables) · `harness/principles.md` (the seven principles) · `~/.claude/CLAUDE.md` (the dev-flow conventions); the gate inventory = `scripts/check-all.sh` + `wiki/reference/CI-Gates.md`
- **Standards it cites (not owns):** [developer-safety](crickets-developer-safety.md) · [privacy](crickets-privacy.md) · [maintenance](crickets-maintenance.md) · [code-review](crickets-code-review.md)
- **Up:** [crickets HLD](crickets-hld.md) · [composition](crickets-composition.md) · [agentm Opinions](https://github.com/alexherrero/agentm/wiki/agentm-opinions-and-gates) (which cite conventions)

## Amendment log

**2026-06-28 — lock-down sweep + voice pass (operator review).** Converted the relationship mermaid to a house-style hand-SVG (`diagrams/crickets-conventions.svg`); and did a voice pass to the current design-doc standard — fixed the one LLM-tell (`first-class`→`standalone`) and split the longest run-on sentences into one-claim sentences (the doc was otherwise on-standard: active voice, colon-led lists, no peacock words). No change to the conventions contract. Locked as a v5–v8 guidepost.

**2026-06-28 — AG critique revisions (W6 · R4 · R10).** Demoted the gate thesis to **gate-backed OR gate-targeted** and marked `no-skip-tests`'s `check-no-skip-tests.sh` gate `[PENDING-IMPL]` (W6); named the residual-bucket's structural boundary — a `check-conventions-cite-not-duplicate` portfolio lint (fails on a standard duplicated rather than cited) — in the re-audit triggers (R4); folded `skill-quality` + `check-slop` into the code-quality domain as the gate-targeted skill-shape gate, and scoped `self-correction-loop` out as the agentm Experience→Opinions loop, not a convention (R10). *Re-audit:* ship `check-no-skip-tests.sh` + the cite-not-duplicate lint.

**2026-06-24 — subsumed `continuous-integration.md` + `wiki-section-taxonomy.md` (AG Wave 2, move-and-retire).** Two superseded designs whose still-live convention substance lands here; both deleted (git history retains the full PRD text + part files). The two C4-folded ADRs they had absorbed (AG Phase-2) are preserved below with decision + why-not + re-audit; the seven-section frame is also reflected in the `documentation` domain body, and the `ci`-consistency mechanism is noted in the `ci` domain.

- **ADR 0021 — per-plugin marketplace versioning sourced from `group.yaml` (2026-06-11).** Each plugin owns a `version:` in its `src/<slug>/group.yaml` (parsed by `src_model.Group`, written by both emitters into `plugin.json` + the Claude marketplace entry), replacing the frozen `PLUGIN_VERSION="0.1.0"` constant that made `claude plugin update` a permanent no-op. Anti-recurrence gate `check-version-bump.py` fails when `src/<slug>/**` changed vs the base ref without a **strict** SemVer increase (content diffed from merge-base, version vs base tip, graceful-skip when the base is unresolvable); wired into `check-all.sh` + CI. This is the decision record behind the `version-bump-required` rule. *Why not the repo-level pin / one global version / a side registry / trust-the-author / mere-inequality:* the pin *is* the bug; a global version couples unrelated plugins into spurious churn; a registry is a second source to drift; author vigilance isn't a gate; inequality admits downgrades + garbage. *Re-audit trigger:* Claude changing the update trigger (content-hash), the publish model moving off `dist/`-on-main, or Antigravity shipping a version-driven `agy plugin update`.
- **ADR 0020 — seven-section wiki taxonomy: fixed frame + per-project Architecture manifest + conditional gates (2026-06-11).** A fixed seven-section frame in fixed order — **How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational** — scaffolded by `wiki_init.py`'s `DEFAULT_SECTIONS`, allow-listed by `check-wiki`'s `_FOLDER_MODE`; supersedes-in-spirit the intent-folder IA (ADR 0018) while keeping its nearest-`_Sidebar.md` + two-level reachability. Two **conditional** sections: Architecture renders on declaration (a `wiki/architecture.yml` manifest of `components:` `{slug,title,summary,overview}` + optional `pillars:` toggles; the generator scaffolds `architecture/<slug>/` + a landing and renders a third sidebar nesting level, validated + fail-closed), and Operational renders on audience/visibility (public wikis suppress it), not per-page sensitivity. *Why not per-repo improvised folders / Diátaxis-type-only / hard-coded architecture / always-present sections / sensitivity-gated Operational:* improvisation drifts with no source of truth; Diátaxis modes don't cover Architecture/Designs/Decisions/Operational; a hard-coded architecture list is wrong for every repo but one; stub sections are noise; sensitivity is the per-page PII gate's job. *Re-audit trigger:* a recurring doc type with no home (add a section) or a universally-empty section (drop it); the `{slug,title,summary,overview}` shape proving too thin/thick.

**2026-06-23 — added the `documentation` domain (operator review of wiki).** The **Diátaxis structure** (four modes · single-mode-per-page · intent-group layout · length ceilings · naming) is a base standard, so it lands as the **`documentation` convention domain** — the canonical home for "how we structure docs," alongside testing/ci. **[wiki](crickets-wiki.md) consumes + enforces it** (`check-wiki.py` is its gate; the templates + `diataxis-author` skill author against it) — one-way: wiki tools the standard, conventions owns it. The prose *voice* stays a separate agentm opinion (subjective, learned), not a convention. `partial` (the standard + gate ship in wiki; the convention home here is new).

**2026-06-23 — authored from the seeded stub, then expanded on operator review from "testing + releasing" to the base-standards shell.** A `conventions-scope-investigation` workflow (mining the HLDs + every sub-design + `AGENTS.md` / `principles.md`) found **~23 conventions homeless** in the harness prose. Reframed `conventions` as **the objective base standards a plugin consumes before opinions weigh in** — the clean line: a convention is an objective house fact (gate-backed, no judgment, consumed directly, crickets-side); an opinion is a judgment stance asked by name (agentm-side). They relate by **implementation** — the `done` opinion *is* the check battery + the written conventions; opinions **cite** conventions, the arrow one-way. Expanded the domains to **testing · releasing · ci · code-quality · agentic-engineering · reliability · coding**, added a `reference/` shape for objective house facts, and locked the **cite-don't-duplicate** rule (conventions cites `developer-safety` / `privacy` / `maintenance` / `code-review`, never re-owns). **Operator decisions (2026-06-23):** the boundary as above; the 7 domains + `reference/` shape; **subjective knowledge-refs (language / platform / per-language perf) are OUT** → the Opinions pillar / memory; **cite-don't-duplicate** for the standards other capabilities own; **one aliased `conventions` plugin** (testing + releasing fold in, domains as sub-folders). **Built-vs-designed:** testing + releasing delivered; ci / code-quality / reliability partial (gate-backed pieces exist, the convention home does not); agentic-engineering + coding mostly to-migrate. **Re-audit:** land the merge + homeless-migration; add the reference shape; each rule names its gate.
