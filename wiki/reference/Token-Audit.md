<!-- mode: reference -->
# Token Audit

## Architecture

Token Audit tells you what a Claude Code session actually cost. It reads the session transcript and prices every message from a pinned rate table, so the numbers are deterministic — no model is asked to estimate its own spend. It is the measurement half of the `efficient` opinion: the opinion sets the budget, and this plugin supplies the cost truth that budget is weighed against.

### Diagram

_None / not needed._

### How it works

Run `/token-audit` and it resolves the current session's JSONL transcript, then hands it to `analyzer.py`. The analyzer streams the file, reads the `message.usage` fields on each turn, and splits every message into cache-read, cache-write, and fresh-input tokens — so you can see what share of the session was served from cache rather than re-billed. It rolls costs up into 5-hour windows to match Claude's rolling-limit math, breaks out the always-load floor (the fixed cost every turn carries before you type anything), and prices each slice from `pricing.py`, the one place a per-model rate lives. Pass `--by-phase` and it attributes cost to the `/plan`, `/work`, `/review`, `/release`, and `/bugfix` markers it finds in the transcript. Every figure traces back to a usage field and a pinned price; nothing is inferred by an LLM.

### Composition

| Direction | Plugin | How |
|---|---|---|
| Enhances (soft) | — | None. |
| Enhanced by (soft) | [Status-Line-Meter](Status-Line-Meter) | Adds a live status-line meter — used-%, 5h-window cost, and floor-share badge — that reuses this plugin's `pricing.py` at runtime and degrades gracefully when it is absent. |
| Requires (hard) | — | None. Token Audit is fully standalone. |
| Required by (hard) | — | None. |

### Why not

Token Audit is deliberately narrow, and it will not fit every need. Reach for something else if:

- You want billing across your whole account or team, not one session — this reads a single Claude Code transcript, not your Anthropic invoice.
- You need continuous, live cost feedback while you work rather than an after-the-fact breakdown — install [Status-Line-Meter](Status-Line-Meter) for that.
- You only want a rough ballpark and don't care about the cache split, the 5-hour windows, or the always-load floor — the full breakdown may be more than a quick glance needs.

## Reference

### Commands & skills

Each primitive links to the source that implements it.

| Primitive | Kind | What it does |
|---|---|---|
| [`/token-audit`](https://github.com/alexherrero/crickets/blob/main/src/token-audit/commands/token-audit.md) | command | Prints the cost breakdown for a session transcript; `--by-phase` attributes cost per phase. |
| [`analyzer.py`](https://github.com/alexherrero/crickets/blob/main/src/token-audit/scripts/analyzer.py) | script | Streams the JSONL, computes the cache split, 5-hour windows, and the always-load floor. |
| [`pricing.py`](https://github.com/alexherrero/crickets/blob/main/src/token-audit/scripts/pricing.py) | script | The one pinned table of per-model rates — the only place a price lives. |

### Configuration

No configuration — the plugin works out of the box. It resolves the session automatically from `CLAUDE_SESSION_ID` or the most-recently modified transcript; pass `--session <id>` to target a specific one.

## See also

- [Composition design](crickets-composition) · [Token-audit design](crickets-token-audit) — the deeper design.
- [Status-Line-Meter](Status-Line-Meter) — the live-metering companion that builds on this plugin.

[Reference](Reference) · [Architecture](Architecture) · [Home](Home)