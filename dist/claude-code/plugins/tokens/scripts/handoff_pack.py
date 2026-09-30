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


# What a snapshotted note is once it sits in a pack: a copy made for the next
# sessions, not the note it was copied from. A pack that kept its originals'
# kinds put a second `kind: tracker` beside the task's own (six in pixelcity's
# desk/ by 2026-09-29, each still `status: active`), which agentm's
# check-tracker-schema fails as a tracker outside a tracker's place, and it
# carried unregistered values like `backlog` into the corpus. `handoff-artifact`
# is the record kind agentm's storage rules register for exactly this; a record
# carries `kind:` and never `type:`, so a snapshotted memory loses its type.
SNAPSHOT_KIND = "handoff-artifact"
_KIND_FIELDS = ("kind", "type")


def _field_name(line: str) -> "str | None":
    """The top-level frontmatter key `line` opens, or None when it opens none."""
    if not line or line[0] in " \t-#":
        return None
    name, sep, _ = line.partition(":")
    return name.strip() if sep else None


def _continues(line: str) -> bool:
    """Whether `line` belongs to the key above it: indented, or a `- ` item."""
    return bool(line) and line[0] in " \t-"


def as_snapshot(content: str) -> "tuple[str, dict]":
    """`content` as the pack keeps it: a note whose frontmatter carries `kind:`
    or `type:` gets `kind: handoff-artifact` in place of the first and loses the
    rest, and every other byte is unchanged. Returns the text and the fields it
    replaced (`{"kind": "tracker"}`), empty when nothing changed. A file with no
    frontmatter, an unclosed one, or none of the two fields comes back as is."""
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return content, {}
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
    if close is None:
        return content, {}

    replaced: dict = {}
    head: list = [lines[0]]
    i = 1
    while i < close:
        name = _field_name(lines[i])
        if name not in _KIND_FIELDS:
            head.append(lines[i])
            i += 1
            continue
        end = i + 1
        while end < close and _continues(lines[end]):
            end += 1
        value = "".join(lines[i:end]).partition(":")[2].strip().strip("'\"")
        replaced[name] = value
        if len(replaced) == 1:
            eol = lines[i][len(lines[i].rstrip("\r\n")):] or "\n"
            head.append(f"kind: {SNAPSHOT_KIND}{eol}")
        i = end
    if not replaced or replaced == {"kind": SNAPSHOT_KIND}:
        return content, {}
    return "".join(head + lines[close:]), replaced


def build_handoff_pack(
    entries: list[HandoffEntry],
    session_outputs: dict[str, str],
    dest_dir: Path,
) -> dict:
    """Snapshot `session_outputs` (filename -> content) into `dest_dir`, then
    write `prompts.json` (the structured manifest) and `PROMPTS.md` (the
    paste-ready human rendering, generated from the same structured data —
    never authored separately, so the two can't drift).

    A Markdown output is snapshotted as `as_snapshot` rewrites it, and the
    manifest's `snapshot_kinds` names what each one was (`{"tracker.md":
    {"kind": "tracker"}}`); every other output is copied byte for byte.

    Creates `dest_dir` if absent. Returns the manifest dict that was written.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    snapshotted: list[str] = []
    snapshot_kinds: dict = {}
    for name, content in session_outputs.items():
        if name.lower().endswith(".md"):
            content, replaced = as_snapshot(content)
            if replaced:
                snapshot_kinds[name] = replaced
        (dest_dir / name).write_text(content, encoding="utf-8")
        snapshotted.append(name)

    manifest = {
        "snapshotted_files": sorted(snapshotted),
        "snapshot_kinds": dict(sorted(snapshot_kinds.items())),
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
