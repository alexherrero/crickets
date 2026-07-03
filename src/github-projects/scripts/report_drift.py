#!/usr/bin/env python3
"""report_drift.py — the scheduled, report-only drift cycle (board-write-path
task 6).

Runs check_project_sync's drift detector UNMODIFIED, then posts a single
summary comment on the vault's Version issue when drift is found (or logs the
report when no Version issue resolves) — detection and reporting only, never
a corrective write. Fits the same Claude-first cron/`/loop` scheduling pattern
wiki-watch uses: one invocation is one idempotent cycle. Idempotent by a
hidden marker keyed to the exact drift content (list-and-match against the
Version issue's existing comments — same discipline as the per-commit comment
path), so a re-run against unchanged drift is a no-op, not a duplicate post.

Correction stays operator-confirmed until the Planner (TPM) persona ships
(AG Wave D) — this cycle never creates, updates, or deletes a board item.

stdlib only.
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    # Register before exec: project_model's @dataclass under `from __future__
    # import annotations` resolves its own module via sys.modules.
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _siblings():
    pm = _load("project_model", _HERE / "project_model.py")
    ps = _load("project_sync", _HERE / "project_sync.py")
    cps = _load("check_project_sync", _HERE / "check_project_sync.py")
    return pm, ps, cps


def drift_report_marker(drift: list) -> str:
    digest = hashlib.sha256("\n".join(sorted(drift)).encode("utf-8")).hexdigest()[:12]
    return f"<!-- board:driftreport:{digest} -->"


def render_drift_report(drift: list) -> str:
    lines = ["**Drift report** (report-only — no auto-correction):", ""]
    lines.extend(f"- {line}" for line in drift)
    lines.append("")
    lines.append(drift_report_marker(drift))
    return "\n".join(lines)


def _find_version_issue(graph):
    for item in graph.values():
        if item.type == "version" and item.issue is not None:
            return item.issue
    return None


def run(graph, cfg, drift, *, ps=None, runner=None, dry_run=True, out=None) -> int:
    """Post `drift`'s findings as a single summary comment on the Version
    issue, or log the report when no Version issue resolves. Never mutates a
    board item — no item-edit, no issue-edit, no item-add; the only write
    this ever performs is the one comment post, and only when drift is
    non-empty and not already reported. Returns 0 (clean or logged-only) or 1
    (drift reported/no-op-reported)."""
    if ps is None:
        _, ps, _ = _siblings()
    out = out if out is not None else sys.stdout
    runner = runner or ps._run_gh
    if not drift:
        print("report_drift: PASS — vault and board in sync", file=out)
        return 0

    version_issue = _find_version_issue(graph)
    if version_issue is None:
        print("report_drift: drift found, no Version issue to comment on — "
             "logging instead:", file=out)
        for line in drift:
            print(f"  {line}", file=out)
        return 1

    marker = drift_report_marker(drift)
    if ps.has_comment_marker(cfg, version_issue, marker, runner=runner) is not False:
        print(f"report_drift: drift unchanged since the last report — no-op "
             f"(issue #{version_issue})", file=out)
        return 1

    body = render_drift_report(drift)
    argv = ps.issue_comment_argv(cfg["github"]["repo"], version_issue, body)
    if dry_run:
        print(ps.GhCommand(argv).render(), file=out)
    else:
        runner(argv)
    return 1


def _default_config() -> Path:
    return Path(".harness/project.json")


def main(argv=None, *, runner=None, fetch=None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="report_drift.py")
    p.add_argument("--config",
                   help="path to project.json (default: .harness/project.json)")
    p.add_argument("--active-plan", action="append", default=[],
                   dest="active_plans", help="plan id to materialize (repeatable)")
    p.add_argument("--private", action="store_true",
                   help="diff against the private render (keep silent-source)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the exact gh argv without executing")
    args = p.parse_args(argv)

    cfg_path = Path(args.config) if args.config else _default_config()
    if not cfg_path.exists():
        print(f"report_drift: no project.json at {cfg_path} — "
             f"skipping (not a board-synced repo)")
        return 0
    if fetch is None and shutil.which("gh") is None:
        print("report_drift: gh not on PATH — skipping")
        return 0

    pm, ps, cps = _siblings()
    cfg = ps.load_config(cfg_path)
    items_path = ps._items_path_from_cfg(cfg, cfg_path)
    graph = pm.load(items_path)
    templates_dir = _HERE.parent / "templates"

    board = fetch(cfg) if fetch is not None else cps.fetch_board_bodies(cfg, runner=runner)
    closed = set() if fetch is not None else cps.fetch_closed_issue_numbers(cfg, runner=runner)
    drift = cps.compute_drift(graph, cfg, templates_dir, board, pm=pm, ps=ps,
                              active_plans=set(args.active_plans),
                              public=not args.private,
                              closed_issue_numbers=closed)
    return run(graph, cfg, drift, ps=ps, runner=runner, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
