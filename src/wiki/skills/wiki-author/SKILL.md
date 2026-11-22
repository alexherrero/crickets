---
name: wiki-author
description: "Update or create a page in a repo's six-section wiki (how-to · reference · architecture · designs · explanation · operational). Triggers when the operator says 'update the wiki', 'document this in the wiki', 'add this to the wiki', 'create a wiki page for X', or 'update <repo>'s wiki'. Resolves the target repo (cwd, or a registered slug), picks the page and its mode, and dispatches the documenter sub-agent, which drafts from the bundled templates, runs the prose pass, previews the diff and writes only on approval. check-wiki --strict is the gate. Does not invent content: the agent gathers it from the conversation."
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.2.0
---

# wiki-author — the wiki skill

Updates or creates one wiki page at the operator's request. The **`documenter` sub-agent** writes; it is scoped to `wiki/**`, and every write waits on the operator's approval of a previewed diff. The other wiki surfaces are commands: `/wiki-watch` (the same documenter on a change feed), `/wiki-init` (scaffold a wiki), `/recent-wiki-changes` (read-only).

## When it fires

Imperative wiki-write phrases only:

| Phrase | Resolution |
|---|---|
| "update the wiki" | cwd repo; the documenter picks the page the conversation's change touches |
| "document this in the wiki" / "add this to the wiki" | cwd repo; mode from the content (a new command → reference, a procedure → how-to, a why → explanation) |
| "create a wiki page for X" | cwd repo; ask for the mode if X doesn't settle it |
| "update {slug}'s wiki" | the registered repo: `python3 scripts/repo_registry.py list`, then its `root_path`/`wiki` |
| "what's new in {slug}'s wiki" | read-only: point to `/recent-wiki-changes --repo {slug}` |

Not on descriptive mentions ("the wiki page says…", "the wiki/ tree", Wikipedia). If the ask is vague ("put this somewhere"), ask.

**Target.** Default is `<cwd-root>/wiki/`. A named slug resolves through the repo registry. Outside a registered repo with no slug, refuse: "Register first (`python3 scripts/repo_registry.py register <slug> --root <path>`) or name the target." With no vault or an empty registry, work in the cwd only.

## The six sections

One page, one mode. Each folder is a mode; a page that mixes them fails `check-wiki.py --strict` and is split, not stretched.

| Folder | Mode | Holds |
|---|---|---|
| `how-to/` | task | steps to get one thing done (a first-run walkthrough lives here too, marked as a tutorial) |
| `reference/` | lookup | facts: commands, flags, schemas, configuration |
| `architecture/` | how it fits | components and how they connect; per-plugin pages use `templates/plugin-reference.md` |
| `designs/` | decisions | living design pages, changed with an amendment-log entry |
| `explanation/` | why | background and the reasoning behind a choice |
| `operational/` | running it | runbooks, troubleshooting, recovery |

- **Filenames** are `CamelCase-With-Dashes.md`: letters, digits and dashes only, which `check-wiki`'s rule (g) enforces.
- **Updating** keeps the page's mode. **Creating** takes the mode from the ask, or asks.
- **Templates** are in [`templates/`](templates/) — one per mode plus `sections/` for composed landing pages. [`templates/README.md`](templates/README.md) is the authoritative house standard: curated landings, scenarios as a table, long lists behind an index link, the user/contributor split, plain prose.
- **Diagrams** follow [`style/diagram-style.md`](style/diagram-style.md).

## Dispatch

1. **Conventions.** Load the target repo's `.diataxis-conventions.md` if present; it overrides the defaults.
2. **Context.** `python3 scripts/harness_memory.py documenter-context --slug <slug> --format text` returns the operator's conventions, the project's decisions and its locked design calls. On rc 1 (no vault) say "[wiki-author] vault unreachable; proceeding without vault context" and carry on; on rc 2 (unregistered) use the operator-global conventions it still returns.
3. **Draft.** The documenter drafts from the template for the page's mode, then runs the design plugin's **`prose-pass` skill**: Gemini simplifies with the base style floor (`style/base-style-guide.md`) and the vault's `docs-prose-style` overlay inlined verbatim; Claude lists the facts first, then checks the result against them and the code, and scans for `style/voice-rules.json`'s banned vocabulary. If Gemini is unavailable the pass falls back to Claude alone, and says so.
4. **Preview.** Show the unified diff with the context bundle beside it. One approval per write, even when one conversation touches several pages.
5. **Write.** On approval the documenter writes within its `wiki/**` scope ([documenter spec](../../agents/documenter.md)).
6. **Gate.** `python3 scripts/check-wiki.py --strict` stays green. It enforces single mode per page, length ceilings, naming, links, and the component-overview section model (built from `templates/sections/` by `scripts/composer.py` and `scripts/section_schema.py`).

## The voice files

`style/voice-rules.json` is the one banned-vocabulary rule pack. `scripts/rule_pack.py` loads it, with the vault's overlay, for `check-slop`, the `commit-msg-gate` hook and the prose pass's scan. `style/base-style-guide.md`'s `banned:` line must agree with it (`check-voice-floor-parity`). `scripts/style_resolver.py` and `scripts/vault_layout.py` find the operator's voice lessons in the vault on demand; they are never always-loaded.

## Not this skill's job

- Writing content nobody gave it: the invoking agent brings the facts (the diff that landed, the call that was made).
- Writing outside `wiki/**`: plans, progress logs, AGENTS.md and code are off limits; say which surface owns them.
- Batching writes past the per-write approval.
- Read-only questions: `/recent-wiki-changes`.

Retired in crickets plan 105 and not coming back: `/diataxis` migrate, classify, relocate, repair, capture and promote, and the `diataxis-evaluator` and `style-scope-evaluator` agents. Mode is picked from the ask or by asking; voice lessons are edited in the vault by hand.
