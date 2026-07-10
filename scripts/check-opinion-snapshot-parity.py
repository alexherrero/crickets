#!/usr/bin/env python3
"""check-opinion-snapshot-parity.py — keeps crickets' committed opinion
snapshots (scripts/opinion-snapshots/<name>.md) honest against agentm's live
opinions/<name>.md (PLAN-opinion-consumer-grammar task 1).

crickets bakes a cross-plugin opinion's coded base into dist/ at generate.py
build time from a committed snapshot — never a live read of agentm (crickets
ships standalone; generate.py check's determinism gate can't depend on a
sibling repo a CI run or a standalone install may not have). This gate is the
honesty check on that snapshot: it runs only here, in check-all.sh, never in
the build path itself, and gracefully skips (not false-passes) when the
agentm sibling isn't present to diff against — mirroring the development-lifecycle
plugin's agentm_bridge.py `capability` verb's sibling-discovery-with-graceful-None
shape (formerly find_capability.py, merged in CONS-2 task 2).

Exit 0: every snapshot matches its agentm source, or agentm is absent
        (graceful skip — printed distinctly from a real match)
Exit 1: at least one snapshot has drifted from its agentm source
Exit 2: usage/read error (a declared snapshot has no matching agentm file
        or vice versa)

--report forces exit 0 (non-blocking wiring), matching
check-voice-floor-parity.py's posture — there is no automated snapshot
refresh yet, so this stays report-only in check-all.sh until one exists.

Stdlib-only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src_model import find_agentm_opinions_dir  # noqa: E402

_HERE = Path(__file__).resolve().parent
_SNAPSHOT_DIR = _HERE / "opinion-snapshots"


def snapshot_names(snapshot_dir: Path) -> list[str]:
    return sorted(p.stem for p in snapshot_dir.glob("*.md"))


def compare_one(name: str, snapshot_dir: Path, agentm_dir: Path) -> str | None:
    """Return a description of the drift if name's snapshot has drifted, else
    None. Raises FileNotFoundError if agentm has no matching opinion file —
    that's an error (a stale/orphaned snapshot), not silent drift."""
    snap_text = (snapshot_dir / f"{name}.md").read_text(encoding="utf-8")
    live_path = agentm_dir / f"{name}.md"
    if not live_path.is_file():
        raise FileNotFoundError(f"agentm has no opinions/{name}.md to compare against")
    live_text = live_path.read_text(encoding="utf-8")
    if snap_text != live_text:
        return f"{name}: scripts/opinion-snapshots/{name}.md differs from agentm's opinions/{name}.md"
    return None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="check-opinion-snapshot-parity", description=__doc__)
    p.add_argument("--snapshot-dir", default=None, type=Path)
    p.add_argument("--agentm-opinions-dir", default=None, type=Path,
                    help="override agentm opinions/ dir discovery (tests)")
    p.add_argument("--report", action="store_true", help="always exit 0 — non-blocking wiring")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    snapshot_dir = args.snapshot_dir or _SNAPSHOT_DIR

    if not snapshot_dir.is_dir():
        print(f"check-opinion-snapshot-parity: no snapshots at {snapshot_dir} — nothing to check")
        return 0

    names = snapshot_names(snapshot_dir)
    if not names:
        print("check-opinion-snapshot-parity: snapshot dir is empty — nothing to check")
        return 0

    agentm_dir = args.agentm_opinions_dir or find_agentm_opinions_dir()
    if agentm_dir is None or not agentm_dir.is_dir():
        print("check-opinion-snapshot-parity: agentm sibling not found — "
              "SKIPPING (snapshots were NOT compared, this is not a pass)")
        return 0

    drifted: list[str] = []
    for name in names:
        try:
            result = compare_one(name, snapshot_dir, agentm_dir)
        except FileNotFoundError as exc:
            print(f"check-opinion-snapshot-parity: error comparing {name!r}: {exc}")
            return 2
        if result:
            drifted.append(result)

    if drifted:
        print(f"check-opinion-snapshot-parity: {len(drifted)} snapshot(s) drifted from agentm:")
        for line in drifted:
            print(f"  {line}")
    else:
        print(f"check-opinion-snapshot-parity: {len(names)} snapshot(s) match agentm — in sync")

    if args.report:
        return 0
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
