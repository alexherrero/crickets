<!-- mode: reference -->
# Style-learning loop

The style-learning loop is the voice layer of the `wiki-maintenance` plugin. It is the style overlay you compose every draft against. It uses edit-driven capture to grow from your own edits. Templates fix a page's *structure*. This loop fixes its *voice*. The wiki reads as your voice, not the agent's. The workflows that author your wiki run this loop for you. Each edit teaches a lesson. Drafts converge on your voice over time.

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

You rarely touch the loop directly. The wiki-authoring workflows run it for you.

| Workflow | How it uses the loop |
|---|---|
| **`development-lifecycle` phase commands** — `/plan` · `/work` · `/release` · `/bugfix` | dispatch the `documenter` at phase boundaries to author/update wiki pages, composed against the current overlay; operator edits feed the capture |
| **wiki-watcher** ([Wiki Watch Config](Wiki-Watch-Config)) | runs the `documenter` on a loop to keep a wiki in sync — the same compose-then-capture path |
| **`wiki-author` / `diataxis-author` skill** | the engine — composes drafts via `style_resolver` and captures edits into lessons |

The loop's effect is mostly invisible. The documenter's drafts already carry the learned voice. You review them to grow that voice.

## How it works

This is the lifecycle of a voice lesson:

- **Compose.** The `style_resolver` builds a draft from `template ⊕ base style-guide ⊕ overlay`. It takes structure from the template. It takes voice from the base plus any learned lessons.
- **Capture.** You edit that draft. The capture diffs draft ↔ edited. It clusters the changes (word choice · rhythm · structure · cuts · additions) into proposed lessons.
- **Two gates.** Each proposal passes *generality*. You rewrite it into a real lesson with a semantic trigger. You reject one-offs. Then it passes *scope*. The read-only `style-scope-evaluator` recommends `global`/`per-project`/`per-repo`. You confirm this scope.
- **Store + read back.** The confirmed lesson lands in that scope's on-demand store. It never lands in `_always-load`. The next draft's `style_resolver` reads it back automatically.

## Where lessons live

| Scope | Store |
|---|---|
| global | `projects/_global/wiki-style/` |
| per-project | `projects/<slug>/wiki-style/` |
| per-repo | `wiki/.diataxis-conventions.md` |

Narrower scopes win. More recent lessons win. You can promote a proven lesson into the committed base style-guide. It then ships in the plugin. Every fresh draft inherits it without an overlay. `convention-drift` catches voice drift. The `/diataxis check` command flags every banned term a page uses. It logs info by default. It fails under `--strict`.

## Drive it by hand

The workflows above invoke the loop automatically. You can experiment with it explicitly:

- `/diataxis author` — You compose a draft.
- `/diataxis capture <draft> <edited>` — You diff your edits into lesson proposals.
- `/diataxis check` — You flag voice drift. You use `--strict` to fail on it.
- `/diataxis promote <lesson>` — You graduate a proven lesson into the base. This command is maintainer-only. It is preview-first. You run `git commit` + `python3 scripts/generate.py build`. You read full flags in the [`diataxis-author` SKILL.md](https://github.com/alexherrero/crickets/blob/main/src/wiki-maintenance/skills/diataxis-author/SKILL.md).

## Related

- [Wiki Maintenance design](crickets-wiki) — This explains why the voice layer and operator-in-the-loop learning exist.
- [Wiki Watch Config](Wiki-Watch-Config) — This is the wiki-watcher. It runs the documenter.
- [Customization types](Customization-Types) — These are the kinds the `wiki-maintenance` plugin ships.
