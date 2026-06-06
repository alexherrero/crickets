#!/usr/bin/env python3
# capture.py — edit-driven voice-lesson capture for diataxis-author
# (wiki-maintenance part 3/5, style-learning-loop, task 3).
#
# The DECISION-driven capture (agentmemory_conventions.confirm_save_convention)
# records key:value conventions to _always-load/. THIS is the EDIT-driven path:
# diff an authored draft against the operator's edited version, cluster the
# changes by kind, and propose voice lessons {trigger, guidance, before->after}
# for the operator to generalize (gate 1) + the style-scope-evaluator sub-agent
# to scope (gate 2) before the confirmed lesson is written to its on-demand scope
# store via agentmemory_conventions.confirm_save_lesson().
#
# This module owns only the DETERMINISTIC pieces — diff -> cluster -> propose,
# and the save passthrough. The two operator/LLM gates live in the skill body
# (SKILL.md). Nothing here auto-writes: `propose` never touches disk; `save` only
# runs on an explicit, already-confirmed {trigger, guidance, scope}. Stdlib-only.

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# The five change kinds the loop clusters by (parent Detailed Design §3):
#   word-choice · rhythm · structure · cuts (=slop/jargon) · additions
KINDS = ("word-choice", "rhythm", "structure", "cuts", "additions")

# Structural lines: headings, list items, ordered items, table rows.
_STRUCTURE_RE = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)")
# Terminal punctuation immediately followed by whitespace or EOL. Deliberately
# SIMPLE: also allowing a trailing close-quote/bracket (to catch `"done."`-style
# ends) miscounts mid-clause `(it works!)` / `"verbose."` as ends, flipping common
# word-choice edits to rhythm — a worse false-positive class than the benign
# quoted-terminator under-count. This is a heuristic bucketing hint for an
# operator-gated proposal, not a contract; keep it false-positive-free.
_SENTENCE_END_RE = re.compile(r"[.!?]+(?:\s|$)")


@dataclass(frozen=True)
class Change:
    """One classified edit: a draft-side span replaced/removed (`before`) and/or
    an edited-side span added (`after`). Empty side = pure cut / pure addition."""

    kind: str
    before: str
    after: str


@dataclass
class ProposedLesson:
    """A draft lesson proposal — scaffolding, NOT the final lesson. The operator
    generalizes `trigger` + `guidance` (gate 1) before any save (DC-7: the
    generalization is operator-gated, so proposal *content* is not unit-tested)."""

    trigger: str
    guidance: str
    before: str
    after: str
    cluster_kind: str


def _is_structural(line: str) -> bool:
    return bool(_STRUCTURE_RE.match(line))


def _sentence_count(text: str) -> int:
    return len(_SENTENCE_END_RE.findall(text))


def _classify_replace(before: str, after: str) -> str:
    """A non-structural replacement is `rhythm` when the sentence/line shape
    shifted (cadence change), else `word-choice` (same shape, different words)."""
    b_lines = [ln for ln in before.splitlines() if ln.strip()]
    a_lines = [ln for ln in after.splitlines() if ln.strip()]
    if len(b_lines) != len(a_lines):
        return "rhythm"
    if _sentence_count(before) != _sentence_count(after):
        return "rhythm"
    return "word-choice"


def diff_changes(draft: str, edited: str) -> list:
    """Deterministic diff -> classified Changes via difflib line opcodes.

      delete (non-structural)  -> cuts        insert (non-structural) -> additions
      any structural side      -> structure   replace (non-structural)-> rhythm | word-choice

    A within-line word removal surfaces as a `replace` (the line still exists), so
    it clusters as word-choice/rhythm; only whole removed lines/blocks are `cuts`.
    """
    draft_lines = draft.splitlines()
    edited_lines = edited.splitlines()
    sm = difflib.SequenceMatcher(None, draft_lines, edited_lines, autojunk=False)
    changes: list = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        before = "\n".join(draft_lines[i1:i2])
        after = "\n".join(edited_lines[j1:j2])
        b_struct = any(_is_structural(ln) for ln in draft_lines[i1:i2])
        a_struct = any(_is_structural(ln) for ln in edited_lines[j1:j2])
        if tag == "delete":
            kind = "structure" if b_struct else "cuts"
        elif tag == "insert":
            kind = "structure" if a_struct else "additions"
        else:  # replace
            kind = "structure" if (b_struct or a_struct) else _classify_replace(before, after)
        changes.append(Change(kind=kind, before=before, after=after))
    return changes


def cluster_changes(changes: list) -> dict:
    """Group classified Changes into kind-buckets (empty buckets omitted)."""
    buckets: dict = {}
    for ch in changes:
        buckets.setdefault(ch.kind, []).append(ch)
    return buckets


# Per-kind guidance scaffolds — the operator rewrites these into the real lesson.
_GUIDANCE_TEMPLATE = {
    "word-choice": "Word choice: the operator changed wording here. Generalize the preferred term/register.",
    "rhythm": "Sentence rhythm: the operator reshaped sentence/line cadence. Generalize the rhythm rule.",
    "structure": "Structure: the operator changed page/section/list shape. Generalize the structural rule.",
    "cuts": "Cut: the operator removed this as slop/jargon. Generalize what to drop.",
    "additions": "Addition: the operator added this. Generalize what to include.",
}


def propose_lessons(buckets: dict) -> list:
    """One draft proposal per non-empty bucket, in canonical KINDS order. Trigger
    defaults to the kind; guidance is a template — both are operator-generalized
    (gate 1) before save. This is scaffolding for the gate, not the final lesson."""
    proposals: list = []
    for kind in KINDS:
        chs = buckets.get(kind)
        if not chs:
            continue
        before = "\n---\n".join(c.before for c in chs if c.before).strip()
        after = "\n---\n".join(c.after for c in chs if c.after).strip()
        proposals.append(ProposedLesson(
            trigger=kind,
            guidance=_GUIDANCE_TEMPLATE[kind],
            before=before,
            after=after,
            cluster_kind=kind,
        ))
    return proposals


# ── CLI ──────────────────────────────────────────────────────────────────────

def _cmd_propose(args) -> int:
    """diff draft<->edited, cluster, print proposals as JSON. Writes NOTHING."""
    draft = Path(args.draft).read_text(encoding="utf-8")
    edited = Path(args.edited).read_text(encoding="utf-8")
    buckets = cluster_changes(diff_changes(draft, edited))
    out = {
        "clusters": {
            k: [{"before": c.before, "after": c.after} for c in v]
            for k, v in buckets.items()
        },
        "proposals": [asdict(p) for p in propose_lessons(buckets)],
    }
    print(json.dumps(out, indent=2))
    return 0


def _cmd_save(args) -> int:
    """Write ONE already-confirmed lesson to its on-demand scope store."""
    import agentmemory_conventions as amc
    vault_path = Path(args.vault_path).expanduser() if args.vault_path else None
    wiki_root = Path(args.wiki_root).expanduser() if args.wiki_root else None
    written = amc.confirm_save_lesson(
        args.trigger, args.guidance, args.scope,
        vault_path=vault_path, project_slug=args.project_slug,
        wiki_root=wiki_root, before=args.before, after=args.after, mode=args.mode,
    )
    if written is None:
        print("[capture] lesson NOT written (declined, or scope context missing)", file=sys.stderr)
        return 1
    print(str(written))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="diataxis-capture",
        description="Edit-driven voice-lesson capture for diataxis-author.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("propose", help="diff draft<->edited, cluster, print proposals (writes nothing)")
    pp.add_argument("--draft", required=True)
    pp.add_argument("--edited", required=True)
    pp.set_defaults(fn=_cmd_propose)

    ps = sub.add_parser("save", help="write ONE confirmed lesson to its on-demand scope store")
    ps.add_argument("--trigger", required=True)
    ps.add_argument("--guidance", required=True)
    ps.add_argument("--scope", required=True, choices=("global", "per-project", "per-repo"))
    ps.add_argument("--before", default=None)
    ps.add_argument("--after", default=None)
    ps.add_argument("--vault-path", default=None)
    ps.add_argument("--project-slug", default=None)
    ps.add_argument("--wiki-root", default=None)
    ps.add_argument("--mode", default=None, choices=("interactive", "silent", "auto"))
    ps.set_defaults(fn=_cmd_save)

    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
