#!/usr/bin/env python3
"""Read-only health probe over `/work`'s auto-spawned `worktree-<slug>` worktrees.

Rewritten for the host-native worktree flow (worktree-native-flow task 5):
`spawn_worker.py`'s `worker/<slug>` + sibling-`<repo>.worktrees/` convention is
retired; `EnterWorktree` (Claude Code) / New-Worktree-Mode (Antigravity) create
branches named `worktree-<name>` inside `.claude/worktrees/<name>` instead — this
probe now anchors on THAT convention. It is the read-only detector half of the
shepherd sidecar (`worktree_shepherd.py`, which reclaims + rebases); this module
only **lists and classifies** — it never removes a worktree, deletes a branch, or
touches the integration branch.

`scan_slots()` is a second, convention-agnostic pass (worktree-slot integrity
fix): `diagnose()` above only sees worktrees on a `worktree-<slug>` branch, so
it can't see a slot the HOST's own session-per-worktree feature spawned (not
`/work`'s auto-spawn) that never got that branch shape at all — the observed
fake-slot bug, where a bare directory sits at `.claude/worktrees/<name>` and
was never actually `git worktree add`-ed. `scan_slots()` walks every slot
directory directly and flags any not present in `git worktree list`.

`stranded_worktrees()` is a third pass, over every *linked* worktree git knows
about, wherever it lives: a linked worktree checked out on the integration
branch itself (`main`). Nothing in the flow puts one there on purpose. The
observed cause is `gh pr merge --delete-branch` run from inside the worktree:
to delete the local PR branch gh first has to leave it, so it runs
`git checkout main` *in that worktree*, and the worktree walks off holding
`refs/heads/main` while its own branch is gone. `diagnose()` cannot see it
(the `worktree-<slug>` branch no longer exists to anchor on) and
`scan_slots()` calls it real (it is registered), so without this pass the
theft is silent. The shepherd detaches a clean one; the fix by hand is
`git -C <worktree> checkout --detach`, which frees the ref and loses nothing.

    doctor_worktrees.py [--project-root <path>]
    # stdout: one line per worktree-<slug> worktree, with its status + plan
    # mapping, followed by a fake-slot summary over every .claude/worktrees/*
    # directory on disk, followed by every linked worktree stranded on the
    # integration branch

Each `worktree-<slug>` worktree (or lingering branch) is classified into exactly
one of four states, in precedence order:

    orphaned         — the branch has no worktree at all (already pruned, or never
                       checked out), OR its registered worktree's directory is gone
                       (git lists it as prunable). A leftover ref / stale
                       registration; `git worktree prune` + `git branch -d` cleans
                       it up.
    dangling-marker  — the worktree is on disk but has no readable
                       `.harness/active-plan` marker (missing or blank), so a
                       `/work` session inside it could not bind to its named plan.
    merged-but-unpruned — on disk, marker present, and the branch has landed on
                       the integration branch: an ancestor of it, or — since
                       these repos squash-merge, which leaves no ancestry — the
                       same content file by file (`content_landed()`). Either
                       the PR merged without a prune, or work that landed by
                       hand — a prune candidate.
    active           — on disk, marker present, branch NOT yet merged. Work in
                       progress; leave it alone.

The integration reference is the repo's current `HEAD` (normally `main`). The
probe is anchored on worktree branches (`git for-each-ref refs/heads/worktree-`)
correlated with `git worktree list --porcelain`, so it reports both lingering
branches and prunable worktrees. (A worktree whose branch ref was surgically
deleted while it stayed on disk — "branch gone, dir lingers" — needs manual ref
surgery to create and is out of scope; git refuses to delete a branch checked out
in a worktree.)

**Read-only by contract.** Exit code is always 0 — this is a report, not a gate.
Every git call is a query (`list`, `for-each-ref`, `merge-base`, `diff
--name-only`, `rev-parse`);
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

# TEMPORARY (worktree-native-flow task 2): `spawn_worker.py` — the prior single
# source of truth for this prefix — is retired. Inlined here as a stopgap so this
# probe's import doesn't break mid-plan; task 5 rewrites this module's whole
# detection model against the `EnterWorktree` convention (`.claude/worktrees/`,
# `worktree-<name>` branches), at which point this constant goes away too.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_PREFIX = "worktree-"

# Status constants (one per worktree; mutually exclusive, precedence-ordered).
ACTIVE = "active"
MERGED = "merged-but-unpruned"
ORPHANED = "orphaned"
DANGLING = "dangling-marker"


class WorkerWorktree(NamedTuple):
    """One classified `/work`-spawned worktree (or lingering branch)."""
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
    """Every `worktree-<slug>` branch, sorted. Any git error collapses to []."""
    try:
        # `for-each-ref`'s pattern matches by path COMPONENT, not string prefix —
        # `refs/heads/worker/` (old convention) matched fine since it ends on a
        # `/` boundary, but `refs/heads/worktree-` does not (git requires a `*`
        # to do a string-prefix match within a path component; verified live —
        # without it this silently returns nothing, no error).
        r = _git(["for-each-ref", "--format=%(refname:short)", f"refs/heads/{_PREFIX}*"], root)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return sorted(b for b in (ln.strip() for ln in r.stdout.splitlines()) if b)


def _is_merged(root: str | os.PathLike, branch: str, ref: str) -> bool:
    """True iff `branch` has landed on `ref`: an ancestor of it (a real merge or
    a fast-forward), or — failing that — the same content file by file, which
    is what a squash merge leaves behind (`content_landed`). False on any error."""
    try:
        r = _git(["merge-base", "--is-ancestor", branch, ref], root)
    except (OSError, subprocess.SubprocessError):
        return False
    if r.returncode == 0:
        return True
    return content_landed(root, branch, ref=ref)


def _landed_ref(root: str | os.PathLike) -> str:
    """The ref that says what has LANDED. `origin/<integration>` when that
    remote-tracking ref exists — the remote is the authority for landed, and it
    is current after a fetch even while the local checkout sits stale — else
    the local integration branch, else `HEAD`."""
    name = _integration_branch(root)
    for ref in (f"refs/remotes/origin/{name}", f"refs/heads/{name}"):
        try:
            r = _git(["rev-parse", "--verify", "--quiet", ref], root)
        except (OSError, subprocess.SubprocessError):
            return "HEAD"
        if r.returncode == 0:
            return ref
    return "HEAD"


def content_landed(root: str | os.PathLike, branch: str, *, ref: str | None = None) -> bool:
    """True iff everything `branch` changed is already on the integration
    branch, file by file — the squash-merge answer to "has this landed?".

    Commit identity cannot answer it here. These repos squash-merge, so the
    commit on `main` has no ancestry link to the branch commits it was built
    from, and `merge-base --is-ancestor` says no for every branch that ever
    landed the normal way. The operator's own rule for this repo family is
    that only file-level presence on `main` is reliable. So: for every path
    the branch touched since it forked (`diff --name-only` from the
    merge-base), the blob the branch holds must be the blob the integration
    ref holds — or, where the branch deleted the path, the ref must lack it
    too. A branch that changed nothing since its fork point trivially landed.

    False whenever anything differs — including a file `main` has since
    edited further. That branch really did land, but this cannot prove it,
    and unprovable stays unsafe: the conservative direction. False on any git
    error, never guessing "landed" on an unreadable repo. `ref` defaults to
    `_landed_ref(root)`.
    """
    ref = ref or _landed_ref(root)
    try:
        mb = _git(["merge-base", ref, branch], root)
        if mb.returncode != 0 or not mb.stdout.strip():
            return False
        changed = _git(["diff", "--name-only", "-z", mb.stdout.strip(), branch], root)
        if changed.returncode != 0:
            return False
        for path in (p for p in changed.stdout.split("\0") if p):
            on_branch = _git(["rev-parse", "--verify", "--quiet", f"{branch}:{path}"], root)
            on_ref = _git(["rev-parse", "--verify", "--quiet", f"{ref}:{path}"], root)
            if on_branch.returncode != 0:
                # The branch deleted it: landed only if the ref lacks it too.
                if on_ref.returncode == 0:
                    return False
                continue
            if on_ref.returncode != 0 or on_ref.stdout.strip() != on_branch.stdout.strip():
                return False
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _integration_branch(root: str | os.PathLike) -> str:
    """The integration branch's short name: what `origin/HEAD` points at, else
    `main`. A name, not a ref — `diagnose()` compares commits against `HEAD`,
    but the stranded pass has to compare a *checked-out branch name* against
    the one branch no linked worktree should hold. Any git error collapses to
    the fallback (never guess a different name from an unreadable repo)."""
    try:
        r = _git(["symbolic-ref", "--short", "--quiet", "refs/remotes/origin/HEAD"], root)
    except (OSError, subprocess.SubprocessError):
        return "main"
    name = r.stdout.strip()
    if r.returncode != 0 or not name:
        return "main"
    return name[len("origin/"):] if name.startswith("origin/") else name


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
    """Classify every `worktree-<slug>` worktree / lingering branch. Read-only.

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
                "(its PR already merged, or it landed by hand)"))
        else:
            reports.append(WorkerWorktree(
                slug, branch, path, ACTIVE,
                f"work in progress (bound to plan {marker!r}); leave it alone"))
    return reports


# ── fake-slot scan (repo-wide, convention-agnostic) ────────────────────────────

FAKE = "fake-slot"
REAL = "real-worktree"


class SlotReport(NamedTuple):
    """One `.claude/worktrees/<name>` directory found on disk, checked against
    the registry regardless of branch naming convention. `diagnose()` above is
    anchored on `worktree-<slug>` branches (the crickets `/work` auto-spawn
    convention) and can't see a slot that never got a branch of that shape at
    all — the fake-slot bug observed live: a host worktree primitive (Claude
    Code's own session-per-worktree feature, not `/work`) leaves a bare
    directory behind `.claude/worktrees/<name>` instead of an actual
    `git worktree add`-created checkout, with no `worktree-<slug>` branch to
    anchor on. This scan walks every slot directory directly instead, so it
    catches both conventions."""
    name: str
    path: str
    status: str          # REAL or FAKE
    detail: str


def scan_slots(root: str | os.PathLike) -> list[SlotReport]:
    """Every `.claude/worktrees/<name>` directory on disk, flagged FAKE when it
    is not a real, git-registered worktree of `root`. Read-only; mutates
    nothing. Returns [] when `<root>/.claude/worktrees/` doesn't exist."""
    root = Path(root)
    slots_dir = root / ".claude" / "worktrees"
    if not slots_dir.is_dir():
        return []

    registered: set[str] = set()
    for w in _worktrees(root):
        p = w["path"]
        try:
            registered.add(str(Path(p).resolve()))
        except OSError:
            registered.add(p)

    reports: list[SlotReport] = []
    for entry in sorted(slots_dir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            resolved = str(entry.resolve())
        except OSError:
            resolved = str(entry)
        if resolved in registered:
            reports.append(SlotReport(entry.name, str(entry), REAL,
                                      "real, git-registered worktree"))
        else:
            reports.append(SlotReport(
                entry.name, str(entry), FAKE,
                "NOT registered in `git worktree list` — every git command run "
                "here silently operates on the parent checkout's shared "
                "HEAD/index/working-tree instead of an isolated one. Do not bind "
                "a plan or trust isolation here; confirm with `git worktree list "
                "--porcelain` before using it, and check for a live session "
                "(open file handles / recent .harness/session-id-*.start "
                "markers) before removing it."))
    return reports


def _format_slots(reports: list[SlotReport]) -> str:
    if not reports:
        return ""
    fake = [r for r in reports if r.status == FAKE]
    lines = [f"[doctor_worktrees] {len(reports)} .claude/worktrees/ slot(s) on disk: "
             f"{len(reports) - len(fake)} real, {len(fake)} FAKE"]
    for r in fake:
        lines.append(f"  {r.name}  {r.status}")
        lines.append(f"    {r.path}")
        lines.append(f"    → {r.detail}")
    return "\n".join(lines) + "\n"


# ── stranded-on-main scan (every linked worktree, wherever it lives) ──────────

STRANDED = "stranded-on-main"


class StrandedWorktree(NamedTuple):
    """One linked worktree checked out on the integration branch. See the
    module docstring for how one comes to exist; the short version is that
    `gh pr merge --delete-branch`, run inside a worktree, checks `main` out
    there before deleting the PR branch."""
    path: str
    branch: str          # the integration branch it is holding
    detail: str


def stranded_worktrees(root: str | os.PathLike, *,
                       integration_branch: str | None = None) -> list[StrandedWorktree]:
    """Every *linked* worktree whose checked-out branch is the integration
    branch. Read-only; mutates nothing.

    The main worktree is skipped — it is the one place the integration branch
    may legitimately be checked out — identified as the first entry of
    `git worktree list`, which git documents as always the main worktree. A
    detached linked worktree is never stranded, even at the integration
    branch's tip: it holds no ref, so it blocks nothing. `integration_branch`
    defaults to `_integration_branch(root)`.
    """
    target = integration_branch or _integration_branch(root)
    reports: list[StrandedWorktree] = []
    for i, w in enumerate(_worktrees(root)):
        if i == 0 or w["bare"] or w["detached"]:
            continue
        if w["branch"] != target:
            continue
        # Resolved, like scan_slots(): git prints this path with forward
        # slashes on every platform and may print a realpath, and the report
        # should carry the native form — the one a person pastes into `git -C`.
        try:
            path = str(Path(w["path"]).resolve())
        except OSError:
            path = w["path"]
        reports.append(StrandedWorktree(
            path, target,
            f"a linked worktree is holding `{target}` — the integration branch, "
            "which no worktree but the main one should have checked out. Almost "
            "always `gh pr merge --delete-branch` run from inside this worktree: "
            "gh checks the base branch out HERE before deleting the PR branch. "
            "`git -C <path> checkout --detach` frees the ref and loses nothing "
            "(the working tree stays put); then remove the slot normally. Merge "
            "with `gh pr merge --squash` (no -d), or arm `--auto` at open, so it "
            "does not recur."))
    return reports


def _format_stranded(reports: list[StrandedWorktree]) -> str:
    if not reports:
        return ""
    lines = [f"[doctor_worktrees] {len(reports)} linked worktree(s) STRANDED on the "
             "integration branch:"]
    for r in reports:
        lines.append(f"  {r.path}  {STRANDED}  (holding {r.branch})")
        lines.append(f"    → {r.detail}")
    return "\n".join(lines) + "\n"


# ── CLI (formats + prints; exit 0 always — a report, not a gate) ──────────────

def _format(reports: list[WorkerWorktree]) -> str:
    if not reports:
        return "[doctor_worktrees] no worktree-<slug> worktrees or branches found.\n"
    counts: dict[str, int] = {}
    for r in reports:
        counts[r.status] = counts.get(r.status, 0) + 1
    tally = ", ".join(f"{counts[s]} {s}" for s in (ACTIVE, MERGED, DANGLING, ORPHANED)
                      if s in counts)
    lines = [f"[doctor_worktrees] {len(reports)} worktree(s)/branch(es): {tally}"]
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
        description="Read-only: list + classify worktree-<slug> worktrees (active / "
                    "merged-but-unpruned / dangling-marker / orphaned), flag fake "
                    ".claude/worktrees/ slots, and flag any linked worktree stranded "
                    "on the integration branch. Mutates nothing.",
    )
    p.add_argument("--project-root", default=None, help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    sys.stdout.write(_format(diagnose(root)))
    sys.stdout.write(_format_slots(scan_slots(root)))
    sys.stdout.write(_format_stranded(stranded_worktrees(root)))
    return 0  # read-only diagnostic — never a gate


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
