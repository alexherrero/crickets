---
title: Crickets — High Level Design
status: launched
visibility: published
author: Alex Herrero
contributors: []
created: 2026-06-19
updated: 2026-06-21
last_major_revision: 2026-06-20
prd:
project: https://github.com/users/alexherrero/projects/5
kind: design
scope: arc
reconciles: developer-plugin-suite.md, crickets-v3-native-plugins.md
governs:
  - src/**
  - scripts/**
area: crickets/architecture
---

> [!NOTE]
> **LAUNCHED — the live crickets parent design** (lifted into tracked `wiki/designs/` 2026-06-20, AG Phase-2 C0). Framed around crickets' capability model; the mechanics live in sub-designs under `children/` (seeded, authored in Phase 3). **Reconciles** the earlier `developer-plugin-suite.md` + `crickets-v3-native-plugins.md` — their "three"/"six"-plugin identity-lines are superseded. Built on design-doc Appendix C; inherits the shared beliefs from the [Foundations HLD](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld) by reference, and composes onto the person — the [agentm HLD](https://github.com/alexherrero/agentm/wiki/agentm-hld). Governance keys stamped: `governs: [src/**, scripts/**]`, `area: crickets/architecture` (AG Phase-2 C0.2).

# Crickets — the toolbox the assistant picks up

A useful assistant is a person and the tools it works with — the [Foundations](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld) make that case, and [agentm](https://github.com/alexherrero/agentm/wiki/agentm-hld) is the person. crickets is the tools: the abilities the assistant picks up to actually get work done — planning, building, reviewing, releasing, and more. Each is **stateless** — it holds nothing of its own between uses. The memory, the opinions, and the hat being worn all live in agentm; a tool draws on them, does its job, and is set back down, and the person remembers what happened. Add a tool or take one away and the person still stands; the toolbox grows and changes without disturbing who's holding it.

This doc is about the toolbox: the capabilities it implements, how a capability is built once and shipped everywhere, and how the whole thing composes onto the person. The shared beliefs live up in the [Foundations](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld); the person is the [agentm HLD](https://github.com/alexherrero/agentm/wiki/agentm-hld).

## What crickets is for

- **One source of truth** — each capability is described once; everything it ships is generated from that, never kept in sync by hand.
- **Clean composition** — tools sit beside each other and combine, instead of tangling into one another.
- **Optionality** — any capability can be added or left out, and the base still works on its own. A bare agentm is whole; crickets is the part you bolt on.
- **Subordination** — the tools serve the person and never grow a will of their own: crickets can lean on agentm, agentm never leans on crickets.

## The capabilities

crickets is **fourteen capabilities** — each a self-contained plugin, each written once and generated for every host (next section). A capability is a named ability with a handful of primitives inside it — commands, agents, skills, hooks. *(Thirteen ship today; `research`, `diagnostics`, and `lifecycle` are newly designed.)* A few examples:

- **`developer-workflows`** (the phase loop) — the phase commands (`/plan`, `/work`, `/review`, `/release`, `/bugfix`, `/setup`), the agent-defs that run them (worker, tech-lead, project-manager), and the phase hooks.
- **`code-review`** — the adversarial-reviewer agent (plus a cross-model variant), the `/code-review` command, and the cross-review shell-out.
- **`developer-safety`** — the recoverability skill, the commit-on-stop hook, and the gate carve-out tests.

The capability *name* is the plugin name; the makeup is what's inside. A capability is really just a **shell with a name** — the work lives in the primitives it holds:

![Developer Workflows — one example of a capability: a named shell holding its commands, agents, and hooks](diagrams/crickets-capability-example.svg)

*A capability is a shell that holds primitives. Here, `developer-workflows` holds its commands, agents, and hooks — every capability is the same shape, just a different name and a different set of primitives.*

**Capabilities build on each other.** The same primitive can sit in more than one capability, and a capability can lean on another — it may **depend on** one (it won't run without it) or be **enhanced by** one (it works alone, but does more when the other is present). Those depend-and-enhance links come, in part, from primitives being shared or building on each other.

**They can lean on an opinion, too.** A capability — or a single primitive — can depend on or be enhanced by one of agentm's named [opinions](https://github.com/alexherrero/agentm/wiki/agentm-hld) (*what "done" looks like*, *what "good" looks like*), the same way it leans on another capability. When the opinion is present it shapes the work; when it's absent, the capability degrades gracefully and carries on.

Crickets is fourteen capabilities. Full details are available below and in the composition sub-design *(seeded — Phase 3)*.

## How a capability is composed

A capability is written **once** and runs on **many platforms**. You author it in one place — the capability's primitives — and a build step renders it into the native shape each host expects, so the same capability runs on Claude Code, Antigravity, and any host added later. Different hosts support different primitive types, so a host may get only the subset of a capability's primitives it can express. *(The build pipeline — the single source, the per-host generator, the drift gate — is the build-system sub-design *(seeded — Phase 3)*.)*

## Roles

Roles aren't a thing in crickets. What looks like a role — *worker*, *reviewer*, *tech-lead* — is a **persona**, which is an agentm concept; crickets only supplies the tools (capabilities and their primitives) a persona wields. See the [agentm Personas design](https://github.com/alexherrero/agentm/wiki/agentm-hld) for how primitives and capabilities get composed into a stance and wired to opinions. *(The transitional shape of today's role-style agent-defs lives in the composition sub-design *(seeded — Phase 3)*.)*

## How crickets composes onto agentm

Two things compose here, both **one-way**. Capabilities compose with **each other** by name — one names what it depends on or enhances, and the toolbox wires them at runtime, so any subset installs and runs. And the whole toolbox composes onto **agentm**: crickets leans on agentm, agentm never leans on crickets. A bare agentm is whole on its own; remove a tool — or the substrate — and what's left degrades gracefully rather than breaking. *(The resolver, the bridge to agentm, and how the one-way rule is held are the composition sub-design *(seeded — Phase 3)*.)*

## Sub-designs

The mechanics live in sub-designs, so this HLD stays high-level.

**Cross-cutting:**
- **Build system** *(seeded — Phase 3)* — the single source, the per-host generator, the drift gate, host-subset coverage.
- **Composition** *(seeded — Phase 3)* — capability↔capability and capability↔opinion (depends/enhances), the full relationship map, the one-way arrow onto agentm, and the role-retirement detail.

**One per capability** *(the consolidated target set — follow-up, not yet written; one design each):*

| Capability | What it is |
|---|---|
| developer-workflows | the phase loop — setup / plan / work / review / release / bugfix (the spine; sheds the design + post-merge commands) |
| code-review | adversarial review |
| design | design authoring — abbreviated / full / architecture rungs |
| developer-safety | the recoverability gate |
| wiki | docs upkeep |
| github-projects | board-sync |
| github-ci | CI / dependabot (+ `/ci-cd`) |
| conventions | conventions for anything that needs them (testing + releasing first) |
| obsidian-vault | the storage backend |
| token-audit | token metering (absorbs `status-line-meter`) |
| privacy | privacy / data protection — `pii` first, extensible (e.g. secret-leak prevention, redaction) |
| research | deep research *(new)* |
| diagnostics | observability / troubleshooting *(new)* |
| lifecycle | feature go-live + sunset — `/launch` + `/deprecate` *(new)* |

## References

- design-doc **Appendix C** — the ratified crickets Overview this HLD expands (the input spec, not a sibling)
- [Foundations HLD](https://github.com/alexherrero/agentm/wiki/agentm-foundations-hld) — the shared beliefs, inherited by reference; [agentm HLD](https://github.com/alexherrero/agentm/wiki/agentm-hld) — the person (personas, opinions) crickets composes onto
- `wiki/designs/developer-plugin-suite.md` + `crickets-v3-native-plugins.md` — the launched designs this HLD **reconciles** (their "three"/"six"-plugin identity-lines are superseded by the current set — fourteen capabilities at target, thirteen shipping today)
- per-component source paths (scripts, ADRs, manifests) live in the sub-designs above

## Amendment log

**2026-06-21 (C4 fold) — ADRs 0001 + 0007 retired into this HLD (AG Phase 2).** The agentm/crickets ADR model was retired (AG design-doc §5); ADR 0001 (crickets purpose / public-with-PII-guardrails framing) and ADR 0007 (MemoryVault discovery + mining) folded into this parent HLD and deleted via `migrate-adr.py` (inbound links repointed here, index + sidebars pruned). Their decision history is preserved in the two dated entries at the **foot** of this log. *Why not keep them as ADRs:* the append-only model forces a chain-read to reach live truth; one living body collapses the chain. *Re-audit trigger:* if the crickets↔agentm split, the public-repo posture, or the adapt-don't-import enforcement is revisited, amend the relevant section here rather than reviving a record.

**2026-06-21 (C0.2) — stamped governance keys: `governs: [src/**, scripts/**]`, `area: crickets/architecture`.** AG Phase-2 C0.2. The two broad globs make the parent HLD the **broad fallback** over both crickets code trees (mirrors the agentm HLD's multi-tree `[scripts/**, harness]`); Phase-3 / C4 sub-designs narrow with capability-specific globs (`src/<group>/**`, specific `scripts/*.py`) and the resolver prefers them automatically (most-specific-wins). `area: crickets/architecture` follows the canonical two-level `<root>/<domain>` vocabulary the AG area-taxonomy defines and the shipped agentm designs carry (`agentm/architecture`, `shared/foundations`); child areas are `crickets/<capability>` (e.g. `crickets/developer-safety`, seeded by the C4 ADR fold). `shape:` is not stamped on design docs per the governance contract (it is the SHAPE axis for host-loaded primitives, not design artifacts). With these keys the crickets bridge (`find_governing_design.py --root <crickets>`) resolves `src/…` and `scripts/…` targets to this HLD instead of greenfield. *(Corrected from the initial 2026-06-21 stamp — bare `crickets` / `[src, scripts]` — to the canonical two-level area + glob form once agentm's shipped designs confirmed the convention.)* *Re-audit trigger:* when C4 / Phase-3 sub-designs are authored, narrow their `governs:` globs and seed child areas; the parent's broad globs can tighten as every subtree gains a more-specific owner.

**2026-06-20 (lift) — lifted into tracked `wiki/designs/`; `status: proposed → launched`.** AG Phase-2 C0. Moved from the vault `hld-drafts/` to `wiki/designs/crickets-hld.md` as the live crickets parent design; frontmatter took the tracked-design convention plus `kind: design` / `scope: arc`. Cross-repo links to the agentm Foundations + agentm HLDs were rewritten to `github.com/alexherrero/agentm/wiki/…` URLs (they resolve once agentm lifts its parents — A0); the still-seeded cross-cutting children (build-system, composition) are now plain-text references pending their Phase-3 authoring (a launched wiki page must not link to unpublished pages). Up-pointers added on `developer-plugin-suite.md` + `crickets-v3-native-plugins.md`. **Why not stamp `governs:`/`area:`/`shape:` now:** that convention is agentm A1's substrate deliverable — stamping before it locks risks the two repos diverging; deferred to C0.2. *Re-audit trigger:* stamp the governance keys when A1's convention + the area taxonomy are confirmed; confirm the agentm-wiki URLs resolve once A0 lands.

**2026-06-20 — authored, reviewed, and finalized.**

Authored 2026-06-19 from the ratified Overview (design-doc Appendix C) and a read-only grounding sweep, then upleveled through operator review to plain English: a **capability is a shell that holds primitives** (commands, agents, skills, hooks), led by one worked example (developer-workflows). The mechanics were sharded into two seeded cross-cutting children — **build-system** (the single-source → generated, drift-gated build) and **composition** (capability↔capability, capability↔opinion, and the one-way compose-onto-agentm seam). The **role-retirement** is propagated here: there is no role tier — a role *is* a persona, and crickets provides tools + packages.

The 2026-06-20 **portfolio chart pass** (design-doc "Forward plan") set the target to **fourteen capabilities**: a **naming rule** (bare-noun default; banned `-workflows` + Opinion-names; the `developer-` exception), the consolidations (`testing` + `releasing` → `conventions`, `status-line-meter` → `token-audit`, `pii` → `privacy`), the spine **re-homing** into new `research` / `diagnostics` / `lifecycle` capabilities, and three proposed renames (`code-review` → `review-workflows`, `token-audit` → `efficiency`, `research` → `research-workflows`) adversarially **rejected**. The Sub-designs table is the consolidated fourteen in **final names**; the chart was verified **sound** by the `ag-portfolio-verify` workflow. (Thirteen capabilities ship today.)

`status` stays `proposed` until the Phase-1 lift flips it to `launched`. **Re-audit triggers:** author the fourteen per-capability sub-designs in Phase 3 (final names); reconcile `Coordinator-Roles.md` + the agent-defs when the role-retirement lands. *(2026-06-20 cleanup: the example diagram is now a vector image, and the composition child's relationship map carries the final fourteen names — that map stays mermaid, since a dependency graph benefits from auto-layout, with vector conversion an option at its voice pass.)*

---

*Folded decision history (AG Phase-2 C4 — records retired into this HLD; git holds the full ADR text):*

**2026-05-22 — MemoryVault discovery + mining (was ADR 0007).** Shipped the discovery surface as `/memory` sub-commands (index-skills · reflect corpus · discover-skills · adapt-skills · watchlist) with a deterministic-Python Pass-1 (6-rule rubric + GitHub-metadata + trust signals) → LLM-sub-agent Pass-2 (`adapt-evaluator`) architecture for the highest-judgment task. *Load-bearing:* **adapt-don't-import is architecturally enforced** — the sub-agent's write allowlist is scoped to the watchlist, so new skills enter only by operator-typed fork, never auto-promotion. Stdlib-only; operator-editable source/trust whitelists (configure-don't-build). *Why not auto-fork / pure-heuristic / hardcoded lists:* auto-fork makes adoption advisory not architectural; a heuristic alone is blind to semantic fit; hardcoded lists can't evolve without code. *Note:* the memory surface itself moved to agentm in the V5 unbundling — this records the crickets-era decision. *Re-audit trigger:* any request to soften the manual-fork-only contract (e.g. auto-promote HIGH + trusted-org + stars) supersedes the enforcement and must be re-decided here.

**2026-05-12 — crickets purpose, scope, public-with-PII-guardrails (was ADR 0001).** Established crickets as a **separate public GitHub repo** sibling to agentm: independent release cycles, `lib/install/` shared byte-identically (CI-gated), every customization-primitive kind in its own `src/` subdir with a YAML manifest (`name`/`description`/`kind`/`supported_hosts`/`version`), the installer dispatching per host. **Public-with-PII-guardrails** — three layers from day one: the pre-push hook (mandatory enforcer) · the `pii-scrubber` skill (interactive layer) · the CI gitleaks gate. *Why not lower-parity-in-place / two-surfaces-one-repo:* both keep one README balancing harness-users vs customization-users and either tax skill growth or harness coherence; the clean repo split removes the parity tax and keeps each identity focused (full discussion: [agentm ADR 0006](https://github.com/alexherrero/agentm/blob/main/wiki/explanation/decisions/0006-crickets-split.md)). **Amended 2026-05-17** (v0.9.0): Gemini CLI dropped from supported hosts → forward scope `{claude-code, antigravity}` (the host-scope reduction is its own record, ADR 0006, folding in a later C4 arc). **Amended 2026-05-20** (v0.9.2): embeddings narrowed to local-only (`{local, stub}`), default `BAAI/bge-large-en-v1.5`, assuming desktop-class operator hardware. *Re-audit trigger:* a customization kind needing a fundamentally different shape (binary artifacts, large-file storage), or `lib/install/` byte-identity drift (recovery: `sync-lib.sh`).
