# How to see every active plan at a glance

> [!NOTE]
> **Goal:** List every active plan in the harness state dir — each plan's name, its `Status:` line, and the most-recent entry of its `progress*.md` — in one read-only dashboard, so a coordinator can see the queue before deciding what to `/work` next.
> **Prereqs:** the `developer-workflows` plugin installed ([Install crickets plugins](Install-Into-Project)); at least one plan in the harness dir (the singleton `PLAN.md`, or named `PLAN-<slug>.md` pairs — see [Named plans](Named-Plans)).

Use `/queue-status-lite` when several plans are in flight at once and you want a single view of all of them. It is the **read side** of the multi-plan surface: the `--name` writers ([Run a named plan](Run-A-Named-Plan)) drive one plan; this glance shows them all. It only reads: it shows you the queue and leaves every decision — what to work, review, or merge — to you.

## Steps

1. **Run the glance.** Invoke `/queue-status-lite`. With no argument it resolves the harness dir from the current working directory (the vault-backed `_harness/`, or `<repo>/.harness/` when standalone). To point it at a specific directory, pass `--harness-dir <path>`:

   ```
   /queue-status-lite
   /queue-status-lite --harness-dir /path/to/_harness
   ```

2. **Read the dashboard.** One entry per active plan — its name, its `Status:` line, and the last line of the matching `progress*.md`. The command lists `PLAN.md` plus every `PLAN-<slug>.md`; archives (`PLAN.archive.*.md`) and GDrive conflict copies are skipped. The output is the bridge's verbatim render — the same shape whether an agentm clone is present or not (see [Named plans § Reading the queue](Named-Plans#reading-the-queue--queue-status-lite)).

3. **Decide, then act.** The glance stops at showing. Choose the next move yourself — `/work --name <slug>` to work a plan, `/review --name <slug>` to review one, or nothing at all.

## Verify

- Running `/queue-status-lite` prints one block, one entry per active plan, and exits `0`.
- With **no** harness dir to read, it prints a clean notice and still exits `0` — a status read is never an error.
- No file changes: the working tree is identical before and after (`git status` shows nothing new) — the command mutates no state.

## Troubleshooting

- **No agentm clone installed.** Expected and fine — the command renders a minimal local `.harness/` dashboard mirroring the agentm reader's format. The glance degrades gracefully rather than vanishing; this is the standalone behavior working as designed.
- **A plan is missing from the list.** Confirm its file is named `PLAN.md` or `PLAN-<slug>.md` directly in the harness dir. Archived (`PLAN.archive.*.md`) and conflict-copy files are intentionally skipped.

## Related

- [Named plans](Named-Plans) — the lookup: the command's arguments, the two backends, and the read bridge's contract.
- [Run a named plan](Run-A-Named-Plan) — the write-side recipe: driving `/work --name <slug>` and friends against one named plan.
- [Developer Workflows](Developer-Workflows) — the phase-loop plugin this command belongs to.
- [Why phase-gating](Why-Phase-Gating) — why state lives on disk and one harness dir can hold several plans.
