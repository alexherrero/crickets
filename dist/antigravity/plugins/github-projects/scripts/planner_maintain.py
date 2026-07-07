#!/usr/bin/env python3
"""planner_maintain.py — the Planner (TPM) persona's one composed entrypoint.

AG Wave D, task 4. Runs `depth_maintain.py` (task 2) then `drift_correct.py`
(task 3) end to end against the same resolved `board-items.json`, in that
order — a newly depth-materialized Plan/Task becomes eligible for its own
drift classification in the same cycle, same as `depth_maintain.run()`'s own
internal Feature->Plan-then-Plan->Task cascade. Neither underlying module is
modified by this file; it is purely a composition + a single persisted write
at the end (`project_model.dump()`, once, after both passes) — never two
separate saves racing each other.

**Why this file exists, given no persona-activation dispatcher exists yet.**
A live grounding check this task (AG Wave D) ran against agentm found the
persona-activation plumbing built in "AG Wave B" (`persona_resolve.py`,
`persona_compile.py`) validates a persona's `modes:`/`triggers:` frontmatter
for SHAPE only — there is no dispatcher anywhere that reads `modes: [loop,
sub-agent]` and branches actual behavior, and no existing call site wires a
persona's `triggers:` to an invocation of anything. That plumbing, and the
`team-coordinator.md` manifest itself (the Planner's seed, authored in
`PLAN-wave-d-personas`), both live in agentm — outside this crickets-side
worktree's authority per this plan's own guardrail (stop rather than reach
across repos). So this task cannot wire "the Planner activates and this runs"
end-to-end today; what it CAN do, entirely within crickets, is give the
Planner's future activation something concrete to call, and wire the one
real workflow-step gate that already exists in this repo (`/work` step 10 and
`/release` step 7/8 already call `project_sync.py post` at a graceful-skip
board-sync gate) to also run it. When the agentm-side activation dispatcher
ships, it calls this same script — no further crickets-side wiring needed.

    planner_maintain.py --config <project.json> --harness-dir <dir> [--dry-run]

Exit codes: 0 clean (nothing materialized, nothing flagged); 1 something was
flagged for operator judgment (a depth gap needing content this module can't
infer, or a drift orphan) — informational, not a hard failure signal for a
graceful-skip caller; 2 an operational error (bad config, `gh` failure).

stdlib only.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _siblings():
    pm = _load("project_model", _HERE / "project_model.py")
    ps = _load("project_sync", _HERE / "project_sync.py")
    cps = _load("check_project_sync", _HERE / "check_project_sync.py")
    dm = _load("depth_maintain", _HERE / "depth_maintain.py")
    dc = _load("drift_correct", _HERE / "drift_correct.py")
    return pm, ps, cps, dm, dc


def run(graph: dict, cfg: dict, config_path, harness_dir, templates_dir,
       board_bodies, items_path, *, pm, ps, dm, dc, active_plans=None,
       public=True, runner=None, dry_run=True, out=None) -> dict:
    """The Planner's one composed cycle: depth-maintenance, then
    drift-correction, over the SAME in-memory graph (so a Plan/Task the
    depth pass just added is visible to the drift pass's own re-derivation).

    The drift pass shells out to `project_sync.py post` (`drift_correct.py`'s
    own contract — it reuses that write path rather than duplicating it),
    which re-reads `board-items.json` from disk rather than sharing this
    in-memory graph. So when live (not `dry_run`) and the depth pass
    materialized anything, this persists the graph via `project_model.dump()`
    BEFORE the drift pass runs — otherwise a Plan/Task depth-maintenance just
    added would be invisible to `post`'s own disk read. Under `dry_run` no
    intermediate persist happens (a preview must never write, even between
    its own two internal steps). Returns:

        {"depth_materialized": [Item, ...], "depth_flagged": [DepthGap, ...],
         "drift_corrected": [item_id, ...], "drift_flagged": [issue_num, ...]}
    """
    depth_result = dm.run(graph, harness_dir, materialize=not dry_run)
    if not dry_run and depth_result["materialized"]:
        pm.dump(graph, items_path)
    drift_result = dc.run(graph, cfg, config_path, templates_dir, board_bodies,
                          pm=pm, ps=ps, active_plans=active_plans, public=public,
                          runner=runner, dry_run=dry_run, out=out)
    return {
        "depth_materialized": depth_result["materialized"],
        "depth_flagged": depth_result["flagged"],
        "drift_corrected": drift_result["corrected"],
        "drift_flagged": drift_result["flagged"],
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def _default_config() -> Path:
    return Path(".harness/project.json")


def main(argv=None, *, runner=None, fetch=None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="planner_maintain.py")
    p.add_argument("--config", help="path to project.json (default: .harness/project.json)")
    p.add_argument("--harness-dir", help="the _harness/ dir to scan for active PLAN-<slug>.md "
                                        "files (default: the config's own directory)")
    p.add_argument("--active-plan", action="append", default=[], dest="active_plans",
                  help="plan id to materialize (repeatable)")
    p.add_argument("--private", action="store_true",
                  help="diff against the private render (keep silent-source)")
    p.add_argument("--dry-run", action="store_true",
                  help="preview only — print what would happen, write/post nothing")
    args = p.parse_args(argv)

    cfg_path = Path(args.config) if args.config else _default_config()
    if not cfg_path.exists():
        print(f"planner_maintain: no project.json at {cfg_path} — "
             f"skipping (not a board-synced repo)")
        return 0
    if fetch is None and shutil.which("gh") is None:
        print("planner_maintain: gh not on PATH — skipping")
        return 0

    pm, ps, cps, dm, dc = _siblings()
    cfg = ps.load_config(cfg_path)
    items_path = ps._items_path_from_cfg(cfg, cfg_path)
    graph = pm.load(items_path)
    templates_dir = _HERE.parent / "templates"
    harness_dir = Path(args.harness_dir) if args.harness_dir else cfg_path.resolve().parent

    board = fetch(cfg) if fetch is not None else cps.fetch_board_bodies(cfg, runner=runner)
    result = run(graph, cfg, cfg_path, harness_dir, templates_dir, board, items_path,
                pm=pm, ps=ps, dm=dm, dc=dc, active_plans=set(args.active_plans),
                public=not args.private, runner=runner, dry_run=args.dry_run)

    for item in result["depth_materialized"]:
        print(f"materialized {item.type}:{item.id} under {item.parent}")
    for gap in result["depth_flagged"]:
        print(f"FLAGGED  feature:{gap.feature_id} ({gap.feature_title!r}) — {gap.reason}")
    for item_id in result["drift_corrected"]:
        print(f"corrected {item_id}")
    for issue in result["drift_flagged"]:
        print(f"FLAGGED  orphan issue #{issue} — needs operator judgment")

    # run() already persisted the depth-materialized graph BEFORE the drift
    # pass (see its own docstring) when live; nothing further to save here.
    return 1 if (result["depth_flagged"] or result["drift_flagged"]) else 0


if __name__ == "__main__":
    sys.exit(main())
