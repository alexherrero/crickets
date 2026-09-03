#!/usr/bin/env python3
"""resolve_project.py — LOCATE + CONFIRM for `/open` / `/orient`
(PLAN-open-a-project-by-name task 2).

Resolves the operator's "open the file for X" intent to a project / idea /
context across three independent sources, each individually graceful-skip
(never raises, never hangs, degrades to "found nothing" on its own):

  (a) **repo-registry** — agentm's registered-repos list, via
      `agentm_bridge.py repo-registry list` (task 1's new verb).
  (b) **vault project tree** — file-path-loads agentm's `harness_memory.py`
      (same conventional-clone cascade `agentm_bridge.py` already uses) to
      resolve `vault_path()` in-process, then globs the vault's project space
      (vault-root `Projects/` on the current layout, `desk/projects/` before it — see PROJECT_SPACE_SEGMENTS).
      Catches vault-only projects/ideas that were never registered as a repo
      (e.g. a pure design/roadmap context with no local git checkout).
  (c) **agentm recall** — file-path-loads `harness/skills/memory/scripts/
      recall.py`, mirroring `src/research/scripts/agentm_bridge.py`'s
      `load_recall_module()` / `query_semantic()` exactly (same cascade, same
      graceful-skip-to-`[]` contract). A recall hit under
      `<projects-space>/<slug>/...` surfaces that slug as a candidate.

`resolve(query_text)` merges + dedupes the three sources' candidates by
normalized slug and classifies the result as **none** / **one** / **many**
(plain case-insensitive substring/token matching — no ranking model; recall,
source (c), already brings semantic matching for the harder cases).

DC-2: siblings not layers. Every agentm touch point here is either a
subprocess bridge (repo-registry, via agentm_bridge.py) or an isolated
file-path-load of an installed-skill-bundle module (harness_memory.py,
recall.py) — never a direct cross-repo import.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


# ── source (a): repo-registry, via agentm_bridge.py's new verb ─────────────────

def list_registered_repos(*, bridge: "Path | None" = None) -> "list[dict]":
    """[{'slug', 'root_path', 'wiki_path'}, ...], or [] on any failure.

    Graceful-skip: an absent bridge script, a non-zero exit (agentm/vault
    unresolvable — repo-registry's own documented skip), or unparsable JSON
    all resolve to [], never an exception.
    """
    if bridge is None:
        bridge = _HERE / "agentm_bridge.py"
    if not Path(bridge).is_file():
        return []
    try:
        res = subprocess.run(
            [sys.executable, str(bridge), "repo-registry", "list"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if res.returncode != 0 or not res.stdout.strip():
        return []
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError:
        return []
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        return []
    return [r for r in repos if isinstance(r, dict) and r.get("slug")]


# ── source (b): the vault's projects/ tree, via harness_memory.py ──────────────
# Mirrors agentm_bridge.py's own _default_candidate_dirs cascade (no existing
# agentm CLI verb lists vault projects, so this file-path-loads harness_memory.py
# directly, the same in-process pattern research's agentm_bridge.py already uses
# for recall.py, below).

_HARNESS_MEMORY_NAME = "harness_memory.py"

_harness_memory_module = None
_hm_loaded = False


def _bridge_candidate_dirs() -> "list[Path]":
    candidates: "list[Path]" = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(_HERE)
    candidates.append(Path.home() / "Antigravity" / "agentm" / "scripts")
    return candidates


def _find_harness_memory() -> "Path | None":
    for d in _bridge_candidate_dirs():
        c = d / _HARNESS_MEMORY_NAME
        if c.is_file():
            return c.resolve()
    return None


def load_harness_memory_module():
    """Return agentm's harness_memory module, loaded once and cached.

    None if unresolvable — graceful-skip, not an error. `_reset_cache_for_tests`
    clears the cache between isolated test cases.
    """
    global _harness_memory_module, _hm_loaded
    if _hm_loaded:
        return _harness_memory_module
    _hm_loaded = True
    path = _find_harness_memory()
    if path is None:
        _harness_memory_module = None
        return None
    spec = importlib.util.spec_from_file_location("resolve_project_harness_memory_bridge", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["resolve_project_harness_memory_bridge"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        _harness_memory_module = None
        return None
    _harness_memory_module = module
    return module


def resolve_vault_path() -> "Path | None":
    """The agent's MEMORY ROOT, or None — graceful-skip on any failure
    (module unresolvable, the resolver raises, or the path doesn't exist).

    `memory_root()`, not `vault_path()`: the latter is the Obsidian vault, and
    everything below joins agent-tree segments (`desk/projects/…`) onto this.
    Rooting at the vault lands one level too high, where a case-insensitive
    filesystem can match the operator's own `Projects/` folder instead. Falls
    back to `vault_path()` only for a kernel old enough to lack `memory_root`.
    """
    module = load_harness_memory_module()
    if module is None:
        return None
    try:
        resolver = getattr(module, "memory_root", None) or module.vault_path
        vp = resolver()
    except Exception:
        return None
    if not vp:
        return None
    p = Path(vp)
    return p if p.is_dir() else None


def _extract_gloss(text: str) -> "str | None":
    """First `Brief:` line (markdown-bold tolerated), else the first non-empty
    line under `## Objective`."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("*").strip()
        if stripped.lower().startswith("brief:"):
            val = stripped.split(":", 1)[1].strip().strip("*").strip()
            if val:
                return val
        if stripped == "## Objective":
            for nxt in lines[i + 1:]:
                nxt = nxt.strip()
                if nxt:
                    return nxt
            break
    return None


def _one_line_gloss(project_dir: Path) -> "str | None":
    """Best-effort one-line gloss from the project's own design docs or
    _harness/PLAN.md — None if nothing found, never an error."""
    candidates: "list[Path]" = []
    harness = project_dir / "_harness"
    if harness.is_dir():
        plan = harness / "PLAN.md"
        if plan.is_file():
            candidates.append(plan)
        candidates.extend(sorted(harness.glob("PLAN-*.md")))
        designs = harness / "designs"
        if designs.is_dir():
            candidates.extend(sorted(designs.glob("*.md")))
    for c in candidates:
        try:
            text = c.read_text(encoding="utf-8")
        except OSError:
            continue
        gloss = _extract_gloss(text)
        if gloss:
            return gloss
    return None


# The vault's project-keyed space, newest layout generation first. Filing-v2 2b
# (2026-09) lifts it to the vault-root `Projects/` — a SIBLING of the memory
# root, hence the `..` segment; the stage-2 four-space migration (2026-08-11)
# had pushed it down to `desk/projects/`; V4 #26 had already renamed
# `personal-projects/` to `projects/`. Probe rather than pin a literal — a vault
# on any rung stays discoverable, and one that migrates does not silently stop
# resolving projects. Duplicated locally rather than imported from the wiki
# plugin's vault_layout.py: plugins emit independently into dist/, the same
# reason this file file-path-loads harness_memory instead of importing it.
PROJECT_SPACE_SEGMENTS = (("Projects",), ("..", "Projects"), ("desk", "projects"),
                          ("projects",), ("personal-projects",))


def root_sibling_witnessed(vault: "Path") -> bool:
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


def _space_candidates(vault: "Path") -> "list[Path]":
    """Each rung's directory for this vault, newest first — the `..` rung only
    under the witness, the flat `Projects` rung only when it exists with that
    exact name."""
    witnessed = root_sibling_witnessed(vault)
    flat = flat_root_space_present(vault)
    return [vault.joinpath(*seg) for seg in PROJECT_SPACE_SEGMENTS
            if (seg[0] != ".." or witnessed) and (seg != ("Projects",) or flat)]


def vault_projects_dirs(vault: "Path") -> "list[Path]":
    """Every project space this vault has, newest layout first.

    Filing-v2 2b: the newest generation is the vault-ROOT `Projects/` — the
    flat `<memory-root>/Projects`, or the sibling of a nested memory root
    (the `..` segment, probed only under `root_sibling_witnessed`). During
    the merge window both it and `desk/projects/` exist and each may hold
    projects, so listing callers must union the spaces rather than stop at
    the first. Rungs that name the same directory — `Projects/` and the
    V4-era `projects/` on a case-insensitive filesystem — count once, under
    the newest name."""
    out, seen = [], set()
    for cand in _space_candidates(vault):
        if not cand.is_dir():
            continue
        try:
            st = cand.stat()
        except OSError:
            continue
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out


def vault_projects_dir(vault: "Path") -> "Path | None":
    """The newest project space present, or None. Prefer vault_projects_dirs
    for anything that lists; this remains the single-space answer for callers
    that only need "where do new projects go"."""
    dirs = vault_projects_dirs(vault)
    return dirs[0] if dirs else None


def _project_slug_from_vault_relpath(path: str) -> "str | None":
    """The slug in a vault-relative `<projects-space>/<slug>/...` path, else None."""
    parts = Path(path).parts
    for seg in PROJECT_SPACE_SEGMENTS:
        if seg[0] == "..":
            # Root-space paths arrive root-relative ("Projects/<slug>/…"),
            # never with a literal "..".
            seg = seg[1:]
        n = len(seg)
        if len(parts) >= n + 1 and parts[:n] == seg:
            return parts[n]
    return None


def scan_vault_projects(*, vault: "Path | None" = None) -> "list[dict]":
    """[{'slug', 'vault_project_path', 'gloss'}, ...], or [] on any failure."""
    if vault is None:
        vault = resolve_vault_path()
    if vault is None:
        return []
    spaces = vault_projects_dirs(vault)
    if not spaces:
        return []
    # Union the spaces, newest layout winning a slug collision — during the
    # 2b merge window the root space exists (near-empty) while the agent's
    # projects still sit under desk/projects; first-space-only would hide
    # every one of them behind the empty shell.
    by_slug: "dict[str, Path]" = {}
    for space in spaces:
        try:
            entries = [p for p in space.iterdir() if p.is_dir() and not p.name.startswith(".")]
        except OSError:
            continue
        for p in entries:
            by_slug.setdefault(p.name, p)
    return [
        {"slug": slug, "vault_project_path": str(p), "gloss": _one_line_gloss(p)}
        for slug, p in sorted(by_slug.items())
    ]


# ── source (c): agentm recall, mirrors src/research/scripts/agentm_bridge.py ───

_MEMORY_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"

_recall_module = None
_recall_loaded = False


def _recall_candidate_dirs() -> "list[Path]":
    candidates: "list[Path]" = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(_HERE / _MEMORY_SCRIPTS_REL)
    candidates.append(Path.home() / "Antigravity" / "agentm" / _MEMORY_SCRIPTS_REL)
    return candidates


def _find_recall_module_path() -> "Path | None":
    for d in _recall_candidate_dirs():
        c = d / "recall.py"
        if c.is_file():
            return c
    return None


def load_recall_module():
    """Return agentm's recall module, loaded once and cached. None if
    unresolvable (graceful-skip, not an error)."""
    global _recall_module, _recall_loaded
    if _recall_loaded:
        return _recall_module
    _recall_loaded = True
    path = _find_recall_module_path()
    if path is None:
        _recall_module = None
        return None
    spec = importlib.util.spec_from_file_location("resolve_project_recall_bridge", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["resolve_project_recall_bridge"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        _recall_module = None
        return None
    _recall_module = module
    return module


def query_recall(vault: Path, query_text: str, *, k: int = 5) -> "list[dict]":
    """agentm's hybrid recall query. [] if agentm is unresolvable or errors."""
    module = load_recall_module()
    if module is None:
        return []
    try:
        return module.query(vault=vault, query_text=query_text, k=k)
    except Exception:
        return []


def _recall_project_candidates(query_text: str) -> "list[dict]":
    """Recall hits whose vault-relative path starts with `<projects-space>/<slug>/`
    surface that slug as a candidate. [] when recall or the vault is absent,
    or the query is empty (nothing to search for)."""
    if not query_text.strip():
        return []
    vault = resolve_vault_path()
    if vault is None:
        return []
    out: "list[dict]" = []
    for hit in query_recall(vault, query_text):
        slug = _project_slug_from_vault_relpath(hit.get("path") or "")
        if slug:
            out.append({"slug": slug, "recall_score": hit.get("combined")})
    return out


# ── merge + classify ────────────────────────────────────────────────────────────

def _normalize_slug(s: str) -> str:
    return s.strip().lower().replace(" ", "-").replace("_", "-")


def _merge_candidates(*groups: "list[dict]") -> "list[dict]":
    merged: "dict[str, dict]" = {}
    for group in groups:
        for cand in group:
            slug = cand.get("slug")
            if not slug:
                continue
            key = _normalize_slug(slug)
            if key not in merged:
                entry = dict(cand)
                entry["slug"] = slug
                merged[key] = entry
            else:
                existing = merged[key]
                for field in ("root_path", "wiki_path", "vault_project_path", "gloss", "recall_score"):
                    if not existing.get(field) and cand.get(field):
                        existing[field] = cand[field]
    return list(merged.values())


def _matches_query(candidate: dict, query_text: str) -> bool:
    q = query_text.strip().lower()
    if not q:
        return True
    haystacks = [candidate.get("slug") or "", candidate.get("gloss") or ""]
    q_tokens = q.split()
    for h in haystacks:
        h_low = h.lower()
        if q in h_low:
            return True
        if q_tokens and all(tok in h_low for tok in q_tokens):
            return True
    return False


def resolve(query_text: str) -> dict:
    """LOCATE + classify. Returns
    {"matches": [{"slug", "root_path"?, "wiki_path"?, "vault_project_path"?,
    "gloss"?}, ...], "classification": "none" | "one" | "many"}.

    Every source degrades independently — an all-absent agentm still returns
    a clean {"matches": [], "classification": "none"}, never an exception.
    """
    repo_cands = list_registered_repos()
    vault_cands = scan_vault_projects()
    recall_cands = _recall_project_candidates(query_text)
    merged = _merge_candidates(repo_cands, vault_cands, recall_cands)
    matches = [c for c in merged if _matches_query(c, query_text)]
    matches.sort(key=lambda c: c["slug"].lower())

    if len(matches) == 0:
        classification = "none"
    elif len(matches) == 1:
        classification = "one"
    else:
        classification = "many"

    return {"matches": matches, "classification": classification}


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level caches between isolated test cases."""
    global _harness_memory_module, _hm_loaded, _recall_module, _recall_loaded
    _harness_memory_module = None
    _hm_loaded = False
    _recall_module = None
    _recall_loaded = False


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="resolve_project.py",
        description="LOCATE + CONFIRM a project/idea/context by name.",
    )
    ap.add_argument("query", nargs="?", default="", help="the operator's raw query text")
    ap.add_argument("--json", action="store_true", help="emit the raw result dict")
    return ap


def main(argv: "list[str]") -> int:
    ns = _build_parser().parse_args(argv[1:])
    result = resolve(ns.query)
    if ns.json:
        print(json.dumps(result, indent=2))
    else:
        for m in result["matches"]:
            print(f"{m['slug']} — {m.get('gloss') or '(no gloss)'}")
        print(f"classification: {result['classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
