<!-- mode: reference -->
# Style-learning loop

The **voice layer** of the `wiki-maintenance` plugin: a style overlay every wiki draft is composed against, plus the edit-driven capture that grows it. Templates fix a page's *structure*; this fixes its *voice*, so the wiki reads as the operator's, not the agent's. It is **infrastructure, not a task** — the workflows that author your wiki run it, and each operator edit teaches a reusable lesson, so drafts converge on the house voice over time.

## ⚡ Quick Reference

| Piece | What it is |
|---|---|
| **base style-guide** | the committed house voice — `src/…/style/base-style-guide.md` |
| **overlay** | learned voice lessons layered on the base, at `global` / `per-project` / `per-repo` scope |
| **`style_resolver`** | composes `template ⊕ base ⊕ overlay` at draft time (narrower scope wins) |
| **edit-driven capture** | diffs an operator's edits into proposed lessons |
| **`style-scope-evaluator`** | read-only sub-agent that recommends a lesson's scope |
| **`convention-drift`** | the `/diataxis check` pass that flags banned-term use (voice drift) |

## How the infrastructure uses it

You rarely touch the loop directly — the wiki-authoring workflows run it for you:

| Workflow | How it uses the loop |
|---|---|
| **`developer-workflows` phase commands** — `/plan` · `/work` · `/release` · `/bugfix` | dispatch the `documenter` at phase boundaries to author/update wiki pages, composed against the current overlay; operator edits feed the capture |
| **wiki-watcher** ([Wiki Watch Config](Wiki-Watch-Config)) | runs the `documenter` on a loop to keep a wiki in sync — the same compose-then-capture path |
| **`wiki-author` / `diataxis-author` skill** | the engine — composes drafts via `style_resolver` and captures edits into lessons |

So the loop's effect is mostly invisible: the documenter's drafts already carry the learned voice, and reviewing them is what grows it.

## How it works

The lifecycle of a voice lesson:

- **Compose.** `style_resolver` builds a draft from `template ⊕ base style-guide ⊕ overlay` — structure from the template, voice from the base plus any learned lessons.
- **Capture.** When the operator edits that draft, the capture diffs draft ↔ edited and clusters the changes (word choice · rhythm · structure · cuts · additions) into proposed lessons.
- **Two gates.** Each proposal passes *generality* — the operator rewrites it into a real lesson with a semantic trigger, and one-offs are rejected — then *scope*, where the read-only `style-scope-evaluator` recommends `global`/`per-project`/`per-repo` and the operator confirms.
- **Store + read back.** The confirmed lesson lands in that scope's on-demand store — never `_always-load` — and the next draft's `style_resolver` reads it back automatically.

## Where lessons live

| Scope | Store |
|---|---|
| global | `projects/_global/wiki-style/` |
| per-project | `projects/<slug>/wiki-style/` |
| per-repo | `wiki/.diataxis-conventions.md` |

Narrower and more recent wins. A proven lesson can be **promoted** into the committed base style-guide, so it ships in the plugin and every fresh draft inherits it without an overlay. Voice drift is caught by `convention-drift`: `/diataxis check` flags every banned term a page uses (info by default, failing under `--strict`).

## Drive it by hand

The workflows above invoke the loop automatically; to experiment with it explicitly:

- `/diataxis author` — compose a draft.
- `/diataxis capture <draft> <edited>` — diff your edits into lesson proposals.
- `/diataxis check` — flag voice drift (`--strict` to fail on it).
- `/diataxis promote <lesson>` — graduate a proven lesson into the base (maintainer-only, preview-first; you `git commit` + `python3 scripts/generate.py build`). Full flags: the [`diataxis-author` SKILL.md](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/skills/diataxis-author/SKILL.md).

## Related

- [Wiki Maintenance design](wiki-maintenance) — why the voice layer + operator-in-the-loop learning exist.
- [Wiki Watch Config](Wiki-Watch-Config) — the wiki-watcher that runs the documenter.
- [Customization types](Customization-Types) — the kinds the `wiki-maintenance` plugin ships.
