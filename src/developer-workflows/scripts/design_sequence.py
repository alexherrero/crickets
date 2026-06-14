#!/usr/bin/env python3
"""Topo-order a design's `parts/` into a deterministic plan sequence (sibling #5).

`design_sequence.py` is the deterministic ordering core behind `/design
sequence`: read `<doc-dir>/parts/*.md`, validate each part's frontmatter, build
the dependency DAG keyed by `part_slug`, and Kahn-topo-sort it with an
**alphabetical tie-break** so the same parts always yield the same order. Cycles
and dangling dependencies are loud refusals (exit 2) — never a guessed order.

    design_sequence.py order <parts-dir>    # print the topo-ordered slugs, one per line

The command body (`commands/design.md`) owns the part→PLAN-body mapping and the
`stage_plan.py` wiring (first slug `activate`d → `PLAN-<doc-slug>-<part-slug>.md`,
the rest staged into `queued-plans/`) — the interactive / judgment work. This
helper owns only the falsifiable ordering, unit-tested like its siblings
(`resolve_plan.py` / `stage_plan.py` / `design_doc.py`).

**Stdlib-only — no PyYAML** (same constraint as the sibling helpers: PyYAML is
repo-CI-only, not on the plugin runtime). Scalar frontmatter is read through
`design_doc.parse_frontmatter`; the `dependencies:` list is parsed here, handling
both the inline form translate writes (`dependencies: [a, b]`) and a YAML block
form (`dependencies:` then indented `- a` lines) so a hand-edited part can't
silently drop its edges.

Exit codes (aligned with the sibling helpers so the surface is transparent):
    0 — ok; the topo-ordered slugs, one per line, on stdout.
    2 — loud: empty/missing dir, invalid part frontmatter, missing-dep, or a cycle.
"""
from __future__ import annotations

import argparse
import heapq
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# One owner of the minimal stdlib-only frontmatter parse (and the leading-block
# regex). design_doc is a sibling in this same scripts dir.
import design_doc  # noqa: E402

_SCOPE_VALUES = ("S", "M", "L")
_DEPENDENCIES_RE = re.compile(r"^dependencies:", re.MULTILINE)


# ── dependency-list parsing (inline + block forms) ───────────────────────────────

def _parse_inline_list(raw: str) -> list[str]:
    """`[a, b]` (or `[]`) → ['a', 'b'] (or []). Strips quotes + blanks."""
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    items = []
    for tok in inner.split(","):
        t = tok.strip().strip("'\"").strip()
        if t:
            items.append(t)
    return items


def _dependencies_from_block(fm_text: str) -> list[str]:
    """Parse the `dependencies:` value from the raw frontmatter block.

    Supports the inline form translate writes (`dependencies: [a, b]`) and a YAML
    block form (`dependencies:` then following indented `- item` lines). Returns
    [] when the value is absent or empty. Reading the block form explicitly keeps
    a hand-edited part from silently dropping its edges (the scalar parser would
    skip the indented lines).
    """
    lines = fm_text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("dependencies:"):
            continue
        inline = line.partition(":")[2].strip()
        if inline:
            return _parse_inline_list(inline)
        deps = []
        for nxt in lines[i + 1:]:
            if nxt[:1] in (" ", "\t"):
                s = nxt.strip()
                if s.startswith("-"):
                    item = s[1:].strip().strip("'\"").strip()
                    if item:
                        deps.append(item)
                continue
            break  # back to column 0 → the dependencies block ended
        return deps
    return []


# ── read + validate parts ────────────────────────────────────────────────────────

def read_parts(parts_dir: str) -> tuple[list[dict] | None, str]:
    """Read + validate `<parts-dir>/*.md`; (parts, "") or (None, reason).

    Each part dict is {slug, deps, scope, path}. Refuses (None, reason) on an
    empty/missing dir, a file with no frontmatter, a missing/blank `part_slug`,
    a missing `dependencies` key (use `[]` for none), an `estimated_scope` not in
    S|M|L, or a duplicate `part_slug`. Never auto-repairs — the validation IS the
    contract between translate's output and sequence's input.
    """
    d = Path(parts_dir)
    if not d.is_dir():
        return (None, f"{d} does not exist; run /design translate <slug> first to "
                      f"generate the structural parts.")
    files = sorted(d.glob("*.md"))
    if not files:
        return (None, f"{d} contains zero part files; /design translate either failed "
                      f"or was cancelled. Re-run /design translate.")
    parts: list[dict] = []
    seen: dict[str, Path] = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as exc:
            return (None, f"cannot read {f}: {exc}")
        fm = design_doc.parse_frontmatter(text)
        if fm is None:
            return (None, f"{f}: no YAML frontmatter found — not a valid part file. "
                          f"Not auto-repairing.")
        slug = fm.get("part_slug")
        if not slug:
            return (None, f"{f}: missing required field 'part_slug' in frontmatter.")
        scope = fm.get("estimated_scope")
        if scope not in _SCOPE_VALUES:
            return (None, f"{f}: 'estimated_scope' must be one of "
                          f"{'|'.join(_SCOPE_VALUES)} (got {scope!r}).")
        m = design_doc._FRONTMATTER_RE.match(text)
        fm_text = m.group(1) if m else ""
        if not _DEPENDENCIES_RE.search(fm_text):
            return (None, f"{f}: missing required field 'dependencies' "
                          f"(use '[]' for a foundational part with none).")
        if slug in seen:
            return (None, f"duplicate part_slug {slug!r} in {seen[slug]} and {f}; "
                          f"each part needs a unique slug.")
        seen[slug] = f
        parts.append({"slug": slug, "deps": _dependencies_from_block(fm_text),
                      "scope": scope, "path": f})
    return (parts, "")


# ── topological sort (Kahn + alphabetical tie-break) ─────────────────────────────

def _find_cycle(deps_by: dict[str, list[str]], nodes: list[str]) -> list[str] | None:
    """A concrete cycle path among `nodes`, following dependency edges (s → dep).

    DFS for a back-edge; returns e.g. ['a', 'b', 'a'] (a depends on b depends on
    a), or None if none found. Used only for the refusal message after Kahn has
    proven a cycle exists.
    """
    nodeset = set(nodes)
    visited: set[str] = set()
    onstack: set[str] = set()
    stack: list[str] = []

    def dfs(u: str) -> list[str] | None:
        visited.add(u)
        onstack.add(u)
        stack.append(u)
        for dep in deps_by.get(u, []):
            if dep not in nodeset:
                continue
            if dep in onstack:
                return stack[stack.index(dep):] + [dep]
            if dep not in visited:
                found = dfs(dep)
                if found:
                    return found
        stack.pop()
        onstack.discard(u)
        return None

    for n in sorted(nodes):
        if n not in visited:
            found = dfs(n)
            if found:
                return found
    return None


def topo_order(parts: list[dict]) -> tuple[list[str] | None, str]:
    """Kahn topo-sort the parts → ordered slugs, alphabetical within a level.

    (order, "") on success; (None, reason) on a missing dependency (a dep slug
    not present in parts/) or a cycle (with a concrete path). Determinism comes
    from a min-heap ready-set: re-running on the same parts/ yields an identical
    order, so `queued-plans/` ordering never churns across runs.
    """
    slugs = {p["slug"] for p in parts}
    deps_by = {p["slug"]: list(p["deps"]) for p in parts}

    for p in parts:
        for dep in p["deps"]:
            if dep not in slugs:
                return (None, f"part {p['slug']!r} depends on {dep!r} which does not "
                              f"exist in parts/. Remove the dependency or create the "
                              f"missing part.")

    indeg = {s: 0 for s in slugs}
    succ: dict[str, list[str]] = {s: [] for s in slugs}
    for s in slugs:
        for dep in deps_by[s]:  # edge dep → s ("dep must come before s")
            succ[dep].append(s)
            indeg[s] += 1

    ready = [s for s in slugs if indeg[s] == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        s = heapq.heappop(ready)
        order.append(s)
        for nb in succ[s]:
            indeg[nb] -= 1
            if indeg[nb] == 0:
                heapq.heappush(ready, nb)

    if len(order) < len(slugs):
        remaining = sorted(slugs - set(order))
        cycle = _find_cycle(deps_by, remaining)
        path = " → ".join(cycle) if cycle else " → ".join(remaining)
        return (None, f"dependency cycle detected: {path}. Edit parts/ files to break "
                      f"the cycle and re-run.")
    return (order, "")


def sequence(parts_dir: str) -> tuple[int, str, str]:
    """(rc, stdout, stderr): the topo-ordered slugs, or a loud refusal.

    Composes read_parts + topo_order. rc 0 + newline-joined slugs on success;
    rc 2 + reason (no stdout) on any validation / graph failure.
    """
    parts, err = read_parts(parts_dir)
    if parts is None:
        return (2, "", f"[design_sequence] {err}\n")
    order, oerr = topo_order(parts)
    if order is None:
        return (2, "", f"[design_sequence] {oerr}\n")
    return (0, "".join(f"{s}\n" for s in order), "")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="design_sequence.py",
        description="Topo-order a design's parts/ into a deterministic plan sequence.",
    )
    sub = p.add_subparsers(dest="mode", required=True)
    o = sub.add_parser("order", help="print the topo-ordered part slugs, one per line")
    o.add_argument("parts_dir", help="path to the design's parts/ directory")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    rc, out, err = sequence(ns.parts_dir)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
