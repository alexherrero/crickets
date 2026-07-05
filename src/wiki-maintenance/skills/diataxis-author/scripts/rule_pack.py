#!/usr/bin/env python3
# rule_pack.py — loader for the versioned voice rule pack (PLAN-r3-voice-mechanism
# task 1). One JSON pack collapses the five drifting banned-vocabulary stores
# voice.json found; check-slop.py (task 2) and the voice kernel / style_resolver.py
# (task 3) both read this loader — never a second copy of the term list.
#
# Stdlib-only; mirrors the style_resolver.py scope-precedence convention (global
# → per-project → per-repo, narrower wins) for the vault-side overlay hook.

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS_DIR.parent
_RULE_PACK_PATH = _SKILL_ROOT / "style" / "voice-rules.json"

_REQUIRED_RULE_FIELDS = ("id", "severity", "kind", "pattern", "hint", "weight", "source-url")
_VALID_SEVERITIES = ("error", "warning", "suggestion")
_VALID_KINDS = ("word", "phrase", "template", "metric")

_OVERLAY_SCOPE_ORDER = ("global", "per-project", "per-repo")
_PER_REPO_OVERLAY_FILE = ".diataxis-voice-rules.json"


class RulePackError(ValueError):
    """Raised when a rule pack (shipped or overlay) fails schema validation."""


def validate_rule_pack(pack: dict) -> None:
    """Raise RulePackError on any schema violation. Empty pack is valid (no rules)."""
    if not isinstance(pack, dict):
        raise RulePackError("rule pack must be a JSON object")
    if "schema_version" not in pack:
        raise RulePackError("rule pack missing top-level 'schema_version'")
    if "era" not in pack:
        raise RulePackError("rule pack missing top-level 'era'")
    rules = pack.get("rules", [])
    if not isinstance(rules, list):
        raise RulePackError("'rules' must be a list")
    seen_ids: set[str] = set()
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise RulePackError(f"rule[{i}] must be an object")
        missing = [f for f in _REQUIRED_RULE_FIELDS if f not in rule]
        if missing:
            raise RulePackError(f"rule[{i}] ({rule.get('id', '?')}) missing fields: {missing}")
        if rule["severity"] not in _VALID_SEVERITIES:
            raise RulePackError(f"rule[{i}] ({rule['id']}) invalid severity: {rule['severity']!r}")
        if rule["kind"] not in _VALID_KINDS:
            raise RulePackError(f"rule[{i}] ({rule['id']}) invalid kind: {rule['kind']!r}")
        if rule["id"] in seen_ids:
            raise RulePackError(f"duplicate rule id: {rule['id']!r}")
        seen_ids.add(rule["id"])


def load_shipped_pack(path: Path | None = None) -> dict:
    """Read + validate the committed pack. Raises RulePackError on malformed JSON/schema."""
    p = path or _RULE_PACK_PATH
    with open(p, encoding="utf-8") as f:
        pack = json.load(f)
    validate_rule_pack(pack)
    return pack


def _read_overlay(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            overlay = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    validate_rule_pack(overlay)
    return overlay


def load_rule_pack(
    *,
    vault_path: Path | None = None,
    project_slug: str | None = None,
    wiki_root: Path | None = None,
    shipped_path: Path | None = None,
) -> dict:
    """Compose the shipped pack ⊕ vault-side overlays (narrower wins by id).

    Precedence (lowest → highest): global → per-project → per-repo, matching
    style_resolver.resolve_style's scope order. Each scope is independently
    graceful-skipped when its overlay file is absent or unreadable — with no
    vault and no overlay, the result is the shipped pack alone.
    """
    pack = load_shipped_pack(shipped_path)
    merged: dict[str, dict] = {r["id"]: r for r in pack.get("rules", [])}

    if vault_path is not None:
        vp = Path(vault_path)
        gdir = vp / "projects" / "_global" / "wiki-style" / "voice-rules-overlay.json"
        for r in _read_overlay(gdir).get("rules", []):
            merged[r["id"]] = r
        if project_slug:
            pdir = vp / "projects" / project_slug / "wiki-style" / "voice-rules-overlay.json"
            for r in _read_overlay(pdir).get("rules", []):
                merged[r["id"]] = r
    if wiki_root is not None:
        rfile = Path(wiki_root) / _PER_REPO_OVERLAY_FILE
        for r in _read_overlay(rfile).get("rules", []):
            merged[r["id"]] = r

    composed = dict(pack)
    composed["rules"] = list(merged.values())
    return composed


def render_base_style_banned_line(pack: dict | None = None) -> str:
    """Render the comma-joined `banned:` line base-style-guide.md#L54 promotes from.

    Only word/phrase-kind rules render (check.py's convention-drift scanner is a
    literal comma-list matcher — templates and metrics aren't expressible there).
    Deterministic: pack order in, same order out. A term containing a comma is
    double-quoted (matches check.py's _TERM_RE quoting convention).
    """
    pack = pack if pack is not None else load_shipped_pack()
    terms = [r["pattern"] for r in pack.get("rules", []) if r["kind"] in ("word", "phrase")]
    rendered = [f'"{t}"' if "," in t else t for t in terms]
    return "banned: " + ", ".join(rendered)


def _main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "render-base-banned-line":
        print(render_base_style_banned_line())
        return 0
    pack = load_shipped_pack()
    print(f"OK: {len(pack.get('rules', []))} rules, schema_version={pack['schema_version']}, era={pack['era']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
