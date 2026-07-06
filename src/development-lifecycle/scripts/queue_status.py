#!/usr/bin/env python3
"""Read-only dashboard of every active plan in `_harness/` — the coordinator's glance.

The developer-workflows `/queue-status-lite` command calls this to list, for each
active plan (`PLAN.md` plus every named `PLAN-<name>.md`), its `Status:` line and
the most-recent entry of the matching `progress*.md`. **Read-only by contract**
(the V5-10 design call): no claim arbitration, no leases, no writes — the human is
the arbiter.

    queue_status.py [--harness-dir PATH]
    # stdout: a deterministic, human-scannable dashboard block

**Two backends, one contract** (mirrors the sibling `resolve_plan.py`). When an
agentm source clone is installed this is a thin **bridge** to agentm's shipped
`queue_status_lite.py` reader — the single owner of the enumeration + render
(naming contract, GDrive-conflict skipping, vault redirection). The bridge
re-emits the reader's stdout verbatim. When **no** agentm clone is found,
developer-workflows still works standalone via a minimal local `.harness/`
enumeration that mirrors the reader's format (so the dashboard degrades, it does
not vanish).

The agentm-clone lookup and the PLAN→progress naming helpers are **imported** from
`resolve_plan.py` — one owner of that logic, never a copy. A status read, never a
gate: always exits 0 in normal use.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# One owner of the agentm-clone lookup + the PLAN/progress naming contract: the
# sibling bridge. The queue reader is harness_memory.py's neighbour in the clone.
from resolve_plan import (  # noqa: E402
    _normalize_plan_name,
    _plan_pair,
    locate_resolver,
)

# Same interpreter that runs this bridge runs the agentm reader — avoids a PATH
# `python3` that differs from the one developer-workflows was launched with.
_PY = sys.executable or "python3"

# Sentinel: `run(reader=_AUTO)` (the default, and what main() uses) locates an
# agentm clone; tests pass `reader=<stub path>` to force the delegate branch or
# `reader=None` to force the standalone `.harness/` fallback.
_AUTO = object()

_READER_NAME = "queue_status_lite.py"
_PROGRESS_HEAD_MAXLEN = 120


# ── locating the agentm reader (sibling of the resolver) ───────────────────────

def locate_reader(*, config_path=None, home=None) -> Path | None:
    """The agentm `queue_status_lite.py`, or None when no clone is installed.

    Delegates the clone lookup to `resolve_plan.locate_resolver` (recorded
    `source_clones.agentm` → conventional `~/Antigravity/agentm`) and returns the
    reader sitting beside `harness_memory.py`. `config_path`/`home` are injectable
    for tests, exactly as on the resolver locator.
    """
    resolver = locate_resolver(config_path=config_path, home=home)
    if resolver is None:
        return None
    reader = resolver.parent / _READER_NAME
    return reader if reader.is_file() else None


# ── the two backends ────────────────────────────────────────────────────────────

def _delegate(reader: Path, harness_dir: str | None) -> tuple[int, str, str]:
    """Shell to the agentm reader and propagate (rc, stdout, stderr) verbatim.

    With no `--harness-dir` the reader resolves the directory from cwd itself
    (vault-backed, or `<repo>/.harness/`), which is the default the command relies
    on. The reader always exits 0; a launch failure surfaces as a soft non-zero.
    """
    cmd = [_PY, str(reader)]
    if harness_dir is not None:
        cmd += ["--harness-dir", str(harness_dir)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception as exc:  # the reader path existed but would not run
        return (1, "", f"[queue_status] could not invoke agentm reader: {exc}\n")
    return (r.returncode, r.stdout, r.stderr)


def _extract_status(plan_text: str) -> str:
    """The value of the first `Status:` line (markdown-bold tolerated), or "—".

    Mirrors the agentm reader's extraction so the standalone dashboard reads the
    same as the delegated one.
    """
    for line in plan_text.splitlines():
        stripped = line.strip().lstrip("*").strip()
        if stripped.lower().startswith("status:"):
            value = stripped[len("status:"):].strip().strip("*").strip()
            return value or "—"
    return "—"


def _progress_head(path: Path) -> str:
    """The most-recent (last non-empty) line of an append-only progress log."""
    if not path.is_file():
        return "(no progress file)"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "(unreadable)"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "(empty)"
    head = lines[-1]
    if len(head) > _PROGRESS_HEAD_MAXLEN:
        head = head[: _PROGRESS_HEAD_MAXLEN - 1].rstrip() + "…"
    return head


def _list_plan_files(harness_dir: Path) -> list[Path]:
    """Active plan files: the singleton `PLAN.md` plus each `PLAN-<name>.md`.

    The `PLAN-*` glob naturally excludes archives (`PLAN.archive.*.md` start
    `PLAN.`, not `PLAN-`). The agentm reader additionally drops GDrive conflict
    copies via `harness_memory`; this minimal fallback skips the obvious conflict
    marker only — the reader is the canonical handler when a clone is present.
    """
    files: list[Path] = []
    singleton = harness_dir / "PLAN.md"
    if singleton.is_file():
        files.append(singleton)
    named = [
        p for p in harness_dir.glob("PLAN-*.md")
        if p.is_file() and "(conflicted copy" not in p.name
    ]
    files.extend(sorted(named, key=lambda p: p.name))
    return files


def _render(harness_dir: Path, rows: list[tuple[str, str, str]]) -> str:
    """A deterministic, human-scannable block (mirrors the agentm reader's render).

    Output depends only on `harness_dir`'s contents — no wall-clock, no colour —
    so it is test-stable.
    """
    if not rows:
        return f"No plans found in {harness_dir}\n"
    width = max(len(name) for name, _, _ in rows)
    lines = [f"Active plans in {harness_dir}:", ""]
    for name, status, head in rows:
        lines.append(f"  {name:<{width}}  [{status}]")
        lines.append(f"  {'':<{width}}  last: {head}")
    return "\n".join(lines) + "\n"


def _fallback(harness_dir: str | None) -> tuple[int, str, str]:
    """Standalone (no agentm clone): a minimal local `.harness/` dashboard.

    Mirrors the reader's format and `Status:`/progress extraction; the reader
    stays the canonical renderer when a clone is present (LC-2 / R1). With no
    explicit dir, defaults to `<cwd>/.harness`.
    """
    hd = Path(harness_dir) if harness_dir is not None else Path.cwd() / ".harness"
    if not hd.is_dir():
        return (0, f"No _harness/ directory to read ({hd}).\n", "")
    rows: list[tuple[str, str, str]] = []
    for plan_path in _list_plan_files(hd):
        try:
            plan_text = plan_path.read_text(encoding="utf-8")
        except OSError:
            plan_text = ""
        status = _extract_status(plan_text)
        progress_name = _plan_pair(_normalize_plan_name(plan_path.name))[1]
        head = _progress_head(hd / progress_name)
        rows.append((plan_path.name, status, head))
    return (0, _render(hd, rows), "")


def run(harness_dir: str | None, *, reader=_AUTO) -> tuple[int, str, str]:
    """Core: delegate to a located agentm reader, else the standalone fallback.

    `reader` defaults to `_AUTO` (locate a clone). A located reader is
    authoritative — its output passes through verbatim; the fallback fires *only*
    when no clone is found (`reader is None`).
    """
    if reader is _AUTO:
        reader = locate_reader()
    if reader is None:
        return _fallback(harness_dir)
    return _delegate(reader, harness_dir)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="queue_status.py",
        description="Read-only dashboard of every active plan in _harness/.",
    )
    p.add_argument(
        "--harness-dir", default=None,
        help="the _harness/ directory to enumerate (default: resolve from cwd).",
    )
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    rc, out, err = run(ns.harness_dir)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
