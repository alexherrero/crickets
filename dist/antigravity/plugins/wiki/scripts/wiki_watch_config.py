#!/usr/bin/env python3
# wiki_watch_config.py — config + wiki-target resolution for the wiki-watcher
# (wiki-maintenance part 4/5, the wiki-watcher (W1), task 1).
#
# The wiki-watch engine reads its config through THREE existing sources — there
# is no new config file (DC-W2), and config never lives in the vault (DC-8):
#
#   (a) Host enablement   <install-prefix>/.agentm-config.json
#                         A device-level opt-in toggle. The watcher autonomously
#                         dispatches the documenter (and, PR-default, opens PRs),
#                         so it stays OFF until the operator turns it on. Read
#                         vault-free, mirroring harness_memory._read_config_state_mode.
#
#   (b) Per-repo run cfg   <repo>/.harness/wiki-watch.json   (NET-NEW marker)
#                         The per-repo opt-in + run config: which sources to watch
#                         and the dispatch mode {pr|direct}. Modeled on
#                         harness_memory._read_mode_marker, but JSON-shaped because
#                         it carries structure (a flat .project-mode marker can't).
#                         Its PRESENCE signals "watch this repo"; absent → skip.
#
#   (c) Wiki target        repo_registry  <vault>/_meta/repos.json  (NET-NEW resolver)
#                         repos.json already carries an optional per-entry wiki_path
#                         but ships NO repo->wiki lookup. This module adds one:
#                         match the watched repo (by root_path or slug) -> wiki_path,
#                         falling back to <root>/wiki when wiki_path is absent but the
#                         dir exists, else skip. Reached via a path-fallback shell-out
#                         to agentm's repo_registry.py (kernel infra is NOT folded in —
#                         parent Dependencies bucket B), with graceful-skip when agentm
#                         is unreachable (mirrors recent-wiki-changes.sh:86-94).
#
# The PURE resolvers (read_enablement / read_run_config / resolve_wiki_target)
# take explicit inputs and are deterministically unit-tested (DC-W8). The locator
# / shell-out layer is best-effort + graceful-skip; it is not unit-tested against a
# live agentm.
#
# Stdlib-only; matches the established skill/script convention.

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ----------------------------------------------------------------------------
# (a) Host enablement — <install-prefix>/.agentm-config.json
# ----------------------------------------------------------------------------

_VALID_DISPATCH_MODES = {"pr", "direct"}
_DEFAULT_DISPATCH_MODE = "pr"  # DC-W1: PR is the default boundary; direct is opt-in.

# Default watch set when the marker omits `watch_sources`. "." = the whole repo;
# the task-2 significance pre-filter drops noise (lockfiles / dist/ / *.pyc) and
# keeps doc-relevant paths (code + PLAN/design/ROADMAP).
DEFAULT_WATCH_SOURCES = ["."]


def _agentm_install_prefix() -> Path:
    """Resolve the install prefix per the agentm convention:
    $AGENTM_INSTALL_PREFIX -> ~/.claude. (Mirrors harness_memory._agentm_install_prefix.)"""
    raw = os.environ.get("AGENTM_INSTALL_PREFIX", "").strip()
    if raw:
        return Path(os.path.expanduser(raw))
    return Path.home() / ".claude"


def _load_agentm_config(install_prefix: Optional[Path] = None) -> Optional[dict]:
    """Parse <install-prefix>/.agentm-config.json, or None when absent / unreadable /
    not a JSON object. Vault-free (DC-8): config is on-host only."""
    if install_prefix is None:
        install_prefix = _agentm_install_prefix()
    config_path = install_prefix / ".agentm-config.json"
    if not config_path.is_file():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def read_enablement(install_prefix: Optional[Path] = None) -> bool:
    """True iff the wiki-watcher is enabled on this device.

    Reads <install-prefix>/.agentm-config.json (vault-free). Recognized shapes,
    nested block first:

        {"wiki_watch": {"enabled": true}}      # canonical (extensible)
        {"wiki_watch_enabled": true}            # top-level alias shorthand

    The watcher dispatches autonomously, so it is OPT-IN: absent config, an
    unreadable / malformed file, or a falsey value all resolve to False.
    """
    data = _load_agentm_config(install_prefix)
    if data is None:
        return False
    block = data.get("wiki_watch")
    if isinstance(block, dict) and "enabled" in block:
        return bool(block.get("enabled"))
    return bool(data.get("wiki_watch_enabled"))


def read_vault_path(install_prefix: Optional[Path] = None) -> Optional[str]:
    """Resolve the MemoryVault root for registry/state lookups, vault-free of the
    agentm kernel: $MEMORY_VAULT_PATH env (must exist) -> .agentm-config.json::vault_path.

    Returns the path string when a directory exists there, else None (graceful-skip).
    Mirrors harness_memory.vault_path() without importing agentm_config.py (not bundled).
    """
    raw = os.environ.get("MEMORY_VAULT_PATH", "").strip()
    if raw:
        p = Path(os.path.expanduser(raw))
        return str(p) if p.is_dir() else None
    data = _load_agentm_config(install_prefix)
    if data is None:
        return None
    vp = data.get("vault_path")
    if not isinstance(vp, str) or not vp.strip():
        return None
    p = Path(os.path.expanduser(vp.strip()))
    return str(p) if p.is_dir() else None


# ----------------------------------------------------------------------------
# (b) Per-repo run config — <repo>/.harness/wiki-watch.json  (NET-NEW marker)
# ----------------------------------------------------------------------------

WIKI_WATCH_MARKER_REL = Path(".harness") / "wiki-watch.json"


@dataclass
class RunConfig:
    """Normalized per-repo run config parsed from the marker."""
    watch_sources: list[str]
    dispatch_mode: str               # "pr" | "direct"
    raw: dict = field(default_factory=dict)

    @property
    def is_direct(self) -> bool:
        return self.dispatch_mode == "direct"


def marker_path(repo_root: Path | str) -> Path:
    """The per-repo run-config marker path: <repo>/.harness/wiki-watch.json."""
    return Path(repo_root) / WIKI_WATCH_MARKER_REL


def parse_run_config(data: dict) -> RunConfig:
    """Normalize a parsed marker dict into a RunConfig. Pure (no I/O).

    - `watch_sources`: a list of repo-relative paths/globs; non-list or empty ->
      DEFAULT_WATCH_SOURCES; non-string entries dropped.
    - `dispatch_mode`: lowercased; anything outside {pr, direct} (incl. absent) ->
      the safe default "pr" (DC-W1: direct-commit is an explicit opt-in only).
    """
    raw_sources = data.get("watch_sources")
    if isinstance(raw_sources, list):
        sources = [s for s in raw_sources if isinstance(s, str) and s.strip()]
    else:
        sources = []
    if not sources:
        sources = list(DEFAULT_WATCH_SOURCES)

    raw_mode = data.get("dispatch_mode")
    mode = raw_mode.strip().lower() if isinstance(raw_mode, str) else ""
    if mode not in _VALID_DISPATCH_MODES:
        mode = _DEFAULT_DISPATCH_MODE

    return RunConfig(watch_sources=sources, dispatch_mode=mode, raw=data)


def read_run_config(repo_root: Path | str) -> Optional[RunConfig]:
    """Read <repo>/.harness/wiki-watch.json -> RunConfig, or None when the marker
    is absent / unreadable / malformed / not a JSON object.

    The marker's PRESENCE is the per-repo opt-in: None means "this repo is not
    configured for watching -> skip it" (graceful, never crashes). Modeled on
    harness_memory._read_mode_marker (absent/unreadable -> None) but JSON-shaped.
    A malformed marker logs to stderr (so a typo is visible) and still skips.
    """
    path = marker_path(repo_root)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.strip():
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"[wiki-watch] ignoring malformed marker {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"[wiki-watch] ignoring marker {path}: not a JSON object", file=sys.stderr)
        return None
    return parse_run_config(data)


# ----------------------------------------------------------------------------
# (c) Wiki target — repo_registry resolver  (NET-NEW: registry has the field,
#     ships no lookup)
# ----------------------------------------------------------------------------

def _norm_path(p: str | Path) -> str:
    """Canonicalize a path for stable comparison: expanduser + resolve-ish + posix.
    Does not require the path to exist (uses os.path.normpath, not Path.resolve)."""
    s = os.path.normpath(os.path.expanduser(str(p)))
    return Path(s).as_posix()


def find_repo_entry(
    repos: list[dict], *, root_path: str | Path | None = None,
    slug: str | None = None,
) -> Optional[dict]:
    """Return the registry entry matching `root_path` (path-normalized) or `slug`,
    or None. root_path takes precedence when both are given. Pure (no I/O)."""
    if root_path is not None:
        want = _norm_path(root_path)
        for entry in repos:
            rp = entry.get("root_path")
            if isinstance(rp, str) and _norm_path(rp) == want:
                return entry
    if slug is not None:
        for entry in repos:
            if entry.get("slug") == slug:
                return entry
    return None


def resolve_wiki_target(
    entry: Optional[dict], *, check_fallback_exists: bool = True,
) -> Optional[str]:
    """Resolve a registry entry to its wiki target path, or None to skip.

    - explicit `wiki_path` present -> return it (normalized).
    - absent `wiki_path` -> fall back to <root_path>/wiki when that dir exists
      (or unconditionally when check_fallback_exists=False), else skip (None).
    - entry is None (unregistered repo) -> skip (None).

    Pure given check_fallback_exists=False; with the default it stats the fallback
    dir (the one filesystem touch, kept behind a flag so tests can stay pure).
    """
    if entry is None:
        return None
    wp = entry.get("wiki_path")
    if isinstance(wp, str) and wp.strip():
        return _norm_path(wp)
    root = entry.get("root_path")
    if not isinstance(root, str) or not root.strip():
        return None
    fallback = Path(_norm_path(root)) / "wiki"
    if check_fallback_exists and not fallback.is_dir():
        return None
    return fallback.as_posix()


def resolve_wiki_target_for_repo(
    repos: list[dict], *, root_path: str | Path | None = None,
    slug: str | None = None, check_fallback_exists: bool = True,
) -> Optional[str]:
    """Convenience: find the entry then resolve its wiki target. Pure given
    check_fallback_exists=False."""
    entry = find_repo_entry(repos, root_path=root_path, slug=slug)
    return resolve_wiki_target(entry, check_fallback_exists=check_fallback_exists)


# ----------------------------------------------------------------------------
# Cross-repo registry locator + shell-out (best-effort; graceful-skip)
# ----------------------------------------------------------------------------

def find_agentm_script(name: str) -> Optional[Path]:
    """Locate an agentm kernel script (e.g. repo_registry.py / harness_memory.py)
    via path-fallback, or None.

    Candidates, first hit wins (mirrors recent-wiki-changes.sh:86-94 + an env
    override for separately-installed agentm — the portable cross-repo seam):

      1. $AGENTM_SCRIPTS_DIR/<name>          (explicit operator override)
      2. <this-script-dir>/<name>            (co-located install)
      3. <this-script-dir>/../lib/install/python/<name>

    Kernel infra is NOT folded into crickets (bucket B): when none resolve, the
    caller graceful-skips (the watcher no-ops / falls back to repo-local state
    rather than hard-failing). The V5 storage slim owns the real seam move.
    """
    here = Path(__file__).resolve().parent
    candidates = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)) / name)
    candidates.append(here / name)
    candidates.append(here / ".." / "lib" / "install" / "python" / name)
    for c in candidates:
        if c.is_file():
            return c
    return None


def find_registry_script() -> Optional[Path]:
    """Locate agentm's repo_registry.py (see find_agentm_script)."""
    return find_agentm_script("repo_registry.py")


def list_repos_via_registry(
    vault_path: Optional[str] = None, *, registry_script: Optional[Path] = None,
) -> list[dict]:
    """Shell out to agentm's `repo_registry.py list` and return its `repos` list.

    Graceful-skip to [] when: the registry script can't be located, the vault is
    unavailable, python3 is missing, or the call errors / returns non-JSON. Never
    raises. This is the impure seam; the pure resolvers above consume its output.
    """
    if registry_script is None:
        registry_script = find_registry_script()
    if registry_script is None:
        return []
    if vault_path is None:
        vault_path = read_vault_path()
    if not vault_path:
        return []
    env = {**os.environ, "MEMORY_VAULT_PATH": vault_path}
    try:
        res = subprocess.run(
            [sys.executable, str(registry_script), "list"],
            capture_output=True, text=True, env=env, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return []
    repos = data.get("repos") if isinstance(data, dict) else None
    return repos if isinstance(repos, list) else []


# ----------------------------------------------------------------------------
# CLI — for the task-4 skill + manual debugging. JSON out; exit 0 ok / 1 skip.
# ----------------------------------------------------------------------------

def _emit(obj: dict) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True))


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="wiki_watch_config",
        description="Resolve wiki-watch config (enablement / run config / wiki target).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("enabled", help="print device enablement (exit 0 enabled / 1 disabled)")
    p_run = sub.add_parser("run-config", help="print per-repo run config")
    p_run.add_argument("repo_root")
    p_wt = sub.add_parser("wiki-target", help="resolve a repo's wiki target via the registry")
    p_wt.add_argument("repo_root")
    p_wt.add_argument("--slug", default=None)
    args = parser.parse_args(argv)

    if args.cmd == "enabled":
        enabled = read_enablement()
        _emit({"enabled": enabled})
        return 0 if enabled else 1

    if args.cmd == "run-config":
        cfg = read_run_config(args.repo_root)
        if cfg is None:
            _emit({"skipped": True, "reason": "no/unreadable .harness/wiki-watch.json marker"})
            return 1
        _emit({"watch_sources": cfg.watch_sources, "dispatch_mode": cfg.dispatch_mode})
        return 0

    if args.cmd == "wiki-target":
        repos = list_repos_via_registry()
        target = resolve_wiki_target_for_repo(
            repos, root_path=args.repo_root, slug=args.slug)
        if target is None:
            _emit({"skipped": True,
                   "reason": "repo unregistered, no wiki_path, or registry unavailable"})
            return 1
        _emit({"wiki_target": target})
        return 0

    return 2  # argparse should prevent this


if __name__ == "__main__":
    sys.exit(main())
