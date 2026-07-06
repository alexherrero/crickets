#!/usr/bin/env python3
"""Live context/cost meter for the Claude Code status line (#46 Part C).

Claude Code pipes a JSON payload to this script via stdin after each API
response; the script prints one line to stdout that becomes the status line.

Rendered format (each badge is independently optional):
  ▌42%  ·  ⌊18%⌋  ·  $0.14

  ▌42%    context window used-percentage (context_window.used_percentage)
  ⌊18%⌋   floor-share: always-load surface % of session cost
  $0.14   estimated session cost (transcript analysis via token-audit pricing.py)

Any missing field, null value, or exception → graceful-skip (omit the badge,
never hang, never print an error to stdout that would corrupt the status line).

Cross-plugin: runtime-discovers token-audit's pricing.py from the sibling
plugins directory. Degrades gracefully to used-% only when token-audit is absent.

Verified against Claude Code v2.1.153 status-line JSON schema (2026-06-14).
Minimum host version for used_percentage: v2.1.132.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

_FIVE_HOURS_SECONDS = 5 * 3600
_WEEK_SECONDS = 7 * 24 * 3600

# ---------------------------------------------------------------------------
# Runtime discovery of token-audit's pricing module.
# Both plugins install as sibling directories under the same plugins root:
#   <plugins>/status-line-meter/scripts/  ← __file__
#   <plugins>/token-audit/scripts/pricing.py
# Works in src/ (for tests), dist/, and at installed location.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_TA_SCRIPTS = _HERE.parent.parent / "token-audit" / "scripts"

_HAS_PRICING = False
cost_usd = None  # populated below if pricing module found

if _TA_SCRIPTS.is_dir():
    sys.path.insert(0, str(_TA_SCRIPTS))
    try:
        from pricing import cost_usd as _cu  # type: ignore
        cost_usd = _cu
        _HAS_PRICING = True
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Incremental transcript reader.
# Caches running totals in /tmp so each call reads only new bytes (O(new-lines)).
# ---------------------------------------------------------------------------

def _cache_path(session_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"crickets_slm_{session_id}.json"


def _read_usage(rec: dict) -> tuple[int, int, int, int]:
    usage = rec.get("message", {}).get("usage") or {}
    return (
        int(usage.get("input_tokens", 0)),
        int(usage.get("cache_creation_input_tokens", 0)),
        int(usage.get("cache_read_input_tokens", 0)),
        int(usage.get("output_tokens", 0)),
    )


def _get_session_stats(data: dict) -> dict | None:
    """Incrementally read the transcript and return running cost totals.

    Returns a dict with total_cost and floor_cost (both float), or None on any
    error. Caches results so repeated calls are O(new-lines-per-call).
    """
    if not _HAS_PRICING:
        return None

    transcript_path = data.get("transcript_path")
    if not transcript_path:
        return None

    tp = Path(transcript_path)
    if not tp.exists():
        return None

    session_id = data.get("session_id") or tp.stem
    cache = _cache_path(session_id)

    try:
        state: dict = {}
        last_pos = 0
        if cache.exists():
            try:
                state = json.loads(cache.read_text(encoding="utf-8"))
                if state.get("transcript_path") == transcript_path:
                    last_pos = int(state.get("last_pos", 0))
                else:
                    state = {}
                    last_pos = 0
            except (json.JSONDecodeError, ValueError):
                state = {}
                last_pos = 0

        with open(tp, "rb") as fh:
            current_size = fh.seek(0, 2)
            if current_size == last_pos:
                return state if state else None
            if current_size < last_pos:
                # File shrank — transcript was truncated or compacted; reset.
                state = {}
                last_pos = 0
            fh.seek(last_pos)
            new_bytes = fh.read(current_size - last_pos)

        total_cost: float = state.get("total_cost", 0.0)
        floor_cost: float = state.get("floor_cost", 0.0)
        fallback_model: str = (data.get("model") or {}).get("id", "")

        for raw in new_bytes.decode("utf-8", errors="replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            usage = rec.get("message", {}).get("usage")
            if not usage:
                continue
            msg_model = rec.get("message", {}).get("model") or fallback_model
            c = cost_usd(usage, msg_model)
            total_cost += c
            _, cw, cr, _ = _read_usage(rec)
            if cr == 0 and cw == 0:
                floor_cost += c

        new_state = {
            "transcript_path": transcript_path,
            "last_pos": current_size,
            "total_cost": total_cost,
            "floor_cost": floor_cost,
        }
        cache.write_text(json.dumps(new_state), encoding="utf-8")
        return new_state

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Budget readout (token-audit automation layer, PLAN-efficiency-automation task 5).
#
# Reads `session-cost` records (token-audit design's 2026-07-04 amendment) and
# renders a 5h-window sum + a weekly sum against an operator-configured
# ceiling — degrading the same way the existing cost badge does: missing
# config, missing records, or any read error all omit the readout, never an
# error string.
#
# NOTE (design divergence, honest not silent — Hook 4): task 4 (the Stop hook
# that WRITES session-cost records) was deferred pending roadmap-session
# confirmation (see progress-efficiency-automation.md), so this reader has no
# real writer yet. The JSONL-log shape below and the env-var ceiling config
# are this task's own placeholder integration, not a decision the design doc
# locked — task 4, when it lands, should either conform to this shape or this
# reader should be revisited to match whatever it actually writes.
# ---------------------------------------------------------------------------

def _default_session_cost_log_path() -> Path:
    override = os.environ.get("CRICKETS_SESSION_COST_LOG")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "crickets_session_cost.jsonl"


def _read_session_cost_records(path: Path) -> list[dict]:
    """One JSON object per line: {model, tokens_by_kind, cost_usd, timestamp}.

    Missing file, unreadable, or malformed lines -> skip/empty. Never raises.
    """
    try:
        if not path.is_file():
            return []
        records: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                records.append(rec)
        return records
    except Exception:
        return []


def _read_budget_ceiling() -> dict | None:
    """{"window_5h": float, "weekly": float} (either or both keys), or None.

    Configured via CRICKETS_BUDGET_5H / CRICKETS_BUDGET_WEEKLY env vars (USD).
    Absent, empty, or unparseable -> None (readout omitted, not an error).
    """
    raw_5h = os.environ.get("CRICKETS_BUDGET_5H")
    raw_weekly = os.environ.get("CRICKETS_BUDGET_WEEKLY")
    ceiling: dict = {}
    try:
        if raw_5h:
            ceiling["window_5h"] = float(raw_5h)
        if raw_weekly:
            ceiling["weekly"] = float(raw_weekly)
    except ValueError:
        return None
    return ceiling or None


def budget_readout(records: list[dict], ceiling: dict | None, now_epoch: float) -> str:
    """Pure: fixture records + ceiling + now -> readout string, or "" if unconfigured.

    Sums `cost_usd` for records whose `timestamp` (epoch seconds) falls
    within the trailing 5h / 7-day window from `now_epoch`. Renders only the
    ceiling keys actually configured.
    """
    if not ceiling:
        return ""

    window_sum = 0.0
    week_sum = 0.0
    for rec in records:
        ts = rec.get("timestamp")
        cost = rec.get("cost_usd")
        if ts is None or cost is None:
            continue
        try:
            age = now_epoch - float(ts)
            cost = float(cost)
        except (TypeError, ValueError):
            continue
        if age < 0:
            continue
        if age <= _FIVE_HOURS_SECONDS:
            window_sum += cost
        if age <= _WEEK_SECONDS:
            week_sum += cost

    parts: list[str] = []
    if "window_5h" in ceiling:
        parts.append(f"5h ${window_sum:.2f}/${ceiling['window_5h']:.2f}")
    if "weekly" in ceiling:
        parts.append(f"wk ${week_sum:.2f}/${ceiling['weekly']:.2f}")
    return "  ·  ".join(parts)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(data: dict) -> str:
    """Build the status-line string from a parsed stdin JSON payload."""
    parts: list[str] = []

    # Badge 1: context used-%
    cw = data.get("context_window") or {}
    used_pct = cw.get("used_percentage")
    if used_pct is not None:
        try:
            parts.append(f"▌{float(used_pct):.0f}%")
        except (TypeError, ValueError):
            pass

    # Badges 2 + 3: floor-share and cost from transcript analysis
    try:
        stats = _get_session_stats(data)
        if stats:
            total_cost: float = stats.get("total_cost", 0.0)
            floor_cost: float = stats.get("floor_cost", 0.0)

            if total_cost > 0:
                floor_pct = floor_cost / total_cost * 100
                parts.append(f"⌊{floor_pct:.0f}%⌋")
                parts.append(f"${total_cost:.2f}")
    except Exception:
        pass

    # Badge 4: budget readout (5h-window + weekly sums vs. a configured ceiling)
    try:
        ceiling = _read_budget_ceiling()
        if ceiling:
            records = _read_session_cost_records(_default_session_cost_log_path())
            readout = budget_readout(records, ceiling, time.time())
            if readout:
                parts.append(readout)
    except Exception:
        pass

    return "  ·  ".join(parts)


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    try:
        line = render(data)
    except Exception:
        line = ""

    print(line)


if __name__ == "__main__":
    main()
