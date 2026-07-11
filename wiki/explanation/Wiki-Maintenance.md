<!-- mode: explanation -->
# Wiki Maintenance

## Architecture

Wiki Maintenance keeps a repo's docs alive instead of letting them rot. It sets up a wiki from scratch, holds every page to a clear Diátaxis shape and your own writing voice, and watches the code so the docs move with it rather than falling behind. The idea is that a wiki fails when it's hand-tended and inconsistent, so this plugin makes the structure enforce itself, teaches the agent your voice from your own edits, and runs the upkeep safely enough to leave on. It stands alone — you can use it in any repo on its own — and it slots naturally into Developer Workflows when that plugin is installed, updating pages as part of the normal loop.

### Diagram

How the authoring flow runs — from a request or a code change through page-choice to the documenter, with your edits teaching it your voice:

![The wiki-maintenance authoring flow: an operator request or a watcher run feeds a page-and-mode choice, which hands off to the documenter to author, repair, or migrate a page into an updated page shipped as a pull request; your own edits feed a voice-learning loop that shapes the next write](diagrams/wiki-maintenance-authoring.svg)

How it composes — standalone, resting on the AgentM substrate, softly enhancing Developer Workflows when both are installed:

![How wiki-maintenance composes: it stands alone and rests on the AgentM substrate of memory, opinions, and personas, with a dashed-green soft-enhances arrow out to developer-workflows, which it documents at phase boundaries only when both are installed](diagrams/wiki-maintenance-composition.svg)

### How it works

You start by scaffolding the wiki — the plugin lays down the folders, sidebars, and section landing pages, and it never overwrites anything that already exists, so it's safe to run on a wiki you've already begun. After that, a plain request like "update the wiki with what we just shipped" is enough: the plugin works out which page should change, then hands the actual writing to a documenter that only ever touches the wiki, keeps your hand edits intact, and never edits code. Behind that write sits the real discipline — picking the right kind of page, filling it to the template, fixing pages that have drifted, and, when you're moving an older wiki over, reshaping it into the standard layout. It also learns your voice: when you edit a page, it can pick up a lasting lesson from your change, and it checks with you before treating that lesson as a general rule.

For ongoing upkeep, a watcher can run on its own. Each run looks at what's changed in the code, decides whether it's worth documenting, and, when it is, sends the documenter to write the update — opening a pull request by default so a human still merges it. It's built to be run on a schedule without ever doubling up or dropping a change. And when Developer Workflows is installed, the same documenter is called at the end of each phase, so the docs get refreshed as a normal part of the loop rather than as a separate chore.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | [Developer-Workflows](Developer-Workflows) | Dispatches the `documenter` to author or repair pages at phase boundaries — only when both are installed (`enhances: documentation`). |
| Enhanced by (soft) | — | None. |
| Requires (hard) | — | None. Wiki Maintenance is fully standalone (`requires: []`). |
| Required by (hard) | — | None. |

### Why not

Wiki Maintenance is opinionated, and it will not fit every project. Reach for something else if:

- You already run a wiki generator or docs pipeline you're happy with — this plugin wants to own `wiki/`'s shape and voice, and it will fight a competing convention.
- You don't want Diátaxis single-mode discipline. The structure is enforced, not suggested, and a free-form wiki will read as constant drift to the linter and the documenter.
- The change is small. Scaffolding a wiki, wiring the watcher, and learning your voice is overhead a one-page README or a quick hand edit doesn't need.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`/wiki-init`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/commands/wiki-init.md) | command | Scaffold a repo's wiki to the intent-group structure — idempotent, preview-first. |
| [`/wiki-watch`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/commands/wiki-watch.md) | command | Run one watcher cycle; the thin entry for driving the watcher on a loop or cron. |
| [`/recent-wiki-changes`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/commands/recent-wiki-changes.md) | command | List wiki pages modified recently across registered repos. |
| [`wiki-author`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/skills/wiki-author/SKILL.md) | skill | Operator-facing dispatcher — resolve the target page and hand the write to the documenter. |
| [`diataxis-author`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/skills/diataxis-author/SKILL.md) | skill | Author, repair, migrate, and classify pages; learn voice lessons from your edits. |
| [`wiki-watch`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/skills/wiki-watch/SKILL.md) | skill | The single-cycle watcher engine `/wiki-watch` delegates to. |
| [`documenter`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/agents/documenter.md) | sub-agent | The write-executor — creates, updates, and prunes pages; preserves human edits; never touches code. |
| [`diataxis-evaluator`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/agents/diataxis-evaluator.md) | sub-agent | Read-only — classifies a page whose Diátaxis mode is ambiguous. |
| [`style-scope-evaluator`](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/agents/style-scope-evaluator.md) | sub-agent | Read-only — recommends where a captured voice lesson should live. |

### Configuration

The authoring primitives work out of the box; only the watcher is opt-in. `wiki-watch` stays a clean no-op until you enable it in two places:

- **Device toggle** — set `wiki_watch.enabled: true` (or `wiki_watch_enabled: true`) in `<install-prefix>/.agentm-config.json`.
- **Per-repo marker** — add a `<repo>/.harness/wiki-watch.json` file; its presence is the opt-in. It carries `watch_sources` and `dispatch_mode` (`pr` default, or `direct` for a trusted repo).

Per-repo voice and structure overrides live in `wiki/.diataxis-conventions.md`; global voice conventions come from AgentMemory `_always-load/diataxis-*.md`.

## See also

- [Provision a repo's wiki](Provision-A-Repo-Wiki) · [Run the wiki-watcher](Run-The-Wiki-Watcher) — the how-tos.
- [Style-Learning Loop](Style-Learning-Loop) · [Wiki Watch Config](Wiki-Watch-Config) — the voice layer and the watcher config.
- [Wiki design](crickets-wiki) — why provisioning joins authoring, and the gate-distribution split.
- [Developer-Workflows](Developer-Workflows) — the base plugin this enhances at phase boundaries.
- [Antigravity Limitations](Antigravity-Limitations) — which surfaces are Claude-first.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)