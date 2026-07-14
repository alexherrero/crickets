# How to sync a vault project to its GitHub Project board

> [!NOTE]
> **Goal:** Render the current vault project state for a configured project and push it one-way to its GitHub Project board — idempotently, with a dry-run preview first.
> **Prereqs:** the `github-projects` plugin installed (`requires: development-lifecycle`); a `project.json` (in the project's vault `_harness/`) wiring the vault project to its Project — at minimum `vault_project` + `github.{owner,number}`; the `gh` CLI authenticated.

## Steps

1. Confirm the `project.json` resolves. The loader needs `vault_project` + `github.owner` + `github.number`; `github.url` is derived from owner+number when omitted, and `items_source` defaults to the sibling `board-items.json`.

2. Preview the render with the dry-run boundary — no write hits GitHub. Omit `--type` for a full template-driven re-render of one item:

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/project_sync.py" post \
     --config <vault>/_harness/project.json --id <item-id> --dry-run
   ```

3. Push the one-way update via the single live write path — idempotent create-or-update by stable id, so re-running converges. For a progress stage use the `--type` shortcut; for a kickoff or closeout omit it (those re-render in full from `board-items.json`):

   ```bash
   # full re-render of one item
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/project_sync.py" post \
     --config <vault>/_harness/project.json --id <item-id>

   # task progress stage shortcut
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/project_sync.py" post \
     --config <vault>/_harness/project.json --type task-progress \
     --id <task-id> --commit <SHA> --summary "<one human sentence>"
   ```

4. Confirm the board matches the vault — run the drift gate (next section). Exit `0` = in sync, `1` = drift, `2` = operational error.

## Backfill both boards (operator-gated)

The inaugural backfill brings both boards (agentm Project #2, crickets Project #5) up to current state in one pass. It is the **one bulk write** and is **operator-gated** — it runs only on explicit approval, never automatically.

Author the project's full state into `board-items.json`, in the vault `_harness/` — this is the renderer's source of truth; never create items with raw `gh project item-create`, which the drift gate flags as an orphan. Run the post with `--dry-run` first and inspect the render. Only on explicit operator approval, drop `--dry-run` to push. A re-fetch should report every item a `noop`. Both boards were backfilled this way: crickets #5 (18 open issues) and agentm #2 (16 items).

> [!WARNING]
> The backfill writes to live GitHub Projects. Always run the `--dry-run` render first and inspect it before approving the bulk push.

## Verify

The drift gate is the verification surface: it asserts `vault == board` and is wired into `scripts/check-all.sh`.

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/check_project_sync.py"
# graceful-skip when no project.json or no gh; otherwise asserts vault == board
```

It checks four drift kinds: `create`, `missing`, `update`, and `orphan`. `tests-linux.yml` also runs it in CI.

> [!NOTE]
> With no `project.json` or no `gh` the gate **graceful-skips** — it is never an error to run the check on a repo that has no board wired.

## Troubleshooting

- **The gate reports drift after a sync**: the board diverged from the vault. Re-run the `post` path — it is idempotent (create-or-update by stable id), so re-running converges. An `orphan` finding means a board issue is backed by no vault item — add it to `board-items.json` (or remove the stray issue).
- **A link in the rendered board looks hand-typed / wrong**: links are built from `github.url`, never hand-typed — a wrong link points at a bad `github.url` (or a wrong `owner`/`number` it derives from) in `project.json`.
- **A phase command didn't emit a board update**: emission is gated on the `board-sync` capability being available — `/plan`, `/work`, `/release` check `agentm_bridge.py capability board-sync` and graceful-skip when it returns non-zero. Confirm the `github-projects` plugin is installed, agentm is present (the capability resolver), and `project.json` + `gh` are present.

## See also

- [GitHub Projects plugin](GitHub-Projects) — the reference for the config schema, Type taxonomy, templates, field schema, and the write path.
- [One-way vault-to-board synthesis](One-Way-Vault-To-Board-Synthesis) — why this is one-way and deterministic.
- [Development Lifecycle](Development-Lifecycle) — the base plugin whose phase commands emit board updates.
- [CI gates](CI-Gates) — the gate battery the drift gate joins.
