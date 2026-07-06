#!/usr/bin/env python3
"""Streaming Claude Code transcript-JSONL cost analyzer.

Entry points for consumers (Part C, Part G, /token-audit command):
  analyze_session(path)  -> SessionReport
  cache_split(messages)  -> CacheSplitResult

All numbers are deterministic — computed from message.usage fields + the
pinned pricing table in pricing.py. No LLM calls.

Schema (Claude Code 1.x JSONL, verified 2026-06-14):
  type=assistant lines carry message.usage with:
    input_tokens, cache_creation_input_tokens,
    cache_read_input_tokens, output_tokens
  type=user lines carry message.content (list of {type, text} items or a string)
    — scanned for phase-command markers (/plan, /work, /review, /release, /bugfix)
    when track_phases=True.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

# Import pricing from the same scripts/ directory whether running from src/ or
# from the installed dist/ plugin dir (both land the scripts/ folder alongside).
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from pricing import PRICING, cost_usd  # noqa: E402

_WINDOW = timedelta(hours=5)
_PHASE_CMDS = {"/plan", "/work", "/review", "/release", "/bugfix"}
_PHASE_NAMES = {cmd.lstrip("/") for cmd in _PHASE_CMDS}
# Live Claude Code transcripts encode a slash-command invocation as XML, e.g.
# "<command-message>work</command-message>\n<command-name>/work</command-name>
# \n<command-args>...</command-args>" — the raw '/work' text a human typed
# never appears at the start of the message. Search for the <command-name>
# marker first; keep the raw '/cmd' prefix as a fallback for non-Claude-Code
# hosts that don't wrap slash commands in this XML.
_COMMAND_NAME_RE = re.compile(
    r"<command-name>/(" + "|".join(re.escape(n) for n in _PHASE_NAMES) + r")</command-name>"
)


@dataclass
class MessageRecord:
    timestamp: str
    model: str
    input_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    output_tokens: int
    cost_usd: float
    is_floor: bool   # True when cache_read==0 and cache_write==0 (always-load surface)
    phase: str = "unknown"


@dataclass
class CacheSplitResult:
    fresh_input_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    output_tokens: int
    pct_served_from_cache: float


@dataclass
class WindowSummary:
    start_ts: str
    message_count: int
    total_cost_usd: float


@dataclass
class SessionReport:
    messages: list[MessageRecord]
    total_cost_usd: float
    cache_split: CacheSplitResult
    windows: list[WindowSummary]
    floor_cost_usd: float


def _parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _user_text(rec: dict) -> str:
    """Extract the first text string from a user message record."""
    msg = rec.get("message", {})
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text", "")
    return ""


def iter_messages(path: Path | str, *, track_phases: bool = False) -> Iterator[MessageRecord]:
    """Stream MessageRecord objects from a Claude Code JSONL transcript.

    Reads line-by-line (never slurps) — safe for large files.
    When track_phases=True, user lines are scanned for /plan|/work|/review|
    /release|/bugfix and the current phase is attached to subsequent assistant
    messages.
    """
    path = Path(path)
    current_phase = "unknown"
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rtype = rec.get("type")
            if track_phases and rtype == "user":
                text = _user_text(rec)
                m = _COMMAND_NAME_RE.search(text)
                if m:
                    current_phase = m.group(1)
                else:
                    stripped = text.lstrip()
                    for cmd in _PHASE_CMDS:
                        if stripped.startswith(cmd):
                            current_phase = cmd.lstrip("/")
                            break
                continue
            if rtype != "assistant":
                continue
            msg = rec.get("message", {})
            usage = msg.get("usage")
            if not usage:
                continue
            model = msg.get("model", "unknown")
            ts = rec.get("timestamp", "")
            it = int(usage.get("input_tokens", 0))
            cw = int(usage.get("cache_creation_input_tokens", 0))
            cr = int(usage.get("cache_read_input_tokens", 0))
            ot = int(usage.get("output_tokens", 0))
            c = cost_usd(usage, model)
            yield MessageRecord(
                timestamp=ts,
                model=model,
                input_tokens=it,
                cache_write_tokens=cw,
                cache_read_tokens=cr,
                output_tokens=ot,
                cost_usd=c,
                is_floor=(cr == 0 and cw == 0),
                phase=current_phase,
            )


def cache_split(messages: list[MessageRecord]) -> CacheSplitResult:
    """Compute the cache-read / cache-write / fresh-input split.

    pct_served_from_cache = cache_read / (fresh + write + read) × 100.
    The denominator is total prompt tokens excluding output.
    """
    fi = sum(m.input_tokens for m in messages)
    cw = sum(m.cache_write_tokens for m in messages)
    cr = sum(m.cache_read_tokens for m in messages)
    ot = sum(m.output_tokens for m in messages)
    total_input = fi + cw + cr
    pct = (cr / total_input * 100) if total_input > 0 else 0.0
    return CacheSplitResult(
        fresh_input_tokens=fi,
        cache_write_tokens=cw,
        cache_read_tokens=cr,
        output_tokens=ot,
        pct_served_from_cache=pct,
    )


def _compute_windows(messages: list[MessageRecord]) -> list[WindowSummary]:
    """Group messages into 5-hour windows.

    A new window starts when a message's timestamp is ≥ 5h after the current
    window's start. Concurrent agents running within the same 5h span fold into
    one window.
    """
    if not messages:
        return []
    windows: list[WindowSummary] = []
    win_start_ts = messages[0].timestamp
    win_start_dt = _parse_ts(win_start_ts)
    win_cost = 0.0
    win_count = 0
    for msg in messages:
        dt = _parse_ts(msg.timestamp)
        if win_start_dt is not None and dt is not None and dt - win_start_dt >= _WINDOW:
            windows.append(WindowSummary(win_start_ts, win_count, win_cost))
            win_start_ts = msg.timestamp
            win_start_dt = dt
            win_cost = 0.0
            win_count = 0
        win_cost += msg.cost_usd
        win_count += 1
    if win_count:
        windows.append(WindowSummary(win_start_ts, win_count, win_cost))
    return windows


def phase_breakdown(messages: list[MessageRecord]) -> dict[str, tuple[int, float]]:
    """Return {phase: (message_count, total_cost_usd)} for messages with phase attribution."""
    result: dict[str, tuple[int, float]] = {}
    for m in messages:
        cnt, cost = result.get(m.phase, (0, 0.0))
        result[m.phase] = (cnt + 1, cost + m.cost_usd)
    return result


def analyze_session(path: str | Path, *, track_phases: bool = False) -> SessionReport:
    """Analyze a single Claude Code session JSONL transcript.

    Returns a SessionReport with per-message records, total cost, cache split,
    5h window sums, and floor cost (always-load surface).
    """
    messages = list(iter_messages(path, track_phases=track_phases))
    total = sum(m.cost_usd for m in messages)
    split = cache_split(messages)
    windows = _compute_windows(messages)
    floor = sum(m.cost_usd for m in messages if m.is_floor)
    return SessionReport(
        messages=messages,
        total_cost_usd=total,
        cache_split=split,
        windows=windows,
        floor_cost_usd=floor,
    )


def _print_report(report: SessionReport, *, path: str, by_phase: bool) -> None:
    """Print a human-readable cost report to stdout."""
    sp = report.cache_split
    total_input = sp.fresh_input_tokens + sp.cache_write_tokens + sp.cache_read_tokens
    floor_pct = (report.floor_cost_usd / report.total_cost_usd * 100) if report.total_cost_usd else 0.0
    floor_msgs = [m for m in report.messages if m.is_floor]

    print(f"── Token Audit {'─' * 34}")
    print(f"Session:  {path}")
    print(f"Total:    ${report.total_cost_usd:.6f}")
    print(f"Cached:   {sp.pct_served_from_cache:.1f}% served from cache")
    print("─" * 50)

    print("\nCache split (prompt tokens)")
    print(f"  Fresh input:   {sp.fresh_input_tokens:>8,} tokens  ({sp.fresh_input_tokens / total_input * 100:.1f}%)" if total_input else "  Fresh input:        0 tokens")
    print(f"  Cache write:   {sp.cache_write_tokens:>8,} tokens  ({sp.cache_write_tokens / total_input * 100:.1f}%)" if total_input else "  Cache write:        0 tokens")
    print(f"  Cache read:    {sp.cache_read_tokens:>8,} tokens  ({sp.pct_served_from_cache:.1f}%)" if total_input else "  Cache read:         0 tokens")
    print(f"  Output:        {sp.output_tokens:>8,} tokens")

    print("\nPer-message cost")
    header = f"{'#':>3} │ {'Timestamp':<21} │ {'Model':<20} │ {'Cost':>10} │ {'In':>7} │ {'CW':>7} │ {'CR':>7} │ {'Out':>6}"
    print(header)
    print("─" * len(header))
    for i, m in enumerate(report.messages, 1):
        ts = m.timestamp[:23] if len(m.timestamp) > 23 else m.timestamp
        print(
            f"{i:>3} │ {ts:<21} │ {m.model:<20} │ ${m.cost_usd:.6f} │"
            f" {m.input_tokens:>7,} │ {m.cache_write_tokens:>7,} │ {m.cache_read_tokens:>7,} │ {m.output_tokens:>6,}"
        )

    print("\n5h windows")
    for i, w in enumerate(report.windows, 1):
        msg_label = "message" if w.message_count == 1 else "messages"
        print(f"  Window {i}  started {w.start_ts}  {w.message_count} {msg_label}  ${w.total_cost_usd:.6f}")

    print("\nFloor (always-load surface — zero cache hits)")
    print(f"  {len(floor_msgs)} message{'s' if len(floor_msgs) != 1 else ''}   ${report.floor_cost_usd:.6f}   ({floor_pct:.1f}% of total)")

    if by_phase:
        pb = phase_breakdown(report.messages)
        print("\nBy phase")
        for ph, (cnt, cost) in sorted(pb.items()):
            msg_label = "message" if cnt == 1 else "messages"
            print(f"  {ph:<12} {cnt} {msg_label}   ${cost:.6f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze a Claude Code session JSONL transcript.")
    parser.add_argument("path", help="Path to the session JSONL file")
    parser.add_argument("--by-phase", action="store_true", help="Group cost by /plan|/work|/review phase")
    args = parser.parse_args()

    report = analyze_session(args.path, track_phases=args.by_phase)
    _print_report(report, path=args.path, by_phase=args.by_phase)
