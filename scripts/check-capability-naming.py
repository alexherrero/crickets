#!/usr/bin/env python3
"""Conformance gate: capability names + plugin slugs obey the AG naming rule.

The rule (design-doc "Forward plan — the naming rule"): a capability is named for
what it *is*, as a bare noun — the action and output format live inside the
primitives, not the name. Two names are banned outright because they break the
resolver's one-way model or manufacture false peerage:

  1. The ``-workflows`` suffix is RESERVED, singular, for ``developer-workflows``
     — the phase spine. A second ``*-workflows`` capability or plugin manufactures
     false peerage with the spine, so it is banned everywhere except that one name.
  2. An **Opinion name** (``efficiency`` / ``quality`` / ``good`` / ``done``) may
     never be a capability name: it collides at the resolver with the Opinion
     surfaces tools request by name, inverting the one-way capability→opinion rule.

The ``developer-`` *prefix* is allowed — a deliberate spine / control-layer marker
on ``developer-workflows`` + ``developer-safety``, not suffix debt — so only the
``-workflows`` *suffix* is gated, with ``developer-workflows`` exempt.

Bare-noun-ness itself is NOT hard-enforced: legitimate hyphenated capability names
exist (``adversarial-review``, ``board-sync``, ``storage-backend``, ``ci-repair``),
so a "must be a single word" rule would false-positive. The gate enforces the two
bans only — deterministic, no judgment.

Checks every ``src/<slug>/group.yaml``: the plugin slug (dir name) and each name
in its ``capabilities:`` list. Exit 0 clean, 1 on any violation, 2 on usage error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# The one name allowed to keep the reserved -workflows suffix (the phase spine).
WORKFLOWS_EXCEPTION = "developer-workflows"
BANNED_SUFFIX = "-workflows"
# Opinion surfaces tools request by name — never legal as a capability name.
# (Extensible: add new Opinion surfaces here as agentm names them.)
OPINION_NAMES = frozenset({"efficiency", "quality", "good", "done"})


def name_violation(name: str, *, kind: str, source: str) -> str | None:
    """Return a violation message for ``name``, or None if it conforms.

    ``kind`` is "capability" or "plugin" (for the message); ``source`` names the
    group slug it was declared in, so the operator can find it.
    """
    if name.endswith(BANNED_SUFFIX) and name != WORKFLOWS_EXCEPTION:
        return (f"{kind} name {name!r} (in {source}) uses the reserved "
                f"'{BANNED_SUFFIX}' suffix — reserved for the spine "
                f"'{WORKFLOWS_EXCEPTION}'; name the capability for what it is.")
    if name in OPINION_NAMES:
        return (f"{kind} name {name!r} (in {source}) is an Opinion name — Opinion "
                f"names ({', '.join(sorted(OPINION_NAMES))}) collide with the "
                f"Opinion surfaces tools request by name (one-way rule); rename it.")
    return None


def find_naming_violations(caps_by_slug: dict[str, list[str]]) -> list[str]:
    """Pure logic: given ``{plugin-slug: [capability names]}``, return all
    violations. Checks both the plugin slug itself and each capability it declares.
    """
    violations: list[str] = []
    for slug in sorted(caps_by_slug):
        v = name_violation(slug, kind="plugin", source=slug)
        if v:
            violations.append(v)
        for cap in caps_by_slug[slug]:
            v = name_violation(cap, kind="capability", source=slug)
            if v:
                violations.append(v)
    return violations


def load_caps_by_slug(src: Path) -> dict[str, list[str]]:
    """Read every ``src/<slug>/group.yaml`` into ``{slug: [capability names]}``."""
    out: dict[str, list[str]] = {}
    for gd in sorted(p for p in src.iterdir() if p.is_dir()):
        gy = gd / "group.yaml"
        if not gy.is_file():
            continue
        try:
            meta = yaml.safe_load(gy.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            meta = {}
        caps = meta.get("capabilities") if isinstance(meta, dict) else None
        out[gd.name] = [c for c in caps if isinstance(c, str)] if isinstance(caps, list) else []
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Enforce the AG capability-naming rule.")
    ap.add_argument("--src", type=Path, default=SRC,
                    help="src/ tree to scan (default: repo src/)")
    args = ap.parse_args(argv)

    if yaml is None:
        print("check-capability-naming: PyYAML not available — cannot parse group.yaml.",
              file=sys.stderr)
        return 2
    if not args.src.is_dir():
        print(f"check-capability-naming: src not found ({args.src}) — nothing to check.")
        return 0

    caps = load_caps_by_slug(args.src)
    violations = find_naming_violations(caps)
    if violations:
        print("check-capability-naming: FAIL — capability/plugin name(s) violate the naming rule:")
        for v in violations:
            print(f"  - {v}")
        return 1

    n_caps = sum(len(v) for v in caps.values())
    print(f"check-capability-naming: OK — {len(caps)} plugin(s), {n_caps} capability name(s) conform.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
