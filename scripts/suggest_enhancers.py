#!/usr/bin/env python3
"""Suggest enhancer plugins to install (crickets soft composition).

Reads the `enhances` edges from a generated marketplace.json + the set of
installed (or recommended) plugin slugs, and prints a tip for each **enhancer**
that is NOT in the set while its **enhancee** IS — "you have <enhancee>; install
<enhancer> too for a richer experience." Wired into `bootstrap.sh` after its
install loop (graceful + non-fatal): in the full-default-set flow it prints
nothing (every enhancer is installed); it fires for partial / manual installs.

The `enhances` metadata is identical on both hosts' marketplaces, so either the
Claude (`.claude-plugin/marketplace.json`) or Antigravity
(`.agents/plugins/marketplace.json`) render works as the source. Stdlib-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _enhances_of(entry: dict) -> list[str]:
    """The enhancee group slugs an entry's `enhances` targets — accepts the
    string shorthand (`enhances: [wf]`) and the dict form (`{group, …}`)."""
    out = []
    for e in entry.get("enhances") or []:
        if isinstance(e, str):
            out.append(e)
        elif isinstance(e, dict) and e.get("group"):
            out.append(str(e["group"]))
    return out


def suggestions(marketplace: dict, installed) -> list[dict]:
    """Return `[{enhancer, enhancee}]` for each enhancer NOT in `installed`
    whose enhancee IS in `installed`. Deterministic (sorted)."""
    inst = set(installed)
    out = []
    for entry in marketplace.get("plugins", []):
        enhancer = entry.get("name")
        if not enhancer or enhancer in inst:
            continue
        for enhancee in _enhances_of(entry):
            if enhancee in inst:
                out.append({"enhancer": enhancer, "enhancee": enhancee})
    return sorted(out, key=lambda d: (d["enhancer"], d["enhancee"]))


def format_tips(sugs: list[dict]) -> str:
    return "\n".join(
        f"  tip: you have '{s['enhancee']}' — also install '{s['enhancer']}' "
        f"for a richer experience (it enhances '{s['enhancee']}')"
        for s in sugs
    )


def main(argv: list[str]) -> int:
    # usage: suggest_enhancers.py <marketplace.json> <installed-slug>...
    if len(argv) < 2:
        print("usage: suggest_enhancers.py <marketplace.json> <installed-slug>...",
              file=sys.stderr)
        return 2
    mk_path = Path(argv[1])
    if not mk_path.is_file():
        return 0  # graceful — no marketplace, no suggestions
    try:
        mk = json.loads(mk_path.read_text(encoding="utf-8"))
    except Exception:
        return 0  # graceful — unreadable marketplace is non-fatal
    sugs = suggestions(mk, argv[2:])
    if sugs:
        print(format_tips(sugs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
