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
# `$MEMORY_ROOT` is returned as-is: the variable names the memory tree to every
# consumer that reads it, so joining the prefix again would address
# `<vault>/Agent/Agent`. Same contract as harness_memory.memory_root().
# `$MEMORY_VAULT_PATH` is the deprecated alias agentm exports alongside it for
# one release; it is read only when `$MEMORY_ROOT` is unset or empty.
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

    Order: explicit CLI value -> `$MEMORY_ROOT` (else `$MEMORY_VAULT_PATH`;
    as-is, already a memory root) -> config `vault_path` joined with
    `plugins.obsidian-vault.memory_root`.
    Returns None when nothing resolves to a real directory — graceful-skip, the
    same shape every caller here already handles.
    """
    for raw in (cli_value, os.environ.get("MEMORY_ROOT") or os.environ.get("MEMORY_VAULT_PATH", "")):
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


# Newest layout first. Each entry is one generation of the project space. The
# root casing (agentm-vault plan 08, 2026-09-14) spells the root space
# lowercase; both spellings stay listed so a vault on either side of the rename
# resolves, and on a case-insensitive disk they name one directory.
PROJECT_SPACE_SEGMENTS: tuple[tuple[str, ...], ...] = (
    ("projects",),             # the root space of a FLAT vault since the root casing; also the V4 #26 spelling
    ("..", "projects"),        # the root casing, 2026-09-14: vault-ROOT projects/, sibling of a NESTED memory root
    ("Projects",),             # filing-v2 2b: the root space of a FLAT vault, spelled the retired way
    ("..", "Projects"),        # filing-v2 2b, 2026-09: vault-ROOT Projects/, spelled the retired way
    ("desk", "projects"),      # stage-2 four-space migration, 2026-08-11
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
    """Whether a directory named `projects` — in either spelling — sits at the
    memory root, which is what admits the Title Case flat rung. The name is
    read from the listing, case-folded, so a vault on either side of the root
    casing answers; the lowercase rung needs no witness, since it is the V4-era
    spelling as well as the root space's."""
    v = Path(vault)
    try:
        return any(p.name.lower() == "projects" and p.is_dir() for p in v.iterdir())
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
            return as_listed(cand, vault)
    return None


def as_listed(cand, vault) -> Path:
    """A rung's path under `vault` (or, through a leading `..`, beside it)
    with each segment spelled as its directory lists it, the `..` kept. A
    case-insensitive disk opens `projects` on a vault still spelled
    `Projects`; the path handed back names what is there, on any disk."""
    cand, vault = Path(cand), Path(vault)
    try:
        parts = cand.relative_to(vault).parts
    except ValueError:
        return cand
    nested = parts[:1] == ("..",)
    out = vault.parent if nested else vault
    spelled = []
    for part in (parts[1:] if nested else parts):
        try:
            names = {n.lower(): n for n in os.listdir(out)}
        except OSError:
            return cand
        real = names.get(part.lower(), part)
        spelled.append(real)
        out = out / real
    return vault.joinpath("..", *spelled) if nested else vault.joinpath(*spelled)


def resolve_under_projects(vault, *parts: str) -> Path:
    """`<projects-space>/<parts>`, resolved newest-layout-first.

    Falls back to the current layout when no rung resolves, so writes to a
    vault that has no project space yet land in the current shape.
    """
    found = resolve_existing_under_projects(vault, *parts)
    if found is not None:
        return found
    return Path(vault).joinpath(*CURRENT_SPACE_SEGMENT, *parts)


# ── standards/ — the always-load tier and the voice library ─────────────────
#
# agentm-vault plan 05 (the memory-root trims, 2026-09-11) moved two more
# stores. The always-load pen `<memory-space>/_always-load/` folded into
# `<vault>/standards/`, the operator's rule files; the cross-project voice
# rules left `<projects-space>/_global/wiki-style/` for `<vault>/standards/voice/`.
# Both sit at the VAULT root beside a nested memory root, so the sibling probe
# comes first — under the same witness the `..` Projects rung uses, or a
# `standards/` directory beside the root (the loader's own contract) — and the
# flat `<memory-root>/standards` second. The retired rungs stay behind as the
# fallback, so a vault on either side of the move resolves; nothing here
# conjures `standards/` on a vault that has none.

STANDARDS_DIRNAME = "standards"
VOICE_DIRNAME = "voice"


def standards_dir_candidates(vault) -> list:
    """`<vault>/standards` spelled both ways, sibling first when witnessed."""
    v = Path(vault)
    out = []
    witnessed = root_sibling_witnessed(v) or (
        (v.parent / STANDARDS_DIRNAME).is_dir() and not (v / ".obsidian").is_dir())
    if witnessed:
        out.append(v.parent / STANDARDS_DIRNAME)
    out.append(v / STANDARDS_DIRNAME)
    return out


def standards_dir_if_present(vault):
    """The standards directory on whichever spelling exists, else None."""
    for cand in standards_dir_candidates(vault):
        if cand.is_dir():
            return cand
    return None


def voice_library_dir_if_present(vault):
    """`<standards>/voice/` when it exists, else None."""
    s = standards_dir_if_present(vault)
    if s is not None and (s / VOICE_DIRNAME).is_dir():
        return s / VOICE_DIRNAME
    return None


def global_wiki_style_dir(vault) -> Path:
    """The cross-project voice store: `<vault>/standards/voice/` since the
    memory-root trims, `<projects-space>/_global/wiki-style/` before them."""
    voice = voice_library_dir_if_present(vault)
    if voice is not None:
        return voice
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
    """The always-injected tier: `<vault>/standards/` since the memory-root
    trims (the operator's rule files, read whole every session), the retired
    pen `<memory-space>/_always-load` on a vault that still has only that.
    A convention captured here lands in standards/ — where the loader reads
    it — on a migrated vault, and in the pen on an unmigrated one."""
    s = standards_dir_if_present(root)
    if s is not None:
        return s
    return resolve_under_memory(root, "_always-load")


# The project every feature's working state files under since plan 05: the
# watchlists are agentm's feature state, not memory, and you edit them in
# Obsidian, so they live in the vault's project space.
FEATURE_PROJECT = "agentm"


def watchlist_dir(root) -> Path:
    """The forward-learning watchlist: `resources/watchlist` at the vault root
    since the AgentKV layout move (agentm task 176, 2026-09-24),
    `<projects-space>/agentm/_watchlist` after the memory-root trims and
    before the move, `<memory-space>/_watchlist` before them."""
    v = Path(root)
    for base in ([v.parent, v] if root_sibling_witnessed(v) else [v]):
        cand = base / "resources" / "watchlist"
        if cand.is_dir():
            return cand
    found = resolve_existing_under_projects(root, FEATURE_PROJECT, "_watchlist")
    if found is not None:
        return found
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
    voice = voice_library_dir_if_present(vault)
    if voice is not None:
        return voice
    return resolve_existing_under_projects(vault, "_global", "wiki-style")
