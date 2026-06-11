<!-- mode: index -->
# Reference

Look up how crickets is built — what a plugin is, the kinds you can author, where each lands, the manifest contract, and the host hooks.

## What's here

- **[Plugin anatomy](Plugin-Anatomy)** — what a crickets plugin *is* and how it's structured (the anchor — start here).
- **[Repo layout](Repo-Layout)** — what lives where in the repo.
- **[Customization Types](Customization-Types)** — the primitive kinds (`skill` · `agent` · `command` · `hook` · `snippet`).
- **[Per-Host Paths](Per-Host-Paths)** — where each kind lands inside the generated plugin, per host.
- **[Manifest Schema](Manifest-Schema)** — the frontmatter + `group.yaml` contract.
- **[Compatibility](Compatibility)** — supported hosts + per-plugin and per-hook effectiveness.
- **[CI gates](CI-Gates)** — the local gate battery + the 3-OS CI matrix.
- **[Troubleshooting](Troubleshooting)** — symptom-first lookup when something stops working.
- **[Antigravity Limitations](Antigravity-Limitations)** — the `agy` host-gaps register + crickets mitigations.
- **[Hooks](Hooks)** — the hook catalog + how hooks work (the `developer-safety` control trio is driven from its [plugin page](Developer-Safety)).
- **[Evaluator](Evaluator)** — the read-only rubric grader + its dispatch contract.
- **[Wiki Watch Config](Wiki-Watch-Config)** — the wiki-watcher config contract.
- **[Style-learning loop](Style-Learning-Loop)** — how the wiki stays in your voice + what invokes it.
- **[Modify a plugin](Modify-A-Plugin)** · **[Add a skill](Add-A-Skill)** · **[Add a plugin](Add-A-Plugin)** — author, extend, and create plugins.

## Recent changes

<!-- maintained by the wiki tooling -->

- **2026-06-08** — the whole Reference section rewritten for v3.0 (Compatibility · Per-Host-Paths · Customization-Types · Manifest-Schema · the new Plugin-Anatomy anchor); this index added.
- **2026-06-09** — four references added: CI gates · Troubleshooting · Repo layout · Add a plugin.

## See also

[How-to](How-To) · [Architecture](Architecture) · [Designs](Designs) · [Home](Home)
