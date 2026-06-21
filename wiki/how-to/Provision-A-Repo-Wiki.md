# How to provision a repo's wiki

> [!NOTE]
> **Goal:** Stand up a repo's `wiki/` from nothing — the seven-section folder structure plus the CI that lints and publishes it — with one idempotent, preview-first command.
> **Prereqs:** the `wiki-maintenance` plugin installed ([Install crickets plugins](Install-Into-Project)); run from the target repo's root; `git`, and — for visibility detection + publishing — an authenticated `gh` and a wiki enabled on the repo.

`wiki-init` is an **agent action**, not an install hook — plugins have no target-repo install step, so you run the bundled scaffolder yourself. It's **idempotent + preview-first**: it fills only what's missing, never overwrites an operator-authored page, and a second run is a no-op. The companion that keeps the wiki current afterward is the [wiki-watcher](Run-The-Wiki-Watcher).

## Steps

1. **Preview first — always.** From the target repo root:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wiki_init.py" --preview
   ```

   It prints the gap-fill plan and writes nothing. On Claude Code, `/wiki-init` runs this for you.

2. **Read the plan.** It has two halves:
   - **Scaffold** — the section folders (the seven-section frame by default: `how-to · reference · architecture · designs · explanation · decisions · operational`), each with a `<!-- mode: index -->` landing and a per-folder `_Sidebar.md`, plus the curated `Home.md` and root `_Sidebar.md`. Two of the seven are **conditional** — `architecture/` renders only when the repo declares components in a [`wiki/architecture.yml` manifest](Declare-Architecture), `operational/` only on a non-public wiki — so a public repo with no manifest scaffolds five. The scaffold is **gate-passing by construction** (zero hard `check-wiki` issues on a fresh `wiki/`).
   - **CI** — one workflow, `.github/workflows/wiki-sync.yml` (named **`[W] Update Wiki`**), and the vendored gate `.github/scripts/check-wiki.py`.

   Every line is an **add** (`+`) or a **kept existing** (`=`) — it never lists an overwrite.

3. **Heed the cost warning on non-public targets.** Before it writes the workflow, the preview auto-detects visibility (via `gh`) and prints a **billed-minutes** warning when the repo isn't public — Actions minutes are free only on public repos. Relay that warning and get an explicit OK before applying; don't silently `--yes` past it. To scaffold the wiki only, with no workflow and no billing surface, add `--no-ci`.

4. **Apply.** Drop `--preview`:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wiki_init.py" --yes
   ```

   `--yes` skips the script's own prompt (use it once you've confirmed the plan); omit it to keep the interactive guard. The workflow's `lint-wiki` job runs the gate on every push and PR; its `update-wiki` job (`needs: lint-wiki`) publishes to the GitHub Wiki only on the default branch — so a structurally-broken wiki never publishes.

5. **Tailor with flags.** `--sections a,b,c` selects the folder set (default: the seven-section frame; `architecture`/`operational` still gate on their conditions even if listed); `--name <project>` sets the `Home`/`_Sidebar` titles (defaults to the repo dir name); `--visibility public|private|internal` overrides auto-detection when `gh` can't see the repo (and decides whether `operational/` renders).

6. **Re-sync the gate after a plugin upgrade.** CI runs a **vendored** copy of `check-wiki.py` (GitHub Actions has no `${CLAUDE_PLUGIN_ROOT}` to reference the plugin's). After upgrading the plugin, refresh that copy:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wiki_init.py" --resync-gate
   ```

   It re-vendors `.github/scripts/check-wiki.py` and exits. (The agent path needs no re-sync — it references the plugin directly.)

## Related

- [Wiki-Maintenance plugin](Wiki-Maintenance) — the plugin that bundles `wiki-init`, the gate, and the watcher.
- [Maintain a wiki — wiki-watcher](Run-The-Wiki-Watcher) — keep the provisioned wiki in sync after scaffolding.
- [Provisioning design](wiki-maintenance-provisioning) — why provisioning joins authoring, and the gate-distribution split (reference for the agent, vendor for CI).
- [Declare a project's Architecture](Declare-Architecture) — write the `wiki/architecture.yml` that grows the scaffolded `architecture/` section.
- [ADR 0020 — seven-section wiki taxonomy](wiki-section-taxonomy) — why the frame is fixed at seven, and the two conditional-section gates.
- [Install crickets plugins](Install-Into-Project) — get `wiki-maintenance` onto your host.
