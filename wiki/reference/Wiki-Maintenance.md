<!-- mode: reference -->
# Wiki Maintenance

## Architecture

Wiki Maintenance provisions a repo's `wiki/` from nothing, keeps it in Diátaxis single-mode shape and your house voice, and watches for doc-worthy changes so the docs track the code without a separate step. A wiki rots when it's hand-maintained and voiceless — this plugin makes the structure self-enforcing, the prose learnable, and the automation safe to leave running.

### Diagram

_None / not needed._

### How it works

You provision a wiki with `wiki-init`, which scaffolds the intent-group folders, per-folder sidebars, and section landings — idempotent and preview-first, so it never clobbers a page that already exists. From then on, `wiki-author` fires on operator phrases like "update the wiki with what we just shipped": it resolves which Diátaxis mode page to touch, then hands the mechanical write to the `documenter` sub-agent, which is hard-scoped to `wiki/**`, preserves human edits, and never touches code. The `diataxis-author` skill supplies the deeper discipline behind that write — mode selection, template-fill, drift repair, and one-shot migration of a legacy audience-based wiki into the six-section layout — and it learns generalizable voice lessons from your own edits, gated by you for scope. Two read-only evaluators back the ambiguous calls: `diataxis-evaluator` classifies a page whose mode is unclear, and `style-scope-evaluator` recommends where a captured voice lesson should live. For continuous upkeep, `wiki-watch` runs one idempotent cycle — poll, detect, judge significance, dispatch the documenter PR-default — cooldown-gated and cursor-backed so a `/loop` or cron line never drops a change or double-dispatches. When `developer-workflows` is also installed, its phase commands dispatch the same `documenter` at phase boundaries, so the wiki updates as part of the normal loop.

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