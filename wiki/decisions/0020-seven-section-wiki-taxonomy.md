# ADR 0020 — Seven-section wiki taxonomy: fixed frame + per-project Architecture manifest + conditional gates

> [!NOTE]
> **Status:** accepted · **Date:** 2026-06-11

## Context

[ADR 0018](0018-per-folder-sidebars) gave the wiki intent-grouped folders (`get-started/ · do/ · reference/ · why/ · designs/ · decisions/`) and per-folder sidebars. That solved navigation but left the **taxonomy itself open-ended**: each repo improvised its own folder set at provisioning time, so the section list drifted across repos and had no single source `wiki-init` could scaffold or `check-wiki` could enforce. Reader-intent names (`do/`, `why/`) also read as placeholders rather than a deliberate frame, and there was nowhere structured for a project's **architecture** to live — `plugins/` was a crickets-specific bolt-on, not a general bucket.

The [wiki-section-taxonomy design](wiki-section-taxonomy) closes that: one fixed frame, scaffolded by `wiki_init.py`'s `DEFAULT_SECTIONS` and allow-listed by `check-wiki`'s `_FOLDER_MODE`, dogfooded by restructuring both crickets and agentm (parts 4–5). This ADR records the three load-bearing calls.

Open questions this resolves:

- Should the section set be **fixed** (uniform, lintable, one-shot-scaffoldable) or **per-repo improvised** (flexible, but drift-prone with no source of truth)?
- Where does a project's **architecture** come from — hard-coded sub-sections in the scaffolder, or a per-project declaration?
- Are all sections **always present**, or do some appear only when they apply — and if conditional, gated on *what*?

## Decision

### 1. A fixed seven-section frame, in a fixed order

The wiki is a fixed frame of seven sections in a fixed order: **How-to · Reference · Architecture · Designs · Explanation · Decisions · Operational**. `wiki_init.py`'s `DEFAULT_SECTIONS` scaffolds them; `check-wiki`'s `_FOLDER_MODE` is the matching allow-list (`how-to→how-to`, `reference→reference`, `architecture→index`, `designs→explanation`, `explanation→explanation`, `decisions→explanation`, `operational→how-to`). This replaces ADR 0018's reader-intent folders — `get-started/`+`do/`→`how-to/`, `why/`→`explanation/`, `plugins/`→`architecture/plugins/`.

- **Why not the open-ended intent folders** (ADR 0018's `get-started/do/why/plugins`). They were improvised per repo with no single source of truth, so the section set drifted and provisioning hand-picked folders each time. A fixed frame makes the taxonomy uniform across every repo, lintable by one allow-list, and scaffoldable in one shot.
- **Why not Diátaxis-type folders alone** (`tutorial/how-to/reference/explanation`). Diátaxis has four content modes, but a project's docs need buckets that aren't Diátaxis modes — Architecture, Designs, Decisions, Operational. The seven-section frame maps each folder to a mode via `_FOLDER_MODE` while keeping intent-legible section names, so it's Diátaxis-disciplined *and* covers the non-Diátaxis buckets.

### 2. Architecture comes from a per-project `wiki/architecture.yml` manifest

The Architecture section's contents are declared in a per-project `wiki/architecture.yml` manifest — a `components:` list of `{slug, title, summary, overview}` (all four required, else a fail-closed `ManifestError`) plus an optional `pillars:` list of one-word toggles (`host-adapters · sibling-interface · distribution`) for recurring cross-repo shapes. The generator reads it for render order, the section landings, and the third-level nested sidebar. Absent manifest → no components → Architecture suppressed (not an error).

- **Why not hard-code the Architecture sub-sections** in the scaffolder. Every project's architecture differs — crickets has plugins / customization-model / build-distribution / host-adapters / harness-interface; another repo shares none of them. A hard-coded list is wrong for every repo but the one it was written against.
- **Why not free-form `architecture/` folders with no manifest.** Then render order, the per-component landings, and the third-level sidebar nesting would all be hand-maintained — exactly the drift the fixed frame exists to kill. The manifest is the single source the generator reads, so the nested nav can't fall out of sync with the pages.
- **Why the recurring-pillar toggles.** `host-adapters / sibling-interface / distribution` recur across sibling repos; toggle-able one-word entries (expanded from `PILLAR_TEMPLATES` *first*, ahead of free-form components) save re-typing the same boilerplate, and a `components:` entry with a matching slug overrides the pillar's fields **in place** (keeps position) when a repo needs to customize one.

### 3. Two conditional sections — Architecture on declaration, Operational on visibility

Five of the seven sections are always scaffolded. Two are conditional: **Architecture** renders only when the manifest declares components (`has_architecture = bool(components)`); **Operational** renders only for a non-public wiki (`renders_operational(visibility)`: private/internal render, public/unknown suppress). The gate is the wiki's **audience, not any page's sensitivity**. crickets and agentm are both **public** → Operational is suppressed in both.

- **Why gate Architecture on declaration**, not always-present-but-empty. A stub Architecture section — heading, landing, sidebar entry, no content — is noise. A repo with no declared components shouldn't carry one.
- **Why gate Operational on visibility (audience)**, not on whether ops docs happen to exist. Operational docs (runbooks, on-call, internal dashboards) are *for an internal audience*; a public wiki shouldn't surface an Operational section at all, even if someone writes ops notes into the repo. The gate asks "who is this wiki for," not "does ops content exist."
- **Why not gate Operational on sensitivity** (does a page contain secrets). Sensitivity is per-page and already the PII gate's job. The section gate is coarser and about audience: a public wiki has no Operational section regardless of any single page's sensitivity.

## Consequences

**Positive:**

- One uniform, lintable, one-shot-scaffoldable taxonomy across every provisioned repo — replaces per-repo improvisation with a single frame `wiki-init` scaffolds and `check-wiki` enforces.
- Architecture grows from a declarative manifest the generator reads — render order, titles, summaries, and the nested sidebar all single-sourced, so the third-level nav can't drift from the pages.
- A public repo carries exactly five sections (no empty Architecture, no Operational); the frame self-adjusts to the repo instead of forcing every repo into the same seven.
- Proven, not theoretical: the frame was dogfooded by restructuring both crickets and agentm (taxonomy parts 4–5) before this ADR recorded it.

**Negative:**

- A fixed frame is less flexible than per-repo folders — a repo wanting an eighth top-level section can't add one without editing `DEFAULT_SECTIONS` + `_FOLDER_MODE`.
- `wiki/architecture.yml` is another file to maintain and keep in sync with the actual `architecture/` pages.
- Two conditional code paths (`has_architecture`, `renders_operational`) instead of a flat always-scaffold; Architecture's third-level sidebar nesting is a special case on top of ADR 0018's two-level model.

**Load-bearing assumptions (re-audit triggers):**

- **The seven sections cover every project's doc needs.** **Re-audit if** a recurring doc type has no home (add a section) or a section proves universally empty across repos (drop it).
- **`wiki/architecture.yml` is the single source for the Architecture section.** **Re-audit if** components ever need declaring elsewhere (e.g. derived from code), or the `{slug, title, summary, overview}` shape proves too thin or too thick.
- **Operational's gate is audience (visibility), not per-page sensitivity.** **Re-audit if** a public wiki legitimately needs an Operational section, or `visibility` stops being a reliable audience proxy.
- **Architecture is the one section that nests a third sidebar level** (ADR 0018's model is two). **Re-audit if** a second section ever needs third-level nesting — then the root-sidebar special-case should generalize rather than gain a second exception.

## Related

- [Wiki Section Taxonomy](wiki-section-taxonomy) — the design this ADR records; the six parts that shipped + dogfooded the frame.
- [Declare a project's Architecture](Declare-Architecture) — the how-to for writing `wiki/architecture.yml`.
- [Wiki design](wiki-design) — the umbrella wiki system this frame restructures; Detailed Design #1 carries the as-built frame.
- [ADR 0018 — per-folder sidebars](0018-per-folder-sidebars) — the intent-folder IA this frame supersedes in spirit (`get-started/do/why/plugins` → the fixed seven); its nearest-sidebar + two-level reachability model still holds.
- [ADR 0019 — wiki provisioning](0019-wiki-provisioning) — `wiki-init` scaffolds the frame and reads the manifest.
