#!/usr/bin/env python3
"""orient_render.py — the ORIENT renderer for `/open` / `/orient`
(PLAN-open-a-project-by-name tasks 3 + 5; the brief and the plan list through
agentm since PLAN-tracker-commands task 8; agentm alone since crickets task 101).

Given one confirmed project (a match dict from `resolve_project.resolve()`),
renders a short read-only orientation block:

  - **what it is** — the one-line gloss `resolve_project.py` already extracted
    (the charter's What line).
  - **brief** — agentm's opening brief for the project's checkout, through
    `agentm_bridge.run_project_brief(root_path)`: where the bound project and
    task stand. Left out when agentm has none (exit 3) or the match has no
    `root_path`.
  - **plans** — every active plan agentm lists through
    `agentm_bridge.run_list_plans`: by the checkout (`root_path`), or by the
    project's slug when there is none. The plans in flight come first, by their
    tracker's `importance` and then by name, each with its status from
    `plan_tracker.py status` and a ✅/⬜ step checklist, and the finished ones
    collapse to a count. When agentm lists nothing, one line says so.
  - **recent progress** — the last few progress lines of each unfinished plan.
  - **queued plans** — the plans whose tracker is `queued`.
  - **board state** — a read-only glance at the board ledger github-projects
    reads (the checkout's `project.json` `items_source`, else its default beside
    `project.json`), filtered to items whose title/id matches the confirmed
    project. File-only, no `gh` calls.

Nothing here composes a plan's path: every path comes from the rows agentm
returns.

Task 5 (goal 6, the pointer-note flag): `write_orientation_note()` writes the
rendered block to `<desk>/orientation-note.md`, the project's desk as
`project_homes.py` names it, idempotent overwrite, only ever called from the
`--note` opt-in flag — never from the base render path. It never creates the
desk: without one there is nowhere to put the note.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
import sys  # noqa: E402

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Step 8 of crickets task 101 retires the Status line, and this fallback with it.
def _extract_status(plan_text: str) -> str:
    """The value of the first `Status:` line (markdown-bold tolerated), or "—"."""
    for line in plan_text.splitlines():
        stripped = line.strip().lstrip("*").strip()
        if stripped.lower().startswith("status:"):
            value = stripped[len("status:"):].strip().strip("*").strip()
            return value or "—"
    return "—"


def _load_sibling(name: str):
    """A script from this directory, loaded by path under its own module name,
    so another plugin's `agentm_bridge` already in the process can't stand in
    for this one. None when it can't be loaded."""
    spec = importlib.util.spec_from_file_location(f"orient_render_{name}", _HERE / f"{name}.py")
    if not spec or not spec.loader:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


_bridge = _load_sibling("agentm_bridge")
_plan_tracker = _load_sibling("plan_tracker")
_homes = _load_sibling("project_homes")

_PROGRESS_TAIL_DEFAULT_N = 3
_PROGRESS_LINE_MAXLEN = 200
_FINAL = ("done", "dropped")

_TASK_STATUS_RE = re.compile(r"^-\s*\*\*Status:\*\*\s*\[( |x|X)\]\s*$")
_TASK_TITLE_RE = re.compile(r"^###\s*\d+\.\s*(.+)$")

_ORIENTATION_NOTE_NAME = "orientation-note.md"
_NO_PLAN_LIST = "(no plan list: agentm is absent, or keeps no plans for this project)"
_NO_PLANS = "(agentm lists no plans for this project)"


# ── PLAN status chart ────────────────────────────────────────────────────────────

def _task_checklist(plan_text: str) -> "list[str]":
    """['✅ Step title', '⬜ Step title', ...] parsed from a plan's step
    headings + their `- **Status:** [x]`/`[ ]` lines. Skips a step with no
    parseable status line rather than guessing."""
    lines = plan_text.splitlines()
    out: "list[str]" = []
    current_title: "str | None" = None
    for line in lines:
        title_match = _TASK_TITLE_RE.match(line.strip())
        if title_match:
            current_title = title_match.group(1).strip()
            continue
        status_match = _TASK_STATUS_RE.match(line.strip())
        if status_match and current_title is not None:
            mark = "✅" if status_match.group(1).lower() == "x" else "⬜"
            out.append(f"{mark} {current_title}")
            current_title = None
    return out


# ── recent progress ──────────────────────────────────────────────────────────────

def progress_tail(path: Path, n: int = _PROGRESS_TAIL_DEFAULT_N) -> "list[str]":
    """The last `n` non-empty lines of an append-only progress log. [] if the
    file is missing or unreadable — graceful, never an error."""
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    tail = lines[-n:] if n > 0 else []
    return [
        (ln[: _PROGRESS_LINE_MAXLEN - 1].rstrip() + "…") if len(ln) > _PROGRESS_LINE_MAXLEN else ln
        for ln in tail
    ]


# ── the brief and the plans, through agentm ─────────────────────────────────────

def render_brief(root_path) -> "list[str]":
    """The opening brief's lines for the project's checkout, or [] when agentm
    has none (exit 3), is absent, or the match has no `root_path`."""
    if not root_path or _bridge is None:
        return []
    code, text = _bridge.run_project_brief(root_path)
    if code != 0 or not text:
        return []
    return text.splitlines()


def _plan_rows(project: dict) -> "list[tuple[str, str, str]] | None":
    """Every active plan agentm lists for the project, as (plan, progress,
    tracker) rows: by its checkout, or by its slug when it has none. None when
    agentm gives no listing."""
    if _bridge is None:
        return None
    root_path, slug = project.get("root_path"), project.get("slug")
    if root_path:
        code, rows = _bridge.run_list_plans(root_path)
    elif slug:
        code, rows = _bridge.run_list_plans(project=slug)
    else:
        return None
    return rows if code == 0 else None


def _plan_label(plan: str) -> str:
    """A task's directory name, or a flat plan's file name."""
    p = Path(plan)
    return p.parent.name if p.name == "plan.md" else p.name


def _status(plan: str, tracker: str) -> str:
    """`plan_tracker.py status`: the tracker, else the plan's Status line."""
    if _plan_tracker is not None:
        return _plan_tracker.plan_status(Path(plan), tracker)[0]
    try:
        return _extract_status(Path(plan).read_text(encoding="utf-8"))
    except OSError:
        return "none"


def _importance(tracker: str) -> "int | None":
    """The tracker's `importance`, from `tracker.py show`, when it has one."""
    if not tracker or _bridge is None or not Path(tracker).is_file():
        return None
    code, out, _err = _bridge.run_tracker(["show", tracker])
    if code != 0:
        return None
    try:
        value = json.loads(out).get("importance")
        return int(value) if value is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def _checklist_for(plan: str) -> "list[str]":
    try:
        return _task_checklist(Path(plan).read_text(encoding="utf-8"))
    except OSError:
        return []


def render_plans_from_agentm(
    rows: "list[tuple[str, str, str]]", n: int = _PROGRESS_TAIL_DEFAULT_N,
) -> "tuple[list[str], list[str], list[str]]":
    """(plan blocks, progress lines, queued names) for the rows agentm listed.

    The plans in flight come first, by their tracker's importance (highest
    first, plans without one after) and then by name, each with its status and
    step checklist. Finished plans (`done`, `dropped`) collapse to one count
    line, and `queued` ones are named for the queued section instead. Progress
    tails come only from plans that aren't finished.
    """
    in_flight, queued, finished = [], [], 0
    for plan, progress, tracker in rows:
        status = _status(plan, tracker)
        if status in _FINAL:
            finished += 1
        elif status == "queued":
            queued.append((plan, progress))
        else:
            in_flight.append((plan, progress, tracker, status))
    in_flight.sort(key=lambda row: (-(_importance(row[2]) or 0), _plan_label(row[0])))

    blocks: "list[str]" = []
    for plan, _progress, _tracker, status in in_flight:
        header = f"{_plan_label(plan)} [{status}]"
        checklist = _checklist_for(plan)
        blocks.append(header + ("\n  " + "\n  ".join(checklist) if checklist else ""))
    if finished:
        blocks.append(f"{finished} finished plan{'' if finished == 1 else 's'}")

    progress_lines: "list[str]" = []
    for plan, progress in [(row[0], row[1]) for row in in_flight] + queued:
        tail = progress_tail(Path(progress), n) if progress else []
        if tail:
            progress_lines.append(f"{_plan_label(plan)}:")
            progress_lines.extend(f"  {ln}" for ln in tail)
    return blocks, progress_lines, sorted(_plan_label(plan) for plan, _ in queued)


# ── board state (read-only glance) ──────────────────────────────────────────────

def _board_items_path(root_path) -> "Path | None":
    """The ledger github-projects reads for the checkout: its `project.json`'s
    `items_source`, else `board-items.json` beside `project.json` — the rule
    of github-projects' own `_items_path_from_cfg`. None without a checkout or a
    config."""
    if not root_path:
        return None
    cfg_path = Path(root_path) / ".harness" / "project.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    src = cfg.get("items_source") if isinstance(cfg, dict) else None
    return Path(src) if src else cfg_path.resolve().parent / "board-items.json"


def render_board_state(root_path, project_slug: str) -> "list[str]":
    """Board items whose id/title mentions the confirmed project — a
    read-only glance at the existing board-items.json cache, no `gh` calls.
    [] when project.json / board-items.json is absent or unparsable."""
    items_path = _board_items_path(root_path)
    if items_path is None or not items_path.is_file():
        return []
    try:
        data = json.loads(items_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = data.get("items", [])
    if not isinstance(items, list):
        return []
    needle = project_slug.strip().lower()
    out: "list[str]" = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", ""))
        title = str(item.get("title", ""))
        if needle and needle not in item_id.lower() and needle not in title.lower():
            continue
        status = item.get("status", "—")
        out.append(f"{item.get('type', 'item')}: {title} [{status}]")
    return out


# ── the full render ──────────────────────────────────────────────────────────────

def render_orientation(project: dict) -> str:
    """The full ORIENT block for a confirmed project. Every section degrades
    gracefully to an omitted heading when its source is absent — this
    function never raises."""
    slug = project.get("slug", "?")
    gloss = project.get("gloss")
    root_path = project.get("root_path")

    lines: "list[str]" = [f"# {slug}"]
    if gloss:
        lines.append(gloss)

    brief = render_brief(root_path)
    if brief:
        lines.append("\n## Brief")
        lines.extend(brief)

    rows = _plan_rows(project)
    plan_blocks, progress_blocks, queued = render_plans_from_agentm(rows or [])

    if plan_blocks:
        lines.append("\n## Plans")
        lines.extend(plan_blocks)
    elif not queued:
        lines.append("\n" + (_NO_PLAN_LIST if rows is None else _NO_PLANS))

    if progress_blocks:
        lines.append("\n## Recent progress")
        lines.extend(progress_blocks)

    if queued:
        lines.append("\n## Queued plans")
        lines.extend(f"- {name}" for name in queued)

    board = render_board_state(root_path, slug)
    if board:
        lines.append("\n## Board state")
        lines.extend(f"- {row}" for row in board)

    return "\n".join(lines)


# ── task 5: the goal-6 pointer-note flag ─────────────────────────────────────────

def write_orientation_note(project: dict, rendered_text: str) -> "Path | None":
    """Write `rendered_text` to `<desk>/orientation-note.md`, idempotent
    overwrite (never append), and return the note's path. The desk is the one
    `project_homes.py` names — by the checkout, or by the slug when there is
    none. Never creates it: when agentm names no desk, or the desk doesn't exist
    yet, this writes nothing and returns None. Only ever called from the
    explicit `--note` opt-in — never from the base render path. Raises on a
    genuine write failure (permissions, read-only fs) rather than silently
    dropping the orientation."""
    if _homes is None:
        return None
    root_path, slug = project.get("root_path"), project.get("slug")
    if root_path:
        desk = _homes.home("desk", cwd=root_path)
    elif slug:
        desk = _homes.home("desk", project=slug)
    else:
        return None
    if desk is None or not Path(desk).is_dir():
        return None
    note_path = Path(desk) / _ORIENTATION_NOTE_NAME
    note_path.write_text(rendered_text, encoding="utf-8")
    return note_path
