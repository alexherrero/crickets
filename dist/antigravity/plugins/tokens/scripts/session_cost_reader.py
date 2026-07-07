#!/usr/bin/env python3
"""Read real `kind: session-cost` records back from the vault
(PLAN-wave-d-tokens-and-privacy task 2) -- the read-side counterpart to
session_cost_writer.py's write path.

fanout_cost_gate.estimate_per_agent_cost() accepts an `observed_records`
param shaped `[{"model": ..., "cost_usd": ...}, ...]` but, before this
module, nothing populated it from real data -- every call fell back to
`pricing.cost_usd` over DEFAULT_AGENT_USAGE_PROFILE (a documented
placeholder, never a measured average). `load_observed_records()` closes
that gap: it globs the vault's session-cost entries session_cost_writer.py
actually writes and parses their `model:` / `cost_usd:` lines back out.

Deliberately does NOT depend on agentm's SQL/vec-index internals (recall.py,
vec_index.py) -- reading back entries this capability itself wrote is a
plain filesystem glob + regex parse, not a semantic-recall query. Keeps the
one-way capability boundary clean (tokens doesn't need agentm's indexing
machinery just to read its own writes back).
"""
from __future__ import annotations

import re
from pathlib import Path

_MODEL_RE = re.compile(r"^- model: (.+)$", re.MULTILINE)
_COST_RE = re.compile(r"^- cost_usd: ([0-9.eE+-]+)$", re.MULTILINE)


def load_observed_records(vault_path: "str | Path | None", *, project: str = "personal") -> list[dict]:
    """Return `[{"model": ..., "cost_usd": ...}, ...]` for every real
    `session-cost` entry found under
    `<vault>/projects/<project>/session-cost/session-cost/*.md` (the group/
    kind path shape save_entry() produces for session_cost_writer.py's
    writes -- see its own group=f"projects/{project}/session-cost" call).

    Graceful-empty on any absent/unreadable path -- never raises. An empty
    return means "no observed data yet", which callers (fanout_cost_gate.py)
    already treat as "fall back to the pricing-profile estimate".
    """
    if not vault_path:
        return []
    vault = Path(vault_path)
    entry_dir = vault / "projects" / project / "session-cost" / "session-cost"
    if not entry_dir.is_dir():
        return []

    records: list[dict] = []
    for path in sorted(entry_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        model_match = _MODEL_RE.search(text)
        cost_match = _COST_RE.search(text)
        if not model_match or not cost_match:
            continue
        try:
            cost = float(cost_match.group(1))
        except ValueError:
            continue
        records.append({"model": model_match.group(1).strip(), "cost_usd": cost})
    return records
