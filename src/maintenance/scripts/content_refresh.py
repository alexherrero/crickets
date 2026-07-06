#!/usr/bin/env python3
"""content-refresh -- bounded mechanical re-pin engine for externally-sourced
content (crickets wave-c-maintenance, task 4).

Proven by its two named first consumers (crickets-maintenance.md): a
`pricing.py` model-version re-pin (mechanical) and the model+effort routing
chart (judgment-bound when a genuinely new model needs a tier placement, not
a drop-in rename). The classifier is a hard rule, not a confidence
threshold (Locked design call): an existing reference changing value is a
rename -- mechanical, auto-applied under the bounded/never-merge guarantee.
No existing reference to rename FROM means there's nothing drop-in about it
-- judgment-bound, surfaced to the watchlist, never auto-edited.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_sibling(name: str, filename: str):
    # See tech_debt_inventory.py's _load_sibling for the cross-plugin
    # collision this avoids (a bare `import agentm_bridge` by name).
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


agentm_bridge = _load_sibling("maintenance_agentm_bridge_content_refresh", "agentm_bridge.py")

MECHANICAL = "mechanical"
JUDGMENT_BOUND = "judgment-bound"


def classify(target_path: Path, item: dict) -> str:
    """`item`: {"old_ref": str | None, "new_ref": str, ...}. MECHANICAL if
    `old_ref` is a rename target already present in `target_path`'s
    content; JUDGMENT_BOUND if there's no existing reference to rename
    from (a genuinely new entry needing a human placement decision)."""
    old_ref = item.get("old_ref")
    if not old_ref:
        return JUDGMENT_BOUND
    content = target_path.read_text(encoding="utf-8")
    return MECHANICAL if old_ref in content else JUDGMENT_BOUND


def _watchlist_slug(target_path: Path, item: dict) -> str:
    raw = f"content-refresh-{target_path.stem}-{item['new_ref']}"
    kebab = "".join(c if c.isalnum() else "-" for c in raw.lower())
    while "--" in kebab:
        kebab = kebab.replace("--", "-")
    return kebab.strip("-")


def refresh(target_path: Path, item: dict, vault: Path) -> dict:
    """Apply `item` to `target_path` if mechanical (a bounded find-and-
    replace of `old_ref` -> `new_ref`, touching nothing else in the file);
    otherwise leave `target_path` byte-identical and write exactly one
    watchlist entry describing the judgment call needed.

    Returns {"classification", "applied": bool, "watchlist_path": Path | None}.
    """
    classification = classify(target_path, item)
    if classification == MECHANICAL:
        content = target_path.read_text(encoding="utf-8")
        content = content.replace(item["old_ref"], item["new_ref"])
        target_path.write_text(content, encoding="utf-8")
        return {"classification": MECHANICAL, "applied": True, "watchlist_path": None}

    body = (
        f"## Judgment call needed\n"
        f"`{item['new_ref']}` has no existing pin to rename from in "
        f"`{target_path.name}` -- surfaced instead of auto-edited "
        f"(Locked design call: judgment-bound drift never auto-applies).\n\n"
        f"## Context\n{item.get('context', '(none given)')}\n"
    )
    slug = _watchlist_slug(target_path, item)
    watchlist_path = agentm_bridge.write_content_refresh_watchlist_entry(
        vault, slug=slug, body=body, tags=[JUDGMENT_BOUND],
    )
    return {"classification": JUDGMENT_BOUND, "applied": False, "watchlist_path": watchlist_path}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="content-refresh -- bounded mechanical re-pin engine")
    parser.add_argument("target_path")
    parser.add_argument("--item", required=True, help="path to a JSON {old_ref, new_ref, context} checklist item")
    parser.add_argument("--vault-path", required=True)
    args = parser.parse_args(argv)
    item = json.loads(Path(args.item).read_text(encoding="utf-8"))
    result = refresh(Path(args.target_path), item, Path(args.vault_path))
    result["watchlist_path"] = str(result["watchlist_path"]) if result["watchlist_path"] else None
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
