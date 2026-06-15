#!/usr/bin/env python3
"""Integrate a finished worker's branch into the integration branch (the keystone).

The coordinator runs this to *close the loop* opened by `spawn_worker.py`: where
`/spawn-worker <name>` creates a `worker/<slug>` branch + worktree bound to a
named plan, `/integrate-worker <name>` lands that branch on the integration
branch (normally `main`) **only if the integrated result still passes the full
deterministic battery**, then folds the worker's progress into the mainline log
(additive) and prunes the worktree + now-merged branch.

    integrate_worker.py <name> [--project-root <path>]
    # stdout (rc 0): a one-line integration summary
    # stderr (rc 2): the refusal / rollback report

**The integration is verified, not assumed (R04 keystone, LC-I).** The gate runs
on the *post-merge tree* — the actual integrated result — not the worker branch
in isolation, so an integration that merges cleanly but breaks `main` is caught.
`main` is never left broken: a merge conflict is `git merge --abort`-ed and a red
gate hard-resets the integration branch to the captured pre-merge HEAD. Every
refusal path leaves the worker's worktree + branch intact for the operator to
inspect, fix, and re-run.

**Merge strategy: `git merge --no-ff` (LC-H).** Preserves the worker's per-task
commits *and* records an explicit integration point; because `--no-ff` records
the merge, the post-green safe `git branch -d` prune deletes the branch cleanly.

**Pure core + injectable gate (LC-K).** `integrate(name, root, *, gate, resolver)`
takes the gate as a **callable** `gate(root) -> (rc, output)`, so tests drive the
green/red paths with a *stub* gate over real git in throwaway temp repos. They
NEVER run the real `check-all.sh` — which itself runs the unit suite that includes
this module's tests (infinite recursion). Only the command spec wires the real
`bash scripts/check-all.sh` (`_DEFAULT_GATE`) in production, and `integrate()`
never calls itself, so there is no recursion outside a mis-wired test. Do not
"simplify" the injected gate into a hard-coded call.

**Consume the shipped substrate; never reimplement.** The slug normalizer + the
naming contract come from `resolve_plan` (`_normalize_plan_name`, `resolve`); the
`worker/<slug>` branch convention comes from `spawn_worker.branch_name` — the
single owner, so the two helpers can't drift. Plan resolution is *delegated*: a
non-zero `resolve` (dangling marker, unsafe slug, no resolvable `_harness/`) is
authoritative and propagated verbatim, and nothing is merged.

Exit codes (aligned with `resolve_plan.py` / `spawn_worker.py`, so the helpers
stay transparent):
    0 — integrated; a summary is on stdout.
    1 — graceful-skip: propagated from a located resolver (agentm present, no
        resolvable `_harness/`).
    2 — loud: empty/singleton name, a missing `worker/<slug>` branch, an
        undiscoverable worktree, a detached/dirty integration branch, a resolver
        refusal, a merge conflict (aborted), or a red gate (rolled back). The
        guarded helpers mirror `spawn_worker.py`: `_git` never raises on a
        non-zero rc, and a hang/missing-git on a rollback path is absorbed and
        reported (ROLLBACK INCOMPLETE naming exactly what survived) rather than
        crashing or claiming a clean rollback.

Stdlib-only; mirrors `spawn_worker.py`'s shape (pure core + injectable backend).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# `resolve_plan` / `spawn_worker` are sibling modules; ensure this dir is
# importable whether the script is run directly or imported by path (tests).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import resolve_plan  # noqa: E402  — owns the naming contract + plan resolution
import spawn_worker  # noqa: E402  — owns the `worker/<slug>` branch convention

_AUTO = resolve_plan._AUTO
branch_name = spawn_worker.branch_name  # single source of truth for `worker/<slug>`


# ── git helpers (guarded; mirror spawn_worker._git) ───────────────────────────

def _git(args: list[str], root: str | os.PathLike) -> subprocess.CompletedProcess:
    """Run a git command in `root`, capturing output. Never raises on non-zero.

    It DOES raise OSError (missing git) / subprocess.SubprocessError (a >30s hang
    → TimeoutExpired) — callers on a mutation/rollback path guard for those.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _branch_exists(root: str | os.PathLike, branch: str) -> bool:
    return _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], root).returncode == 0


def _find_worktree_for_branch(root: str | os.PathLike, branch: str) -> Path | None:
    """The worktree path checked out on `branch`, or None — authoritative (LC-N).

    Parses `git worktree list --porcelain` blocks (a `worktree <path>` line plus a
    `branch refs/heads/<name>` line, blank-line separated) and returns the path of
    the block whose branch matches. This handles a worker spawned with a custom
    `--worktree-path`, which re-deriving `spawn_worker.worktree_path` would miss.
    Any git error / hang collapses to None (→ a loud refuse, never a crash).
    """
    try:
        r = _git(["worktree", "list", "--porcelain"], root)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    target_ref = f"refs/heads/{branch}"
    cur_path: str | None = None
    for line in r.stdout.splitlines():
        if line.startswith("worktree "):
            cur_path = line[len("worktree "):]
        elif line.startswith("branch "):
            if line[len("branch "):] == target_ref and cur_path is not None:
                return Path(cur_path)
        elif line == "":
            cur_path = None
    return None


def _is_clean(root: str | os.PathLike) -> bool:
    """True iff the integration branch's working tree has no changes.

    `git status --porcelain` empty ⇒ clean. A git error / hang collapses to False
    (refuse), since we must never merge onto an unknown/dirty tree.
    """
    try:
        r = _git(["status", "--porcelain"], root)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and not r.stdout.strip()


def _head_sha(root: str | os.PathLike) -> str | None:
    try:
        r = _git(["rev-parse", "HEAD"], root)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _current_branch(root: str | os.PathLike) -> str | None:
    """The checked-out branch name, or None if detached / error."""
    try:
        r = _git(["symbolic-ref", "--short", "HEAD"], root)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _merge_in_progress(root: str | os.PathLike) -> bool:
    try:
        r = _git(["rev-parse", "-q", "--verify", "MERGE_HEAD"], root)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _restore_to(root: str | os.PathLike, pre_sha: str) -> bool:
    """Bring the integration branch back to `pre_sha`; True iff HEAD == pre_sha after.

    Handles BOTH rollback states with one guarded path: a merge *conflict* (merge
    in progress, uncommitted) is `git merge --abort`-ed first, then a `git reset
    --hard` to the captured SHA covers a committed merge (red gate) and any
    partial/failed abort. Both git calls are guarded — a hang/missing-git is
    absorbed — and the truth is HEAD itself, not an rc, so the caller reports
    exactly whether `main` is really back.
    """
    if _merge_in_progress(root):
        try:
            _git(["merge", "--abort"], root)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        _git(["reset", "--hard", pre_sha], root)
    except (OSError, subprocess.SubprocessError):
        pass
    return _head_sha(root) == pre_sha


def _merge_message(slug: str, branch: str) -> str:
    """The `--no-ff` merge commit subject. No Co-Authored-By trailer (AGENTS.md)."""
    return f"Merge {branch} via integrate-worker (plan {slug})"


# ── consolidation: promote progress + prune the worktree (green path only) ──────

def _branch_safe_gone(root: str | os.PathLike, branch: str) -> bool:
    """Best-effort SAFE branch delete (`git branch -d`); True iff gone afterward.

    Uses `-d`, NOT `-D`: git refuses to delete a branch not fully merged into
    HEAD. After the `--no-ff` merge the branch IS an ancestor of HEAD so `-d`
    succeeds — but an unexpected unmerged state is *preserved* (reported as a
    survivor, never force-dropped), so prune can never silently destroy work.
    Returns True if already absent or deleted now; False if it survives a delete
    attempt or a git call raised. Mirrors `spawn_worker._branch_gone`'s guard
    shape but with the safe flag (its rollback can force; a post-green prune
    must not).
    """
    try:
        if not _branch_exists(root, branch):
            return True
        _git(["branch", "-d", branch], root)
        return not _branch_exists(root, branch)
    except (OSError, subprocess.SubprocessError):
        return False


def _prune(root: str | os.PathLike, wt: Path, branch: str) -> str:
    """Remove the worker's worktree then safe-delete its branch; survivor clause.

    Worktree FIRST (a branch checked out in a worktree can't be deleted), reusing
    `spawn_worker`'s guarded `_worktree_gone`, then the safe `_branch_safe_gone`.
    Returns "" when both are gone (a clean prune) or a human clause naming only
    what survived. Never raises — both helpers swallow a raising/hanging git, and
    truth is the artifact's real presence, never an rc.
    """
    wt_gone = spawn_worker._worktree_gone(root, wt)
    branch_gone = _branch_safe_gone(root, branch)
    survivors = []
    if not wt_gone:
        survivors.append(f"the worktree ({wt})")
    if not branch_gone:
        survivors.append(f"the branch ({branch})")
    return " and ".join(survivors)


def _promote(named_progress: Path | None, root: str | os.PathLike, branch: str,
             sha: str, *, resolver) -> tuple[bool, str]:
    """Fold the worker's progress into mainline progress (additive, never raises).

    Resolves the SINGLETON (mainline) progress path via the same resolver backend,
    then appends the worker's `progress-<slug>.md` content (if present) plus a
    one-line integration record, in append mode — the named file is KEPT, so this
    is additive only (LC-J). Best-effort: any failure returns `(False, reason)`
    and the caller surfaces it on stderr *without* undoing the verified merge.
    Returns `(True, <mainline path>)` on success.
    """
    try:
        rc, out, err = resolve_plan.resolve("", root, resolver=resolver)
        if rc != 0 or not out.strip():
            return (False, f"could not resolve mainline progress (rc={rc}): {err.strip()}")
        mainline = Path(out.strip().split("\t")[1])
        mainline.parent.mkdir(parents=True, exist_ok=True)
        chunk = ""
        if named_progress is not None and named_progress.is_file():
            chunk = named_progress.read_text(encoding="utf-8")
            if chunk and not chunk.endswith("\n"):
                chunk += "\n"
        record = (f"{datetime.now().strftime('%Y-%m-%d %H:%M')} /integrate-worker — "
                  f"merged {branch} at {sha[:9]}, check-all green\n")
        # Symmetric to the chunk's trailing-newline normalization above: ensure the
        # EXISTING mainline ends in a newline before we append, or the first byte we
        # write fuses onto its last line. Seek-based last-byte check (not a full read)
        # so a large progress.md is not pulled into memory; a missing or empty file
        # gets no stray leading newline.
        needs_sep = False
        if mainline.exists() and mainline.stat().st_size > 0:
            with mainline.open("rb") as rfh:
                rfh.seek(-1, os.SEEK_END)
                needs_sep = rfh.read(1) != b"\n"
        with mainline.open("a", encoding="utf-8") as fh:
            if needs_sep:
                fh.write("\n")
            if chunk:
                fh.write(chunk)
            fh.write(record)
        return (True, str(mainline))
    except Exception as exc:  # best-effort: a promotion failure never undoes the merge
        return (False, str(exc))


# ── default production gate (never used by tests — see module docstring) ────────

def _check_all_gate(root: str | os.PathLike) -> tuple[int, str]:
    """Run the repo's `scripts/check-all.sh` battery on the integrated tree.

    THE PRODUCTION GATE ONLY. Tests inject a stub gate instead — running this in a
    test would re-enter the unit suite (which includes this module's tests) and
    recurse. A missing script returns rc 127 (treated as red ⇒ fail-safe: a gate
    that cannot run blocks the integration rather than waving it through).
    """
    script = Path(root) / "scripts" / "check-all.sh"
    if not script.is_file():
        return (127, f"[integrate_worker] gate script not found: {script}\n")
    try:
        r = subprocess.run(
            ["bash", str(script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (1, f"[integrate_worker] gate failed to run: {exc}\n")
    return (r.returncode, r.stdout + r.stderr)


_DEFAULT_GATE = _check_all_gate


# ── default production artifact-prepare (single-writer integration, ADR 0030) ───

_PREPARE_SCRIPT = ("scripts", "integrate-prepare.sh")


def _artifact_prepare(root: str | os.PathLike, pre_sha: str) -> tuple[int, str]:
    """Run the project's artifact-prepare step on the merged tree, if it has one.

    The single-writer-integration model (ADR 0030): a worker branch commits
    src + generated artifacts at the *current* version and defers the version
    bump; the serialized integrator is the single writer of the shared version
    registry. A project that produces such a registry (e.g. crickets'
    `marketplace.json` + committed `dist/`) supplies `scripts/integrate-prepare.sh`,
    which — run here, on the freshly-merged tree, BEFORE the gate — bumps every
    plugin whose `src/` the merge changed, regenerates the artifacts from current
    `main`, and commits, so the version-bump gate passes on the integrated tree.

    The pre-merge SHA is passed as `$1` so the step can diff the merge's
    contribution. When the script is absent this is a graceful no-op (rc 0) —
    back-compat for projects whose workers bump on their own branch (no shared
    registry to serialize). A missing-script no-op keeps every pre-Model-A repo,
    and every test that injects only a gate, behaving exactly as before.

    THE PRODUCTION DEFAULT ONLY — tests inject a stub `prepare` (see the
    `gate` precedent in the module docstring); do not hard-code this call.
    """
    script = Path(root) / Path(*_PREPARE_SCRIPT)
    if not script.is_file():
        return (0, f"[integrate_worker] no artifact-prepare step "
                   f"({'/'.join(_PREPARE_SCRIPT)} absent) — skipping.\n")
    try:
        r = subprocess.run(
            ["bash", str(script), pre_sha],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return (1, f"[integrate_worker] artifact-prepare failed to run: {exc}\n")
    return (r.returncode, r.stdout + r.stderr)


_DEFAULT_PREPARE = _artifact_prepare


# ── core ──────────────────────────────────────────────────────────────────────

def integrate(name: str, root: str, *, gate=_DEFAULT_GATE,
              resolver=_AUTO, prepare=_DEFAULT_PREPARE) -> tuple[int, str, str]:
    """Merge `worker/<slug>` into the integration branch, gated on the merged tree.

    Pure core, injectable backend. Guards run before any mutation; the merge +
    prepare + gate + rollback never leave `main` broken or lose a commit. On green
    the merge stands and the green path consolidates: it promotes the worker's
    progress into mainline progress (additive) then prunes the worktree +
    now-merged branch. Consolidation is best-effort — a promotion or prune failure
    is reported on stderr but NEVER undoes the verified merge (rc stays 0).

    `gate(root) -> (rc, output)` is injected so tests drive green/red without the
    real battery. `prepare(root, pre_sha) -> (rc, output)` is the single-writer
    artifact step (ADR 0030): run on the merged tree BEFORE the gate, it bumps the
    deferred version(s) + regenerates the shared registry so the gate passes on the
    integrated tree; it defaults to a graceful no-op when the project has no such
    step. A failed prepare rolls the merge back exactly like a red gate — the bump
    is part of the integration, so a botched bump must never half-land. `resolver`
    is forwarded to `resolve_plan.resolve` (`_AUTO` locates an agentm clone; tests
    pass `None` for the `.harness/` fallback or a stub Path for the delegate branch).
    """
    slug = resolve_plan._normalize_plan_name(name)
    if not slug:
        return (2, "", f"[integrate_worker] a named plan is required (got {name!r}); "
                       "the singleton plan has no worker branch to integrate.\n")

    # Delegate plan resolution FIRST (mirrors spawn_worker): a non-zero exit
    # (unsafe slug, dangling marker, no resolvable `_harness/`) is authoritative
    # and propagated verbatim — Risk #7, never paper over a refusal — and we never
    # touch git for a plan that doesn't resolve.
    rc, res_out, err = resolve_plan.resolve(name, root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    # The worker's own progress-<slug>.md, for the green-path promotion. A
    # malformed resolver line degrades to None (promotion appends only its own
    # record) rather than crashing the integrate.
    try:
        named_progress: Path | None = Path(res_out.strip().split("\t")[1])
    except (IndexError, AttributeError):
        named_progress = None

    branch = branch_name(slug)

    # Pre-mutation guards — refuse loud, mutate nothing, leave the worktree intact.
    if not _branch_exists(root, branch):
        return (2, "", f"[integrate_worker] no worker branch {branch!r} — nothing to "
                       "integrate. Spawn it with `/spawn-worker` first.\n")
    wt = _find_worktree_for_branch(root, branch)
    if wt is None:
        return (2, "", f"[integrate_worker] no worktree is checked out on {branch!r} "
                       "(`git worktree list` shows none) — refusing to integrate a "
                       "branch with no live worker.\n")
    target = _current_branch(root)
    if target is None:
        return (2, "", "[integrate_worker] HEAD is detached (not on a branch) — check out "
                       "the integration branch (normally `main`) before integrating.\n")
    if not _is_clean(root):
        return (2, "", f"[integrate_worker] the integration branch {target!r} has a dirty "
                       "working tree — commit or stash before integrating.\n")

    pre = _head_sha(root)
    if pre is None:
        return (2, "", "[integrate_worker] could not read HEAD — refusing to merge.\n")

    # Merge --no-ff (LC-H). Guard the call itself: a >30s hang raises
    # subprocess.TimeoutExpired mid-merge (a SubprocessError, not OSError) and
    # leaves a partial merge — restore and report rather than crash.
    try:
        merge = _git(["merge", "--no-ff", "-m", _merge_message(slug, branch), branch], root)
    except (OSError, subprocess.SubprocessError) as exc:
        restored = _restore_to(root, pre)
        if restored:
            return (2, "", f"[integrate_worker] `git merge {branch}` raised ({exc}); rolled "
                           f"{target!r} back to {pre[:9]} — the worktree is untouched.\n")
        return (2, "", f"[integrate_worker] `git merge {branch}` raised ({exc}); ROLLBACK "
                       f"INCOMPLETE — {target!r} is NOT back at {pre[:9]}; inspect it by "
                       "hand. The worktree is untouched.\n")
    if merge.returncode != 0:
        conflict = _merge_in_progress(root)
        restored = _restore_to(root, pre)
        what = "conflicts with" if conflict else "could not be merged into"
        detail = (merge.stdout + merge.stderr).strip()
        base = (f"[integrate_worker] {branch} {what} {target!r}; "
                + ("aborted the merge" if conflict else "the merge failed"))
        if restored:
            return (2, "", f"{base} and restored {target!r} to {pre[:9]}. Resolve it in the "
                           f"worktree, then re-run. The worktree is untouched.\n"
                           + (f"\ngit said:\n{detail}\n" if detail else ""))
        return (2, "", f"{base}, but ROLLBACK INCOMPLETE — {target!r} is NOT back at "
                       f"{pre[:9]}; inspect it by hand. The worktree is untouched.\n"
                       + (f"\ngit said:\n{detail}\n" if detail else ""))

    # The merge committed: HEAD is now the integration merge commit. Before the
    # gate, run the single-writer artifact-prepare step (ADR 0030): the worker
    # deferred its version bump, so the integrator bumps the affected plugin(s) +
    # regenerates the shared registry HERE, on the merged tree, so the version-bump
    # gate passes. A prepare that fails (or raises) rolls the merge back exactly
    # like a red gate — a half-applied bump must never land. A project with no
    # prepare step no-ops (rc 0), so this is invisible to the pre-Model-A flow.
    try:
        prc, poutput = prepare(root, pre)
    except Exception as exc:  # a raising prepare is a failed prepare
        prc, poutput = (1, f"[integrate_worker] artifact-prepare raised: {exc}\n")
    if prc != 0:
        restored = _restore_to(root, pre)
        tail = poutput.strip()
        if restored:
            return (2, "", f"[integrate_worker] artifact-prepare FAILED (rc={prc}) on the "
                           f"merged tree; rolled {target!r} back to {pre[:9]} (zero commits "
                           f"added). The worktree is untouched.\n"
                           + (f"\nprepare output:\n{tail}\n" if tail else ""))
        return (2, "", f"[integrate_worker] artifact-prepare FAILED (rc={prc}) on the merged "
                       f"tree, but ROLLBACK INCOMPLETE — {target!r} is NOT back at {pre[:9]}; "
                       "inspect it by hand. The worktree is untouched.\n"
                       + (f"\nprepare output:\n{tail}\n" if tail else ""))

    # Gate the *integrated* tree (LC-I) — now carrying the integrator's bump. A
    # gate that itself raises is treated as red — we never leave a merge unverified.
    try:
        grc, goutput = gate(root)
    except Exception as exc:  # a raising gate is a failed gate
        grc, goutput = (1, f"[integrate_worker] gate raised: {exc}\n")
    if grc != 0:
        restored = _restore_to(root, pre)
        tail = goutput.strip()
        if restored:
            return (2, "", f"[integrate_worker] integration gate FAILED (rc={grc}) on the "
                           f"merged tree; rolled {target!r} back to {pre[:9]} (zero commits "
                           f"added). The worktree is untouched.\n"
                           + (f"\ngate output:\n{tail}\n" if tail else ""))
        return (2, "", f"[integrate_worker] integration gate FAILED (rc={grc}) on the merged "
                       f"tree, but ROLLBACK INCOMPLETE — {target!r} is NOT back at {pre[:9]}; "
                       "inspect it by hand. The worktree is untouched.\n"
                       + (f"\ngate output:\n{tail}\n" if tail else ""))

    # Green: the merge is verified and STANDS. Consolidate (LC-J), best-effort —
    # a promotion or prune failure is reported on stderr but never undoes the
    # merge (rc stays 0). Promote BEFORE prune so the worker's progress is folded
    # into mainline *before* its worktree disappears.
    new_sha = _head_sha(root) or "?"
    summary = [f"[integrate_worker] merged {branch} into {target} ({new_sha[:9]}); "
               "integration gate passed."]
    warnings = []

    promoted, promo_detail = _promote(named_progress, root, branch, new_sha, resolver=resolver)
    if promoted:
        summary.append(f"Promoted the worker's progress into {promo_detail}.")
    else:
        warnings.append(f"[integrate_worker] progress promotion incomplete ({promo_detail}); "
                        "the merge stands — fold the worker's progress in by hand.")

    survivors = _prune(root, wt, branch)
    if survivors:
        warnings.append(f"[integrate_worker] prune incomplete — manually remove {survivors}. "
                        "The merge stands.")
    else:
        summary.append(f"Pruned the worktree and deleted {branch}.")

    return (0, " ".join(summary) + "\n", ("\n".join(warnings) + "\n") if warnings else "")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="integrate_worker.py",
        description="Integrate a worker's branch into the integration branch, gated on the "
                    "merged tree.",
    )
    p.add_argument("name",
                   help="named plan ('foo', 'PLAN-foo', 'PLAN-foo.md'); the singleton is refused")
    p.add_argument("--project-root", default=None,
                   help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    rc, out, err = integrate(ns.name, root)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
