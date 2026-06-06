#!/usr/bin/env python3
# wiki_watch_dispatch.py — dispatch plumbing for the wiki-watcher
# (wiki-maintenance part 4/5, the wiki-watcher (W1), task 3).
#
# Once task 2 produces a candidate feed, this is how a candidate becomes a wiki
# update. The DOCUMENTER does the authoring (reused as-is via the shipped
# capability-probe + prose-dispatch pattern — NOT a second writer); this module is
# everything AROUND that: the PR-vs-direct decision, branch derivation, the git/gh
# executors, the PII guard that must run before any push, and the audit log.
#
#   PR is the default autonomous boundary (DC-W1): the PR IS the async preview that
#   reconciles the documenter's own interactive preview-before-write gate with
#   autonomous mode. A human merges. Direct-commit bypasses the preview, so it is an
#   explicit per-repo opt-in only (run_config.dispatch_mode == "direct").
#
# Split so the agent's authoring step sits between the deterministic halves:
#     prepare_branch()  ->  [documenter authors on the branch]  ->  finalize_pr()
# (direct mode skips the branch and calls finalize_direct()). The PURE planner +
# branch derivation + audit format are unit-tested (DC-W8); the git/gh executors
# take an injectable runner so their command sequence + the PII-before-push ordering
# + graceful-skip are testable without a real remote.
#
# Stdlib-only; matches the established skill/script convention.

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import wiki_watch_config as cfg  # sibling: find_agentm_script + RunConfig

_AUDIT_FILE = "audit.log"  # JSONL; under _harness/wiki-watch/; LOCAL, never committed.


# ----------------------------------------------------------------------------
# Branch derivation (PURE)
# ----------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Lowercase, non-alnum -> '-', collapse + strip. Git-ref-safe."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", str(text)).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)


def branch_name(slug: str, token: str) -> str:
    """Deterministic branch for a PR-mode dispatch: wiki-watch/<slug>-<short-token>.
    Stable for a given (repo, token) so a re-run reuses the same branch rather than
    spawning duplicates."""
    base = slugify(slug) or "repo"
    short = slugify(token)[:12] or "head"
    return f"wiki-watch/{base}-{short}"


# ----------------------------------------------------------------------------
# PR-vs-direct decision (PURE)
# ----------------------------------------------------------------------------

@dataclass
class DispatchPlan:
    action: str               # "pr" | "direct" | "skip"
    reason: str
    branch: Optional[str] = None


def plan_dispatch(
    run_config: "cfg.RunConfig", *, gh_available: bool, slug: str, token: str,
) -> DispatchPlan:
    """Decide how to land a candidate's wiki update from the per-repo marker.

    - dispatch_mode == "direct" -> commit straight to the default branch (the
      explicit per-repo opt-in; no gh needed).
    - dispatch_mode == "pr" (default) -> open a PR (the DC-W1 boundary). Needs gh;
      when gh is unavailable/unauthenticated we SKIP rather than silently fall back
      to direct-commit (that would bypass the human-merge boundary).
    """
    if run_config.is_direct:
        return DispatchPlan(action="direct",
                            reason="per-repo marker opts into direct-commit (trusted repo)")
    if not gh_available:
        return DispatchPlan(
            action="skip",
            reason="PR-default but gh is unavailable/unauthenticated — not falling "
                   "back to direct-commit (would bypass the human-merge boundary)")
    return DispatchPlan(action="pr", reason="PR-default boundary (DC-W1)",
                        branch=branch_name(slug, token))


# ----------------------------------------------------------------------------
# Capability probe + documenter context (reuse the shipped pattern; don't reimplement)
# ----------------------------------------------------------------------------

def probe_capability(slug: str = "wiki-maintenance") -> Optional[bool]:
    """Best-effort reuse of developer-workflows' capability_probe.py: True/False if
    the probe runs, None when it can't be located. The documenter lives IN
    wiki-maintenance, so a None probe (can't locate the cross-plugin script) is not
    fatal — the task-4 skill proceeds, since wiki-watch running implies the plugin
    is installed. Mirrors the shipped /review -> code-review probe-dispatch idiom."""
    script = cfg.find_agentm_script("capability_probe.py")
    if script is None:
        return None
    try:
        res = subprocess.run([sys.executable, str(script), slug],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.returncode == 0


def build_documenter_context(
    *, repo_root: str, wiki_target: str, candidates, dispatch_mode: str,
    head_token: str,
) -> str:
    """Assemble the prose task the task-4 skill hands to the documenter sub-agent —
    its familiar /work-style 'task + diff' contract (reuse as-is). PURE string
    builder so the dispatch payload is testable + deterministic."""
    paths = candidates if isinstance(candidates, list) else list(candidates)
    bullet = "\n".join(f"  - {p}" for p in paths) or "  (none)"
    boundary = ("Author on a feature branch; the PR is the human-review boundary."
                if dispatch_mode != "direct"
                else "Direct-commit opt-in for this trusted repo (no PR).")
    return (
        f"Wiki-watch dispatch — update the wiki to reflect doc-worthy changes.\n"
        f"Repo: {repo_root}\nWiki target: {wiki_target}\n"
        f"Source state token: {head_token}\nDispatch mode: {dispatch_mode}\n"
        f"{boundary}\n\n"
        f"Doc-worthy changed sources (significance-filtered candidates):\n{bullet}\n\n"
        f"Read each changed source + the current wiki, then create/update only the "
        f"pages those changes affect, in the operator's voice and the Diátaxis "
        f"single-mode discipline. Do not touch unrelated pages. Keep check-wiki "
        f"--strict green."
    )


# ----------------------------------------------------------------------------
# git / gh executors (IMPURE — injectable runner for tests; graceful-skip)
# ----------------------------------------------------------------------------

# A runner takes an argv list + cwd, returns (returncode, stdout). Default shells out.
Runner = Callable[[list, str], "tuple[int, str]"]


def _default_runner(argv: list, cwd: str) -> "tuple[int, str]":
    try:
        res = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return res.returncode, (res.stdout or "").strip()


def check_gh_available(runner: Optional[Runner] = None, cwd: str = ".") -> bool:
    """True iff the `gh` CLI is on PATH AND authenticated. Used by plan_dispatch to
    decide PR-vs-skip. Never raises."""
    if shutil.which("gh") is None:
        return False
    run = runner or _default_runner
    rc, _ = run(["gh", "auth", "status"], cwd)
    return rc == 0


@dataclass
class DispatchResult:
    ok: bool
    action: str
    reason: str = ""
    branch: Optional[str] = None
    pr_url: Optional[str] = None
    commit: Optional[str] = None
    steps: list = field(default_factory=list)  # ordered record of what ran (for audit/tests)


def prepare_branch(repo_root: str, branch: str, *, runner: Optional[Runner] = None) -> DispatchResult:
    """Create + switch to the PR feature branch (before the documenter authors).
    Graceful-skip: any git failure returns ok=False, never raises."""
    run = runner or _default_runner
    rc, out = run(["git", "checkout", "-B", branch], repo_root)
    steps = [("checkout", rc)]
    if rc != 0:
        return DispatchResult(ok=False, action="pr", reason=f"branch create failed: {out}",
                              branch=branch, steps=steps)
    return DispatchResult(ok=True, action="pr", branch=branch, steps=steps)


def finalize_pr(
    repo_root: str, branch: str, *, title: str, body: str,
    pii_guard: Callable[[str], bool], runner: Optional[Runner] = None,
) -> DispatchResult:
    """After the documenter has authored on `branch`: commit -> PII GUARD -> push ->
    open PR. The PII guard runs BEFORE any push (the order is the contract); a failed
    guard aborts before the push. Every step graceful-skips (no raise)."""
    run = runner or _default_runner
    steps: list = []

    rc, out = run(["git", "add", "-A"], repo_root); steps.append(("add", rc))
    rc, out = run(["git", "commit", "-m", title], repo_root); steps.append(("commit", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="pr", reason=f"nothing to commit / commit failed",
                              branch=branch, steps=steps)
    commit = _head_sha(run, repo_root)

    # PII guard MUST precede the push (the pre-push hook is the enforcer; this is the
    # in-engine pre-check so we never even attempt a push of flagged content).
    steps.append(("pii-guard", 0))
    if not pii_guard(repo_root):
        return DispatchResult(ok=False, action="pr", reason="PII guard blocked the push",
                              branch=branch, commit=commit, steps=steps)

    rc, out = run(["git", "push", "-u", "origin", branch], repo_root); steps.append(("push", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="pr", reason=f"push failed: {out}",
                              branch=branch, commit=commit, steps=steps)

    rc, out = run(["gh", "pr", "create", "--title", title, "--body", body,
                   "--head", branch], repo_root)
    steps.append(("pr-create", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="pr", reason=f"gh pr create failed: {out}",
                              branch=branch, commit=commit, steps=steps)
    return DispatchResult(ok=True, action="pr", branch=branch, commit=commit,
                          pr_url=out.strip() or None, steps=steps)


def finalize_direct(
    repo_root: str, *, message: str, pii_guard: Callable[[str], bool],
    runner: Optional[Runner] = None,
) -> DispatchResult:
    """Direct-commit opt-in: commit on the current branch -> PII GUARD -> push.
    Same PII-before-push ordering; graceful-skip on any failure."""
    run = runner or _default_runner
    steps: list = []
    rc, out = run(["git", "add", "-A"], repo_root); steps.append(("add", rc))
    rc, out = run(["git", "commit", "-m", message], repo_root); steps.append(("commit", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="direct", reason="nothing to commit / commit failed",
                              steps=steps)
    commit = _head_sha(run, repo_root)
    steps.append(("pii-guard", 0))
    if not pii_guard(repo_root):
        return DispatchResult(ok=False, action="direct", reason="PII guard blocked the push",
                              commit=commit, steps=steps)
    rc, out = run(["git", "push"], repo_root); steps.append(("push", rc))
    if rc != 0:
        return DispatchResult(ok=False, action="direct", reason=f"push failed: {out}",
                              commit=commit, steps=steps)
    return DispatchResult(ok=True, action="direct", commit=commit, steps=steps)


def _head_sha(run: Runner, repo_root: str) -> Optional[str]:
    rc, out = run(["git", "rev-parse", "HEAD"], repo_root)
    return out.strip() if rc == 0 and out.strip() else None


# ----------------------------------------------------------------------------
# Audit log (saw -> decided -> dispatched) — LOCAL, never committed
# ----------------------------------------------------------------------------

def audit_record(
    *, phase: str, source: str = "", ts: str = "", **fields,
) -> dict:
    """Build one audit record. `phase` is one of saw / decided / dispatched. Extra
    fields (candidates, decision, action, pr_url, commit, ok, reason) pass through.
    PURE."""
    rec = {"ts": ts, "phase": phase, "source": source}
    rec.update(fields)
    return rec


def append_audit(state_dir: Path | str, record: dict) -> Path:
    """Append one JSONL record to <state_dir>/audit.log. Creates the dir. Returns
    the audit path. The log is LOCAL state — never committed (it lives under the
    gitignored _harness/wiki-watch/ tree, or the watched repo's .harness/)."""
    d = Path(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / _AUDIT_FILE
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def read_audit(state_dir: Path | str) -> list[dict]:
    """Read back the audit log as a list of records (skipping any unparseable line)."""
    path = Path(state_dir) / _AUDIT_FILE
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ----------------------------------------------------------------------------
# CLI — debugging
# ----------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="wiki_watch_dispatch",
        description="Wiki-watch dispatch helpers (branch / plan / gh-available).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_b = sub.add_parser("branch", help="derive the PR branch for a (slug, token)")
    p_b.add_argument("slug"); p_b.add_argument("token")
    sub.add_parser("gh-available", help="exit 0 iff gh is installed + authenticated")
    args = parser.parse_args(argv)

    if args.cmd == "branch":
        print(branch_name(args.slug, args.token))
        return 0
    if args.cmd == "gh-available":
        ok = check_gh_available()
        print(json.dumps({"gh_available": ok}))
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
