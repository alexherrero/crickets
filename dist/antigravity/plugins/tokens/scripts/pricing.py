#!/usr/bin/env python3
"""Pinned pricing table for Claude models (per MTok, USD).

ONE source of truth — Part C (status-line meter) imports this module rather than
maintaining a second table. To update pricing: edit PRICING here only.

Verified 2026-07-03 from the Anthropic pricing page (platform.claude.com/docs/en/about-claude/pricing).
cache_write_per_mtok = 5-minute TTL rate (1.25× input).
claude-sonnet-5 is pinned at its introductory rate ($2/$10 input/output),
in effect through 2026-08-31; the standard rate ($3/$15) takes effect
2026-09-01 and needs a re-pin then.
# TODO: distinguish 1h TTL (2× input) once Part C needs it; the
# cache_creation.ephemeral_1h_input_tokens sub-field already tracks it in JSONL.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-8": ModelPricing(
        input_per_mtok=5.00,
        output_per_mtok=25.00,
        cache_write_per_mtok=6.25,
        cache_read_per_mtok=0.50,
    ),
    "claude-sonnet-4-6": ModelPricing(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),
    "claude-haiku-4-5": ModelPricing(
        input_per_mtok=1.00,
        output_per_mtok=5.00,
        cache_write_per_mtok=1.25,
        cache_read_per_mtok=0.10,
    ),
    "claude-fable-5": ModelPricing(
        input_per_mtok=10.00,
        output_per_mtok=50.00,
        cache_write_per_mtok=12.50,
        cache_read_per_mtok=1.00,
    ),
    "claude-sonnet-5": ModelPricing(
        input_per_mtok=2.00,
        output_per_mtok=10.00,
        cache_write_per_mtok=2.50,
        cache_read_per_mtok=0.20,
    ),
}


def cost_usd(usage: dict, model: str) -> float:
    """Return total cost in USD for one message's usage dict.

    Returns 0.0 and prints a WARNING for unknown models so the caller doesn't
    crash; the operator can add a row to PRICING.
    """
    p = PRICING.get(model)
    if p is None:
        import sys
        print(f"WARNING: unknown model {model!r} — priced at $0. Add a row to pricing.py.", file=sys.stderr)
        return 0.0
    it = int(usage.get("input_tokens", 0))
    cw = int(usage.get("cache_creation_input_tokens", 0))
    cr = int(usage.get("cache_read_input_tokens", 0))
    ot = int(usage.get("output_tokens", 0))
    return (
        it * p.input_per_mtok / 1_000_000
        + cw * p.cache_write_per_mtok / 1_000_000
        + cr * p.cache_read_per_mtok / 1_000_000
        + ot * p.output_per_mtok / 1_000_000
    )
