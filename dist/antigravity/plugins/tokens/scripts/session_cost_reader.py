#!/usr/bin/env python3
"""Read real `session-cost` telemetry events back from the device-local
event log (PLAN-observability-ledger task 3) -- the read-side counterpart to
session_cost_writer.py's write path.

fanout_cost_gate.estimate_per_agent_cost() accepts an `observed_records`
param shaped `[{"model": ..., "cost_usd": ...}, ...]`; before real data
accumulates, every call falls back to `pricing.cost_usd` over
DEFAULT_AGENT_USAGE_PROFILE (a documented placeholder, never a measured
average). `load_observed_records()` closes that gap: it reads every
`events-*.jsonl` file under the telemetry directory and filters to
`event == "session-cost"` lines.

**Retargeted off the vault (PLAN-observability-ledger task 1 already moved
the write side; this task moves the read side to match).** Used to glob
`kind: session-cost` markdown under the vault and regex-parse `model:` /
`cost_usd:` lines back out; now reads the same JSONL event log
`session_cost_writer.py` appends to.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, m)
    spec.loader.exec_module(m)
    return m


event_log = _load_sibling("event_log")


def load_observed_records(*, telemetry_root: "str | Path | None" = None) -> list[dict]:
    """Return `[{"model": ..., "cost_usd": ...}, ...]` for every
    `session-cost` event found across all `events-*.jsonl` files under the
    telemetry directory (`telemetry_root`, or `event_log.telemetry_dir()` --
    itself `$AGENTM_TELEMETRY_DIR`-overridable -- when omitted).

    Graceful-empty on any absent/unreadable path, malformed line, or missing
    field -- never raises. An empty return means "no observed data yet",
    which callers (fanout_cost_gate.py) already treat as "fall back to the
    pricing-profile estimate".
    """
    root = Path(telemetry_root) if telemetry_root is not None else event_log.telemetry_dir()
    if not root.is_dir():
        return []

    records: list[dict] = []
    for path in sorted(root.glob("events-*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict) or rec.get("event") != "session-cost":
                continue
            model = rec.get("model")
            cost = rec.get("cost_usd")
            if model is None or not isinstance(cost, (int, float)):
                continue
            records.append({"model": model, "cost_usd": float(cost)})
    return records
