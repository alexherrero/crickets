#!/usr/bin/env python3
"""orient_render.py — the ORIENT renderer for `/open` / `/orient`
(PLAN-open-a-project-by-name tasks 3 + 5).

Given one confirmed project (a match dict from `resolve_project.resolve()`),
renders a short read-only orientation block:

  - **what it is** — the one-line gloss `resolve_project.py` already extracted.
  - **PLAN status chart** — imports `queue_status.py`'s `_list_plan_files` /
    `_extract_status` (no re-derivation) and adds a small per-task ✅/⬜
    checklist parsed from each plan's `- **Status:** [x]`/`[ ]` lines.
  - **recent progress** — the last few non-empty `progress*.md` lines (vs.
    `queue_status.py`'s single-line `_progress_head`).
  - **queued plans** — `<_harness>/queued-plans/*.md` (the tier `stage_plan.py`
    already owns; imports its `_QUEUED_DIR` constant, doesn't re-derive it).
  - **board state** — a read-only glance at `board-items.json` (via
    `project.json`'s `items_source`, or the harness-local fallback), filtered
    to items whose title/id matches the confirmed project. File-only, no `gh`
    calls — the same posture as `/queue-status-lite`.

Task 5 (goal 6, the pointer-note flag): `write_orientation_note()` writes the
rendered block to `<_harness>/orientation-note.md`, idempotent overwrite, only
ever called from the `--note` opt-in flag — never from the base render path.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
import sys  # noqa: E402

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# One owner of plan-file discovery + Status: extraction: the sibling bridge
# (same import contract queue_status.py itself uses for resolve_plan.py).
from queue_status import _extract_status, _list_plan_files  # noqa: E402
from stage_plan import _QUEUED_DIR  # noqa: E402

_PROGRESS_TAIL_DEFAULT_N = 3
_PROGRESS_LINE_MAXLEN = 200

_TASK_STATUS_RE = re.compile(r"^-\s*\*\*Status:\*\*\s*\[( |x|X)\]\s*$")
_TASK_TITLE_RE = re.compile(r"^###\s*\d+\.\s*(.+)$")

_ORIENTATION_NOTE_NAME = "orientation-note.md"


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
    """['✅ Task title', '⬜ Task title', ...] parsed from a plan's task
    headings + their `- **Status:** [x]`/`[ ]` lines. Skips a task with no
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
    """One block per active plan file: its name, `Status:`, and task checklist."""
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
    harness_dir = resolve_harness_dir(project)

    lines: "list[str]" = [f"# {slug}"]
    if gloss:
        lines.append(gloss)

    if harness_dir is None:
        lines.append("\n(no _harness/ found for this project — nothing further to orient on)")
        return "\n".join(lines)

    plan_blocks = render_plan_status(harness_dir)
    if plan_blocks:
        lines.append("\n## Plans")
        lines.extend(plan_blocks)

    progress_blocks = render_recent_progress(harness_dir)
    if progress_blocks:
        lines.append("\n## Recent progress")
        lines.extend(progress_blocks)

    queued = render_queued_plans(harness_dir)
    if queued:
        lines.append("\n## Queued plans")
        lines.extend(f"- {name}" for name in queued)

    board = render_board_state(harness_dir, slug)
    if board:
        lines.append("\n## Board state")
        lines.extend(f"- {row}" for row in board)

    return "\n".join(lines)


# ── task 5: the goal-6 pointer-note flag ─────────────────────────────────────────

def write_orientation_note(harness_dir: Path, rendered_text: str) -> Path:
    """Write `rendered_text` to `<_harness>/orientation-note.md`, idempotent
    overwrite (never append). Creates `_harness/` if it doesn't exist yet.
    Only ever called from the explicit `--note` opt-in — never from the base
    render path. Raises on a genuine write failure (permissions, read-only
    fs) rather than silently dropping the orientation."""
    harness_dir.mkdir(parents=True, exist_ok=True)
    note_path = harness_dir / _ORIENTATION_NOTE_NAME
    note_path.write_text(rendered_text, encoding="utf-8")
    return note_path
