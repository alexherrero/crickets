# How to declare a project's Architecture

> [!NOTE]
> **Goal:** Write a `wiki/architecture.yml` manifest so the wiki grows an **Architecture** section — one landing per large component, plus the nested sidebar — without hand-building any of the scaffolding.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); a scaffolded `wiki/` ([Provision a repo's wiki](Provision-A-Repo-Wiki)); `PyYAML` available (`pip install pyyaml` — the manifest reader needs it); run from the target repo's root.

Architecture is the one wiki section whose contents are **per-project**. Rather than hard-code its sub-sections, the generator reads a small manifest — `wiki/architecture.yml` — listing each large component. No manifest means no Architecture section (the section is gated on `bool(components)`); a malformed manifest **fails closed** and scaffolds nothing.

## Steps

1. **Name your components.** Pick the handful of large parts a reader needs to understand the system — typically 3–6. Each becomes one folder, `architecture/<slug>/`, with its own overview landing. Decide their order now: the manifest order *is* the render order, top to bottom in the sidebar.

2. **Write `wiki/architecture.yml`.** Give each component four required keys — `slug` (folder name), `title` (display name), `summary` (the landing's one-liner), `overview` (the landing's basename within the folder):

   ```yaml
   architecture:
     components:
       - slug: ingest
         title: Ingest pipeline
         summary: How raw events are received, validated, and queued.
         overview: Ingest-Pipeline
       - slug: store
         title: Storage layer
         summary: The durable store and its schema.
         overview: Storage-Layer
   ```

   Any missing key on a component is a fail-closed error — the generator writes nothing until it's fixed.

3. **(Optional) toggle a recurring pillar.** Three components recur across paired repos and ship as one-word toggles under `pillars:` — `host-adapters`, `sibling-interface`, `distribution` — each expanding to a repo-agnostic template:

   ```yaml
   architecture:
     pillars: [distribution]
     components:
       - slug: core
         title: Core engine
         summary: The evaluation loop everything else feeds.
         overview: Core-Engine
   ```

   **Pillars expand first**, in declared order, ahead of free-form components — so a pillar lands at the top of the section. To place a recurring component lower (or to give it repo-specific wording), free-form it under `components:` with the **same slug** instead: a `components:` entry whose slug matches a pillar overrides that template's fields **in place**, keeping its position.

4. **Preview the scaffold.** From the repo root:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wiki_init.py" --preview
   ```

   It reads the manifest and prints the gap-fill plan, writing nothing. On Claude Code, `/wiki-init` runs this for you.

5. **Apply.** Drop `--preview` (add `--yes` to skip the prompt once you've read the plan):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wiki_init.py" --yes
   ```

6. **Fill the overview landings.** The generator scaffolds each `architecture/<slug>/<Overview>.md` as an `<!-- mode: index -->` stub. Replace each stub with a real component overview — what the part *is*, how it works, how it fits its siblings.

## What the generator scaffolds

For a manifest of N components, gap-fill creates: the **Architecture** section landing (`architecture/Architecture.md`) + its `_Sidebar.md`; one `architecture/<slug>/<Overview>.md` landing + `architecture/<slug>/_Sidebar.md` per component, in manifest order; and the **third-level nest** on the root `_Sidebar.md` — the Architecture bullet expands into one indented sub-bullet per component, each linking to its overview. Architecture is the only section that nests on the root; the run is idempotent, so a second pass is a no-op.

## Related

- [Provision a repo's wiki](Provision-A-Repo-Wiki) — scaffold the six-section frame first; this how-to fills its Architecture section.
- [Repo layout](Repo-Layout) — where `wiki/architecture.yml` and the `architecture/` tree sit in the repo.
- [Wiki-Maintenance plugin](Wiki-Maintenance) — the plugin that bundles `wiki-init` and the gate.
- [Wiki Section Taxonomy](crickets-wiki) — why Architecture is a per-project manifest instead of hard-coded sub-sections.
