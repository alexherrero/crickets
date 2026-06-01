#!/usr/bin/env python3
"""Generate native host plugins from the crickets `src/` source of truth.

Reads `src/<group>/` (via `src_model`) and emits committed per-host plugin
artifacts into `dist/`. Host emitters plug into a registry; each emits a plugin
directory per group + contributes a marketplace entry, and the driver writes
the host marketplace manifest.

Deterministic: sorted iteration + stable JSON, so part 4's
`generate.py check` (generated-in-sync) gate is meaningful.

CLI:
  build   write dist/ from src/
  clean   remove dist/

Requires PyYAML. crickets v3.0 #40, part 2.
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


class HostEmitter:
    """Base host emitter. One subclass per host (Claude lands in part 2 task 2,
    Antigravity in part 3). Implementations write a plugin directory per group
    under `dist/` and return a marketplace entry dict; the driver collects the
    entries and asks the emitter to write the host marketplace manifest."""

    host: str = ""

    def emit_group(self, group: Group, dist_root: Path) -> dict | None:
        """Write `group`'s plugin dir under `dist_root`; return a marketplace
        entry (or None to skip the group for this host)."""
        raise NotImplementedError

    def write_marketplace(self, entries: list[dict], dist_root: Path) -> None:
        """Write the host marketplace manifest from the collected entries."""
        raise NotImplementedError


# Emitter registry — populated by host-emitter modules at load time.
EMITTERS: dict[str, HostEmitter] = {}


def register(emitter: HostEmitter) -> None:
    EMITTERS[emitter.host] = emitter


def build(src: Path = SRC, dist: Path = DIST) -> int:
    groups = load_groups(src)
    if not EMITTERS:
        print("generate: no host emitters registered — nothing to emit", file=sys.stderr)
        return 0
    dist.mkdir(parents=True, exist_ok=True)
    for host, emitter in sorted(EMITTERS.items()):
        entries: list[dict] = []
        for group in groups:
            if not group.supports(host):
                continue
            entry = emitter.emit_group(group, dist)
            if entry is not None:
                entries.append(entry)
        emitter.write_marketplace(entries, dist)
    print(f"generate: built dist/ for host(s): {sorted(EMITTERS)}")
    return 0


def clean(dist: Path = DIST) -> int:
    if dist.exists():
        shutil.rmtree(dist)
        print(f"generate: removed {dist.name}/")
    else:
        print("generate: dist/ already absent")
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
    sub.add_parser("clean", help="remove dist/")
    args = ap.parse_args(argv)
    _load_emitters()
    if args.cmd == "build":
        return build()
    if args.cmd == "clean":
        return clean()
    return 2


if __name__ == "__main__":
    sys.exit(main())
