<!-- mode: index -->
# Wiki Maintenance

_Opinionated, template-driven wiki maintenance — provisions a repo's `wiki/` from nothing, keeps it in Diátaxis single-mode shape and your house voice, and watches for doc-worthy changes._

Full design detail: [wiki design](crickets-wiki).

## How it composes

- **Standalone** — maintain any repo's wiki directly; `requires: []`.
- **Enhances `developer-workflows`** — phase commands dispatch the `documenter` to author or repair pages at phase boundaries (`enhances: documentation`), so the wiki tracks the code without a separate step.
- **Hosts** — Diátaxis engine, documenter, and evaluators are host-symmetric; `wiki-author` trigger, `recent-wiki-changes`, and watcher scheduling are Claude-first ([Antigravity limitations](Antigravity-Limitations)).

## Why it works

A wiki rots when it's hand-maintained and voiceless. Diátaxis single-mode discipline keeps the structure honest; a house-voice overlay plus an operator-in-the-loop learning loop keeps the prose yours; and `check-wiki.py` plus the `documenter`'s preserve-human-edits / never-touch-code scoping keep the automation safe.

## Related

- [Provision a repo's wiki](Provision-A-Repo-Wiki) — scaffold a wiki + its CI from nothing with `wiki-init`.
- [Run the wiki-watcher](Run-The-Wiki-Watcher) — drive one watcher cycle.
- [Style-learning loop](Style-Learning-Loop) · [Wiki Watch Config](Wiki-Watch-Config) — the voice layer + the watcher config.
- [Wiki design](crickets-wiki) — why provisioning joins authoring; the gate-distribution split.
- [Developer Workflows](Developer-Workflows) — the base plugin this enhances at phase boundaries.

[Architecture](Architecture) · [Plugins](Plugins) · [Home](Home)
