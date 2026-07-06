#!/usr/bin/env python3
"""Pre-flight fan-out cost gate (crickets-token-audit design, 2026-07-04 amendment).

Before any multi-agent dispatch: estimate spend = agent-count × per-agent
cost, compared against a configured budget share. Below threshold: proceed
silently. Above it: confirm-or-block, and the output always states model ×
agent-count × estimated cost — the direct fix for the Mythos failure mode (a
112-agent fleet that exhausted the session limit mid-run with no pre-flight
estimate in front of the operator).

Stated honestly: this is **local, deterministic accounting from transcripts**
— a hook cannot read Anthropic's actual remaining quota, so the gate
estimates, it never guarantees. Every block/confirm message says so verbatim.
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


pricing = _load("pricing")

# A documented placeholder — not a measured average. Used only when no
# observed session-cost history exists for the dispatched model (today: this
# is always the case, since task 4's writer is deferred; see
# progress-efficiency-automation.md). Task 4's records, once they accumulate,
# should supersede this profile via `observed_records`.
DEFAULT_AGENT_USAGE_PROFILE = {
    "input_tokens": 50_000,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "output_tokens": 8_000,
}

# A conservative fallback share (USD) when the caller supplies no explicit
# budget_share — keeps the gate meaningfully protective, not a no-op, even
# before an operator has configured a real ceiling.
DEFAULT_BUDGET_SHARE_USD = 50.00

_ESTIMATE_DISCLAIMER = (
    "this is a LOCAL ESTIMATE from transcript accounting, not Anthropic's "
    "actual remaining quota"
)


def estimate_per_agent_cost(
    model_id: str,
    *,
    observed_records: list[dict] | None = None,
    usage_profile: dict | None = None,
) -> float:
    """Per-agent cost estimate for `model_id`.

    Prefers the mean `cost_usd` of `observed_records` matching this model
    (drawn from token-audit's own session-cost records, task 4/5). Falls back
    to `pricing.cost_usd` over a fixed usage profile when no matching
    observed record exists.
    """
    if observed_records:
        matching = [
            r["cost_usd"] for r in observed_records
            if r.get("model") == model_id and isinstance(r.get("cost_usd"), (int, float))
        ]
        if matching:
            return sum(matching) / len(matching)
    profile = usage_profile or DEFAULT_AGENT_USAGE_PROFILE
    return pricing.cost_usd(profile, model_id)


@dataclass(frozen=True)
class GateResult:
    proceed: bool
    message: str  # "" when proceeding silently (under budget)
    estimated_cost_usd: float
    agent_count: int
    model_id: str


def fanout_cost_gate(
    agent_count: int,
    model_id: str,
    *,
    per_agent_cost: float | None = None,
    observed_records: list[dict] | None = None,
    budget_share_usd: float | None = None,
) -> GateResult:
    """The pre-dispatch check. Call before any multi-agent fan-out.

    `per_agent_cost` overrides estimation entirely when supplied (the "known
    model, known cost" fixture shape). Otherwise estimated via
    `estimate_per_agent_cost`. `budget_share_usd` defaults to
    `DEFAULT_BUDGET_SHARE_USD` when omitted — the gate is protective by
    default, not a no-op absent operator configuration.
    """
    cost_per_agent = (
        per_agent_cost if per_agent_cost is not None
        else estimate_per_agent_cost(model_id, observed_records=observed_records)
    )
    estimated_total = agent_count * cost_per_agent
    share = budget_share_usd if budget_share_usd is not None else DEFAULT_BUDGET_SHARE_USD

    if estimated_total <= share:
        return GateResult(
            proceed=True, message="",
            estimated_cost_usd=estimated_total, agent_count=agent_count, model_id=model_id,
        )

    message = (
        f"CONFIRM-OR-BLOCK: fan-out of {agent_count} agent(s) at {model_id!r} "
        f"estimated ${estimated_total:.2f} total (${cost_per_agent:.4f}/agent) "
        f"exceeds the configured budget share of ${share:.2f} — {_ESTIMATE_DISCLAIMER}."
    )
    return GateResult(
        proceed=False, message=message,
        estimated_cost_usd=estimated_total, agent_count=agent_count, model_id=model_id,
    )
