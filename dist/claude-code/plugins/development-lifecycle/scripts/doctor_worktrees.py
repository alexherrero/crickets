#!/usr/bin/env python3
"""Read-only health probe over the coordinator's `worker/<slug>` worktrees (Risk #6).

The coordinator runs this to *see* the state of every worker before deciding what
to prune or integrate. It is the diagnostic complement to the mutating lifecycle
(`/spawn-worker` creates, `/integrate-worker` lands + prunes): this command only
**lists and classifies** — it never removes a worktree, deletes a branch, or
touches the integration branch. The operator prunes on demand once they've read
the report.

    doctor_worktrees.py [--project-root <path>]
    # stdout: one line per worker/<slug> worktree, with its status + plan mapping

Each `worker/<slug>` worktree (or lingering worker branch) is classified into
exactly one of four states, in precedence order:

    orphaned         — the branch has no worktree at all (already pruned, or never
                       checked out), OR its registered worktree's directory is gone
                       (git lists it as prunable). A leftover ref / stale
                       registration; `git worktree prune` + `git branch -d` cleans
                       it up.
    dangling-marker  — the worktree is on disk but has no readable
                       `.harness/active-plan` marker (missing or blank), so a
                       `/work` session inside it could not bind to its named plan.
    merged-but-unpruned — on disk, marker present, and the branch is already merged
                       into the integration branch. Either an integration that did
                       not prune, or work that landed by hand — a prune candidate.
    active           — on disk, marker present, branch NOT yet merged. Work in
                       progress; leave it alone.

The integration reference is the repo's current `HEAD` (normally `main`), matching
`integrate_worker.py`, which merges into the checked-out branch. The probe is
anchored on worker branches (`git for-each-ref refs/heads/worker/`) correlated
with `git worktree list --porcelain`, so it reports both lingering branches and
prunable worktrees. (A worktree whose branch ref was surgically deleted while it
stayed on disk — "branch gone, dir lingers" — needs manual ref surgery to create
and is out of scope; git refuses to delete a branch checked out in a worktree.)

**Read-only by contract.** Exit code is always 0 — this is a report, not a gate.
Every git call is a query (`list`, `for-each-ref`, `merge-base --is-ancestor`);
nothing here mutates. Stdlib-only; mirrors the pure-core shape of its siblings
(`diagnose()` returns data; `main()` formats and prints).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

# `spawn_worker` owns the `worker/<slug>` convention — import it for the single
# source of truth on the branch prefix rather than re-hardcoding "worker/".
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import spawn_worker  # noqa: E402  — owns `_BRANCH_PREFIX`

_PREFIX = spawn_worker._BRANCH_PREFIX  # "worker/"

# Status constants (one per worktree; mutually exclusive, precedence-ordered).
ACTIVE = "active"
MERGED = "merged-but-unpruned"
ORPHANED = "orphaned"
DANGLING = "dangling-marker"


class WorkerWorktree(NamedTuple):
    """One classified worker worktree (or lingering worker branch)."""
    slug: str
    branch: str
    worktree: str | None  # the worktree path, or None when the branch has none
    status: str
    detail: str


# ── git helpers (read-only; guarded, mirror integrate_worker._git) ────────────

def _git(args: list[str], root: str | os.PathLike) -> subprocess.CompletedProcess:
    """Run a read-only git query in `root`. Never raises on a non-zero rc.

    DOES raise OSError (missing git) / subprocess.SubprocessError (a >30s hang) —
    callers degrade gracefully (an unreadable git collapses to "nothing found",
    never a crash), since this is a diagnostic that must not blow up.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _worktrees(root: str | os.PathLike) -> list[dict]:
    """Parse `git worktree list --porcelain` into per-worktree dicts.

    Each block is a `worktree <path>` line plus optional `branch refs/heads/<n>`,
    `detached`, `prunable [<reason>]`, `bare`, `locked` lines, blank-separated.
    Returns dicts: {path, branch (short name or None), prunable (bool),
    detached (bool), bare (bool)}. Any git error collapses to [].
    """
    try:
        r = _git(["worktree", "list", "--porcelain"], root)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    out: list[dict] = []
    cur: dict | None = None
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):], "branch": None,
                   "prunable": False, "detached": False, "bare": False}
            out.append(cur)
        elif cur is None:
            continue
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            cur["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
        elif line == "detached":
            cur["detached"] = True
        elif line.startswith("prunable"):
            cur["prunable"] = True
        elif line == "bare":
            cur["bare"] = True
    return out


def _worker_branches(root: str | os.PathLike) -> list[str]:
    """Every `worker/<slug>` branch, sorted. Any git error collapses to []."""
    try:
        r = _git(["for-each-ref", "--format=%(refname:short)", f"refs/heads/{_PREFIX}"], root)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return sorted(b for b in (ln.strip() for ln in r.stdout.splitlines()) if b)


def _is_merged(root: str | os.PathLike, branch: str, ref: str) -> bool:
    """True iff `branch` is an ancestor of `ref` (fully merged). False on any error."""
    try:
        r = _git(["merge-base", "--is-ancestor", branch, ref], root)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _read_marker(wt: Path) -> str | None:
    """The worktree-local `.harness/active-plan` bare slug, or None if missing/blank."""
    marker = wt / ".harness" / "active-plan"
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return text or None


# ── core (pure: returns data, prints/mutates nothing) ─────────────────────────

def diagnose(root: str | os.PathLike, *, integration_ref: str = "HEAD") -> list[WorkerWorktree]:
    """Classify every `worker/<slug>` worktree / lingering worker branch. Read-only.

    Anchored on worker branches, correlated with the worktree list, so it reports
    both branches with no worktree and worktrees whose directory is gone. Returns
    one `WorkerWorktree` per branch, sorted by slug. No mutation, no printing.
    """
    by_branch = {w["branch"]: w for w in _worktrees(root) if w["branch"]}
    reports: list[WorkerWorktree] = []
    for branch in _worker_branches(root):
        slug = branch[len(_PREFIX):]
        w = by_branch.get(branch)
        if w is None:
            reports.append(WorkerWorktree(
                slug, branch, None, ORPHANED,
                "branch has no worktree (already pruned, or never spawned a checkout) — "
                "`git branch -d` to remove the ref"))
            continue
        path = w["path"]
        on_disk = (not w["prunable"]) and os.path.isdir(path)
        if not on_disk:
            reports.append(WorkerWorktree(
                slug, branch, path, ORPHANED,
                "worktree directory is missing (git lists it as prunable) — "
                "`git worktree prune` then `git branch -d`"))
            continue
        marker = _read_marker(Path(path))
        if not marker:
            reports.append(WorkerWorktree(
                slug, branch, path, DANGLING,
                "no readable .harness/active-plan marker (missing or blank) — a /work "
                "session here cannot bind to its named plan"))
            continue
        if _is_merged(root, branch, integration_ref):
            reports.append(WorkerWorktree(
                slug, branch, path, MERGED,
                "branch is merged into the integration branch — prune candidate "
                "(`/integrate-worker` already ran, or it landed by hand)"))
        else:
            reports.append(WorkerWorktree(
                slug, branch, path, ACTIVE,
                f"work in progress (bound to plan {marker!r}); leave it alone"))
    return reports


# ── CLI (formats + prints; exit 0 always — a report, not a gate) ──────────────

def _format(reports: list[WorkerWorktree]) -> str:
    if not reports:
        return "[doctor_worktrees] no worker/<slug> worktrees or branches found.\n"
    counts: dict[str, int] = {}
    for r in reports:
        counts[r.status] = counts.get(r.status, 0) + 1
    tally = ", ".join(f"{counts[s]} {s}" for s in (ACTIVE, MERGED, DANGLING, ORPHANED)
                      if s in counts)
    lines = [f"[doctor_worktrees] {len(reports)} worker worktree(s)/branch(es): {tally}"]
    width = max(len(r.branch) for r in reports)
    for r in reports:
        where = r.worktree if r.worktree else "(no worktree)"
        lines.append(f"  {r.branch:<{width}}  {r.status:<19}  plan: {r.slug}")
        lines.append(f"  {'':<{width}}  {where}")
        lines.append(f"  {'':<{width}}  → {r.detail}")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="doctor_worktrees.py",
        description="Read-only: list + classify worker/<slug> worktrees (active / "
                    "merged-but-unpruned / dangling-marker / orphaned). Mutates nothing.",
    )
    p.add_argument("--project-root", default=None, help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    sys.stdout.write(_format(diagnose(root)))
    return 0  # read-only diagnostic — never a gate


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
