#!/usr/bin/env python3
"""`/handoff-pack` backing logic (crickets-token-audit design, 2026-07-04 amendment).

Generalizes the Mythos `PROMPTS.md` pattern (`<vault>/projects/agentm/_harness/
mythos-readiness-handoff/PROMPTS.md` / `PROMPTS-NEXT.md`): snapshots an
expensive session's outputs into a handoff directory alongside paste-ready
prompts for downstream cheap sessions. The load-bearing difference from the
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


def label_matches_schema(label: dict) -> bool:
    """True iff `label` carries exactly `LABEL_SCHEMA_KEYS`, no more, no fewer."""
    return set(label.keys()) == set(LABEL_SCHEMA_KEYS)


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

    lines = ["# Handoff pack", ""]
    for e in entries:
        lines.append(f"## {e.title} — tier: {e.tier} · model: {e.model_id} · effort: {e.effort}")
        lines.append("")
        lines.append("Paste:")
        lines.append("")
        lines.append(f"> {e.prompt_text}")
        lines.append("")
    (dest_dir / "PROMPTS.md").write_text("\n".join(lines), encoding="utf-8")

    return manifest
