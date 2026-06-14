#!/usr/bin/env python3
"""check_project_sync.py — the vault==board correctness gate (D-④).

A deterministic drift oracle for github-projects: compute the expected board
state from ``board-items.json`` (project_model's graph + project_sync's render
path) and diff it against the live board (read-only ``gh issue list``). Exit
non-zero on drift with a readable per-item report.

**Graceful-skip** (exit 0) when there's no ``project.json`` or no ``gh`` — so it
is a no-op in any repo that does not use the plugin and ``check-all.sh`` stays
green. The diff itself (``compute_drift``) is pure over an injected board
snapshot, so CI exercises it with fixtures and never touches the network; the
live ``gh`` fetch is the only side-effecting seam (read-only) and is injectable.

This is the post-run oracle for the backfill (task 9) and the standing gate that
keeps vault and board in sync once the phase hooks (task 7) drive updates.

stdlib only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


class CheckError(RuntimeError):
    """Raised on an operational failure (a `gh` call failed, config malformed) —
    distinct from *drift*, which is a clean non-zero exit with a report."""


# ── load the sibling helpers (duck-typed Item graph + render path) ────────────
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    # Register before exec: project_model's @dataclass under `from __future__
    # import annotations` resolves its own module via sys.modules.
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _siblings():
    here = Path(__file__).resolve().parent
    pm = _load("project_model", here / "project_model.py")
    ps = _load("project_sync", here / "project_sync.py")
    return pm, ps


# ── pure diff ─────────────────────────────────────────────────────────────────
def compute_drift(graph, cfg, templates_dir, board_bodies, *,
                  pm, ps, active_plans=None, public=True) -> list:
    """Return a list of human-readable drift lines; empty == in sync.

    ``board_bodies`` is a ``{issue_number: body}`` snapshot of the live board.
    A materialized item drifts when it has no issue (``create``), its issue is
    absent from the board (``missing``), or its rendered body differs from the
    board body (``update``). A board issue backed by no materialized item is an
    ``orphan`` — the board is generated, never hand-maintained, so an unclaimed
    issue is itself drift. Pure: no network, no clock, deterministic order.
    """
    drift = []
    repo_url = ps.project_repo_url(cfg)
    materialized = pm.materialize(graph, active_plans=active_plans or set())
    claimed = set()
    for item in materialized:
        body = ps.render_item(item, repo_url, templates_dir,
                              graph=graph, public=public)
        if item.issue is None:
            drift.append(f"create  {item.type}:{item.id} — not yet on the board")
            continue
        if item.issue not in board_bodies:
            drift.append(f"missing {item.type}:{item.id} — issue "
                         f"#{item.issue} not found on the board")
            continue
        claimed.add(item.issue)
        action = ps.plan_item_action(item, body,
                                     current_body=board_bodies[item.issue])
        if action.kind != "noop":
            drift.append(f"update  {item.type}:{item.id} — issue "
                         f"#{item.issue} body differs from the rendered source")
    for num in board_bodies:
        if num not in claimed:
            drift.append(f"orphan  issue #{num} — on the board, "
                         f"not in the vault source")
    return drift


# ── live board snapshot (read-only; the only side-effecting seam) ─────────────
def _run_gh(argv) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CheckError(f"`{' '.join(argv)}` failed: {proc.stderr.strip()}")
    return proc.stdout


def fetch_board_bodies(cfg, runner=None) -> dict:
    """Read the live board's open issues as ``{number: body}`` via ``gh issue
    list`` (read-only). The parse is pure, so tests drive it with a fake runner
    returning canned JSON. Closed issues are excluded — a completed item's issue
    stays on the board as history, not drift."""
    runner = runner or _run_gh
    repo = cfg.get("github", {}).get("repo")
    if not repo:
        raise CheckError("github.repo is required to fetch the board")
    raw = runner(["gh", "issue", "list", "--repo", repo, "--state", "open",
                  "--json", "number,body", "--limit", "1000"])
    data = json.loads(raw) if isinstance(raw, str) else raw
    return {row["number"]: row.get("body", "") for row in data}


# ── CLI ───────────────────────────────────────────────────────────────────────
def _default_config() -> Path:
    # Repo-relative; absent in any repo that doesn't use the plugin → skip.
    return Path(".harness/project.json")


def main(argv=None, *, runner=None, fetch=None) -> int:
    p = argparse.ArgumentParser(prog="check_project_sync.py")
    p.add_argument("--config",
                   help="path to project.json (default: .harness/project.json)")
    p.add_argument("--active-plan", action="append", default=[],
                   dest="active_plans", help="plan id to materialize (repeatable)")
    p.add_argument("--private", action="store_true",
                   help="diff against the private render (keep silent-source)")
    args = p.parse_args(argv)

    cfg_path = Path(args.config) if args.config else _default_config()
    if not cfg_path.exists():
        print(f"check_project_sync: no project.json at {cfg_path} — "
              f"skipping (not a board-synced repo)")
        return 0
    # When a board snapshot is injected (tests), skip the gh-presence guard.
    if fetch is None and shutil.which("gh") is None:
        print("check_project_sync: gh not on PATH — skipping")
        return 0

    pm, ps = _siblings()
    cfg = ps.load_config(cfg_path)
    items_path = ps._items_path_from_cfg(cfg, cfg_path)
    graph = pm.load(items_path)
    templates_dir = Path(__file__).resolve().parent.parent / "templates"

    board = fetch(cfg) if fetch is not None else fetch_board_bodies(cfg, runner=runner)
    drift = compute_drift(graph, cfg, templates_dir, board, pm=pm, ps=ps,
                          active_plans=set(args.active_plans),
                          public=not args.private)
    if drift:
        print("check_project_sync: FAIL — vault and board out of sync:")
        for line in drift:
            print(f"  {line}")
        return 1
    print("check_project_sync: PASS — vault and board in sync")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckError as exc:
        print(f"check_project_sync: {exc}", file=sys.stderr)
        sys.exit(2)
