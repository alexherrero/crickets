#!/usr/bin/env python3
"""Routing-conformance report (crickets-token-audit design, 2026-07-04 amendment).

A post-hoc read of model-used vs. work-type against `routing_table.py`,
cross-referencing the mandatory fan-out announcement `crickets-development-
lifecycle.md`'s amendment adds at the dispatch site — counting dispatches
with no announced model as violations.

NOTE (design divergence, honest per Hook 4): the mandatory fan-out
announcement itself is `[PENDING-IMPL]` — `PLAN-efficiency-dispatch`'s scope,
sequenced after this plan. This module therefore operates on a structured
`DispatchRecord` list (already extracted from wherever the announcement
lines live in a transcript), not on raw transcript text via a regex over an
announcement format that doesn't exist to parse yet. Once the dispatch plan
ships the real announcement line shape, the extraction step that turns
transcript text into `DispatchRecord`s is the piece to add here or in
`/token-audit`'s command doc — this report's classification logic does not
change.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, m)
    spec.loader.exec_module(m)
    return m


classify_work_type = _load("classify_work_type")


@dataclass(frozen=True)
class DispatchRecord:
    role: str
    agent_count: int
    model_id: str | None = None      # None = no model announced at all
    tier_source: str | None = None   # None = no announcement at all (implies model_id is None)


def _expected_model_id(role: str) -> str:
    return classify_work_type.classify_work_type(role_name=role).model_id


def conformance_report(records: list[DispatchRecord]) -> dict:
    """Classify each dispatch record against the routing table's expectation.

    Every record with `model_id is None` (no announcement at all) is an
    **announcement-rule violation**, counted regardless of what the expected
    model would have been — visibility of the gap is the point, not whether
    the gap happened to be harmless.
    """
    total = len(records)
    violations = 0
    matches = 0
    mismatches = 0
    details: list[dict] = []

    for rec in records:
        expected = _expected_model_id(rec.role)
        if rec.model_id is None:
            violations += 1
            status = "VIOLATION-NO-ANNOUNCEMENT"
        elif rec.model_id == expected:
            matches += 1
            status = "MATCH"
        else:
            mismatches += 1
            status = "MISMATCH"
        details.append({
            "role": rec.role,
            "agent_count": rec.agent_count,
            "model_id": rec.model_id,
            "tier_source": rec.tier_source,
            "expected_model_id": expected,
            "status": status,
        })

    return {
        "total": total,
        "matches": matches,
        "mismatches": mismatches,
        "violations_no_announcement": violations,
        "details": details,
    }
