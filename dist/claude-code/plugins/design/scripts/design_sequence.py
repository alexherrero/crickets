#!/usr/bin/env python3
"""Topo-order a design's `parts/` into a deterministic plan sequence (sibling #5).

`design_sequence.py` is the deterministic ordering core behind `/design
sequence`: read `<parts-dir>/*.md`, validate each part's frontmatter, build
the dependency DAG keyed by `part_slug`, and Kahn-topo-sort it with an
**alphabetical tie-break** so the same parts always yield the same order. Cycles
and dangling dependencies are loud refusals (exit 2) — never a guessed order.

    design_sequence.py order <parts-dir>             # the topo-ordered slugs, one per line
    design_sequence.py check-names <name>...          # refuse, before any write
    design_sequence.py place <name> --body <file> --design <slug> --part <slug>

The command body (`commands/design.md`) owns the part→plan-body mapping — the
interactive / judgment work. This helper owns the falsifiable pieces: the
ordering, and placing each part as a new numbered task whose tracker says
`queued`. Where a task goes is agentm's answer, through development-lifecycle's
`resolve_plan.py`; its tracker is opened by development-lifecycle's
`plan_tracker.py`. No part is activated, and nothing is ever written to a flat
staging directory: a project that keeps no tasks is refused before any write.

**Stdlib-only — no PyYAML** (same constraint as the sibling helpers: PyYAML is
repo-CI-only, not on the plugin runtime). Scalar frontmatter is read through
`design_doc.parse_frontmatter`; the `dependencies:` list is parsed here, handling
both the inline form translate writes (`dependencies: [a, b]`) and a YAML block
form (`dependencies:` then indented `- a` lines) so a hand-edited part can't
silently drop its edges.

Exit codes (aligned with the sibling helpers so the surface is transparent):
    0 — ok; the topo-ordered slugs, one per line, on stdout (`order`), or the
        new task's plan path (`place`).
    2 — loud: empty/missing dir, invalid part frontmatter, missing-dep, or a cycle;
        or a name that cannot become a new queued task (`check-names`, `place`).
    other — the resolver's or plan_tracker.py's own code, with its reason.
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
            if not nxt.strip():
                continue  # blank line: a legal YAML continuation, not the block end
            if nxt[:1] in (" ", "\t"):
                s = nxt.strip()
                if s.startswith("-"):
                    item = s[1:].strip().strip("'\"").strip()
                    if item:
                        deps.append(item)
                continue
            break  # a non-blank line back at column 0 → a new key; the block ended
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
    order, so the queued tasks come out in the same order on every run.
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


# ── placing parts as queued tasks ──────────────────────────────────────────────
#
# Every part becomes a numbered task whose tracker says `queued`. Where the task
# goes is agentm's answer, through development-lifecycle's resolver; its tracker
# is written by development-lifecycle's plan_tracker.py (agentm's tracker.py
# underneath). Nothing here composes a project path.

_TASK_PLAN = "plan.md"
_DL = "development-lifecycle"


def _dl_script(rel: str) -> "Path | None":
    """A development-lifecycle script, found through this plugin's resolver
    (design `requires:` development-lifecycle; Claude Code installs each plugin
    in its own versioned directory)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("design_sibling_plugin",
                                                  _HERE / "sibling_plugin.py")
    finder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(finder)
    # Spelled out, one call per script, so test_sibling_plugin.py sees each call
    # site and proves it resolves inside Claude Code's versioned cache.
    calls = {
        "scripts/resolve_plan.py":
            lambda: finder.resolve_sibling("development-lifecycle", "scripts/resolve_plan.py"),
        "scripts/plan_tracker.py":
            lambda: finder.resolve_sibling("development-lifecycle", "scripts/plan_tracker.py"),
    }
    return calls[rel]() if rel in calls else None


def _run_dl(rel: str, args: "list[str]") -> "tuple[int, str, str]":
    import subprocess
    script = _dl_script(rel)
    if script is None:
        return (2, "", f"{rel} not found in the {_DL} plugin — design requires it\n")
    r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)
    return (r.returncode, r.stdout, r.stderr)


def where_task(name: str, root: str, *, run=None) -> "tuple[int, list[str], str]":
    """(rc, [plan, progress, tracker], reason): where agentm places the task
    `name` for the project `root` is bound to."""
    run = run or _run_dl
    rc, out, err = run("scripts/resolve_plan.py", [name, "--project-root", root])
    if rc != 0:
        return (rc, [], err.strip() or f"resolve_plan exited {rc}")
    fields = out.rstrip("\n").split("\t")
    return (0, (fields + ["", "", ""])[:3], "")


def check_names(names: "list[str]", root: str, *, run=None) -> "tuple[int, str]":
    """(rc, reason): whether every name can become a new queued task. Refuses,
    before anything is written, when agentm places a name outside a task (the
    project keeps no tasks), names no tracker for it, or a task by that name
    already exists."""
    for name in names:
        rc, fields, reason = where_task(name, root, run=run)
        if rc != 0:
            return (rc, f"'{name}': {reason}")
        plan, _progress, tracker = fields
        if Path(plan).name != _TASK_PLAN:
            return (2, f"'{name}': agentm placed it at {plan}, not in a task — this project "
                       "keeps no tasks, and /design sequence opens only queued tasks")
        if not tracker:
            return (2, f"'{name}': agentm names no tracker for it, and a queued task needs one")
        if Path(plan).exists():
            return (2, f"'{name}': a task by that name already exists ({Path(plan).parent}) "
                       "— refusing to write over it")
    return (0, "")


def place(name: str, body: str, root: str, *, design: str, part: str,
          today: str, run=None) -> "tuple[int, str]":
    """Write one part's plan into the new task agentm places for `name`, open
    its tracker at `queued`, and log the placement. (rc, plan path or reason).

    One part at a time: agentm numbers a new task from the task directories
    that exist, so the next part is placed only after this one is written.
    """
    run = run or _run_dl
    rc, reason = check_names([name], root, run=run)
    if rc != 0:
        return (rc, reason)
    _rc, (plan, progress, tracker), _ = where_task(name, root, run=run)
    task = Path(plan).parent
    task.mkdir(parents=True)  # the task directory agentm named; it is what makes the task exist
    Path(plan).write_text(body, encoding="utf-8")
    rc, _out, err = run("scripts/plan_tracker.py",
                        ["open", "--plan", plan, "--tracker", tracker, "--root", root])
    if rc != 0:
        return (rc, f"'{name}': the plan is written at {plan}, but its tracker did not open: "
                    f"{err.strip()}")
    if progress:
        with open(progress, "a", encoding="utf-8") as fh:
            fh.write(f"{today} /design sequence — queued task from design {design}, "
                     f"part {part}\n")
    return (0, plan)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="design_sequence.py",
        description="Topo-order a design's parts/ and open each as a queued task.",
    )
    sub = p.add_subparsers(dest="mode", required=True)
    o = sub.add_parser("order", help="print the topo-ordered part slugs, one per line")
    o.add_argument("parts_dir", help="path to the design's parts/ directory")
    c = sub.add_parser("check-names", help="refuse, before any write, a name that cannot "
                                           "become a new queued task")
    c.add_argument("names", nargs="+")
    c.add_argument("--project-root", default=None, help="project root (default: cwd)")
    pl = sub.add_parser("place", help="write one part's plan as a new queued task")
    pl.add_argument("name", help="the task name, <doc-slug>-<part-slug>")
    pl.add_argument("--body", required=True, help="file holding the plan body")
    pl.add_argument("--design", required=True, help="the design's slug")
    pl.add_argument("--part", required=True, help="the part's part_slug")
    pl.add_argument("--project-root", default=None, help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    import datetime
    import os
    ns = _build_parser().parse_args(argv[1:])
    if ns.mode == "check-names":
        rc, reason = check_names(ns.names, ns.project_root or os.getcwd())
        if reason:
            sys.stderr.write(f"[design_sequence] {reason}\n")
        return rc
    if ns.mode == "place":
        body = Path(ns.body).read_text(encoding="utf-8")
        rc, out = place(ns.name, body, ns.project_root or os.getcwd(), design=ns.design,
                        part=ns.part, today=datetime.date.today().isoformat())
        (sys.stdout if rc == 0 else sys.stderr).write(
            f"{out}\n" if rc == 0 else f"[design_sequence] {out}\n")
        return rc
    rc, out, err = sequence(ns.parts_dir)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
