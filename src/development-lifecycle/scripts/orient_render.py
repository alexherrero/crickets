#!/usr/bin/env python3
"""orient_render.py — the ORIENT renderer for `/open` / `/orient`
(PLAN-open-a-project-by-name tasks 3 + 5; the brief and the plan list through
agentm since PLAN-tracker-commands task 8).

Given one confirmed project (a match dict from `resolve_project.resolve()`),
renders a short read-only orientation block:

  - **what it is** — the one-line gloss `resolve_project.py` already extracted
    (the charter's What line, else a plan's Brief line).
  - **brief** — agentm's opening brief for the project's checkout, through
    `agentm_bridge.run_project_brief(root_path)`: where the bound project and
    task stand. Left out when agentm has none (exit 3) or the match has no
    `root_path`.
  - **plans** — for a match with a `root_path`, every active plan agentm lists
    through `agentm_bridge.run_list_plans(root_path)`, in the flat and the task
    layouts: the plans in flight first, by their tracker's `importance` and then
    by name, each with its status from `plan_tracker.py status` and a ✅/⬜ step
    checklist, and the finished ones collapsed to a count. Without agentm, or
    for a match with no `root_path`, the plans come from the project's
    `_harness/` as before, through `queue_status.py`'s `_list_plan_files` /
    `_extract_status` (imported, not re-derived).
  - **recent progress** — the last few progress lines: of each unfinished plan
    on the agentm path, of every `progress*.md` in `_harness/` otherwise.
  - **queued plans** — the plans whose status is `queued`, and, for a project
    that still has a `_harness/`, the `queued-plans/` tier `stage_plan.py` owns
    (imports its `_QUEUED_DIR` constant, doesn't re-derive it).
  - **board state** — a read-only glance at `board-items.json` (via
    `project.json`'s `items_source`, or the harness-local fallback), filtered
    to items whose title/id matches the confirmed project. File-only, no `gh`
    calls — the same posture as `/queue-status-lite`.

Nothing here composes a plan's path: the agentm path takes every path from the
rows agentm returns, and the fallback reads a `_harness/` that already exists.

Task 5 (goal 6, the pointer-note flag): `write_orientation_note()` writes the
rendered block to `<_harness>/orientation-note.md`, idempotent overwrite, only
ever called from the `--note` opt-in flag — never from the base render path. It
never creates the directory: a project with no `_harness/` has nowhere to put
the note yet.
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

# The retired flat staging tier; step 6 of task 101 drops the listing that reads it.
_QUEUED_DIR = "queued-plans"


# Moved here from queue_status.py when it became a pure bridge to agentm's
# reader (task 101 step 1); this module was their only other user. Steps 6 and 8
# retire the directory read and the Status-line fallback that call them.
def _extract_status(plan_text: str) -> str:
    """The value of the first `Status:` line (markdown-bold tolerated), or "—"."""
    for line in plan_text.splitlines():
        stripped = line.strip().lstrip("*").strip()
        if stripped.lower().startswith("status:"):
            value = stripped[len("status:"):].strip().strip("*").strip()
            return value or "—"
    return "—"


def _list_plan_files(harness_dir: Path) -> "list[Path]":
    """Active plan files: the singleton `PLAN.md` plus each `PLAN-<name>.md`."""
    files: "list[Path]" = []
    singleton = harness_dir / "PLAN.md"
    if singleton.is_file():
        files.append(singleton)
    named = [p for p in harness_dir.glob("PLAN-*.md")
             if p.is_file() and "(conflicted copy" not in p.name]
    files.extend(sorted(named, key=lambda p: p.name))
    return files


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

_PROGRESS_TAIL_DEFAULT_N = 3
_PROGRESS_LINE_MAXLEN = 200
_FINAL = ("done", "dropped")

_TASK_STATUS_RE = re.compile(r"^-\s*\*\*Status:\*\*\s*\[( |x|X)\]\s*$")
_TASK_TITLE_RE = re.compile(r"^###\s*\d+\.\s*(.+)$")

_ORIENTATION_NOTE_NAME = "orientation-note.md"
_NOTHING_FURTHER = "\n(no _harness/ found for this project — nothing further to orient on)"


# ── project → _harness/ resolution ──────────────────────────────────────────────

def resolve_harness_dir(project: dict) -> "Path | None":
    """The confirmed project's `_harness/` dir — vault-backed
    (`vault_project_path/_harness`) preferred over the local checkout
    (`root_path/.harness`); None if neither is present."""
    vault_project_path = project.get("vault_project_path")
    if vault_project_path:
        d = Path(vault_project_path) / "_harness"
        if d.is_dir():
            return d
    root_path = project.get("root_path")
    if root_path:
        d = Path(root_path) / ".harness"
        if d.is_dir():
            return d
    return None


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


def render_plan_status(harness_dir: Path) -> "list[str]":
    """One block per active plan file: its name, `Status:`, and step checklist."""
    blocks: "list[str]" = []
    for plan_path in _list_plan_files(harness_dir):
        try:
            text = plan_path.read_text(encoding="utf-8")
        except OSError:
            continue
        status = _extract_status(text)
        checklist = _task_checklist(text)
        header = f"{plan_path.name} [{status}]"
        if checklist:
            blocks.append(header + "\n  " + "\n  ".join(checklist))
        else:
            blocks.append(header)
    return blocks


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


def render_recent_progress(harness_dir: Path, n: int = _PROGRESS_TAIL_DEFAULT_N) -> "list[str]":
    """Recent progress across every progress*.md the harness dir carries."""
    out: "list[str]" = []
    for progress_path in sorted(harness_dir.glob("progress*.md")):
        tail = progress_tail(progress_path, n)
        if tail:
            out.append(f"{progress_path.name}:")
            out.extend(f"  {ln}" for ln in tail)
    return out


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


def _plan_rows(root_path) -> "list[tuple[str, str, str]] | None":
    """Every active plan agentm lists for the checkout, as (plan, progress,
    tracker) rows; None when the match has no `root_path` or agentm gives no
    listing, which is when the `_harness/` read below still applies."""
    if not root_path or _bridge is None:
        return None
    code, rows = _bridge.run_list_plans(root_path)
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


# ── queued plans ──────────────────────────────────────────────────────────────────

def render_queued_plans(harness_dir: Path) -> "list[str]":
    """Filenames under `<_harness>/queued-plans/` — the inert staging tier
    `stage_plan.py` already owns. [] if the dir is absent or empty."""
    queued_dir = harness_dir / _QUEUED_DIR
    if not queued_dir.is_dir():
        return []
    try:
        return sorted(p.name for p in queued_dir.glob("*.md") if p.is_file())
    except OSError:
        return []


# ── board state (read-only glance) ──────────────────────────────────────────────

def _load_project_config(harness_dir: Path) -> "dict | None":
    cfg_path = harness_dir / "project.json"
    if not cfg_path.is_file():
        return None
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _board_items_path(harness_dir: Path, cfg: "dict | None") -> "Path | None":
    if cfg:
        items_source = cfg.get("items_source")
        if items_source:
            p = Path(items_source)
            if p.is_file():
                return p
    fallback = harness_dir / "board-items.json"
    return fallback if fallback.is_file() else None


def render_board_state(harness_dir: Path, project_slug: str) -> "list[str]":
    """Board items whose id/title mentions the confirmed project — a
    read-only glance at the existing board-items.json cache, no `gh` calls.
    [] when project.json / board-items.json is absent or unparsable."""
    cfg = _load_project_config(harness_dir)
    items_path = _board_items_path(harness_dir, cfg)
    if items_path is None:
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
    harness_dir = resolve_harness_dir(project)

    lines: "list[str]" = [f"# {slug}"]
    if gloss:
        lines.append(gloss)

    brief = render_brief(root_path)
    if brief:
        lines.append("\n## Brief")
        lines.extend(brief)

    rows = _plan_rows(root_path)
    if rows is not None:
        plan_blocks, progress_blocks, queued = render_plans_from_agentm(rows)
        if harness_dir is not None:
            queued = queued + render_queued_plans(harness_dir)
    elif harness_dir is not None:
        plan_blocks = render_plan_status(harness_dir)
        progress_blocks = render_recent_progress(harness_dir)
        queued = render_queued_plans(harness_dir)
    else:
        plan_blocks, progress_blocks, queued = [], [], []

    if harness_dir is None and not (brief or plan_blocks or queued):
        lines.append(_NOTHING_FURTHER)
        return "\n".join(lines)

    if plan_blocks:
        lines.append("\n## Plans")
        lines.extend(plan_blocks)

    if progress_blocks:
        lines.append("\n## Recent progress")
        lines.extend(progress_blocks)

    if queued:
        lines.append("\n## Queued plans")
        lines.extend(f"- {name}" for name in queued)

    if harness_dir is not None:
        board = render_board_state(harness_dir, slug)
        if board:
            lines.append("\n## Board state")
            lines.extend(f"- {row}" for row in board)

    return "\n".join(lines)


# ── task 5: the goal-6 pointer-note flag ─────────────────────────────────────────

def write_orientation_note(harness_dir: "Path | None", rendered_text: str) -> "Path | None":
    """Write `rendered_text` to `<_harness>/orientation-note.md`, idempotent
    overwrite (never append), and return the note's path. Never creates the
    directory: when `harness_dir` is None or doesn't exist there is nowhere to
    put the note yet, so this writes nothing and returns None (where the note
    lives once `_harness/` is gone is part 15's call). Only ever called from the
    explicit `--note` opt-in — never from the base render path. Raises on a
    genuine write failure (permissions, read-only fs) rather than silently
    dropping the orientation."""
    if harness_dir is None or not Path(harness_dir).is_dir():
        return None
    note_path = Path(harness_dir) / _ORIENTATION_NOTE_NAME
    note_path.write_text(rendered_text, encoding="utf-8")
    return note_path
