#!/usr/bin/env python3
"""Pre-flight reconcile: refuse to (re)launch a lane whose work already shipped (LC-6).

The coordinator stages a batch of worker plans, then activates them one at a time.
A plan can go redundant *before* it is ever activated — a sibling lane shipped the
same work, or the part was folded into an earlier landing (the run's wasted V5-4
lane re-launched an already-shipped plan). This helper is the cheap pre-flight
guard that `/plan --activate` and `/spawn-worker` consult before they mutate: if
the staged/active plan declares the artifacts it is expected to PRODUCE and every
one already exists on `main`, the lane is already shipped — activation/spawn is a
benign no-op (exit 3), not a fresh worktree (LC-6).

**The signal is opt-in + net-new-only.** A plan opts in by listing the NET-NEW
files it ships under `expected_artifacts:` in its frontmatter (inline `[a, b]` or a
YAML block of `- path` lines). "Already shipped" means *every* listed path exists
under the project root — the working tree on the integration branch IS `main` in
the single-writer flow, so a filesystem existence check reads "exists on main"
without a git subprocess. List only files the plan CREATES (absent before it
ships); a plan that merely edits existing files omits the key and the guard stays
dormant. Absent or empty `expected_artifacts` → the guard never fires (proceed) —
fully back-compat, so every plan authored before this guard activates unchanged.

**This is reconcile, not enforcement.** It removes redundant launches; it never
blocks genuine work. A *partial* match (some artifacts present, some not) is NOT
shipped — the lane still has work, so it proceeds. The ROADMAP-Completed variant of
LC-6 (parent ROADMAP item already in Completed) is the same reconcile against a
different source; it is deferred here because it couples to the vault ROADMAP
format, whereas on-`main` artifacts are a repo-local, hermetically-testable signal.

Stdlib-only; mirrors the sibling helpers' shape — pure functions with no side
effects (it only reads files and tests path existence; it never writes or mutates).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# `_FRONTMATTER_RE` duplicates design_doc.py's constant of the same name
# (crickets/design, a different plugin as of the AG Wave A rename 2 — DC-2
# forbids a cross-plugin Python import, "siblings not layers"). Kept in sync
# by test_preflight_reconcile.py's drift test against design_doc's live copy,
# the same duplicate-with-drift-test pattern the PR helpers use (probe #3
# found cross-plugin import unavailable there too).
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)

# The block-list parse below mirrors design_sequence._dependencies_from_block
# (generalized to an arbitrary key) — we need a *list* field here, which
# design_doc's own scalar parser skips (it ignores indented lines).

_ARTIFACTS_KEY = "expected_artifacts"

# Distinct from the 0/1/2 contract the sibling helpers share: a benign no-op, not a
# loud refusal (2) and not a graceful-skip (1). Callers return this when the lane is
# already shipped — the command body surfaces its stderr and does NOT proceed to
# /work or /spawn-worker, but it is "nothing to do", not "something went wrong".
SHIPPED_NOOP = 3


# ── frontmatter list parsing (inline + block forms) ──────────────────────────────

def _parse_inline_list(raw: str) -> list[str]:
    """`[a, b]` (or `[]`) → ['a', 'b'] (or []). Strips quotes + blanks."""
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    items = []
    for tok in inner.split(","):
        t = tok.strip().strip("'\"").strip()
        if t:
            items.append(t)
    return items


def _list_field(fm_text: str, key: str) -> list[str]:
    """The frontmatter `key:`'s value as a list — inline `[a, b]` or a `- item` block.

    Mirrors `design_sequence._dependencies_from_block`, generalized to any key, so a
    hand-edited block list isn't silently dropped (`design_doc.parse_frontmatter`
    skips indented lines, so it cannot read a block list). Returns [] when the key
    is absent or its value empty.
    """
    lines = fm_text.splitlines()
    prefix = f"{key}:"
    for i, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        inline = line.partition(":")[2].strip()
        if inline:
            return _parse_inline_list(inline)
        items: list[str] = []
        for nxt in lines[i + 1:]:
            if not nxt.strip():
                continue  # blank line: a legal YAML continuation, not the block end
            if nxt[:1] in (" ", "\t"):
                s = nxt.strip()
                if s.startswith("-"):
                    item = s[1:].strip().strip("'\"").strip()
                    if item:
                        items.append(item)
                continue
            break  # a non-blank line back at column 0 → a new key; the block ended
        return items
    return []


def expected_artifacts(plan_path: str | os.PathLike) -> list[str]:
    """The plan's declared net-new artifacts (repo-relative), or [] if none/unreadable.

    Read-only: a missing/unreadable plan, or one with no frontmatter, yields [] —
    the guard's dormant default, never a raise (a reconcile must never crash the
    activation it guards).
    """
    try:
        text = Path(plan_path).read_text(encoding="utf-8")
    except OSError:
        return []
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return []
    return _list_field(m.group(1), _ARTIFACTS_KEY)


# ── the reconcile ─────────────────────────────────────────────────────────────────

def already_shipped(plan_path: str | os.PathLike,
                    root: str | os.PathLike) -> tuple[bool, list[str]]:
    """(shipped, present): is every declared artifact already on `main` under `root`?

    `shipped` is True iff the plan declares ≥1 artifact AND every one exists under
    `root` (the repo working tree == `main` in the single-writer flow). `present` is
    the subset that exists (for the caller's message). An empty declaration → the
    dormant default `(False, [])`; a *partial* match → `(False, present)` — the lane
    still has work, so the caller proceeds.
    """
    arts = expected_artifacts(plan_path)
    if not arts:
        return (False, [])
    present = [a for a in arts if (Path(root) / a).exists()]
    return (len(present) == len(arts), present)


def shipped_message(name: str, present: list[str]) -> str:
    """The standard 'already shipped — nothing to do' refusal, shared by both callers.

    Names the slug and the artifacts found on `main` so the operator sees *why* the
    lane was skipped, and how to override (archive the staged plan, or drop its
    `expected_artifacts`). Both `/plan --activate` and `/spawn-worker` emit this so
    the no-op reads identically wherever the lane is launched.
    """
    found = ", ".join(present) if present else "(none listed)"
    return (f"[preflight] plan {name!r} is already shipped — nothing to do: "
            f"every expected artifact already exists on main ({found}). "
            f"Not activating/spawning. Archive the staged plan, or remove its "
            f"expected_artifacts, to override.\n")
