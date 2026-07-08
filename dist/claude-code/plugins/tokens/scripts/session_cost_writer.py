#!/usr/bin/env python3
"""Session-cost capture — the Stop-hook half absorbed from the never-staged
`PLAN-session-cost-capture` micro-plan (2026-07-05 decision record, absorbed
verbatim into PLAN-wave-d-tokens-and-privacy task 1).

At session Stop: run analyzer.py over the closing session's transcript, group
its per-message records by model, and append one `session-cost` telemetry
event per model to the device-local event log (`event_log.py`) the fan-out
cost gate (fanout_cost_gate.py) can later average over via its
`observed_records` param.

**Retargeted off the vault (PLAN-observability-ledger task 1,
`wiki/designs/agentm-autonomy.md`).** The capture used to write one `kind:
session-cost` memory entry per model via agentm's `save_entry()` path; that
vault write is retired, not duplicated — this module now depends on nothing
but its own sibling `event_log.py`.

Capture-half only, per the decision record's scope: no dreaming-pass trend
analysis lives here (see dreaming_trend_stub.py for that gate, staged dark).

Graceful no-op contract (must never block a session close):
  - transcript unreadable / empty -> return [], no write, no raise
  - event-log append fails (unwritable path, etc.) -> skipped, no raise
  - any unexpected error -> caught, logged to stderr, return None

This module is pure Python (importable + independently testable); the actual
Stop hook (session-cost-capture.sh / .ps1) is a thin shell wrapper that calls
`main()` below.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, m)
    spec.loader.exec_module(m)
    return m


analyzer = _load_sibling("analyzer")
event_log = _load_sibling("event_log")


@dataclass(frozen=True)
class ModelCostSummary:
    model: str
    tokens_by_kind: dict  # {"input", "cache_write", "cache_read", "output"} -> int
    cost_usd: float


def summarize_by_model(messages: list) -> list[ModelCostSummary]:
    """Group analyzer.MessageRecord objects by model, summing tokens + cost."""
    by_model: dict[str, dict] = {}
    for m in messages:
        entry = by_model.setdefault(m.model, {
            "input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "cost_usd": 0.0,
        })
        entry["input"] += m.input_tokens
        entry["cache_write"] += m.cache_write_tokens
        entry["cache_read"] += m.cache_read_tokens
        entry["output"] += m.output_tokens
        entry["cost_usd"] += m.cost_usd
    return [
        ModelCostSummary(
            model=model,
            tokens_by_kind={
                "input": v["input"], "cache_write": v["cache_write"],
                "cache_read": v["cache_read"], "output": v["output"],
            },
            cost_usd=v["cost_usd"],
        )
        for model, v in by_model.items()
    ]


def capture_session_cost(
    transcript_path: "str | Path",
    *,
    session_id: str = "",
    parent_id: "str | None" = None,
    root: "str | Path | None" = None,
    telemetry_root: "str | Path | None" = None,
) -> list[dict]:
    """Analyze `transcript_path` and append one `session-cost` telemetry
    event per model observed. Returns the list of event records successfully
    appended (empty on any graceful-skip condition). Never raises.

    `root` is the directory the active-plan attribution marker is read
    relative to (defaults to `Path.cwd()` inside `event_log`) — pass it
    explicitly in tests instead of chdir'ing. `telemetry_root` overrides the
    event log's own directory the same way (defaults to `event_log.
    telemetry_dir()`, itself `$AGENTM_TELEMETRY_DIR`-overridable).
    """
    try:
        report = analyzer.analyze_session(transcript_path)
    except (OSError, ValueError):
        return []
    if not report.messages:
        return []

    tags = event_log.resolve_attribution_tags(root=Path(root) if root is not None else None)
    telemetry_root_path = Path(telemetry_root) if telemetry_root is not None else None

    written: list[dict] = []
    for summary in summarize_by_model(report.messages):
        record = event_log.build_event(
            "session-cost",
            session_id=session_id,
            parent_id=parent_id,
            model=summary.model,
            tokens_by_kind=summary.tokens_by_kind,
            cost_usd=summary.cost_usd,
            tags=tags,
        )
        if event_log.append_event(record, telemetry_root=telemetry_root_path):
            written.append(record)
    return written


def main(argv: "list[str] | None" = None) -> int:
    """CLI entry point for the Stop hook shell wrapper.

    Usage: session_cost_writer.py <transcript-path> [--session-id <id>] [--parent-id <id>]
    Always exits 0 — a capture failure must never fail the hook / block
    session close. Diagnostic detail (if any) goes to stderr.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("transcript_path")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--parent-id", default=None)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        written = capture_session_cost(
            args.transcript_path, session_id=args.session_id, parent_id=args.parent_id,
        )
        if written:
            print(
                f"session-cost-capture: wrote {len(written)} event(s)",
                file=sys.stderr,
            )
    except Exception as e:  # pragma: no cover — belt-and-suspenders; must never raise
        print(f"session-cost-capture: no-op ({e})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
