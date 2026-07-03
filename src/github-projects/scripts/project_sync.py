#!/usr/bin/env python3
"""project_sync.py — the one deterministic render + write path (DC-4 / rule 6).

crickets github-projects (#41). Task 4 = the **offline render path**; task 5 =
the **live ``gh`` write path** (``post``) on top — the *one* code path that ever
writes an update (design rule 6: this single helper owns render AND gh posting).

Rule 6 (deterministic render): this single stdlib helper owns ALL structure —
field order, dividers, ``YYYY-MM-DD`` dates, and commit/entity link construction
(built from a SHA/id + the remote URL, never hand-typed). The only model-supplied
parts are the human sentences inside the template ``{{placeholders}}``.

Each item's issue body is assembled from its lifecycle thread — ① Kickoff →
② Progress (one line per unit) → ③ Closeout — by filling the locked per-type
templates (task 2) for an item produced by project_model.py (task 3). Optional
clauses (a feature's ``Deferred:``, an idea's ``Could promote →``) drop cleanly
when their value is absent. silent-source attribution is included only in the
**private** render and stripped from the **public** mirror (the github board).

The write path is **idempotent by stable id**: ``plan_item_action`` decides
create / update / no-op by comparing the freshly-rendered body to the body
currently on the item's issue, so a re-run on unchanged state writes nothing
(update-not-duplicate). ``--dry-run`` is the testable boundary — it prints the
exact ``gh`` argv without executing, so the constructed payload is asserted with
no network in CI. Pure planning (``sync_item``) is split from side-effecting
execution (``execute``); the gh argv builders are deterministic given their
inputs. **Scope boundary (task 5):** the body-level lifecycle thread is the
fully-wired path; project membership + the frozen DC-2 field values
(Track/Type/Priority/Start/Target/Status) ship as deterministic argv builders +
an injected-runner-tested id resolver, but the *live* orchestration that threads
runtime node-ids (create → capture URL → item-add → field-edits) is exercised in
task 9's operator-gated backfill, not unit-tested against the network.

stdlib only.
"""
from __future__ import annotations

import argparse
import json
import datetime
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
_CLAUSE_SEP = "  ·  "          # double-space-middot: the between-clause divider
_STAGE_JOIN = "\n\n"           # blank line between lifecycle stages in the body
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Kickoff placeholders per work-type.
_KICKOFF_KEYS = {
    "task": ("goal", "done_when"),
    "plan": ("goal", "done_when"),
    "feature": ("goal", "why_matters"),
    "sub-feature": ("goal", "why_matters"),
}
_WORK_TYPES = frozenset(_KICKOFF_KEYS)


class RenderError(ValueError):
    """Raised on a malformed render: missing required placeholder value, a bad
    date, or an item type with no locked template."""


# ── deterministic link + date construction (rule 6) ──────────────────────────
def commit_url(repo_url: str, sha: str) -> str:
    return f"{repo_url.rstrip('/')}/commit/{sha}"


def issue_url(repo_url: str, number) -> str:
    return f"{repo_url.rstrip('/')}/issues/{number}"


def release_url(repo_url: str, tag: str) -> str:
    return f"{repo_url.rstrip('/')}/releases/tag/{tag}"


def commit_link(repo_url: str, sha: str) -> str:
    return f"[`{sha}`]({commit_url(repo_url, sha)})"


def issue_link(repo_url: str, number, label: str) -> str:
    return f"[{label}]({issue_url(repo_url, number)})"


def release_link(repo_url: str, tag: str) -> str:
    return f"[{tag}]({release_url(repo_url, tag)})"


def fmt_date(value) -> str:
    """Normalize a date to ``YYYY-MM-DD``. Accepts an ISO string (validated) or a
    date/datetime (strftime). Raises RenderError on anything else."""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str) and _DATE_RE.match(value):
        try:
            datetime.date.fromisoformat(value)  # reject impossible calendar dates
        except ValueError:
            raise RenderError(f"date must be YYYY-MM-DD (or a date), got {value!r}")
        return value
    raise RenderError(f"date must be YYYY-MM-DD (or a date), got {value!r}")


def _entity_link(graph, repo_url, entity_id, label=None, default=None):
    """Resolve a referenced entity id -> a link to its materialized issue.

    Falls back to `default` (e.g. the literal word "task") when the entity has no
    materialized issue yet, or to None when there's nothing to link.
    """
    if entity_id and graph is not None and entity_id in graph:
        item = graph[entity_id]
        if item.issue is not None:
            return issue_link(repo_url, item.issue, label or item.title)
    return default


# ── template fill (with optional-clause drop) ────────────────────────────────
def fill(template_text: str, values: dict) -> str:
    """Fill ``{{placeholders}}`` in a single-line template.

    The template is split into ``  ·  ``-separated clauses. A clause is **dropped**
    when any of its placeholders maps to ``None`` (an absent optional — e.g. a
    feature with nothing deferred). A placeholder key that's missing from
    ``values`` entirely is a RenderError (a required value wasn't supplied). The
    single-space ``·`` inside a clause (e.g. ``link · date``) is preserved.
    """
    kept = []
    for clause in template_text.split(_CLAUSE_SEP):
        keys = _PLACEHOLDER.findall(clause)
        for k in keys:
            if k not in values:
                raise RenderError(f"no value supplied for placeholder {{{{{k}}}}}")
        if any(values[k] is None for k in keys):
            continue  # absent optional -> drop the whole clause
        kept.append(_PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), clause))
    return _CLAUSE_SEP.join(kept)


def load_template(templates_dir, name: str) -> str:
    p = Path(templates_dir) / f"{name}.md"
    if not p.exists():
        raise RenderError(f"no template {name!r} in {templates_dir}")
    return p.read_text(encoding="utf-8").strip()


# ── per-stage value preparation ──────────────────────────────────────────────
def _progress_values(t, p, repo_url, graph) -> dict:
    if t == "task":
        return {
            "date": fmt_date(p["date"]),
            "sha": p["sha"],
            "commit_url": commit_url(repo_url, p["sha"]),
            "progress": p["progress"],
        }
    if t == "plan":
        return {
            "date": fmt_date(p["date"]),
            "task_link": _entity_link(graph, repo_url, p.get("task"),
                                      default=p.get("task_label", "task")),
            "progress": p["progress"],
        }
    # feature / sub-feature
    return {
        "date": fmt_date(p["date"]),
        "plan_goal": p["plan_goal"],
        "version": p["version"],
    }


def _closeout_values(t, co, repo_url, graph) -> dict:
    if t == "task":
        return {
            "outcome": co["outcome"],
            "landed_link": commit_link(repo_url, co["sha"]),
            "date": fmt_date(co["date"]),
        }
    if t == "plan":
        return {
            "outcome": co["outcome"],
            "shipped_link": release_link(repo_url, co["release"]),
            "date": fmt_date(co["date"]),
        }
    # feature / sub-feature — release_links is one-or-more, joined; deferred optional.
    # The deferral link is folded INTO the deferred value (not a separate template
    # placeholder): the human-authored `deferred` prose must survive even when the
    # target has no materialized issue yet — appending `→ <link>` only when one
    # resolves, never dropping the whole clause for an absent optional link.
    releases = co.get("releases") or ([co["release"]] if co.get("release") else [])
    deferred = co.get("deferred")
    deferred_link = _entity_link(graph, repo_url, co.get("deferred_target"))
    if deferred and deferred_link:
        deferred = f"{deferred} → {deferred_link}"
    return {
        "outcome": co["outcome"],
        "release_links": " · ".join(release_link(repo_url, r) for r in releases),
        "deferred": deferred,
    }


# ── item render ──────────────────────────────────────────────────────────────
def _render_work_item(item, repo_url, templates_dir, graph) -> str:
    t = item.type
    parts = []
    kf = item.fields.get("kickoff", {})
    parts.append(fill(load_template(templates_dir, f"{t}-kickoff"),
                      {k: kf.get(k) for k in _KICKOFF_KEYS[t]}))
    for p in item.fields.get("progress", []):
        parts.append(fill(load_template(templates_dir, f"{t}-progress"),
                          _progress_values(t, p, repo_url, graph)))
    co = item.fields.get("closeout")
    if co:
        parts.append(fill(load_template(templates_dir, f"{t}-closeout"),
                          _closeout_values(t, co, repo_url, graph)))
    return _STAGE_JOIN.join(parts)


def _render_backlog(item, repo_url, templates_dir, graph) -> str:
    f = item.fields
    parts = [fill(load_template(templates_dir, "backlog-item"), {
        "what": f.get("what"),
        "why_matters": f.get("why_matters"),
        "priority": item.priority,
        "priority_reason": f.get("priority_reason"),
    })]
    promo = f.get("promotion")
    if promo:
        parts.append(fill(load_template(templates_dir, "backlog-item-promotion"), {
            "promoted_link": _entity_link(graph, repo_url, promo.get("target"),
                                          default=promo.get("label")),
            "date": fmt_date(promo["date"]),
        }))
    return _STAGE_JOIN.join(parts)


def render_item(item, repo_url, templates_dir, graph=None, public=True) -> str:
    """Render an item's full issue body deterministically.

    `public=True` (the github-board mirror) strips silent-source attribution;
    `public=False` (a private/local view) appends it. Raises RenderError for an
    item type with no locked template (e.g. ``bug`` — no template this cycle).
    """
    t = item.type
    if t == "version":
        body = fill(load_template(templates_dir, "version"),
                    {"about": item.fields.get("about")})
    elif t in _WORK_TYPES:
        body = _render_work_item(item, repo_url, templates_dir, graph)
    elif t == "backlog-item":
        body = _render_backlog(item, repo_url, templates_dir, graph)
    elif t == "idea":
        body = fill(load_template(templates_dir, "idea"), {
            "spark": item.fields.get("spark"),
            "promote_target": item.fields.get("promote_target"),  # None -> clause drops
        })
    else:
        raise RenderError(f"no locked template for item type {t!r}")

    if not public and item.silent_source:
        body += f"{_STAGE_JOIN}**Source (private):** {item.silent_source}"
    return body


# ══ live gh write path (task 5) ══════════════════════════════════════════════
# Everything below assembles + (optionally) executes `gh` commands. The argv
# builders are pure; execution is isolated in `execute()` behind a `--dry-run`
# boundary and an injectable `runner`, so the constructed payload is asserted in
# CI with no network.

class SyncError(RuntimeError):
    """Raised when a gh command fails or the config/board-items can't be bound."""


# ── config binding ───────────────────────────────────────────────────────────
def load_config(path) -> dict:
    """Load + minimally validate a project.json (the vault↔board binding)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "vault_project" not in data or "github" not in data:
        raise SyncError("project.json must carry 'vault_project' and 'github'")
    gh = data["github"]
    for req in ("owner", "number"):
        if req not in gh:
            raise SyncError(f"project.json github must carry {req!r}")
    return data


def project_repo_url(cfg) -> str:
    """https URL of the backing repo (link construction base). github.repo is
    'owner/name'; falls back to owner + the project owner when repo is omitted."""
    repo = cfg["github"].get("repo")
    if not repo:
        raise SyncError("project.json github.repo ('owner/name') is required")
    return f"https://github.com/{repo}"


def project_url(cfg) -> str:
    gh = cfg["github"]
    if gh.get("url"):
        return gh["url"].rstrip("/")
    return f"https://github.com/users/{gh['owner']}/projects/{gh['number']}"


# ── gh argv builders (deterministic) ─────────────────────────────────────────
def issue_create_argv(repo, title, body):
    return ["gh", "issue", "create", "--repo", repo,
            "--title", title, "--body", body]


def issue_edit_argv(repo, number, body):
    return ["gh", "issue", "edit", str(number), "--repo", repo, "--body", body]


def project_item_add_argv(owner, number, issue_url):
    return ["gh", "project", "item-add", str(number),
            "--owner", owner, "--url", issue_url]


def project_create_argv(owner, title):
    return ["gh", "project", "create", "--owner", owner, "--title", title]


def project_item_edit_text_argv(project_id, item_id, field_id, value):
    return ["gh", "project", "item-edit", "--id", item_id,
            "--project-id", project_id, "--field-id", field_id, "--text", value]


def project_item_edit_date_argv(project_id, item_id, field_id, value):
    return ["gh", "project", "item-edit", "--id", item_id,
            "--project-id", project_id, "--field-id", field_id, "--date", value]


def project_item_edit_select_argv(project_id, item_id, field_id, option_id):
    return ["gh", "project", "item-edit", "--id", item_id,
            "--project-id", project_id, "--field-id", field_id,
            "--single-select-option-id", option_id]


def issue_view_argv(repo, number):
    return ["gh", "issue", "view", str(number), "--repo", repo, "--json", "body"]


_ISSUE_URL_RE = re.compile(r"/issues/(\d+)\s*$")


def parse_created_issue_number(output):
    """Extract the issue number from `gh issue create`'s stdout (the URL of
    the created issue). Returns None on anything that isn't an issue URL."""
    if not output:
        return None
    m = _ISSUE_URL_RE.search(output.strip())
    return int(m.group(1)) if m else None


def issue_comment_argv(repo, number, body):
    return ["gh", "issue", "comment", str(number), "--repo", repo, "--body", body]


def issue_comments_view_argv(repo, number):
    return ["gh", "issue", "view", str(number), "--repo", repo, "--json", "comments"]


def commit_comment_marker(sha):
    return f"<!-- board:sha:{sha[:7]} -->"


def taskclose_comment_marker(item_id):
    return f"<!-- board:taskclose:{item_id} -->"


def render_commit_comment(repo_url, date, sha, summary):
    return (f"{fmt_date(date)} ({commit_link(repo_url, sha)}): {summary}\n"
            f"{commit_comment_marker(sha)}")


def render_taskclose_comment(repo_url, item_id, outcome, sha, date):
    return (f"**Outcome:** {outcome}  ·  **Landed:** {commit_link(repo_url, sha)} · "
            f"{fmt_date(date)}\n{taskclose_comment_marker(item_id)}")


def has_comment_marker(cfg, issue, marker, runner=None):
    """List existing comments (list-and-match — never `--search`, which lags
    the search index and risks a duplicate post on a re-run after a partial
    failure) and report whether `marker` already appears in one.

    Returns True/False when the read succeeds, or None when it can't be
    determined (gh absent, unauthenticated, malformed response) — the caller
    must treat None as "do not post" (never risk a duplicate on an unknown
    state), not as "not yet posted."
    """
    runner = runner or _run_gh
    try:
        raw = runner(issue_comments_view_argv(cfg["github"]["repo"], issue))
        data = json.loads(raw) if isinstance(raw, str) else raw
        return any(marker in (c.get("body") or "") for c in data.get("comments", []))
    except Exception:
        return None


def post_comment(item, update_type, cfg, *, date, commit=None, summary=None,
                 runner=None, dry_run=True, out=None):
    """Post a per-commit or task-close comment with SHA-keyed dedupe, alongside
    (never instead of) the existing body-fold. No-op when the item has no
    materialized issue yet (nothing to comment on), or when `update_type` isn't
    a task-progress/task-closeout post — plan/feature progress lands from the
    full sync, the same boundary `apply_update` already draws.
    """
    runner = runner or _run_gh
    out = out if out is not None else sys.stdout
    if item.issue is None:
        return None
    try:
        itype, stage = update_type.rsplit("-", 1)
    except ValueError:
        return None
    if itype != "task" or stage not in ("progress", "closeout"):
        return None

    repo_url = project_repo_url(cfg)
    if stage == "progress":
        marker = commit_comment_marker(commit)
        body = render_commit_comment(repo_url, date, commit, summary)
    else:
        marker = taskclose_comment_marker(item.id)
        body = render_taskclose_comment(repo_url, item.id, summary, commit, date)

    if has_comment_marker(cfg, item.issue, marker, runner=runner) is not False:
        return None  # already posted, or state unknown — never risk a duplicate

    argv = issue_comment_argv(cfg["github"]["repo"], item.issue, body)
    if dry_run:
        print(GhCommand(argv).render(), file=out)
        return None
    return runner(argv)


def fetch_current_body(cfg, issue, runner=None):
    """Fetch an existing issue's live body via a single `gh issue view` call,
    so the idempotency check compares against real state instead of always
    forcing an update. Never raises — gh absent, unauthenticated, the issue
    missing, or a malformed response all degrade to None (the pre-existing
    always-update behavior), since this is a best-effort preview/read, not a
    write the caller can safely fail on."""
    runner = runner or _run_gh
    try:
        raw = runner(issue_view_argv(cfg["github"]["repo"], issue))
        data = json.loads(raw) if isinstance(raw, str) else raw
        return data.get("body")
    except Exception:
        return None


@dataclass
class GhCommand:
    argv: list

    def render(self) -> str:
        return shlex.join(self.argv)


# ── idempotent action planning (pure) ────────────────────────────────────────
@dataclass
class Action:
    kind: str                 # "create" | "update" | "noop"
    item_id: str
    title: str
    body: str
    issue: int | None = None


def plan_item_action(item, body, current_body=None) -> Action:
    """Decide create / update / no-op for one item — the idempotency core.

    No materialized issue → CREATE. Otherwise compare the freshly-rendered body
    to the body currently on the issue: byte-identical (modulo surrounding
    whitespace) → NOOP (an unchanged re-run writes nothing — update-not-
    duplicate); differ → UPDATE. ``current_body=None`` on an existing issue forces
    an UPDATE (the caller couldn't read the live state, so it must not assume
    no-op).
    """
    if item.issue is None:
        return Action("create", item.id, item.title, body, None)
    if current_body is not None and current_body.strip() == body.strip():
        return Action("noop", item.id, item.title, body, item.issue)
    return Action("update", item.id, item.title, body, item.issue)


def build_commands(action, cfg, issue_url=None) -> list:
    """Translate an Action into the body-level gh commands that realize it.

    CREATE → issue create (+ project item-add once the new issue URL is known —
    a live post-create step; included here only when ``issue_url`` is supplied).
    UPDATE → issue edit. NOOP → no commands.
    """
    if action.kind == "noop":
        return []
    repo = cfg["github"]["repo"]
    if action.kind == "create":
        cmds = [GhCommand(issue_create_argv(repo, action.title, action.body))]
        if issue_url:
            cmds.append(GhCommand(project_item_add_argv(
                cfg["github"]["owner"], cfg["github"]["number"], issue_url)))
        return cmds
    return [GhCommand(issue_edit_argv(repo, action.issue, action.body))]


# ── lifecycle-update fold (the incremental `post`) ───────────────────────────
_UPDATE_STAGES = frozenset({"kickoff", "progress", "closeout"})


def apply_update(item, update_type, *, date, commit=None, summary=None):
    """Fold one lifecycle update into ``item.fields`` IN PLACE, from the flags the
    locked CLI supplies (``--commit`` / ``--summary``). Returns the item.

    ``update_type`` is ``'<type>-<stage>'`` (e.g. ``task-progress``). Only the
    stages the flags can fully supply are first-class — a Task progress line
    (``--commit`` + ``--summary``, one line per commit: the dominant /work hook),
    a Plan progress line (``--summary``, one line per task), and a Task closeout
    (``--summary`` + ``--commit``). A stage that needs template values the flags
    can't carry (a Feature's per-plan progress, a Plan/Feature release closeout)
    is sourced from the full board-items.json sync instead — folding it here would
    write a half-filled update, so it raises RenderError.
    """
    try:
        itype, stage = update_type.rsplit("-", 1)
    except ValueError:
        raise RenderError(f"update type must be '<type>-<stage>', got {update_type!r}")
    if stage not in _UPDATE_STAGES:
        raise RenderError(f"unknown lifecycle stage {stage!r} in {update_type!r}")

    if stage == "progress":
        entry = {"date": date}
        if itype == "task":
            if not (commit and summary):
                raise RenderError("task-progress needs --commit and --summary")
            existing = item.fields.get("progress", [])
            if any(e.get("sha") == commit for e in existing):
                return item  # SHA-keyed dedupe: a re-post of the same commit is a no-op
            entry.update(sha=commit, progress=summary)
        elif itype == "plan":
            if not summary:
                raise RenderError("plan-progress needs --summary")
            entry["progress"] = summary
        else:
            raise RenderError(
                f"{update_type}: incremental progress unsupported — "
                f"feature/sub-feature progress comes from the full sync")
        item.fields.setdefault("progress", []).append(entry)
    elif stage == "closeout":
        if itype != "task":
            raise RenderError(
                f"{update_type}: only task-closeout is flag-supplied — "
                f"plan/feature closeouts (release tags) come from the full sync")
        if not (commit and summary):
            raise RenderError("task-closeout needs --summary (outcome) and --commit")
        item.fields["closeout"] = {"outcome": summary, "sha": commit, "date": date}
    else:  # kickoff
        raise RenderError("kickoff is authored in board-items.json, not posted")
    return item


# ── plan one item → (action, commands) ───────────────────────────────────────
def sync_item(item, cfg, templates_dir, *, graph=None, public=True,
              current_body=None) -> tuple:
    """Render ``item``, plan the idempotent action, build its gh commands. Pure —
    no execution. Returns ``(Action, [GhCommand])``."""
    body = render_item(item, project_repo_url(cfg), templates_dir,
                       graph=graph, public=public)
    action = plan_item_action(item, body, current_body=current_body)
    return action, build_commands(action, cfg)


# ── execution boundary ───────────────────────────────────────────────────────
def _run_gh(argv):
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SyncError(f"gh failed ({proc.returncode}): {shlex.join(argv)}\n{proc.stderr}")
    return proc.stdout.strip()


def execute(cmds, *, dry_run=True, runner=None, out=None) -> list:
    """Run (or, under ``dry_run``, print) each GhCommand. Returns a list of
    ``(argv_line, result)`` pairs — the rendered argv string for every command,
    paired with the runner's return value when live (``None`` under
    ``dry_run``, since nothing executed). The result half matters for a
    ``gh issue create``, whose stdout carries the new issue's URL — dropping it
    silently loses the only way to bind the created issue back to the item."""
    runner = runner or _run_gh
    out = out if out is not None else sys.stdout
    results = []
    for c in cmds:
        line = c.render()
        if dry_run:
            print(line, file=out)
            results.append((line, None))
        else:
            results.append((line, runner(c.argv)))
    return results


# ── id resolution (live; parsing is injected-runner testable) ────────────────
def resolve_field_ids(cfg, runner=None) -> dict:
    """Map field name → {id, options:{name:option_id}} from ``gh project
    field-list --format json``. The gh call is the only live part; the parse is
    pure, so tests drive it with a fake runner returning canned JSON."""
    runner = runner or _run_gh
    raw = runner(["gh", "project", "field-list", str(cfg["github"]["number"]),
                  "--owner", cfg["github"]["owner"], "--format", "json"])
    data = json.loads(raw) if isinstance(raw, str) else raw
    out = {}
    for f in data.get("fields", []):
        entry = {"id": f.get("id"), "options": {}}
        for opt in f.get("options", []) or []:
            entry["options"][opt.get("name")] = opt.get("id")
        out[f.get("name")] = entry
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────
def _items_path_from_cfg(cfg, config_path):
    """Resolve the board-items.json path: an explicit ``items_source`` in the
    config, else a sibling of project.json."""
    src = cfg.get("items_source")
    if src:
        return Path(src)
    return Path(config_path).resolve().parent / "board-items.json"


def _build_parser():
    p = argparse.ArgumentParser(prog="project_sync.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    post = sub.add_parser("post", help="post a lifecycle update to a board item")
    post.add_argument("--config", required=True, help="path to project.json")
    post.add_argument("--type", dest="update_type",
                      help="<type>-<stage>, e.g. task-progress (omit for full re-render)")
    post.add_argument("--issue", type=int, help="target issue number")
    post.add_argument("--id", dest="item_id", help="target item stable id")
    post.add_argument("--commit", help="commit SHA for a progress/closeout line")
    post.add_argument("--summary", help="the human sentence for the update")
    post.add_argument("--date", help="YYYY-MM-DD (default: today)")
    post.add_argument("--templates", help="templates dir (default: ./templates)")
    post.add_argument("--active-plan", action="append", default=[],
                      dest="active_plans", help="plan id to materialize (repeatable)")
    post.add_argument("--private", action="store_true",
                      help="render the private view (keep silent-source attribution)")
    post.add_argument("--dry-run", action="store_true",
                      help="print the exact gh argv without executing")
    return p


def find_item(graph, *, issue=None, item_id=None):
    if item_id is not None:
        if item_id not in graph:
            raise SyncError(f"no item with id {item_id!r}")
        return graph[item_id]
    if issue is not None:
        for it in graph.values():
            if it.issue == issue:
                return it
        raise SyncError(f"no item bound to issue #{issue}")
    raise SyncError("post needs --issue or --id to locate the target item")


def main(argv=None, *, runner=None):
    import datetime
    import importlib.util

    args = _build_parser().parse_args(argv)
    cfg = load_config(args.config)
    runner = runner or _run_gh

    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "project_model", here / "project_model.py")
    pm = importlib.util.module_from_spec(spec)
    # Register before exec: the @dataclass on Item resolves its own module via
    # sys.modules (string annotations under `from __future__ import annotations`),
    # which fails if the module isn't registered yet.
    sys.modules["project_model"] = pm
    spec.loader.exec_module(pm)

    items_path = _items_path_from_cfg(cfg, args.config)
    graph = pm.load(items_path)
    item = find_item(graph, issue=args.issue, item_id=args.item_id)

    date = args.date or datetime.date.today().isoformat()
    if args.update_type:
        apply_update(item, args.update_type, date=date,
                     commit=args.commit, summary=args.summary)
        # The per-commit/task-close comment trail — a second surface alongside
        # the body-fold above, not a replacement for it.
        post_comment(item, args.update_type, cfg, date=date, commit=args.commit,
                     summary=args.summary, runner=runner, dry_run=args.dry_run)

    # A single live read of the current body — real idempotency instead of
    # always forcing an update — for an item that already has a materialized
    # issue. Best-effort: fetch_current_body() degrades to None on any failure.
    current_body = fetch_current_body(cfg, item.issue, runner=runner) \
        if item.issue is not None else None

    # templates/ is a sibling of scripts/ — in src and in the emitted plugin alike.
    tdir = Path(args.templates) if args.templates else here.parent / "templates"
    action, cmds = sync_item(item, cfg, tdir, graph=graph, public=not args.private,
                             current_body=current_body)
    results = execute(cmds, dry_run=args.dry_run, runner=runner)

    # --dry-run is a pure preview boundary: no board-items.json write, no
    # issue-number capture. Live runs persist the graph so a re-run sees real
    # state instead of re-deciding create/update from scratch every time.
    if not args.dry_run:
        if action.kind == "create" and results:
            created = parse_created_issue_number(results[0][1])
            if created is not None:
                item.issue = created
        pm.dump(graph, items_path)

    print(f"# {action.kind}: {item.id} (issue {item.issue})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (SyncError, RenderError) as exc:
        print(f"project_sync: {exc}", file=sys.stderr)
        sys.exit(2)
