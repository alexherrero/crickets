---
name: diataxis-author
description: Author + maintain a Diátaxis-style wiki for any repo. Live authoring guidance (mode selection + template-fill + filename style), ongoing drift detection + repair, one-shot migration of legacy audience-based wikis to the six-section documentation layout (how-to · reference · architecture · designs · explanation · operational; onboarding folds into how-to, marked with a mode-tutorial hint), and single-page mode classification with sub-agent fallback on ambiguous cases. Reads operator conventions from `diataxis-*.md` in the vault's `standards/` (the retired `_always-load/` pen as fallback); composes a base style-guide ⊕ on-demand voice overlay into authored drafts, and learns generalizable voice lessons from the operator's own edits (edit-driven capture, operator-gated for generality + scope); offers to capture judgment calls back as new conventions (operator-confirmed via permeable-boundary helper). Dispatches the existing `documenter` sub-agent for mechanical-write work; never auto-forks into wiki/ without preview. Subsumes the predecessor `migrate-to-diataxis` skill (harness-side) per ROADMAP #13. Hosts: Claude Code + Antigravity (`gemini-cli` removed in v0.9.0 per the gemini-cli host-removal decision, crickets-hld design).
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.1.1
---

The full instructions for the `diataxis-author` skill are too long to load here, so they sit in `references/SKILL.full.md` next to this file.

Before doing anything else, read that whole file with `view_file` and follow it exactly.
