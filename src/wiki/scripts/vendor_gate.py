#!/usr/bin/env python3
"""vendor_gate.py — copy the wiki-maintenance CI scripts (check-wiki.py, the
lint gate, and wiki_publish_transform.py, the publish-time transform) into a
target repo so its CI can run them.

GitHub Actions runners don't have ${CLAUDE_PLUGIN_ROOT}, so neither script can
be *referenced* there — they're VENDORED. `wiki-init`'s `--vendor` (initial
copy) and `--resync-gate` (re-copy after a plugin upgrade) both call
vendor_gate() + vendor_transform().

  python3 vendor_gate.py --target <repo-root>
      # copy check-wiki.py + wiki_publish_transform.py -> <repo>/.github/scripts/

Agent-invoked check-wiki (during /work, wiki-author, …) uses the bundled
${CLAUDE_PLUGIN_ROOT}/scripts/check-wiki.py directly — no vendoring needed there.
Both scripts live together in the plugin's scripts/, so as the bundled dist
copies they resolve each other via __file__.
"""
import argparse
import shutil
import sys
from pathlib import Path

GATE = "check-wiki.py"
TRANSFORM = "wiki_publish_transform.py"
# Where the vendored scripts land in the target repo (kept with its CI).
VENDOR_DIR = Path(".github") / "scripts"
VENDOR_REL = VENDOR_DIR / GATE
TRANSFORM_VENDOR_REL = VENDOR_DIR / TRANSFORM
# The plugin root that holds scripts/check-wiki.py — this script's own dir's parent.
PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def gate_source(plugin_root: Path = PLUGIN_ROOT) -> Path:
    """The bundled gate inside the plugin (<plugin_root>/scripts/check-wiki.py)."""
    return plugin_root / "scripts" / GATE


def transform_source(plugin_root: Path = PLUGIN_ROOT) -> Path:
    """The bundled publish-time transform inside the plugin
    (<plugin_root>/scripts/wiki_publish_transform.py)."""
    return plugin_root / "scripts" / TRANSFORM


def vendor_gate(target_root: Path, plugin_root: Path = PLUGIN_ROOT) -> Path:
    """Copy the plugin's check-wiki.py into <target_root>/.github/scripts/.
    Idempotent: a re-sync overwrites with the current bundled gate. Returns the
    written path. Raises FileNotFoundError if the source gate is missing."""
    src = gate_source(plugin_root)
    if not src.is_file():
        raise FileNotFoundError(f"bundled gate not found at {src}")
    dest = target_root / VENDOR_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def vendor_transform(target_root: Path, plugin_root: Path = PLUGIN_ROOT) -> Path:
    """Copy the plugin's wiki_publish_transform.py into
    <target_root>/.github/scripts/. Idempotent: a re-sync overwrites with the
    current bundled transform. Returns the written path. Raises
    FileNotFoundError if the source is missing."""
    src = transform_source(plugin_root)
    if not src.is_file():
        raise FileNotFoundError(f"bundled transform not found at {src}")
    dest = target_root / TRANSFORM_VENDOR_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Vendor the wiki-maintenance check-wiki.py gate and "
                     "wiki_publish_transform.py into a repo for CI use.")
    ap.add_argument("--target", type=Path, default=Path.cwd(),
                    help="target repo root (default: cwd)")
    ap.add_argument("--plugin-root", type=Path, default=PLUGIN_ROOT,
                    help="plugin root holding scripts/ (default: this script's plugin)")
    args = ap.parse_args(argv)
    try:
        gate_dest = vendor_gate(args.target, args.plugin_root)
        transform_dest = vendor_transform(args.target, args.plugin_root)
    except FileNotFoundError as exc:
        print(f"vendor_gate: {exc}", file=sys.stderr)
        return 1
    print(f"vendor_gate: copied {gate_source(args.plugin_root)} -> {gate_dest}")
    print(f"vendor_gate: copied {transform_source(args.plugin_root)} -> {transform_dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
