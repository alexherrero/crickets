#!/usr/bin/env python3
"""depth_maintain.py — the Planner (TPM) persona's depth-floor maintainer.

AG Wave D. `check_project_sync.py` stays the drift **oracle** (unchanged, per
the plan's own constraint) — this is a *new*, separate module the Planner
persona's activation calls into, sitting one layer above it: it looks for a
Version->Feature->Plan->Task chain that has **collapsed below the >=4 depth
floor** the design (`crickets-github-projects.md` "The depth floor — at least
four") names, and either **materializes** the missing intermediate level or
**flags it for operator judgment** when materialization would require content
this module cannot infer (e.g. what a Feature's Plans should actually be
named). Two levels are checked, symmetrically:

**Feature -> Plan.** A Feature (or Sub-feature) has **zero materialized Plan
children** in the graph, while a **real, on-disk plan file** exists that the
operator intends for that Feature. Nothing in `project_model.py`'s schema
links a Feature's board-item id to a vault plan file's slug (no `plan_id`
field, confirmed against `project_schema.json` and the graph's `Item`
dataclass) — so this module never *guesses* that link via fuzzy title
matching, which would risk silently materializing the wrong Plan under the
wrong Feature. It recognizes exactly two **explicit** signals, and flags for
operator judgment when neither is present:

1. **Slug-equals-feature-id** — a plan file `PLAN-<feature_id>.md` exists (the
   plan file is named after the Feature's own board-item id). This is the
   zero-config convention: name the plan file after the feature you're
   breaking down and it materializes automatically.
2. **Explicit `fields.plan_slug`** — the Feature item's `fields` dict names the
   plan slug directly (`{"plan_slug": "some-other-slug"}`), for the case where
   the plan file's name legitimately differs from the feature id (e.g. an
   AG-track feature whose plan predates a rename). An explicit field always
   wins over the id-equality convention when both are present.

**Plan -> Task.** A Plan that is ALREADY a materialized graph item (bound to
a known slug — a Plan only exists in the graph at all once matched at the
Feature level above, or authored directly) has **zero materialized Task
children**, while its own bound `PLAN-<slug>.md` file's task checklist (the
`### N. <title>` headings every plan in this harness already uses — the same
convention `queue_status_lite`/`resolve_plan` treat as load-bearing) lists
real tasks. Unlike the Feature level, there is no id-matching ambiguity here:
the Plan's own graph id already carries the slug that resolved it, so a
missing Task is unambiguously "this plan's own checklist has an entry with no
board-item counterpart yet" — always auto-materializable, never flagged.

Materialization itself never invents a Plan's `title`/`goal`/`done_when` or a
Task's `title` beyond what the source file already states (a plan's H1, or a
task heading's own text) — it appends a minimal Item to the graph and lets the
existing `project_sync.py`/`sync_all_nesting()` primitives do the actual board
write on the next `post`/`sync-nesting` run. This module only ever edits the
in-memory graph (or `board-items.json` via the existing `project_model.dump()`);
it never calls `gh` itself — reuses `project_sync.py`'s write path, never
duplicates it.

stdlib only.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _project_model():
    return sys.modules.get("project_model") or _load("project_model", _HERE / "project_model.py")


_DEPTH_HOLDING_TYPES = frozenset({"feature", "sub-feature"})

# Matches "PLAN-<slug>.md" (the active-plan naming contract every sibling
# resolver in this repo agrees on: resolve_plan.py, queue_status_lite.py).
# Excludes the singleton "PLAN.md" (no slug) and "PLAN.archive.*" (the `PLAN-`
# vs `PLAN.` distinction the existing listers already rely on).
_PLAN_FILE_RE = re.compile(r"^PLAN-(?P<slug>.+)\.md$")

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# A plan's own task checklist headings: "### 1. Do the thing" (the convention
# every plan in this harness already uses — see PLAN-wave-d-github-projects.md
# itself). Captures the task's number (for a stable, deterministic id) and its
# title text.
_TASK_HEADING_RE = re.compile(r"^###\s+(?P<num>\d+)\.\s+(?P<title>.+?)\s*$", re.MULTILINE)


@dataclass
class DepthGap:
    """One Feature/Sub-feature found below the depth floor."""
    feature_id: str
    feature_title: str
    matched_slug: str | None   # the plan slug resolved to materialize, or None
    plan_path: "Path | None"   # the on-disk PLAN-<slug>.md, when matched_slug is set
    reason: str                # why flagged, when matched_slug is None

    @property
    def plan_item_id(self) -> "str | None":
        """The board-item id the materialized Plan gets — the matched slug,
        namespaced with a `plan-` prefix when it collides with the Feature's
        own id (the id-equality-match convention names a *file*, not a board
        item; the Plan and its parent Feature must never share one graph key)."""
        if self.matched_slug is None:
            return None
        return f"plan-{self.matched_slug}" if self.matched_slug == self.feature_id \
            else self.matched_slug


def list_plan_slugs(harness_dir) -> dict:
    """Every *active* plan slug -> its file path in `harness_dir`.

    Reuses the same `PLAN-<slug>.md` naming contract `resolve_plan.py` and
    `queue_status.py` already enumerate against (never re-derives it) — this
    is purely a slug->Path index for depth_maintain's own matching, not a
    second lister.
    """
    hd = Path(harness_dir)
    out: dict = {}
    if not hd.is_dir():
        return out
    for p in hd.glob("PLAN-*.md"):
        if not p.is_file() or "(conflicted copy" in p.name:
            continue
        m = _PLAN_FILE_RE.match(p.name)
        if m:
            out[m.group("slug")] = p
    return out


def _plan_title(plan_path: Path) -> str:
    """The plan file's own H1 heading text, or its slug-derived filename when
    the file has no H1 (never raises — a materialized Plan always gets SOME
    title rather than blocking on a formatting quirk)."""
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return plan_path.stem
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else plan_path.stem


def find_depth_gaps(graph: dict, plan_slugs: dict) -> list:
    """Scan `graph` for a Feature/Sub-feature with zero materialized Plan
    children, matched against `plan_slugs` (slug -> Path, from
    `list_plan_slugs`). Returns a `DepthGap` for every such item — with
    `matched_slug` set (auto-materializable) or `reason` set (operator-flagged).

    A Feature with children is always skipped, including one whose only
    children are `sub-feature` — depth is measured per level, and a
    sub-feature is itself checked independently as its own potential gap.
    """
    gaps: list = []
    for item in graph.values():
        if item.type not in _DEPTH_HOLDING_TYPES:
            continue
        has_plan_child = any(c.type == "plan" for c in item.children)
        if has_plan_child:
            continue

        explicit_slug = (item.fields or {}).get("plan_slug")
        if explicit_slug:
            plan_path = plan_slugs.get(explicit_slug)
            if plan_path is not None:
                gaps.append(DepthGap(item.id, item.title, explicit_slug, plan_path, ""))
            else:
                gaps.append(DepthGap(
                    item.id, item.title, None, None,
                    f"fields.plan_slug={explicit_slug!r} names a plan that isn't "
                    f"an active PLAN-{explicit_slug}.md — flagged, not materialized"))
            continue

        plan_path = plan_slugs.get(item.id)
        if plan_path is not None:
            gaps.append(DepthGap(item.id, item.title, item.id, plan_path, ""))
            continue

        # No explicit signal at all. A Feature with genuinely no active plan
        # yet (the common, correct case — DC-1's "future plans/tasks live
        # implicitly under their already-materialized feature") is NOT a gap;
        # only flag when there's a *real, un-nested* plan this module can see
        # but cannot confidently attribute. Since neither signal matched,
        # there is nothing to flag either — silently no-op (this is the
        # expected steady state, not a defect).
    return gaps


@dataclass
class TaskGap:
    """One materialized Plan found with zero Task children, while its own
    bound plan file's checklist lists real tasks."""
    plan_id: str
    plan_path: Path
    missing: list   # [(task_num: str, title: str), ...] not yet in the graph


def find_task_gaps(graph: dict, plan_slugs: dict) -> list:
    """Scan `graph` for a materialized `plan` item with zero Task children,
    whose own bound `PLAN-<plan.id>.md` (from `plan_slugs`) lists `### N.
    <title>` task headings not yet represented as Task items under it.

    Unlike `find_depth_gaps`, there is no id-ambiguity to flag here: a Plan
    only ever exists in the graph bound to the slug that resolved it, so its
    own checklist is unambiguously *its* source of truth — always
    auto-materializable, never a TaskGap with nothing to flag against.
    A Plan whose slug has no corresponding `PLAN-<slug>.md` on disk (e.g. an
    already-completed/archived plan with no live task-file) is skipped, not
    flagged — an archived plan's Task breakdown is history, not a gap.
    """
    gaps: list = []
    for item in graph.values():
        if item.type != "plan":
            continue
        if any(c.type == "task" for c in item.children):
            continue
        plan_path = plan_slugs.get(item.id)
        if plan_path is None:
            continue
        try:
            text = plan_path.read_text(encoding="utf-8")
        except OSError:
            continue
        headings = _TASK_HEADING_RE.findall(text)
        if headings:
            gaps.append(TaskGap(item.id, plan_path, list(headings)))
    return gaps


def materialize_task_gap(gap: TaskGap, graph: dict) -> list:
    """Add a minimal Task Item for each of `gap.missing`'s headings into
    `graph` IN PLACE (id = "<plan_id>-t<N>", parent = gap.plan_id, title =
    the heading's own text). Idempotent — skips a task-number id that's
    already present, so a re-run over unchanged state adds nothing twice.
    Returns the list of newly-added Items (empty when all already exist).
    """
    pm = _project_model()
    added = []
    for num, title in gap.missing:
        item_id = f"{gap.plan_id}-t{num}"
        if item_id in graph:
            continue
        item = pm.Item(id=item_id, type="task", title=title.strip(), parent=gap.plan_id)
        graph[item.id] = item
        graph[gap.plan_id].children.append(item)
        added.append(item)
    return added


def materialize_gap(gap: DepthGap, graph: dict) -> "object | None":
    """Add a minimal Plan Item for an auto-materializable `gap` into `graph`
    IN PLACE (id = gap.plan_item_id, parent = gap.feature_id, title = the plan
    file's own H1). No-op (returns None) for a flagged (non-materializable)
    gap, or if a Plan with that id already exists (idempotent — a second run
    over unchanged state adds nothing twice).

    Never writes `board-items.json` itself and never calls `gh` — the caller
    persists via `project_model.dump()` and syncs via the existing
    `project_sync.py`/`sync_all_nesting()` write path on its own next run,
    exactly like every other graph mutation in this plugin.
    """
    item_id = gap.plan_item_id
    if item_id is None:
        return None
    pm = _project_model()
    if item_id in graph:
        return None  # already materialized — idempotent no-op
    title = _plan_title(gap.plan_path) if gap.plan_path else gap.matched_slug
    item = pm.Item(id=item_id, type="plan", title=title, parent=gap.feature_id)
    graph[item.id] = item
    graph[gap.feature_id].children.append(item)
    return item


def run(graph: dict, harness_dir, *, materialize=True) -> dict:
    """The depth-maintainer's one entrypoint: find gaps at both levels
    (Feature->Plan, Plan->Task), optionally materialize the auto-resolvable
    ones in place. Returns a summary dict:

        {"materialized": [Item, ...], "flagged": [DepthGap, ...]}

    `materialize=False` previews only (no graph mutation) — mirrors the
    dry-run boundary the rest of this plugin already uses. Feature->Plan runs
    first so a newly-materialized Plan is immediately eligible for its own
    Plan->Task pass in the same cycle (its bound plan file's checklist is
    checked right away, not only on a later run).
    """
    plan_slugs = list_plan_slugs(harness_dir)
    materialized = []
    flagged = []

    for gap in find_depth_gaps(graph, plan_slugs):
        if gap.matched_slug is not None:
            if materialize:
                item = materialize_gap(gap, graph)
                if item is not None:
                    materialized.append(item)
        else:
            flagged.append(gap)

    if materialize:
        for task_gap in find_task_gaps(graph, plan_slugs):
            materialized.extend(materialize_task_gap(task_gap, graph))

    return {"materialized": materialized, "flagged": flagged}


# ── CLI ──────────────────────────────────────────────────────────────────────
def _build_parser():
    import argparse
    p = argparse.ArgumentParser(prog="depth_maintain.py")
    p.add_argument("--config", required=True, help="path to project.json")
    p.add_argument("--harness-dir", required=True,
                   help="the _harness/ dir to scan for active PLAN-<slug>.md files")
    p.add_argument("--dry-run", action="store_true",
                   help="preview only — print gaps/materializations, write nothing")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    here = Path(__file__).resolve().parent
    ps = _load("project_sync", here / "project_sync.py")
    pm = _project_model()

    cfg = ps.load_config(args.config)
    items_path = ps._items_path_from_cfg(cfg, args.config)
    graph = pm.load(items_path)

    result = run(graph, args.harness_dir, materialize=not args.dry_run)
    for item in result["materialized"]:
        print(f"materialized {item.type}:{item.id} under {item.parent}")
    for gap in result["flagged"]:
        print(f"FLAGGED  feature:{gap.feature_id} ({gap.feature_title!r}) — {gap.reason}")
    if not args.dry_run and result["materialized"]:
        pm.dump(graph, items_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
