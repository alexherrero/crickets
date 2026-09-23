#!/usr/bin/env python3
"""`/handoff` backing logic (crickets-token-audit design, 2026-07-04 amendment).

Generalizes the Mythos `PROMPTS.md` pattern (the Mythos readiness handoff's
`PROMPTS.md` / `PROMPTS-NEXT.md`, now in the agentm vault project's
`completed/`): snapshots an expensive session's outputs into a handoff
directory alongside paste-ready prompts for downstream cheap sessions.

Where a pack goes by default is the project's own `desk/`, as agentm names it
(`default_destination`): `<desk>/<handoff-slug>/`. With no desk (agentm absent,
or no vault for the project) there is no default and the operator names one. The load-bearing difference from the
hand-authored Mythos pack: every prompt here carries a **structured**
tier/model label (`LABEL_SCHEMA_KEYS`), not just a bold-markdown annotation
a human has to parse — so a downstream consumer (including the `/work`
escalation tripwire `PLAN-efficiency-dispatch` adds) can read the label as
data instead of inventing its own parser.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# The shared schema a handoff-pack label must carry. `PLAN-efficiency-dispatch`'s
# escalation tripwire is expected to emit labels conforming to this same key
# set — see scripts/fixtures/handoff_pack_label_schema.json, the fixture both
# this task's test and that future test read, so the two never drift apart
# silently.
LABEL_SCHEMA_KEYS: tuple[str, ...] = ("tier", "model_id", "effort")


@dataclass(frozen=True)
class HandoffEntry:
    title: str
    prompt_text: str
    tier: str
    model_id: str
    effort: str

    def label(self) -> dict:
        """The machine-readable tier/model label — a structured dict, not prose."""
        return {"tier": self.tier, "model_id": self.model_id, "effort": self.effort}


def _project_homes():
    """This plugin's `project_homes.py` — the one pinned way crickets asks agentm
    where a project's desk/ is — loaded by path from this plugin's scripts/."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "tokens_project_homes", Path(__file__).resolve().parent / "project_homes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def default_destination(slug: str, cwd=None, *, homes=None) -> "Path | None":
    """Where a pack named `slug` goes when the operator names no destination:
    `<desk>/<slug>/`, in the project's own desk/ as agentm names it for the
    project `cwd` is bound to. None when there is no desk — then the operator
    names one. Creates nothing, and never composes a project path."""
    homes = _project_homes() if homes is None else homes
    desk = homes.home("desk", cwd=cwd)
    return desk / slug if desk is not None else None


def label_matches_schema(label: dict) -> bool:
    """True iff `label` carries exactly `LABEL_SCHEMA_KEYS`, no more, no fewer."""
    return set(label.keys()) == set(LABEL_SCHEMA_KEYS)


# agentm's handoff marker (agentm miner-provenance, ruling 1, 2026-09-04). A
# message that carries it is text the agent wrote for the operator to paste,
# and agentm's reflect miner mines nothing from it — however the host
# attributes the paste. Kept byte-identical to `reflect.HANDOFF_MARKER`.
HANDOFF_MARKER = "<!-- agentm:handoff — agent-authored; not the operator's own words -->"


def build_handoff_pack(
    entries: list[HandoffEntry],
    session_outputs: dict[str, str],
    dest_dir: Path,
) -> dict:
    """Snapshot `session_outputs` (filename -> content) into `dest_dir`, then
    write `prompts.json` (the structured manifest) and `PROMPTS.md` (the
    paste-ready human rendering, generated from the same structured data —
    never authored separately, so the two can't drift).

    Creates `dest_dir` if absent. Returns the manifest dict that was written.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    snapshotted: list[str] = []
    for name, content in session_outputs.items():
        (dest_dir / name).write_text(content, encoding="utf-8")
        snapshotted.append(name)

    manifest = {
        "snapshotted_files": sorted(snapshotted),
        "prompts": [
            {"title": e.title, "prompt_text": e.prompt_text, "label": e.label()}
            for e in entries
        ],
    }
    (dest_dir / "prompts.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = ["# Handoff pack", "", HANDOFF_MARKER, ""]
    for e in entries:
        lines.append(f"## {e.title} — tier: {e.tier} · model: {e.model_id} · effort: {e.effort}")
        lines.append("")
        # One marker per prompt, inside the block a person copies: agentm's
        # reflect miner skips a pasted message that carries it, so a handoff
        # the agent wrote is never mined as the operator's own words.
        lines.append(HANDOFF_MARKER)
        lines.append("")
        lines.append("Paste:")
        lines.append("")
        lines.append(f"> {HANDOFF_MARKER}")
        lines.append(f"> {e.prompt_text}")
        lines.append("")
    (dest_dir / "PROMPTS.md").write_text("\n".join(lines), encoding="utf-8")

    return manifest
