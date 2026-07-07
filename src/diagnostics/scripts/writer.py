#!/usr/bin/env python3
"""Scrubbed failure-incident writer for /diagnose (crickets wave-c-diagnostics).

Assembles a failure-incident entry (symptom / root cause / fix-or-workaround /
outcome / ranked hypotheses) and writes it via agentm's standard save_entry()
path -- which runs the mandatory privacy scrub for kind="failure-incident"
before anything lands on disk (agentm's own contract; not re-implemented
here) -- then records the fingerprint in the sidecar so Layer-1 recall finds
it immediately. save_entry's fingerprint= param also populates the real
entry_meta.fingerprint column once a drain cycle runs, for other future
SQL-side consumers; diagnostics itself never reads that column back (see
PLAN-wave-c-diagnostics.md's Locked design calls for the full reasoning).

PLAN-wave-d-tokens-and-privacy task 6: the assembled body is ALSO explicitly
scrubbed here, via privacy's own scrub_text() surface, before it's handed to
agentm_bridge.write_failure_incident(). This is a second, explicit, visible
scrub at the crickets call site -- not a replacement for save_entry()'s own
mandatory kind-gated scrub one layer down, which still runs unconditionally.
Scrubbing is idempotent (already-redacted text passes through unchanged), so
the two scrubs never conflict; explicit here means this write path stays
correct even if a future change ever altered save_entry()'s own kind-gating.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PRIVACY_SCRIPTS = _HERE.parent.parent / "privacy" / "scripts"


def _load_sibling(label: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"_diagnostics_internal_{label}", _HERE / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_privacy_scrub_text():
    """Load privacy's scrub_text.py from this repo's own src/ tree (co-located
    plugin install) -- diagnostics `requires: [development-lifecycle]` but not
    `privacy`, so this is a soft, graceful-skip-on-absence load, same pattern
    as agentm_bridge.py's own optional bridges. Falls back to identity (no
    scrub) if privacy's scrub_text.py isn't reachable -- save_entry()'s own
    mandatory kind-gated scrub is still the hard guarantee either way."""
    candidates = [
        _PRIVACY_SCRIPTS / "scrub_text.py",  # co-located src/ checkout
    ]
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_diagnostics_privacy_scrub_text", candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


agentm_bridge = _load_sibling("agentm_bridge", "agentm_bridge.py")
fingerprint_index = _load_sibling("fingerprint_index", "fingerprint_index.py")
_privacy_scrub_text = _load_privacy_scrub_text()

_DEFAULT_HYPOTHESIS = "Unknown -- no hypothesis ranked yet."


def _opinion_section(name: str) -> str:
    """Render `## Opinion: <name>` from the resolved base+supplement, or ""
    when the opinion is unresolvable (no-opinion/error) -- graceful-skip,
    never blocks the incident write (PLAN-wave-d-opinion-wiring task 1)."""
    result = agentm_bridge.opinion_resolve(name)
    if result.get("reason") not in ("served", "base-only") or not result.get("base"):
        return ""
    parts = [result["base"].strip()]
    if result.get("supplement"):
        parts.append(result["supplement"].strip())
    return f"## Opinion: {name}\n" + "\n\n".join(parts) + "\n\n"


def _build_body(
    *,
    symptom: str,
    root_cause: "str | None",
    fix_or_workaround: "str | None",
    outcome: "str | None",
    hypotheses: "list[str] | None",
) -> str:
    hyp_lines = "\n".join(
        f"{i}. {h}" for i, h in enumerate(hypotheses or [_DEFAULT_HYPOTHESIS], start=1)
    )
    return (
        f"## Symptom\n{symptom}\n\n"
        f"## Root cause\n{root_cause or 'Unknown -- no root cause identified yet.'}\n\n"
        f"## Fix / workaround\n{fix_or_workaround or 'None yet -- see hypotheses below.'}\n\n"
        f"## Outcome\n{outcome or 'Pending -- this is a fresh incident.'}\n\n"
        f"## Hypotheses\n{hyp_lines}\n"
        f"\n{_opinion_section('how-we-engineer')}"
    ).rstrip("\n") + "\n"


def write_failure_incident(
    vault: Path,
    *,
    project: str,
    fingerprint: str,
    namespace: str,
    symptom: str,
    root_cause: "str | None" = None,
    fix_or_workaround: "str | None" = None,
    outcome: "str | None" = None,
    hypotheses: "list[str] | None" = None,
) -> Path:
    """Assemble + write one scrubbed kind="failure-incident" entry, then
    record it in the Layer-1 sidecar. Returns the absolute path written."""
    body = _build_body(
        symptom=symptom,
        root_cause=root_cause,
        fix_or_workaround=fix_or_workaround,
        outcome=outcome,
        hypotheses=hypotheses,
    )
    if _privacy_scrub_text is not None:
        body = _privacy_scrub_text.scrub_text(body)
    slug = f"{namespace}-{fingerprint[:12]}"
    target = agentm_bridge.write_failure_incident(
        vault, slug=slug, body=body, project=project, fingerprint=fingerprint, tags=[namespace],
    )
    fingerprint_index.record(vault, fingerprint, project, str(target.relative_to(vault)))
    return target
