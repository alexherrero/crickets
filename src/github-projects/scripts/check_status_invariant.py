#!/usr/bin/env python3
"""check_status_invariant.py — the vault-status vs GitHub-issue-state gate.

The problem this exists for: `check_project_sync.py` diffs rendered issue
**bodies**. `status` appears in no body template, so a row that is `Todo` in the
vault while its issue has been closed for months is **zero drift by
construction** — the gate passes, and the board quietly accumulates rows that
disagree with reality. That is not a bug in `compute_drift`; body-diffing is
exactly what it promises. It is a gap in what anything checks at all.

This gate closes it by asserting a different invariant, on a different axis:

    a row's status and its issue's open/closed state must agree.

Concretely — a non-Done row whose issue is **closed** is drift (the vault lags
reality), and a Done/Parked row whose issue is still **open** is drift (the
board lags the vault). Both directions matter: the first is what makes a
finished arc keep showing up as open work, the second is what lets a shipped
row look unshipped.

**Why a separate module.** `check_project_sync.py` is the drift oracle and the
governing design states it "is never modified by anything below." So this
composes a **second, independent reader** over the same primitives
(`project_model.materialize`) rather than extending `compute_drift` — the
pattern `drift_correct.py` already set, and for the same reason: other modules
depend on `compute_drift`'s behavior, and widening what it counts as drift
would change every one of them. Detects only; never writes, never corrects.

**Truth model.** The vault (`board-items.json`) stays the source of truth and
the write surface — nothing here derives status *from* GitHub or writes back to
it. Issue state is the **checked invariant** over that truth: the one fact both
records independently observe, so a disagreement is real information rather
than a rendering artifact.

**Where it runs — read this before assuming CI coverage.** It does **not** run
in CI, and cannot: `.harness/` is gitignored in every repo using this plugin, so
`project.json` is simply absent on a CI checkout and the gate graceful-skips at
exit 0. It runs in the local gate battery (`scripts/check-all.sh`) and on
explicit invocation, where the vault is actually mounted. Same posture as
`check_project_sync.py`, stated plainly here so nobody reads a green CI run as
evidence this passed.

**Statuses with no assertion.** A row whose `status` is null carries no claim
about its issue, so it produces no violation — but it is reported in its own
section rather than silently dropped, on the same reasoning `compute_body_owned`
gives: an item absent from every report is indistinguishable from one nobody is
tracking.

stdlib only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# A status is a claim about whether the work is still live. These two say the
# work is finished or deliberately set down — either way the issue belongs
# closed. Everything else says it is still live, so the issue belongs open.
_CLOSED_EXPECTING = frozenset({"Done", "Parked"})


class CheckError(Exception):
    """A failure to read the live state — distinct from a drift finding."""


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def _siblings():
    pm = _load("project_model", _HERE / "project_model.py")
    ps = _load("project_sync", _HERE / "project_sync.py")
    return pm, ps


@dataclass
class Violation:
    kind: str        # "stale-open" | "stale-done"
    item_id: str
    item_type: str
    issue: int
    status: "str | None"
    issue_state: str

    def render(self) -> str:
        if self.kind == "stale-open":
            return (f"stale-open  {self.item_type}:{self.item_id} — issue "
                    f"#{self.issue} is closed but the row is {self.status!r}; "
                    f"the vault lags what actually happened")
        return (f"stale-done  {self.item_type}:{self.item_id} — row is "
                f"{self.status!r} but issue #{self.issue} is still open; "
                f"the close never landed")


# ── pure diff ────────────────────────────────────────────────────────────────
def compute_violations(graph, issue_states, *, pm, active_plans=None) -> list:
    """Return `Violation`s for every materialized row whose status disagrees
    with its issue's open/closed state.

    `issue_states` is a `{issue_number: "OPEN"|"CLOSED"}` snapshot. A row with
    no issue, or an issue absent from the snapshot, is skipped — materialization
    and board membership are `check_project_sync`'s axis, not this one, and
    double-reporting them here would just make both gates noisier.

    Pure: no network, no clock, deterministic order.
    """
    violations: list = []
    for item in pm.materialize(graph, active_plans=active_plans or set()):
        if item.issue is None:
            continue
        state = issue_states.get(item.issue)
        if state is None:
            continue  # not on the board / not fetched — the other gate's axis
        if item.status is None:
            continue  # no claim made, so nothing to contradict
        expects_closed = item.status in _CLOSED_EXPECTING
        if expects_closed and state == "OPEN":
            violations.append(Violation("stale-done", item.id, item.type,
                                        item.issue, item.status, state))
        elif not expects_closed and state == "CLOSED":
            violations.append(Violation("stale-open", item.id, item.type,
                                        item.issue, item.status, state))
    return violations


def compute_unasserted(graph, *, pm, active_plans=None) -> list:
    """Informational lines for materialized rows carrying no `status`.

    Deliberately not folded into `compute_violations` — a null status is not a
    disagreement, and failing the gate on one would make it unfixable without
    inventing a status nobody chose. Reported separately so these rows stay
    visible instead of vanishing between the two checks.
    """
    lines = []
    for item in pm.materialize(graph, active_plans=active_plans or set()):
        if item.status is None and item.issue is not None:
            lines.append(f"no-status   {item.type}:{item.id} — issue "
                         f"#{item.issue} carries no status claim")
    return lines


# ── live snapshot (read-only; the only side-effecting seam) ──────────────────
def _run_gh(argv) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CheckError(f"`{' '.join(argv)}` failed: {proc.stderr.strip()}")
    return proc.stdout


def fetch_issue_states(cfg, runner=None) -> dict:
    """Read every issue's open/closed state as `{number: "OPEN"|"CLOSED"}`.

    One `--state all` call rather than separate open and closed passes: half the
    requests, and it cannot produce the torn read two calls can when an issue
    closes between them.

    **Budget note.** `gh issue list --json` is served by GitHub's **GraphQL**
    API, not REST, so this gate draws on the same 5,000-point/hour pool as every
    `gh project` call. That pool is exhaustible in practice — a sweep that
    repeatedly pulls full board item-lists can drain it, after which `gh project`
    fails with the misleading `unknown owner type` and this gate exits 2. Exit 2
    is a read failure, deliberately distinct from exit 1 (a real violation): a
    throttled run must never be mistaken for a clean one.
    """
    runner = runner or _run_gh
    repo = (cfg.get("github") or {}).get("repo")
    if not repo:
        raise CheckError("github.repo is required to fetch issue states")
    raw = runner(["gh", "issue", "list", "--repo", repo, "--state", "all",
                  "--json", "number,state", "--limit", "1000"])
    data = json.loads(raw) if isinstance(raw, str) else raw
    return {row["number"]: row["state"].upper() for row in data}


# ── CLI ──────────────────────────────────────────────────────────────────────
def _default_config() -> Path:
    return Path(".harness/project.json")


def main(argv=None, *, runner=None, fetch=None) -> int:
    p = argparse.ArgumentParser(prog="check_status_invariant.py")
    p.add_argument("--config",
                   help="path to project.json (default: .harness/project.json)")
    p.add_argument("--active-plan", action="append", default=[],
                   dest="active_plans", help="plan id to materialize (repeatable)")
    args = p.parse_args(argv)

    cfg_path = Path(args.config) if args.config else _default_config()
    if not cfg_path.exists():
        print(f"check_status_invariant: no project.json at {cfg_path} — "
              f"skipping (not a board-synced repo)")
        return 0
    if fetch is None and shutil.which("gh") is None:
        print("check_status_invariant: gh not on PATH — skipping")
        return 0

    pm, ps = _siblings()
    cfg = ps.load_config(cfg_path)
    graph = pm.load(ps._items_path_from_cfg(cfg, cfg_path))

    states = fetch(cfg) if fetch is not None else fetch_issue_states(cfg, runner=runner)
    active = set(args.active_plans)
    violations = compute_violations(graph, states, pm=pm, active_plans=active)
    unasserted = compute_unasserted(graph, pm=pm, active_plans=active)

    for line in unasserted:
        print(f"  {line}")
    if violations:
        print("check_status_invariant: FAIL — row status disagrees with issue state:")
        for v in violations:
            print(f"  {v.render()}")
        return 1
    print("check_status_invariant: PASS — every row's status agrees with its "
          "issue state")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CheckError as exc:
        print(f"check_status_invariant: {exc}", file=sys.stderr)
        sys.exit(2)
