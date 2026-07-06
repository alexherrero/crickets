#!/usr/bin/env python3
"""Session-start tier + advisor nudge (PLAN-efficiency-dispatch task 7).

Compares the live session's model against the active plan's next unchecked
task's staged tier hint (task 6) and reports a mismatch — advisory only,
**never** switches the session's model. Also renders the advisor-
availability line (task 3) when an `advisorModel` is configured. No
mismatch and no advisor configured -> "" (silent, not an error string).
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_advisor_rider():
    spec = importlib.util.spec_from_file_location("advisor_rider", _HERE / "advisor_rider.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("advisor_rider", m)
    spec.loader.exec_module(m)
    return m


advisor_rider = _load_advisor_rider()

# The inverse of classify_work_type.render_tier_hint()'s rendering — pulls
# the model_id (the 2nd " · "-separated field) back out of a task's
# "**Tier hint:** <tier> · <model_id> · <effort> (tier-source: ...)" line.
_TIER_HINT_LINE_RE = re.compile(
    r"\*\*Tier hint[^:]*:\*\*\s*([^·\n]+)·\s*([^·\n]+)·",
)
_TASK_STATUS_RE = re.compile(r"\*\*Status:\*\*\s*\[( |x)\]")


def next_unchecked_task_tier_hint_model(plan_text: str) -> str | None:
    """The first unchecked task's Tier-hint model_id, or None (no hint set,
    or no unchecked task — the common case, since most tasks leave the
    optional Work-type/Tier-hint fields unset per task 6)."""
    # Split into per-task blocks on "### " headings (the plan.md template's
    # task-heading shape); scan in document order for the first block whose
    # Status is unchecked, and read its own Tier-hint line if present.
    blocks = re.split(r"(?=^###\s)", plan_text, flags=re.MULTILINE)
    for block in blocks:
        status_match = _TASK_STATUS_RE.search(block)
        if not status_match:
            continue
        if status_match.group(1) != " ":
            continue  # already checked off — not the next task
        hint_match = _TIER_HINT_LINE_RE.search(block)
        if hint_match:
            return hint_match.group(2).strip()
        return None  # this IS the next task; it just has no hint set
    return None


def session_start_nudge(
    live_model: str | None,
    plan_tier_hint_model: str | None,
    advisor_model: str | None = None,
) -> str:
    """Render the session-start nudge. Never mutates anything — pure text."""
    parts: list[str] = []

    if plan_tier_hint_model and live_model and plan_tier_hint_model != live_model:
        parts.append(
            f"NOTE: this session is running {live_model!r}, but the active "
            f"plan's next task is tier-hinted for {plan_tier_hint_model!r}. "
            f"Advisory only — never auto-switches; use /model if you want to match it."
        )

    advisor_line = advisor_rider.advisor_availability_line(advisor_model)
    if advisor_line:
        parts.append(advisor_line)

    return "\n".join(parts)
