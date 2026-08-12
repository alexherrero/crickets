#!/usr/bin/env python3
# vault_layout.py — resolve the vault's project-keyed space across layout generations.
#
# That space has moved twice. V4 #26 renamed `personal-projects/` to
# `projects/`; the stage-2 four-space migration (2026-08-11) pushed it one
# level down to `desk/projects/`. A path literal pinned to any one rung
# resolves to nothing on a vault sitting on another — and because a missing
# overlay directory reads exactly like an empty one, the miss never surfaces.
# That is how nine learned voice lessons went silently absent from every
# authored draft after the stage-2 move.
#
# So: probe newest-first, take the first candidate that exists. Same shape as
# agentm's scripts/migrate-harness-to-vault.sh. Two properties carry the fix:
#
#   * The probe runs on the FULL leaf path, not just the projects root. On a
#     vault carrying both rungs, a read finds wherever the lessons actually
#     live instead of the empty new rung sitting beside them.
#   * Reads and writes call the same function, so a captured lesson always
#     lands where the resolver will read it back. The tree cannot fork.
#
# When nothing resolves the answer is the newest layout, so a fresh vault is
# written in the current shape rather than re-creating a retired one.
#
# Stdlib-only; matches the established skill convention.

from __future__ import annotations

from pathlib import Path

# Newest layout first. Each entry is one generation of the project space.
PROJECT_SPACE_SEGMENTS: tuple[tuple[str, ...], ...] = (
    ("desk", "projects"),      # stage-2 four-space migration, 2026-08-11
    ("projects",),             # V4 #26
    ("personal-projects",),    # pre-V4 #26
)

# What a vault with no project space at all gets written into.
CURRENT_SPACE_SEGMENT: tuple[str, ...] = PROJECT_SPACE_SEGMENTS[0]


def projects_space_candidates(vault, *parts: str) -> list:
    """Every layout's path for `<projects-space>/<parts>`, newest rung first."""
    v = Path(vault)
    return [v.joinpath(*seg, *parts) for seg in PROJECT_SPACE_SEGMENTS]


def resolve_existing_under_projects(vault, *parts: str):
    """First candidate for `<projects-space>/<parts>` that exists, else None.

    `None` is the honest answer for "this vault has no such store on any
    layout" — distinct from an empty-but-present store, which is a legitimate
    state and returns its path.
    """
    for cand in projects_space_candidates(vault, *parts):
        if cand.exists():
            return cand
    return None


def resolve_under_projects(vault, *parts: str) -> Path:
    """`<projects-space>/<parts>`, resolved newest-layout-first.

    Falls back to the current layout when no rung resolves, so writes to a
    vault that has no project space yet land in the current shape.
    """
    found = resolve_existing_under_projects(vault, *parts)
    if found is not None:
        return found
    return Path(vault).joinpath(*CURRENT_SPACE_SEGMENT, *parts)


def global_wiki_style_dir(vault) -> Path:
    """The cross-project voice-overlay store, `<projects-space>/_global/wiki-style`."""
    return resolve_under_projects(vault, "_global", "wiki-style")


def project_wiki_style_dir(vault, project_slug: str) -> Path:
    """One project's voice-overlay store, `<projects-space>/<slug>/wiki-style`."""
    return resolve_under_projects(vault, project_slug, "wiki-style")


def global_wiki_style_dir_if_present(vault):
    """The global overlay store only if it exists on some layout, else None.

    The guard behind the silent-miss: callers use this to tell "no overlay
    store anywhere" (worth a word to the operator) from "store present, no
    lessons in it" (a legitimately empty store — say nothing).
    """
    return resolve_existing_under_projects(vault, "_global", "wiki-style")
