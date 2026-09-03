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

import json
import os
from pathlib import Path

# ── The memory root ─────────────────────────────────────────────────────────
#
# `vault_path` and the memory root are two different directories and conflating
# them is its own silent miss. The kernel is explicit about it:
#
#   vault_path()   -> the Obsidian vault      (/Users/…/Vault)
#   memory_root()  -> the agent's own tree    (/Users/…/Vault/Agent)
#
# `memory_root` is `vault_path` joined with `plugins.obsidian-vault.memory_root`
# from the install config. Anything addressing agent content — memory/,
# desk/projects/, _meta/ — wants the memory root; only callers reaching for the
# repository or the operator's OWN notes want the vault root. Resolving the
# vault root and then joining `desk/projects` onto it lands one level too high,
# and on a case-insensitive filesystem `<vault>/projects` can collide with the
# operator's own `Projects/` folder — a wrong neighbor, not just a miss.
#
# `$MEMORY_VAULT_PATH` is returned as-is: the variable has always named the
# memory tree to the consumers that read it, so joining the prefix again would
# address `<vault>/Agent/Agent`. Same contract as harness_memory.memory_root().
#
# Mirrored here rather than imported — the agentm kernel is not bundled with a
# dist-installed plugin.

_CONFIG_NAME = ".agentm-config.json"
_MEMORY_ROOT_KEY = "plugins.obsidian-vault.memory_root"
_PLUGIN_VAULT_PATH_KEY = "plugins.obsidian-vault.vault_path"


def _install_prefix() -> Path:
    prefix = os.environ.get("AGENTM_INSTALL_PREFIX", "").strip()
    return Path(os.path.expanduser(prefix)) if prefix else Path.home() / ".claude"


def _read_config(install_prefix: Path | None = None) -> dict:
    config = (install_prefix or _install_prefix()) / _CONFIG_NAME
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_memory_root(cli_value: str | None = None,
                        install_prefix: Path | None = None):
    """The agent's own tree, or None. Never a cached literal.

    Order: explicit CLI value -> `$MEMORY_VAULT_PATH` (as-is; already a memory
    root) -> config `vault_path` joined with `plugins.obsidian-vault.memory_root`.
    Returns None when nothing resolves to a real directory — graceful-skip, the
    same shape every caller here already handles.
    """
    for raw in (cli_value, os.environ.get("MEMORY_VAULT_PATH", "")):
        if raw and raw.strip():
            p = Path(os.path.expanduser(raw.strip()))
            return p if p.is_dir() else None
    data = _read_config(install_prefix)
    vp = data.get(_PLUGIN_VAULT_PATH_KEY) or data.get("vault_path")
    if not isinstance(vp, str) or not vp.strip():
        return None
    root = Path(os.path.expanduser(vp.strip()))
    rel = data.get(_MEMORY_ROOT_KEY)
    if isinstance(rel, str) and rel.strip():
        root = root.joinpath(*rel.strip().split("/"))
    return root if root.is_dir() else None


# Newest layout first. Each entry is one generation of the project space.
PROJECT_SPACE_SEGMENTS: tuple[tuple[str, ...], ...] = (
    ("Projects",),             # filing-v2 2b: the root space of a FLAT vault (memory root = vault root)
    ("..", "Projects"),        # filing-v2 2b, 2026-09: vault-ROOT Projects/, sibling of a NESTED memory root
    ("desk", "projects"),      # stage-2 four-space migration, 2026-08-11
    ("projects",),             # V4 #26
    ("personal-projects",),    # pre-V4 #26
)

# What a vault with no project space at all gets written into. The root
# generation is discovered, never conjured: a create-when-absent target that
# escapes the memory root (`..`) would land outside any vault a scratch test
# builds, and one that conjures `<memory-root>/Projects` would invent the
# root generation — so the default is the last pre-2b layout, the same call
# agentm's resolve_project makes for a new project.
CURRENT_SPACE_SEGMENT: tuple[str, ...] = ("desk", "projects")


def root_sibling_witnessed(vault) -> bool:
    """Whether the `..` rung may be probed at all: the memory root is nested
    inside an Obsidian vault — `.obsidian/` at the parent, none at the memory
    root itself. A flat vault (the memory root at the top of its own vault)
    has the operator's home or a sync folder for a parent, where a directory
    named `Projects` is common and is not the vault's; probing it would
    resolve every project into the operator's own tree (agentm's 2b review
    found exactly that). The flat generation `<memory-root>/Projects` needs
    no witness — it is inside the memory root."""
    v = Path(vault)
    return (v.parent / ".obsidian").is_dir() and not (v / ".obsidian").is_dir()


def flat_root_space_present(vault) -> bool:
    """Whether `<memory-root>/Projects` exists with exactly that name — on a
    case-insensitive filesystem `Projects/` would otherwise answer for the
    V4-era `projects/` rung and every legacy project would read as root-space."""
    v = Path(vault)
    try:
        return (v / "Projects").is_dir() and any(p.name == "Projects" for p in v.iterdir())
    except OSError:
        return False


def projects_space_candidates(vault, *parts: str) -> list:
    """Every layout's path for `<projects-space>/<parts>`, newest rung first —
    the `..` rung only under the witness, the flat `Projects` rung only when
    it exists with that exact name."""
    v = Path(vault)
    witnessed = root_sibling_witnessed(v)
    flat = flat_root_space_present(v)
    return [v.joinpath(*seg, *parts) for seg in PROJECT_SPACE_SEGMENTS
            if (seg[0] != ".." or witnessed) and (seg != ("Projects",) or flat)]


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


# ── The memory space ────────────────────────────────────────────────────────
#
# The second half of the same migration: the personal-notes space was renamed
# `personal-private/` -> `personal/` (V5-3) -> `memory/` (stage-2, 2026-08-11).
# Same probe discipline, same reason.

MEMORY_SPACE_SEGMENTS: tuple[tuple[str, ...], ...] = (
    ("memory",),             # stage-2 four-space migration, 2026-08-11
    ("personal",),           # V5-3
    ("personal-private",),   # pre-V5-3
)

CURRENT_MEMORY_SEGMENT: tuple[str, ...] = MEMORY_SPACE_SEGMENTS[0]


def resolve_existing_under_memory(root, *parts: str):
    """First existing candidate for `<memory-space>/<parts>`, else None."""
    r = Path(root)
    for seg in MEMORY_SPACE_SEGMENTS:
        cand = r.joinpath(*seg, *parts)
        if cand.exists():
            return cand
    return None


def resolve_under_memory(root, *parts: str) -> Path:
    """`<memory-space>/<parts>`, newest generation first, current one as fallback."""
    found = resolve_existing_under_memory(root, *parts)
    if found is not None:
        return found
    return Path(root).joinpath(*CURRENT_MEMORY_SEGMENT, *parts)


def always_load_dir(root) -> Path:
    """The always-injected entry tier, `<memory-space>/_always-load`."""
    return resolve_under_memory(root, "_always-load")


def watchlist_dir(root) -> Path:
    """The forward-learning watchlist, `<memory-space>/_watchlist`."""
    return resolve_under_memory(root, "_watchlist")


def find_memory_entry(root, filename: str):
    """Locate a curated memory entry by filename anywhere in the memory space.

    The always-load tier is a *tier*, not a permanent address: an entry that
    graduates out of it stays curated content and moves into the dated tree
    (`memory/2026/07/…`). A caller that only probes `_always-load/` therefore
    loses the entry the moment it graduates — which is what happened to
    voice-kernel.md. Returns the shallowest match so a promoted copy in
    `_always-load/` still wins over an archived one, or None.
    """
    space = resolve_existing_under_memory(root)
    if space is None:
        return None
    matches = sorted(space.rglob(filename), key=lambda p: (len(p.parts), str(p)))
    return matches[0] if matches else None


def global_wiki_style_dir_if_present(vault):
    """The global overlay store only if it exists on some layout, else None.

    The guard behind the silent-miss: callers use this to tell "no overlay
    store anywhere" (worth a word to the operator) from "store present, no
    lessons in it" (a legitimately empty store — say nothing).
    """
    return resolve_existing_under_projects(vault, "_global", "wiki-style")
