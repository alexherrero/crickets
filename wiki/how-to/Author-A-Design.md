# How to write or update a design with `/design`

> [!NOTE]
> **Goal:** Record a settled call in the one living design note for an area, so `/plan` finds it and honours it.
> **Prereqs:** the `design` plugin installed ([Install crickets plugins](Install-Crickets-Plugins)); agentm installed with a vault, so the note has a home (without a vault the note lives at `.harness/design-<slug>.md`).

`/design` does one job: it keeps one note per area true. The note's body says what is true now, and its amendment log says how it got there. It makes no plans; those come from `/plan`.

## Steps

1. **Find the note.** Run `/design <slug or topic>`. The command asks agentm for the project's designs folder (`project_homes.py home designs`), lists it, and opens the note whose slug or aliases match the topic. If none matches, it is a new note.

2. **New note: fill in four sections.** The frontmatter carries `slug`, `aliases`, `tags`, optional `governs`, and a one-line `summary`. The sections, in order, are:

   | Section | What goes in it |
   |---|---|
   | Objective | What the area is for, in a short paragraph |
   | Current design | The locked calls, each with its reason |
   | Open questions | What is not settled, or `none` |
   | Amendment log | Newest last: date, what changed, why not the alternative, the re-audit trigger |

3. **Existing note: change the body and the log together.** State the new truth in the body and add the amendment-log entry in the same edit. Touch only the lines that changed; `updated:` becomes today.

4. **Approve the diff.** The command shows the diff once. The note is live from the first save; there is no status to flip and no review stage.

5. **Make it findable.** `/plan` matches a task to a note three ways: a `governs:` entry naming the folder or file the task touches, an alias equal to the area name, or two shared tags. Fill at least one of them in.

## Verify

- The note sits in the folder agentm named (or `.harness/design-<slug>.md` with no vault), and not under `wiki/designs/`.
- The body and the newest log entry say the same thing, and the entry names a re-audit trigger.
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/vault_designs.py" find <path-or-area> --cwd .` (from the development-lifecycle plugin) prints the note's path.

## Related

- [Record an architectural decision](Record-An-Architectural-Decision) — the amendment-log entry for a decision that settles something.
- [Run a cross-model prose pass](Run-A-Prose-Pass) — optional wording pass on the note; `/design` offers it only when you ask.
- [Development Lifecycle reference](Development-Lifecycle) — the `vault_designs.py` row says how notes are matched.
- [Design Docs](Design-Docs) — what the `design` plugin holds and why.
