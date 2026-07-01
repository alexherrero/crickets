<!-- mode: reference -->
# Status Line Meter

## Architecture

Status Line Meter keeps a small live gauge in your Claude Code status line, so you can see how much of the context window you have used and roughly what the session is costing without pausing to run a report. It reads the transcript incrementally after each response and renders a compact one-line badge, staying out of the way when a number is unavailable.

### Diagram

_None / not needed._

### How it works

After every API response, Claude Code pipes a small JSON payload to the plugin's script on stdin, and the script prints a single line back that becomes your status line. That line carries up to three independently optional badges: the context-window used-percentage (`▌42%`), a floor-share badge showing the always-load surface's share of session cost (`⌊18%⌋`), and the estimated session cost (`$0.14`). The script reads the transcript incrementally — it caches its last read offset per session in the system temp directory and only parses what is new — and it resets cleanly when the transcript is truncated, for example after `/compact`. For the cost and floor-share badges it discovers `token-audit`'s `pricing.py` from the sibling plugins directory at runtime; when `token-audit` is not installed it quietly falls back to the used-percentage alone. Any missing field, null value, or error is a graceful skip: the badge is dropped rather than allowed to hang or corrupt the status line.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | [Token-Audit](Token-Audit) | Adds live, continuous metering in the status line, reusing `token-audit`'s `pricing.py` for the cost and floor-share badges — only when both are installed. |
| Enhanced by (soft) | — | None. |
| Requires (hard) | — | None. Status Line Meter is fully standalone; without `token-audit` it renders the used-percentage alone. |
| Required by (hard) | — | None. |

### Why not

Status Line Meter is opinionated about what belongs in a status line, and it will not suit everyone. Reach for something else if:

- You prefer a quiet, empty status line, or you already run a custom status-line command you would rather not replace.
- You want a full cost breakdown — the per-message curve, the 5-hour window sums, the cache split. That is the `token-audit` skill's job; this plugin is the glanceable live version, not the report.
- Your host is not Claude Code, or it predates the status-line JSON schema the script reads, so the used-percentage field is unavailable.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`status_line_meter.py`](https://github.com/alexherrero/crickets/blob/main/src/status-line-meter/scripts/status_line_meter.py) | status-line script | Reads the per-response JSON payload and prints the used-%, floor-share, and cost badges — incrementally, with graceful-skip on any missing field. |

### Configuration

No configuration — the plugin works out of the box. It reads the status-line payload Claude Code hands it and discovers `token-audit`'s `pricing.py` at runtime; there are no environment variables or config keys to set. (`token-audit` unlocks the cost and floor-share badges; without it you still get the used-percentage.)

## See also

- [Token-Audit](Token-Audit) — the full cost-breakdown skill this plugin meters live.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)