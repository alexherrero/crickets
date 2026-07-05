#!/usr/bin/env python3
"""Hook 3 (AG Phase-2, design-doc §6.3): the plan-grounding gate.

A plan that declares `touches_architecture: true` must be grounded in its
governing design — it must carry a non-empty `parent_design_doc:` frontmatter
value **or** a non-empty `## Locked design calls` section (the greenfield
assertion counts — asserting "no governing design" *is* the grounding step). The
check is deterministic and keyed off the explicit flag, never an inference —
mirroring agentm's static gates (e.g. check-no-hardcoded-vault-path): a real
check, not agent judgment.

Plans live in the (gitignored, often vault-backed) `_harness/`, so this is a
phase-loop gate run against a *resolved plan path*, not a repo-wide CI gate. The
/plan phase self-checks its own output with it; /work can run it as a precondition.

Usage: check-plan-grounding.py <plan-file>
  Exit 0: grounded — or touches_architecture is false/absent (nothing to enforce)
  Exit 1: touches_architecture: true but ungrounded
  Exit 2: usage error / unreadable file
"""
from __future__ import annotations

import sys
from pathlib import Path

_TRUE = {"true", "yes", "on", "1"}


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return ({frontmatter scalars}, body). Minimal, stdlib-only, never raises."""
    fm: dict[str, str] = {}
    body = text
    try:
        if text.startswith("---"):
            lines = text.splitlines()
            if lines and lines[0].strip() == "---":
                end = None
                for i in range(1, len(lines)):
                    if lines[i].strip() == "---":
                        end = i
                        break
                if end is not None:
                    for raw in lines[1:end]:
                        s = raw.strip()
                        if not s or s.startswith("#") or ":" not in s:
                            continue
                        k, _, v = s.partition(":")
                        fm[k.strip()] = v.strip().strip("'\"")
                    body = "\n".join(lines[end + 1:])
    except Exception:
        return ({}, text)
    return (fm, body)


def _has_nonempty_section(body: str, heading: str) -> bool:
    """True iff `body` has a `## <heading>` section with ≥1 non-blank content line
    before the next heading."""
    want = heading.strip().lower()
    lines = body.splitlines()
    in_section = False
    for ln in lines:
        st = ln.strip()
        if st.startswith("#"):
            # a heading line — enter our section, or (if already in) end it
            head_text = st.lstrip("#").strip().lower()
            if in_section:
                break
            in_section = (head_text == want)
            continue
        if in_section and st:
            return True
    return False


def is_grounded(text: str) -> tuple[bool, str]:
    """Return (ok, reason). ok=True when grounding is satisfied or not required."""
    fm, body = _split_frontmatter(text)
    touches = fm.get("touches_architecture", "").strip().lower()
    if touches not in _TRUE:
        return (True, "touches_architecture not true — nothing to enforce")
    if fm.get("parent_design_doc", "").strip():
        return (True, "grounded via parent_design_doc")
    if _has_nonempty_section(body, "Locked design calls"):
        return (True, "grounded via ## Locked design calls")
    return (False, "touches_architecture: true but no parent_design_doc and no "
                   "non-empty '## Locked design calls' section — ground the plan "
                   "in its governing design (run the /plan Hook-2 step) or set "
                   "touches_architecture: false")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check-plan-grounding.py <plan-file>", file=sys.stderr)
        return 2
    p = Path(argv[1])
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"check-plan-grounding: cannot read {p}: {exc}", file=sys.stderr)
        return 2
    ok, reason = is_grounded(text)
    if ok:
        print(f"check-plan-grounding: OK — {reason}")
        return 0
    print(f"check-plan-grounding: FAIL — {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
