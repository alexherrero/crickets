# How to wire a plugin's status line into Claude Code

> [!NOTE]
> **Goal:** Point Claude Code's status line at the `tokens` plugin's script — a one-time, one-line settings change every status-line plugin needs, since only one command can own the status line at a time.
> **Prereqs:** `tokens` installed ([Install crickets plugins](Install-Into-Project)) — the cost and floor-share badges ship in the same plugin, no separate install needed.

Claude Code's status line is a single, exclusive slot: `.claude/settings.json` names exactly one command to run after every response, and its stdout becomes the status bar. Because two plugins can't both own that slot automatically, installing `tokens` puts the script in place but does not — and structurally cannot — wire itself in for you. This is the one manual step.

## Steps

1. **Find the plugin's installed path.** After installing `tokens@crickets`, its script lives at `<plugin-root>/scripts/status_line_meter.py` — Claude Code resolves `${CLAUDE_PLUGIN_ROOT}` to that path for you, so you don't need to hunt for an absolute path.

2. **Add a `statusLine` entry to `.claude/settings.json`** (project-level `.claude/settings.json`, or your user-level `~/.claude/settings.json` if you want it everywhere):

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/status_line_meter.py"
     }
   }
   ```

   If you already have a `statusLine` entry from another tool, only one can be active — replace it, or wrap both commands in a shell script that prints whichever line you want.

3. **Start a new session (or restart the current one).** The status line updates after your next response.

4. **Optional: turn on the budget-readout badge.** The used-%, cost, and floor-share badges work with no further setup. To also see a rolling 5-hour/weekly spend readout against a ceiling, set `CRICKETS_BUDGET_5H` and/or `CRICKETS_BUDGET_WEEKLY` (USD) in your shell environment before starting Claude Code. See [Status Line Meter](Status-Line-Meter#configuration) for the full badge/config breakdown.

## Verifying it worked

Send one message. The status bar should show `▌NN%` (context window used) at minimum. Once the transcript has at least one assistant response with usage data, you'll also see `⌊NN%⌋` (floor-share) and `$N.NN` (session cost).

If nothing appears: check `python3 <path-to>/status_line_meter.py <<< '{}'` runs without error from a shell, and that `.claude/settings.json` is valid JSON (a malformed `statusLine` block is silently ignored by some hosts rather than erroring).

## See also

- [Status Line Meter](Status-Line-Meter) — what each badge means and how it degrades.
- [Token-Audit](Token-Audit) — the pricing source the cost badges reuse.
