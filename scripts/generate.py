#!/usr/bin/env python3
"""Generate native host plugins from the crickets `src/` source of truth.

Reads `src/<group>/` (via `src_model`) and emits committed per-host plugin
artifacts into `dist/`. Host emitters plug into a registry; each emits a plugin
directory per group + contributes a marketplace entry, and the driver writes
the host marketplace manifest.

Deterministic: sorted iteration + stable JSON, so part 4's
`generate.py check` (generated-in-sync) gate is meaningful.

CLI:
  build   write dist/ + repo-root marketplace pointer(s) from src/
  check   exit non-zero if dist/ or the root pointer(s) drift from src/
  clean   remove dist/ + the root pointer(s)

Requires PyYAML. crickets v3.0 #40, part 2 (root pointers: part 6).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import yaml  # noqa: F401  — src_model needs it
except ImportError:
    print("generate: PyYAML not installed (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

from src_model import Group, load_groups  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DIST = ROOT / "dist"


def dump_json(obj) -> str:
    """Deterministic JSON: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_utf8(path: Path, text: str) -> None:
    """Byte-deterministic text write: UTF-8, LF newlines on every OS.

    Path.write_text() runs newline translation on Windows (\\n -> \\r\\n),
    which made `generate.py check` fail there — committed dist/ is LF.
    Writing bytes sidesteps text-mode translation entirely.
    """
    path.write_bytes(text.encode("utf-8"))


class HostEmitter:
    """Base host emitter. One subclass per host (Claude lands in part 2 task 2,
    Antigravity in part 3). Implementations write a plugin directory per group
    under `dist/` and return a marketplace entry dict; the driver collects the
    entries and asks the emitter to write the host marketplace manifest."""

    host: str = ""
    # Repo-ROOT marketplace pointer path (relative to repo root), e.g.
    # ".claude-plugin/marketplace.json". None ⇒ this host emits no root pointer.
    # When set, the file is generator-emitted + covered by `check`, so the
    # one-word `<host> plugin marketplace add <owner/repo>` install can't drift.
    root_marketplace_rel: str | None = None

    def emit_group(self, group: Group, dist_root: Path) -> dict | None:
        """Write `group`'s plugin dir under `dist_root`; return a marketplace
        entry (or None to skip the group for this host)."""
        raise NotImplementedError

    def write_marketplace(self, entries: list[dict], dist_root: Path) -> None:
        """Write the host marketplace manifest from the collected entries."""
        raise NotImplementedError

    def write_root_marketplace(self, entries: list[dict], repo_root: Path) -> None:
        """Write the repo-ROOT marketplace pointer (sources rewritten to the
        committed `dist/<host>/` locations) so `<host> plugin marketplace add
        <owner/repo>` resolves one-word from GitHub. Only called when
        `root_marketplace_rel` is set; default no-op."""
        return


# Emitter registry — populated by host-emitter modules at load time.
EMITTERS: dict[str, HostEmitter] = {}


def register(emitter: HostEmitter) -> None:
    EMITTERS[emitter.host] = emitter


def _emit(src: Path, dist: Path, root: Path) -> bool:
    """Run every registered emitter into `dist/<host>/`, and write each host's
    repo-ROOT marketplace pointer under `root/`. Returns False (no-op) when no
    emitters are registered. Shared by build() + check()."""
    groups = load_groups(src)
    if not EMITTERS:
        return False
    dist.mkdir(parents=True, exist_ok=True)
    for host, emitter in sorted(EMITTERS.items()):
        # per-host namespace: each emitter writes under dist/<host>/ so the
        # hosts' divergent plugin contents never collide.
        host_root = dist / host
        host_root.mkdir(parents=True, exist_ok=True)
        entries: list[dict] = []
        for group in groups:
            if not group.supports(host):
                continue
            entry = emitter.emit_group(group, host_root)
            if entry is not None:
                entries.append(entry)
        emitter.write_marketplace(entries, host_root)
        # Repo-root pointer (one-word GitHub install) — outside dist/, but
        # generator-emitted + check-covered so it can't drift.
        if emitter.root_marketplace_rel:
            emitter.write_root_marketplace(entries, root)
    # host-agnostic default-set manifest (the recommended install list) — read
    # by the one-line installer; data-driven so it can't drift from the catalog.
    write_utf8(dist / "default-set.json",
               dump_json({"plugins": sorted(g.slug for g in groups)}))
    return True


def build(src: Path = SRC, dist: Path = DIST, root: Path = ROOT) -> int:
    if not _emit(src, dist, root):
        print("generate: no host emitters registered — nothing to emit", file=sys.stderr)
        return 0
    print(f"generate: built dist/ + root marketplace pointer(s) for host(s): {sorted(EMITTERS)}")
    return 0


def _diff_trees(committed: Path, fresh: Path) -> list[str]:
    """Compare the committed dist/ against a freshly-generated one. Returns a
    list of human-readable drift descriptions (empty == in sync)."""
    fa = {p.relative_to(committed) for p in committed.rglob("*") if p.is_file()} if committed.exists() else set()
    fb = {p.relative_to(fresh) for p in fresh.rglob("*") if p.is_file()}
    diffs: list[str] = []
    for rel in sorted(str(r) for r in fb - fa):
        diffs.append(f"missing from dist/ (run build): {rel}")
    for rel in sorted(str(r) for r in fa - fb):
        diffs.append(f"stale in dist/ (no longer generated): {rel}")
    for rel in sorted(fa & fb, key=str):
        if (committed / rel).read_bytes() != (fresh / rel).read_bytes():
            diffs.append(f"out of date in dist/: {rel}")
    return diffs


def _diff_root_pointers(committed_root: Path, fresh_root: Path) -> list[str]:
    """Compare ONLY each registered emitter's declared root-pointer file
    (a bounded set — never tree-diff the repo root, which would compare the
    whole working tree). Returns drift descriptions (empty == in sync)."""
    diffs: list[str] = []
    for _host, emitter in sorted(EMITTERS.items()):
        rel = emitter.root_marketplace_rel
        if not rel:
            continue
        cb = (committed_root / rel).read_bytes() if (committed_root / rel).exists() else None
        fb = (fresh_root / rel).read_bytes() if (fresh_root / rel).exists() else None
        if cb == fb:
            continue
        if cb is None:
            diffs.append(f"missing from repo root (run build): {rel}")
        elif fb is None:
            diffs.append(f"stale root pointer (no longer generated): {rel}")
        else:
            diffs.append(f"out of date root pointer: {rel}")
    return diffs


def check(src: Path = SRC, dist: Path = DIST, root: Path = ROOT) -> int:
    """Fail (exit 1) if the committed dist/ OR the repo-root marketplace
    pointer(s) differ from a fresh generation — the generated-in-sync CI gate."""
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        fresh = Path(t) / "dist"
        fresh_root = Path(t) / "root"
        if not _emit(src, fresh, fresh_root):
            print("generate: no host emitters registered — nothing to check", file=sys.stderr)
            return 0
        diffs = _diff_trees(dist, fresh) + _diff_root_pointers(root, fresh_root)
    if diffs:
        print("generate: generated output is OUT OF SYNC with src/ — run "
              "`python3 scripts/generate.py build` and commit:", file=sys.stderr)
        for d in diffs:
            print(f"  - {d}", file=sys.stderr)
        return 1
    print("generate: dist/ + root marketplace pointer(s) in sync with src/")
    return 0


def clean(dist: Path = DIST, root: Path = ROOT) -> int:
    removed = []
    if dist.exists():
        shutil.rmtree(dist)
        removed.append(f"{dist.name}/")
    for emitter in EMITTERS.values():
        rel = emitter.root_marketplace_rel
        if not rel:
            continue
        f = root / rel
        if f.exists():
            f.unlink()
            removed.append(rel)
            # tidy now-empty parent dirs (up to, but not including, repo root)
            p = f.parent
            while p != root and p.exists() and not any(p.iterdir()):
                p.rmdir()
                p = p.parent
    print(f"generate: removed {', '.join(removed)}" if removed else "generate: nothing to clean")
    return 0


# host-emitter module -> emitter class name. Each lands in its own part:
# emit_claude (part 2), emit_antigravity (part 3).
_EMITTER_MODULES = {"emit_claude": "ClaudeEmitter", "emit_antigravity": "AntigravityEmitter"}


def _load_emitters() -> None:
    """Import host-emitter modules + register their emitter on THIS module's
    registry (avoids the __main__-vs-import dual-instance trap if the emitter
    self-registered)."""
    for mod_name, cls_name in _EMITTER_MODULES.items():
        try:
            mod = __import__(mod_name)
        except ImportError:
            continue
        cls = getattr(mod, cls_name, None)
        if cls is not None and cls.host not in EMITTERS:
            register(cls())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="generate.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="write dist/ from src/")
    sub.add_parser("check", help="exit non-zero if dist/ is out of sync with src/")
    sub.add_parser("clean", help="remove dist/")
    args = ap.parse_args(argv)
    _load_emitters()
    if args.cmd == "build":
        return build()
    if args.cmd == "check":
        return check()
    if args.cmd == "clean":
        return clean()
    return 2


if __name__ == "__main__":
    sys.exit(main())
