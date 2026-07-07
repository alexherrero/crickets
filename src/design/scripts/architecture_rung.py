#!/usr/bin/env python3
"""Architecture-rung scaffolding for `/design` (crickets wave-c-design-and-
conventions, task 1).

Generalizes the multi-system HLD pattern already used by hand in agentm's
`agentm-hld.md` / `agentm-foundations-hld.md`: a parent design's frontmatter
`children:` list IS its composition claim (which sub-designs it composes),
and reviewing that claim deterministically means checking every declared
child actually resolves to a real file alongside the parent -- a dangling
child is a broken composition claim, caught mechanically rather than by
re-reading prose.

Design call (documented, not silently decided -- no exact prose-heading
convention exists across the real AG HLD set to match against): the
"composition-analysis artifact" is the parsed `children:`/`governs:`
frontmatter, not a search for specific section headings (the two real
precedent docs use doc-specific prose headings -- "How agentm and crickets
work together", "How it all connects" -- that don't share a common
generic heading string a template could require verbatim). The
"architecture-review pass" is the existence check below: every declared
child resolves. This lets the tool run cleanly against agentm-hld.md /
agentm-foundations-hld.md AS THEY EXIST TODAY, with no retrofitting.

Stdlib-only, mirroring design_doc.py's own no-PyYAML constraint (this is a
plugin-runtime script, not a repo-CI-only one) -- a small block-list-aware
extension of that module's frontmatter parsing, since `children:`/`governs:`
are YAML lists design_doc.py's own minimal parser explicitly skips.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
# An inline list: `key: [a, b, c]`.
_INLINE_LIST_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*\[(.*)\]\s*$")
# A block-list key with no inline value: `key:` (optionally followed by a comment).
_BLOCK_LIST_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(?:#.*)?$")
# A block-list item: `  - value` (optionally with a trailing comment).
_BLOCK_LIST_ITEM_RE = re.compile(r"^\s*-\s*(.+?)\s*(?:#.*)?$")


def parse_frontmatter_lists(text: str) -> dict:
    """Top-level YAML list-valued frontmatter keys (`children:`, `governs:`,
    etc.), both inline (`key: [a, b]`) and block style (`key:\\n  - a\\n  - b`).
    Scalar keys are not parsed here -- design_doc.py's `parse_frontmatter`
    already owns those; this is additive, not a replacement.

    Returns {} if there is no frontmatter block at all. A key with no list
    value found (scalar, or absent) is simply not in the returned dict --
    never an error, matching design_doc.py's graceful-on-absence philosophy."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    lines = m.group(1).splitlines()
    result: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        inline = _INLINE_LIST_RE.match(line)
        if inline:
            key, body = inline.group(1), inline.group(2)
            items = [s.strip().strip("'\"") for s in body.split(",") if s.strip()]
            result[key] = items
            i += 1
            continue
        block_key = _BLOCK_LIST_KEY_RE.match(line)
        if block_key:
            key = block_key.group(1)
            items = []
            j = i + 1
            while j < len(lines) and _BLOCK_LIST_ITEM_RE.match(lines[j]):
                items.append(_BLOCK_LIST_ITEM_RE.match(lines[j]).group(1).strip("'\""))
                j += 1
            if items:
                result[key] = items
                i = j
                continue
        i += 1
    return result


def composition_analysis(doc_path: Path) -> dict:
    """The parsed composition claim: which sub-designs (`children:`) this
    doc composes, and what code it governs (`governs:`). `is_multi_system`
    is true once the doc composes 2+ children -- the frontmatter-level
    signal that this is an architecture-rung doc, not a single-system one."""
    text = Path(doc_path).read_text(encoding="utf-8")
    lists = parse_frontmatter_lists(text)
    children = lists.get("children", [])
    governs = lists.get("governs", [])
    return {"children": children, "governs": governs, "is_multi_system": len(children) >= 2}


def architecture_review(doc_path: Path) -> dict:
    """Reviews the composition claim mechanically: every child in
    `children:` must resolve to a real file alongside the parent doc (the
    same directory -- agentm-hld.md's own children: convention). A
    dangling child is a broken composition claim.

    Returns {"resolved": [...], "missing": [...], "passed": bool}."""
    doc_path = Path(doc_path)
    analysis = composition_analysis(doc_path)
    resolved, missing = [], []
    for child in analysis["children"]:
        if (doc_path.parent / child).is_file():
            resolved.append(child)
        else:
            missing.append(child)
    return {"resolved": resolved, "missing": missing, "passed": not missing}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Architecture-rung composition-analysis + review for /design")
    sub = parser.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("analyze", help="print the composition-analysis artifact as JSON")
    a.add_argument("path")
    r = sub.add_parser("review", help="exit 0 iff every declared child resolves, else 2 + the missing list")
    r.add_argument("path")
    args = parser.parse_args(argv)

    if args.mode == "analyze":
        print(json.dumps(composition_analysis(args.path)))
        return 0
    result = architecture_review(args.path)
    if result["passed"]:
        print(json.dumps(result))
        return 0
    sys.stderr.write(
        f"[architecture_rung] broken composition claim in {args.path}: "
        f"missing children {result['missing']!r}\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
