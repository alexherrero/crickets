#!/usr/bin/env python3
"""coalescence_checks.py — deterministic close-out assertions for ship-release.

The `coalescence-gate` rule (rules/coalescence-gate.md) names seven items a
release must satisfy when it closes an arc, and says so today as "a session
discipline, not new machinery" — nothing actually checks that a cut release
ran the checklist it claims to follow. This script mechanizes three of the
seven (the three that are a cheap file-read or a `gh` API call away from a
real assertion, per that rule's own items 1, 3, and 5):

  1. narrative-row       — the release's tag has a matching row in this
                            project's Completed-Features.md-equivalent
                            narrative timeline page (coalescence-gate item 1).
  2. archive-hygiene      — no `PLAN.archive.*` file sits flat at the top
                            level of the working harness directory; every
                            archived close-out artifact lives one level
                            deeper, under `<harness-dir>/archive/`
                            (coalescence-gate item 5; AGENTS.md's "Close-out
                            archiving" convention).
  3. board-item-closed   — when a board item id is given, that item's
                            GitHub Projects row is closed / moved to Done
                            (coalescence-gate item 3).

The remaining four items (release-body roadmap ids, a plain-English board
pass, dark-registry reconciliation, an orphan census) stay session discipline
— they need human judgment or span surfaces this script has no cheap read on.

crickets itself carries no local Completed-Features.md — its narrative lives
in agentm's combined "agentm and its sibling toolkit crickets" timeline page
(wiki/reference/Completed-Features.md there). `check_narrative_row` falls
back to agentm's copy via the same env-var / conventional-clone cascade every
other agentm-sibling-dependent script in this codebase already uses
(agentm_bridge.py, scripts/src_model.py's `find_agentm_scripts_dir`) — DC-2:
siblings not layers, graceful-skip when agentm is absent, so a third-party
project that installs this plugin is never blocked by a convention it never
adopted.

Every check gracefully skips (does not block) when the convention it's
checking isn't wired up at all in this project (no narrative page anywhere,
no harness dir, no board item id given) — it only FAILs when the convention
is in play and was not actually satisfied. That distinction is the point:
"never adopted" and "adopted but skipped this time" are different findings.

stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_NARRATIVE_PAGE = Path("wiki/reference/Completed-Features.md")
DEFAULT_HARNESS_DIRNAME = ".harness"


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "fail" | "skip"
    message: str


# ── (1) narrative timeline row ──────────────────────────────────────────────

def find_agentm_narrative_page() -> "Path | None":
    """Locate agentm's Completed-Features.md via the same env-var /
    conventional-clone path-fallback cascade `find_agentm_scripts_dir` (this
    repo's `scripts/src_model.py`) and `agentm_bridge.py` already use —
    reused here rather than imported, since this file ships inside the
    distributed `conventions` plugin and must not depend on crickets' own
    repo-root dev tooling (that tooling never leaves this monorepo)."""
    candidates: "list[Path]" = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(
            Path(os.path.expanduser(env_dir)).parent / "wiki" / "reference" / "Completed-Features.md"
        )
    candidates.append(
        Path.home() / "Antigravity" / "agentm" / "wiki" / "reference" / "Completed-Features.md"
    )
    for c in candidates:
        if c.is_file():
            return c.resolve()
    return None


def check_narrative_row(tag: str, repo_name: str, repo_root: Path, *,
                         narrative_page: "Path | None" = None,
                         fallback_page: "Path | None" = None) -> CheckResult:
    """(1) The release's tag must have a matching row in the project's
    Completed-Features.md-equivalent narrative timeline page."""
    page = narrative_page or (repo_root / DEFAULT_NARRATIVE_PAGE)
    used_fallback = False
    if not page.is_file():
        used_fallback = True
        page = fallback_page or find_agentm_narrative_page()
        if page is None or not page.is_file():
            return CheckResult(
                "narrative-row", "skip",
                f"no Completed-Features-equivalent narrative page found locally "
                f"({repo_root / DEFAULT_NARRATIVE_PAGE}) or via the agentm-sibling "
                f"fallback — skipping (this project hasn't adopted the convention)",
            )
    text = page.read_text(encoding="utf-8")
    pattern = re.compile(rf"\b{re.escape(repo_name)}\s+{re.escape(tag)}\b")
    if pattern.search(text):
        return CheckResult(
            "narrative-row", "pass",
            f"found a row for '{repo_name} {tag}' in {page}",
        )
    where = f"{page} (agentm-sibling narrative page)" if used_fallback else str(page)
    return CheckResult(
        "narrative-row", "fail",
        f"no row for '{repo_name} {tag}' found in {where} — coalescence-gate "
        f"item 1 requires a Completed-Features row (plain-English sentence, "
        f"release tag, roadmap id) for every shipped release before the tag "
        f"is cut. Add the row, then re-run this check.",
    )


# ── (2) archive hygiene ──────────────────────────────────────────────────────

def check_archive_hygiene(harness_dir: Path) -> CheckResult:
    """(2) No `PLAN.archive.*` file sits flat at the top level of the working
    harness directory — every archived close-out artifact lives one level
    deeper, under `<harness_dir>/archive/`."""
    if not harness_dir.is_dir():
        return CheckResult(
            "archive-hygiene", "skip",
            f"no {harness_dir} directory — nothing to check",
        )
    flat = sorted(p.name for p in harness_dir.glob("PLAN.archive.*") if p.is_file())
    if not flat:
        return CheckResult(
            "archive-hygiene", "pass",
            f"no flat PLAN.archive.* files at the top level of {harness_dir}",
        )
    listing = ", ".join(flat)
    return CheckResult(
        "archive-hygiene", "fail",
        f"flat close-out artifact(s) sitting directly in {harness_dir}: {listing} "
        f"— archived plans must live under {harness_dir}/archive/, not flat at "
        f"the working directory's top level (AGENTS.md's 'Close-out archiving' "
        f"convention; coalescence-gate item 5). Move them into "
        f"{harness_dir}/archive/ before tagging.",
    )


# ── (3) board item closed ───────────────────────────────────────────────────

def _default_gh_issue_state(repo: str, issue_number: int) -> "str | None":
    """Live `gh issue view` call — the sole side-effecting seam, injectable
    for tests (mirrors check_project_sync.py's own pure-diff / injectable-
    live-fetch posture). Returns the upper-cased state ('OPEN'/'CLOSED'), or
    None on any failure — treated as "can't tell", not a hard error."""
    try:
        proc = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--repo", repo,
             "--json", "state", "-q", ".state"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    state = proc.stdout.strip().upper()
    return state or None


def _load_board_items(board_items_path: Path) -> "list[dict]":
    data = json.loads(board_items_path.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def check_board_item_closed(item_id: "str | None", board_items_path: "Path | None",
                             *, gh_repo: "str | None" = None,
                             gh_issue_state_fn=None) -> CheckResult:
    """(3) The release's board row (GitHub Projects) is closed / moved to
    Done for the shipping item. Prefers the live GitHub issue state (the
    actual board-reconciliation fact); falls back to the vault-side `status`
    field on the board item when it carries no materialized `issue` yet."""
    if not item_id:
        return CheckResult(
            "board-item-closed", "skip",
            "no board item id given — skipping (github-projects not wired "
            "for this release, or no single shipping item to check)",
        )
    if board_items_path is None or not board_items_path.is_file():
        return CheckResult(
            "board-item-closed", "skip",
            f"no board-items.json found at {board_items_path} — skipping",
        )
    try:
        items = _load_board_items(board_items_path)
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult(
            "board-item-closed", "fail",
            f"could not read board-items.json at {board_items_path}: {exc}",
        )
    match = next((it for it in items if it.get("id") == item_id), None)
    if match is None:
        return CheckResult(
            "board-item-closed", "fail",
            f"board item '{item_id}' not found in {board_items_path} — the "
            f"shipping item must be a real, materialized board row",
        )

    issue_number = match.get("issue")
    if issue_number is not None:
        if gh_issue_state_fn is None and not gh_repo:
            return CheckResult(
                "board-item-closed", "skip",
                f"board item '{item_id}' has issue #{issue_number} but no "
                f"--gh-repo was given — skipping the live state check",
            )
        state_fn = gh_issue_state_fn or _default_gh_issue_state
        state = state_fn(gh_repo or "", issue_number)
        if state is None:
            return CheckResult(
                "board-item-closed", "skip",
                f"could not determine the live GitHub state for issue "
                f"#{issue_number} — skipping (gh unavailable or unauthenticated)",
            )
        if state == "CLOSED":
            return CheckResult(
                "board-item-closed", "pass",
                f"board item '{item_id}' (issue #{issue_number}) is closed",
            )
        return CheckResult(
            "board-item-closed", "fail",
            f"board item '{item_id}' (issue #{issue_number}) is still {state} "
            f"on GitHub — coalescence-gate item 3 requires the shipping "
            f"item's board row to be closed/moved to Done before the release "
            f"is cut. Close the issue (or move its board status to Done) and "
            f"re-run.",
        )

    # No materialized issue yet — fall back to the vault-side status field.
    status = str(match.get("status") or "").strip().lower()
    if status == "done":
        return CheckResult(
            "board-item-closed", "pass",
            f"board item '{item_id}' has status Done",
        )
    return CheckResult(
        "board-item-closed", "fail",
        f"board item '{item_id}' has status {match.get('status')!r}, not "
        f"Done — coalescence-gate item 3 requires the shipping item's board "
        f"row to be closed/moved to Done before the release is cut.",
    )


# ── CLI ──────────────────────────────────────────────────────────────────────

_ALL_CHECKS = ("narrative-row", "archive-hygiene", "board-item-closed")


def _resolve_project_json(repo_root: Path) -> "dict | None":
    project_json = repo_root / DEFAULT_HARNESS_DIRNAME / "project.json"
    if not project_json.is_file():
        return None
    try:
        return json.loads(project_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_board_items_path(repo_root: Path, explicit: "Path | None") -> "Path | None":
    if explicit is not None:
        return explicit
    cfg = _resolve_project_json(repo_root)
    src = (cfg or {}).get("items_source")
    return Path(os.path.expanduser(src)) if src else None


def _resolve_gh_repo(repo_root: Path, explicit: "str | None") -> "str | None":
    if explicit:
        return explicit
    cfg = _resolve_project_json(repo_root)
    return ((cfg or {}).get("github") or {}).get("repo")


def _parse_args(argv):
    p = argparse.ArgumentParser(
        prog="coalescence_checks",
        description="Deterministic close-out assertions for ship-release (coalescence-gate items 1, 3, 5).",
    )
    p.add_argument("--tag", required=True, help="the release tag about to be cut, e.g. v3.28.0")
    p.add_argument("--repo-root", default=".", type=Path)
    p.add_argument("--repo-name", default=None, help="defaults to --repo-root's directory name")
    p.add_argument("--narrative-page", default=None, type=Path)
    p.add_argument("--fallback-narrative-page", default=None, type=Path)
    p.add_argument("--harness-dir", default=None, type=Path,
                    help=f"defaults to <repo-root>/{DEFAULT_HARNESS_DIRNAME}")
    p.add_argument("--item-id", default=None, help="the board item id this release ships")
    p.add_argument("--board-items-path", default=None, type=Path)
    p.add_argument("--gh-repo", default=None, help="owner/repo for the live issue-state check")
    p.add_argument("--only", action="append", choices=list(_ALL_CHECKS),
                    help="run only the named check (repeatable); default: all three")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    repo_root = args.repo_root.resolve()
    repo_name = args.repo_name or repo_root.name
    harness_dir = args.harness_dir or (repo_root / DEFAULT_HARNESS_DIRNAME)
    board_items_path = _resolve_board_items_path(repo_root, args.board_items_path)
    gh_repo = _resolve_gh_repo(repo_root, args.gh_repo)

    checks = args.only or list(_ALL_CHECKS)
    results = []
    if "narrative-row" in checks:
        results.append(check_narrative_row(
            args.tag, repo_name, repo_root,
            narrative_page=args.narrative_page,
            fallback_page=args.fallback_narrative_page,
        ))
    if "archive-hygiene" in checks:
        results.append(check_archive_hygiene(harness_dir))
    if "board-item-closed" in checks:
        results.append(check_board_item_closed(args.item_id, board_items_path, gh_repo=gh_repo))

    fail = False
    for r in results:
        marker = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[r.status]
        print(f"coalescence-checks: [{marker}] {r.name} — {r.message}")
        if r.status == "fail":
            fail = True

    if fail:
        print("coalescence-checks: FAIL — fix the blocker(s) above before tagging.")
        return 1
    print("coalescence-checks: PASS (or gracefully skipped) — clear to tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
