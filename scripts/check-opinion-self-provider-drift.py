#!/usr/bin/env python3
"""check-opinion-self-provider-drift.py — flags an agentm opinion stub
falling out of sync with its self-provider caller's own prose, never the
reverse (PLAN-opinion-consumer-grammar task 3).

A self-provider binding (per the locked agentm opinion-registry consumer
grammar) is a caller that IS its opinion's `implements:` artifact —
`good` implements `crickets/code-review`, and code-review's own
`agents/adversarial-reviewer.md` is where that standard actually lives in
shipped prose. The caller's prose is canonical; the opinion stub in agentm
is a condensed mirror of it. This gate is the honesty check on that
mirror, and it is deliberately NOT a byte-diff (unlike
check-opinion-snapshot-parity.py's cross-plugin case) — a stub that
paraphrases a caller's prose can never be byte-identical by design.

The check: each binding names a short list of anchor phrases lifted from
the stub's own concrete, checkable claims (e.g. "failing test", "no issues
found"). If the caller's file stops mentioning ANY anchor, the stub can no
longer be trusted to summarize what the caller actually asks for --
flag it. This is a coarse heuristic, never a full semantic diff -- the
same report-only, term-presence posture as check-voice-floor-parity.py.

Exit 0: every binding's anchors are present in its caller, or agentm is
        absent (graceful skip -- printed distinctly from a real match)
Exit 1: at least one binding's caller is missing an anchor
Exit 2: usage/read error (a declared caller file doesn't exist, or agentm
        has no matching opinions/<name>.md)

--report forces exit 0, matching the other opinion gates' posture.

Stdlib-only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src_model import strip_frontmatter, find_agentm_opinions_dir  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent

# opinion name -> (caller file, anchor phrases lifted from the stub's own
# concrete claims). Anchors are matched case-insensitively as substrings.
# Add a new binding here as each self-provider case is proven, per the
# plan's task-4 grounding-first discipline -- never speculatively.
SELF_PROVIDER_BINDINGS: dict[str, dict] = {
    "good": {
        "caller": _ROOT / "src" / "code-review" / "agents" / "adversarial-reviewer.md",
        "anchors": ["failing test", "no issues found"],
    },
    # PLAN-wave-d-personas task 3: development-lifecycle's own two direct
    # bindings. work.md is the canonical `done` site -- the check-battery /
    # task-marker / progress.md triad the stub states lives there most
    # completely. bugfix.md is the canonical `how-we-engineer` site -- not
    # work.md/plan.md (the plan's own first guess): "Report -> Analyze ->
    # Fix -> Verify" is the one phrase, verbatim, from the stub that appears
    # in exactly one command file, confirmed by grep across all six before
    # picking it (never the first hit assumed).
    "done": {
        "caller": _ROOT / "src" / "development-lifecycle" / "commands" / "work.md",
        "anchors": ["marked `[x]`", "progress.md"],
    },
    "how-we-engineer": {
        "caller": _ROOT / "src" / "development-lifecycle" / "commands" / "bugfix.md",
        "anchors": ["Report → Analyze → Fix → Verify"],
    },
}


def missing_anchors(caller_text: str, anchors: list[str]) -> list[str]:
    lowered = caller_text.lower()
    return [a for a in anchors if a.lower() not in lowered]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="check-opinion-self-provider-drift", description=__doc__)
    p.add_argument("--agentm-opinions-dir", default=None, type=Path,
                    help="override agentm opinions/ dir discovery (tests)")
    p.add_argument("--report", action="store_true", help="always exit 0 — non-blocking wiring")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    agentm_dir = args.agentm_opinions_dir or find_agentm_opinions_dir()
    if agentm_dir is None or not agentm_dir.is_dir():
        print("check-opinion-self-provider-drift: agentm sibling not found — "
              "SKIPPING (bindings were NOT compared, this is not a pass)")
        return 0

    drifted: list[str] = []
    for name, binding in sorted(SELF_PROVIDER_BINDINGS.items()):
        caller_path = binding["caller"]
        if not caller_path.is_file():
            print(f"check-opinion-self-provider-drift: error: caller file for "
                  f"{name!r} does not exist: {caller_path}")
            return 2
        stub_path = agentm_dir / f"{name}.md"
        if not stub_path.is_file():
            print(f"check-opinion-self-provider-drift: error: agentm has no "
                  f"opinions/{name}.md for binding {name!r}")
            return 2
        # Anchors are curated per-binding above (deriving them generically
        # from arbitrary prose isn't reliable), but each must still be a
        # real substring of the LIVE stub -- if the stub's own wording moves
        # on, a stale hardcoded anchor would silently stop checking anything
        # meaningful. That's this check's own upkeep, not the caller's drift.
        stub_body = strip_frontmatter(stub_path.read_text(encoding="utf-8"))
        stale_anchors = missing_anchors(stub_body, binding["anchors"])
        if stale_anchors:
            print(f"check-opinion-self-provider-drift: warning: anchor(s) "
                  f"{stale_anchors!r} for {name!r} no longer appear in agentm's "
                  f"own opinions/{name}.md -- this check's anchor list needs review")
        caller_text = caller_path.read_text(encoding="utf-8")
        missing = missing_anchors(caller_text, binding["anchors"])
        if missing:
            try:
                rel = caller_path.relative_to(_ROOT)
            except ValueError:
                rel = caller_path
            drifted.append(
                f"{name}: {rel} no longer mentions {missing!r} — the agentm "
                f"opinions/{name}.md stub may no longer mirror it")

    if drifted:
        print(f"check-opinion-self-provider-drift: {len(drifted)} binding(s) may have drifted:")
        for line in drifted:
            print(f"  {line}")
    else:
        print(f"check-opinion-self-provider-drift: {len(SELF_PROVIDER_BINDINGS)} "
              f"binding(s) still anchored — in sync")

    if args.report:
        return 0
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
