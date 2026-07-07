#!/usr/bin/env python3
"""drift_correct.py — the Planner (TPM) persona's drift-corrector.

AG Wave D. `check_project_sync.py` stays the drift **oracle** — this module
never modifies `compute_drift()`, `fetch_board_bodies()`, or any of
`check_project_sync.py`'s own behavior (per the plan's own constraint) — it
composes a **second, separate reader** over the exact same primitives
(`project_model.materialize`, `project_sync.render_item`,
`project_sync.plan_item_action`) to independently re-derive which items are
`update` drift, so it can act on them **by item, not by parsing
`compute_drift`'s human-readable string lines** (fragile, and `compute_drift`'s
docstring makes no promise about that string's exact shape being a stable
machine contract).

`report_drift.py`/`github-projects:report-board-drift` stays report-only for
its own direct callers, unmodified — this is an entirely separate module the
Planner persona's activation calls into; it does not turn the underlying
skill into an auto-corrector.

**What it does, per drift kind:**

- **`update`** — the board issue exists but its body differs from the
  rendered source. The corrector calls `project_sync.py`'s existing `post`
  path (no `--type`, matching a manual re-sync) for that item: the same
  idempotent body-render + `sync_fields` + `sync_nesting` write path
  `project_sync.py post` already runs by hand. Never a new write path —
  reuses the one this plugin already owns.
- **`orphan`** — a board issue with no backing vault item. **Never
  auto-closed or edited** (the plan's own locked design call, carried
  forward from the superseded chief-of-staff plan): an orphan might be a
  legitimately hand-created issue, so silently correcting it would itself be
  a mistake, not a fix. Surfaced in the corrector's output as a clear,
  operator-facing flag — the live board issue is never touched.
- **`create` / `missing`** — out of this corrector's scope for now (an
  operator-gated backfill decision the design already names as such, same
  boundary `project_sync.py`'s own docstring draws at task 5's "operator-gated
  backfill, not unit-tested against the network"); left untouched, not
  silently absorbed into a corrector that was only asked to fix `update` +
  surface `orphan`.

Activates only under an explicit call (the Planner persona's launch mode) —
never a background daemon, matching `report_drift.py`'s own `/loop`-or-cron
scheduling posture: one invocation is one idempotent cycle.

stdlib only.
"""
from __future__ import annotations

import importlib.util
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


def _siblings():
    pm = _load("project_model", _HERE / "project_model.py")
    ps = _load("project_sync", _HERE / "project_sync.py")
    cps = _load("check_project_sync", _HERE / "check_project_sync.py")
    return pm, ps, cps


@dataclass
class Finding:
    kind: str            # "update" | "orphan"
    item_id: "str | None"  # None for an orphan (no vault item backs it)
    issue: int            # the board issue number
    item_type: "str | None" = None


def classify(graph, cfg, templates_dir, board_bodies, *, pm, ps,
             active_plans=None, public=True) -> list:
    """Re-derive `update`/`orphan` drift as structured `Finding`s — the same
    classification `check_project_sync.compute_drift` makes (never imported
    or re-executed; independently computed from the same primitives), kept
    separate so the corrector never depends on parsing that function's
    human-readable string lines. `create`/`missing` are deliberately not
    classified here — out of this corrector's scope (see module docstring).
    """
    findings: list = []
    repo_url = ps.project_repo_url(cfg)
    materialized = pm.materialize(graph, active_plans=active_plans or set())
    claimed = set()
    for item in materialized:
        if item.issue is None or item.issue not in board_bodies:
            continue  # create / missing — not this corrector's scope
        claimed.add(item.issue)
        body = ps.render_item(item, repo_url, templates_dir,
                              graph=graph, public=public)
        action = ps.plan_item_action(item, body, current_body=board_bodies[item.issue])
        if action.kind != "noop":
            findings.append(Finding("update", item.id, item.issue, item.type))
    for num in board_bodies:
        if num not in claimed:
            findings.append(Finding("orphan", None, num))
    return findings


def correct(findings, cfg, config_path, *, ps, runner=None, dry_run=True, out=None) -> dict:
    """Act on `findings`: `update` -> `project_sync.py post` (the existing
    idempotent body-sync path, by item id); `orphan` -> flagged only, no
    board write of any kind. Returns:

        {"corrected": [item_id, ...], "flagged": [issue_number, ...]}

    Never calls `gh` directly — every write goes through `project_sync.main`,
    so the corrector adds zero new gh argv surface. `dry_run` mirrors the
    plugin-wide preview boundary: True prints what `post` would do (via
    `project_sync.main`'s own `--dry-run`) without executing.
    """
    out = out if out is not None else sys.stdout
    corrected: list = []
    flagged: list = []
    for f in findings:
        if f.kind == "orphan":
            flagged.append(f.issue)
            print(f"FLAGGED  orphan issue #{f.issue} — on the board, not in the "
                 f"vault source; needs operator judgment (never auto-closed)",
                 file=out)
            continue
        if f.kind == "update":
            argv = ["post", "--config", str(config_path), "--id", f.item_id]
            if dry_run:
                argv.append("--dry-run")
            rc = ps.main(argv, runner=runner)
            if rc == 0:
                corrected.append(f.item_id)
    return {"corrected": corrected, "flagged": flagged}


def run(graph, cfg, config_path, templates_dir, board_bodies, *,
       pm=None, ps=None, active_plans=None, public=True,
       runner=None, dry_run=True, out=None) -> dict:
    """The drift-corrector's one entrypoint: classify, then correct. Returns
    the same `{"corrected": [...], "flagged": [...]}` shape as `correct()`.
    """
    if pm is None or ps is None:
        pm2, ps2, _ = _siblings()
        pm = pm or pm2
        ps = ps or ps2
    findings = classify(graph, cfg, templates_dir, board_bodies, pm=pm, ps=ps,
                       active_plans=active_plans, public=public)
    return correct(findings, cfg, config_path, ps=ps, runner=runner,
                   dry_run=dry_run, out=out)


# ── CLI ──────────────────────────────────────────────────────────────────────
def _default_config() -> Path:
    return Path(".harness/project.json")


def main(argv=None, *, runner=None, fetch=None) -> int:
    import argparse
    import shutil

    p = argparse.ArgumentParser(prog="drift_correct.py")
    p.add_argument("--config", help="path to project.json (default: .harness/project.json)")
    p.add_argument("--active-plan", action="append", default=[], dest="active_plans",
                  help="plan id to materialize (repeatable)")
    p.add_argument("--private", action="store_true",
                  help="diff against the private render (keep silent-source)")
    p.add_argument("--dry-run", action="store_true",
                  help="preview the gh argv the corrector would run, without executing")
    args = p.parse_args(argv)

    cfg_path = Path(args.config) if args.config else _default_config()
    if not cfg_path.exists():
        print(f"drift_correct: no project.json at {cfg_path} — "
             f"skipping (not a board-synced repo)")
        return 0
    if fetch is None and shutil.which("gh") is None:
        print("drift_correct: gh not on PATH — skipping")
        return 0

    pm, ps, cps = _siblings()
    cfg = ps.load_config(cfg_path)
    items_path = ps._items_path_from_cfg(cfg, cfg_path)
    graph = pm.load(items_path)
    templates_dir = _HERE.parent / "templates"

    board = fetch(cfg) if fetch is not None else cps.fetch_board_bodies(cfg, runner=runner)
    result = run(graph, cfg, cfg_path, templates_dir, board, pm=pm, ps=ps,
                active_plans=set(args.active_plans), public=not args.private,
                runner=runner, dry_run=args.dry_run)
    for item_id in result["corrected"]:
        print(f"corrected {item_id}")
    return 1 if result["flagged"] else 0


if __name__ == "__main__":
    sys.exit(main())
