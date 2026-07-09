#!/usr/bin/env python3
"""Device-local telemetry event log — the observability ledger's write path
(PLAN-observability-ledger task 1, `wiki/designs/agentm-autonomy.md` Design
section).

Append-only JSONL, rotated monthly, outside both the repo and the vault. An
append can never block a session or raise; if a write fails, the caller
carries on and the line is simply missing — the same graceful contract
`session_cost_writer.py`'s (now-retired) vault write already held.

Event shape (one JSON line per event):
  {ts, schema_version, device, session_id, parent_id, event, model,
   tokens_by_kind, cost_usd, tags: {plan, task, arc, grade}}

`device` and `schema_version` ship from day one even though multi-machine
support isn't live yet — the aggregator merges logs by device id once a
second machine joins, and a cheap field now saves a migration later.
"""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

_DEFAULT_TOKENS_BY_KIND = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}


def telemetry_dir() -> Path:
    """`$AGENTM_TELEMETRY_DIR` override, else `~/.agentm/telemetry/`."""
    env = os.environ.get("AGENTM_TELEMETRY_DIR", "").strip()
    return Path(env) if env else Path.home() / ".agentm" / "telemetry"


def device_id() -> str:
    """Best-effort stable device identifier. Never raises."""
    try:
        return socket.gethostname() or "unknown-device"
    except OSError:
        return "unknown-device"


def _log_path(*, telemetry_root: "Path | None" = None, when: "datetime | None" = None) -> Path:
    root = telemetry_root if telemetry_root is not None else telemetry_dir()
    ts = when or datetime.now(timezone.utc)
    return Path(root) / f"events-{ts.strftime('%Y%m')}.jsonl"


def build_event(
    event: str,
    *,
    session_id: str = "",
    parent_id: "str | None" = None,
    model: "str | None" = None,
    tokens_by_kind: "dict | None" = None,
    cost_usd: float = 0.0,
    tags: "dict | None" = None,
    device: "str | None" = None,
    ts: "str | None" = None,
) -> dict:
    """Build one event record matching the ledger schema. Pure — no I/O."""
    return {
        "ts": ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": SCHEMA_VERSION,
        "device": device if device is not None else device_id(),
        "session_id": session_id,
        "parent_id": parent_id,
        "event": event,
        "model": model,
        "tokens_by_kind": dict(tokens_by_kind) if tokens_by_kind else dict(_DEFAULT_TOKENS_BY_KIND),
        "cost_usd": cost_usd,
        "tags": dict(tags) if tags else {"plan": None, "task": None, "arc": None, "grade": None},
    }


def append_event(record: dict, *, telemetry_root: "Path | None" = None) -> bool:
    """Append one JSON line to the current month's event log. Never raises.

    Returns True on a successful append, False on any graceful-skip
    condition (unwritable path, unserializable record, unexpected error).
    """
    try:
        path = _log_path(telemetry_root=telemetry_root)
        line = json.dumps(record, sort_keys=True)
    except (TypeError, ValueError):
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        return False
    return True


def _read_marker(name: str, root: "Path | None" = None) -> "str | None":
    """The worktree-local `.harness/<name>` bare value, or None if
    missing/blank. Mirrors `development-lifecycle`'s own
    `doctor_worktrees._read_marker()` inline — tokens must not depend on a
    sibling capability to resolve its own attribution (same one-way-bridge
    convention `session_cost_writer.py` already follows for `save.py`)."""
    base = Path(root) if root is not None else Path.cwd()
    marker = base / ".harness" / name
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text or None


def _read_active_plan_marker(root: "Path | None" = None) -> "str | None":
    return _read_marker("active-plan", root=root)


def _read_active_task_marker(root: "Path | None" = None) -> "str | None":
    """The worktree-local `.harness/active-task` bare value, written by the
    control-plane dispatch (`PLAN-observability-residue-trio` task 1)
    alongside `active-plan`. `None` when the caller isn't a dispatched
    session (e.g. an interactive Stop-hook capture with no task context)."""
    return _read_marker("active-task", root=root)


def resolve_attribution_tags(*, root: "Path | None" = None, grade: "str | None" = None) -> dict:
    """Best-effort `{plan, task, arc, grade}` tags for a telemetry event.

    `plan` and `task` come from their respective worktree-local markers.
    `arc` has no marker or dispatch-side source today — the dispatch
    substrate's `WorkItem` carries no arc concept (`PLAN-observability-
    residue-trio`'s own locked design call) — and stays `None` until a
    future plan introduces one. Never raises — a missing/blank marker just
    means an untagged event, not a crash.
    """
    return {
        "plan": _read_active_plan_marker(root=root),
        "task": _read_active_task_marker(root=root),
        "arc": None,
        "grade": grade,
    }
