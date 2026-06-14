#!/usr/bin/env python3
"""project_sync.py — the one deterministic render + write path (DC-4 / rule 6).

crickets github-projects (#41). Task 4 = the **offline render path** (this file);
task 5 adds the live ``post`` (gh) write path on top.

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

stdlib only. No ``gh`` calls in this module.
"""
from __future__ import annotations

import re
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
    releases = co.get("releases") or ([co["release"]] if co.get("release") else [])
    return {
        "outcome": co["outcome"],
        "release_links": " · ".join(release_link(repo_url, r) for r in releases),
        "deferred": co.get("deferred"),
        "deferred_link": _entity_link(graph, repo_url, co.get("deferred_target")),
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
