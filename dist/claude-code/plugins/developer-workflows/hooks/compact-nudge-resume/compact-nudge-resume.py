#!/usr/bin/env python3
"""compact-nudge-resume — UserPromptSubmit hook.

When the session context is large (≥ 60 % via CLAUDE_CONTEXT_USAGE_PERCENTAGE
or > 400 assistant turns in the session JSONL), nudge the operator toward
/clear rather than /compact. Silent no-op below the threshold or when the
session appears brand-new (zero prior assistant turns).

Output: JSON {"additionalContext": "..."} on stdout when nudge fires; nothing
on stdout otherwise. Always exits 0 — must never block the user prompt.

Test override: set COMPACT_NUDGE_JSONL_PATH to bypass JSONL path derivation.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

THRESHOLD_PCT = 60.0    # context-usage % that triggers the nudge
THRESHOLD_LINES = 400   # assistant-turn count proxy when % is unavailable


def _count_assistant_lines(path: Path) -> int:
    """Count lines with type=assistant in the session JSONL."""
    count = 0
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    if json.loads(line).get("type") == "assistant":
                        count += 1
                except Exception:
                    pass
    except Exception:
        pass
    return count


def main() -> None:
    # ── Parse event JSON from stdin ─────────────────────────────────────────────
    payload: dict = {}
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        pass

    # ── Context usage — path A: env var or event field ──────────────────────────
    context_pct: float | None = None
    raw = os.environ.get("CLAUDE_CONTEXT_USAGE_PERCENTAGE", "")
    if raw:
        try:
            context_pct = float(raw)
        except ValueError:
            pass
    if context_pct is None:
        for key in ("context_usage_percentage", "contextUsagePercentage"):
            if key in payload:
                try:
                    context_pct = float(payload[key])
                    break
                except (TypeError, ValueError):
                    pass

    # ── Locate session JSONL ─────────────────────────────────────────────────────
    jsonl_path: Path | None = None
    override = os.environ.get("COMPACT_NUDGE_JSONL_PATH", "")
    if override:
        jsonl_path = Path(override)
    else:
        session_id = os.environ.get("CLAUDE_SESSION_ID", "")
        cwd = payload.get("cwd", "") or os.getcwd()
        if session_id and cwd:
            slug = Path(cwd).as_posix().replace("/", "-").lstrip("-")
            jsonl_path = Path.home() / ".claude" / "projects" / slug / f"{session_id}.jsonl"

    # ── Resumed-session gate — must have at least one prior assistant turn ───────
    assistant_count = _count_assistant_lines(jsonl_path) if jsonl_path else 0
    appears_resumed = assistant_count > 0

    # No signal of any kind AND no JSONL history → silent (fresh session)
    if not appears_resumed and context_pct is None:
        sys.exit(0)

    # ── Decide whether to nudge ─────────────────────────────────────────────────
    if context_pct is not None:
        triggered = context_pct >= THRESHOLD_PCT
    else:
        triggered = assistant_count > THRESHOLD_LINES

    if not triggered:
        sys.exit(0)

    # ── Build and emit nudge ─────────────────────────────────────────────────────
    cost_line = ""
    try:
        import pricing  # Part B cost helper — soft dependency
        cost_line = f"  Estimated session cost so far: ~${pricing.cost_usd():.2f}\n"
    except Exception:
        pass

    nudge = (
        "Session context is large — consider one of:\n"
        "  /clear — starts a fresh context; PLAN.md / progress.md are on disk, "
        "so no work is lost. Zero re-billing cost; KV cache stays intact for the "
        "new session.\n"
        "  /compact — rewrites context in-place; breaks the KV cache and re-bills "
        "the compacted summary on every subsequent turn.\n"
        f"{cost_line}"
        "State is on disk. /clear is almost always the right choice."
    )
    print(json.dumps({"additionalContext": nudge}))
    sys.exit(0)


if __name__ == "__main__":
    main()
