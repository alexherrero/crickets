<!-- mode: explanation -->
# Token Audit

## Architecture

Token Audit tells you what a Claude Code session actually cost, and where the money went. It reads the session's own record of work and prices it out for you — the total, how much was served cheaply from cache versus billed fresh, and the fixed cost every turn carries before you type a word. The numbers are trustworthy because they come from a fixed price list, not a guess: no model is asked to estimate its own spend. If you are trying to stretch a plan and stay coding all day, this is how you see where your budget is going. It stands alone and needs nothing else, and Status-Line-Meter can build on it to put a live cost badge in front of you as you work.

### Diagram

How a session's record becomes a cost breakdown — read each turn, split cache-read vs cache-write vs fresh tokens, price every slice from the pinned table, then roll it up into windows and a floor:

![Token Audit's metering flow: the operator runs the audit, which reads the session transcript turn by turn, splits each message into cache-read, cache-write, and fresh tokens, prices every slice from a pinned rate table, and rolls the result up into a cost breakdown of total, cache split, five-hour windows, floor, and per-message curve](diagrams/token-audit-metering.svg)

How it composes — Token Audit stands alone on the AgentM substrate, with Status-Line-Meter building on it for live metering:

![How token-audit composes: it stands alone requiring nothing, rests one-way on the AgentM substrate of memory, opinions, and personas, and is enhanced (soft, optional) by status-line-meter, which reuses its pricing table for a live status-line badge](diagrams/token-audit-composition.svg)

### How it works

You run it, and it finds the current session's record of work and reads it turn by turn. For each turn it separates the tokens into three buckets — the ones served cheaply from cache, the ones written into cache, and the fresh input billed at full rate — so you can see how much of the session was re-used rather than re-paid. It then prices every slice from a single fixed rate table, adds it all up, and shows the breakdown: the total, the share that came from cache, and the always-load floor that each turn carries before you type anything.

Because a plan's limits reset on a rolling clock, it also groups the cost into five-hour windows so the sums line up with how you actually get billed, and it can attribute cost to each phase of your workflow when you ask it to. Every figure traces back to a real usage number and a pinned price — nothing is inferred by a model.

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