#!/usr/bin/env python3
"""Lint the crickets `src/` source-of-truth tree (crickets v3.0 #40, part 1).

Validates every `group.yaml` + primitive frontmatter under `src/` against the
schema documented in `src/SCHEMA.md`. Exits 1 with `file:line: reason` per
violation, 0 with a summary when clean.

Shares parsing (frontmatter reader, kind/host enums, primitive globs) with the
generator via `scripts/src_model.py`.

Checks
------
group.yaml:
  - required: `name`, `description`, `standalone`.
  - `standalone` is a bool; `requires` (default []) is a list of existing group slugs.
  - invariant: `standalone: true` ⟺ `requires: []`.
  - `capabilities` is a REQUIRED, non-empty list of strings (AG Phase-2 hygiene:
    every plugin declares what it provides, so the resolver is complete).
  - `enhances` (default []) is a list; each entry (a group slug, or
    `{group, capability?, effect}`) targets an existing group, is not the plugin
    itself, is not also in `requires`, and any named `capability` is declared in
    the target's `capabilities`.
primitive frontmatter:
  - required: `name`, `description`, `kind`, `supported_hosts`.
  - `kind` in the enum and matches the primitive's `<kind>/` folder.
  - `supported_hosts` a non-empty subset of {claude-code, antigravity}.
  - kind×host expressibility (R2.1 / cricketsBuild#1): every host named in
    `supported_hosts` must actually turn that `kind` into real emitted output
    (`KIND_HOST_EXPRESSIBLE` in `src_model.py`) — catches a primitive
    overstating support for a host whose emitter silently drops its kind.
  - `name` matches the primitive's dir (skill/hook) or file stem (agent).
agent tool allowlists (`kind: agent` only):
  - every agent carries a `tools:` line, unless its `description` says
    "Full tool access" — Claude Code grants a tools-less agent EVERY tool, so a
    missing line is never a neutral default; it has to be a stated choice.
  - an agent that says it is read-only (in its `description`, or in its body
    as "read-only by contract" / "a read-only <agent|sub-agent|grader|…>")
    must carry a `tools:` line naming none of Edit, Write, NotebookEdit,
    MultiEdit, and not `*`. A read-only contract held only in prose is the
    failure this guards: the host enforces the allowlist, not the body.

Run: `python3 scripts/lint_src.py`
Requires PyYAML (CI installs it).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Make the sibling shared module importable regardless of how this file is
# loaded (direct run or importlib in the test).
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import yaml
except ImportError:  # graceful-skip when PyYAML is absent
    print("lint_src: PyYAML not installed — skipping (pip install pyyaml)", file=sys.stderr)
    sys.exit(0)

from src_model import (  # noqa: E402  (after the yaml guard by design)
    HOST_ENUM,
    KIND_ENUM,
    KIND_HOST_EXPRESSIBLE,
    KNOWN_KIND_DIRS,
    PRIMITIVE_KINDS,
    read_frontmatter,
    strip_frontmatter,
)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


# Claude Code tools that change files. A read-only agent's allowlist names none
# of them (`*` grants all of them).
WRITE_TOOLS = frozenset({"Edit", "Write", "NotebookEdit", "MultiEdit"})
_FULL_ACCESS_RE = re.compile(r"\bfull tool access\b", re.I)
_READ_ONLY_RE = re.compile(r"\bread-only\b", re.I)
# A body's self-declaration of read-only status. Deliberately narrow: an agent
# that writes may still describe one tool as "read-only" (documenter's
# "Bash (read-only: `git diff`, ...)"), which is not a claim about the agent.
_READ_ONLY_BODY_RE = re.compile(
    r"read-only by contract"
    r"|\b(?:a|an|is|are)\s+\**read-only\**\s+(?:[\w-]+\s+)?"
    r"(?:sub-agent|subagent|agent|grader|explorer|coordinator|role|reviewer|evaluator)\b",
    re.I,
)


def _parse_tools(value) -> list[str] | None:
    """`tools:` as Claude Code reads it — a comma string or a YAML list.
    None when the value has neither shape or names nothing."""
    if isinstance(value, str):
        items = [t.strip() for t in value.split(",")]
    elif isinstance(value, list) and all(isinstance(t, str) for t in value):
        items = [t.strip() for t in value]
    else:
        return None
    items = [t for t in items if t]
    return items or None


def claims_read_only(fm: dict, body: str) -> bool:
    """True when the agent says it is read-only — in its description, or in
    its body as a self-declaration (see `_READ_ONLY_BODY_RE`)."""
    return bool(_READ_ONLY_RE.search(str(fm.get("description") or ""))
                or _READ_ONLY_BODY_RE.search(body))


def lint_agent_tools(path: Path, fm: dict, body: str) -> list[tuple[str, str]]:
    """Agent tool-allowlist rules. Returns `(key, reason)` pairs; `key` is the
    frontmatter field to anchor the line number to."""
    out: list[tuple[str, str]] = []
    desc = str(fm.get("description") or "")
    read_only = claims_read_only(fm, body)
    if "tools" not in fm:
        if read_only:
            out.append(("description",
                        "agent says it is read-only but has no 'tools:' line — Claude Code "
                        "grants a tools-less agent every tool, Edit and Write included; add "
                        "an allowlist without " + "/".join(sorted(WRITE_TOOLS))))
        elif not _FULL_ACCESS_RE.search(desc):
            out.append(("description",
                        "agent has no 'tools:' line, so Claude Code grants it every tool — "
                        "add an allowlist, or say 'Full tool access' in its description "
                        "if that is the intent"))
        return out
    tools = _parse_tools(fm["tools"])
    if tools is None:
        out.append(("tools", f"'tools' must be a comma-separated string or a list of tool "
                             f"names (got {fm['tools']!r})"))
        return out
    if read_only:
        wide = sorted(t for t in tools if t in WRITE_TOOLS or t == "*")
        if wide:
            out.append(("tools", f"agent says it is read-only but its 'tools:' line grants "
                                 f"{', '.join(wide)}"))
    return out


def _line_of(path: Path, key: str) -> int:
    import re
    try:
        for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(rf"^\s*{re.escape(key)}\s*:", ln):
                return i
    except OSError:
        pass
    return 1


def lint_tree(src: Path) -> list[str]:
    """Return a list of `file:line: reason` violation strings (empty == clean)."""
    errors: list[str] = []

    def err(path: Path, msg: str, line: int = 1) -> None:
        try:
            rel = path.relative_to(src.parent)
        except ValueError:
            rel = path
        errors.append(f"{rel}:{line}: {msg}")

    if not src.is_dir():
        return errors

    group_dirs = sorted(p for p in src.iterdir() if p.is_dir())
    group_slugs = {p.name for p in group_dirs}

    # pre-pass: each group's declared `capabilities` (targets for enhances)
    group_caps: dict[str, set[str]] = {}
    for gd in group_dirs:
        gy = gd / "group.yaml"
        if not gy.exists():
            continue
        try:
            meta = yaml.safe_load(gy.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            meta = {}
        caps = meta.get("capabilities") if isinstance(meta, dict) else None
        group_caps[gd.name] = {c for c in caps if isinstance(c, str)} if isinstance(caps, list) else set()

    for gd in group_dirs:
        gy = gd / "group.yaml"
        if not gy.exists():
            err(gd, "group folder has no group.yaml")
            continue
        try:
            d = yaml.safe_load(gy.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            err(gy, f"invalid YAML: {e}")
            continue
        if not isinstance(d, dict):
            err(gy, "group.yaml must be a mapping")
            continue
        for f in ("name", "description", "standalone"):
            if f not in d:
                err(gy, f"missing required field '{f}'")
        if "standalone" in d and not isinstance(d["standalone"], bool):
            err(gy, f"'standalone' must be a bool (got {d['standalone']!r})", _line_of(gy, "standalone"))
        requires = d.get("requires") or []
        if not isinstance(requires, list):
            err(gy, f"'requires' must be a list (got {requires!r})", _line_of(gy, "requires"))
            requires = []
        for r in requires:
            if r not in group_slugs:
                err(gy, f"requires '{r}' is not an existing group under src/", _line_of(gy, "requires"))
        if isinstance(d.get("standalone"), bool) and d["standalone"] == bool(requires):
            err(gy, f"invariant violated: standalone={d['standalone']} with requires={requires} "
                    f"(must be: standalone ⟺ requires:[])", _line_of(gy, "standalone"))

        # capabilities: a NON-EMPTY list of strings — every plugin declares what it
        # provides, so the resolver can answer "is <capability> available?" (AG Phase-2
        # capability-declaration hygiene). The names are also the targets enhances may point at.
        caps = d.get("capabilities")
        if caps is None:
            err(gy, "missing required field 'capabilities' (every plugin must declare what it provides)")
        elif not (isinstance(caps, list) and all(isinstance(c, str) for c in caps)):
            err(gy, f"'capabilities' must be a list of strings (got {caps!r})", _line_of(gy, "capabilities"))
        elif not caps:
            err(gy, "'capabilities' must be non-empty (declare what this plugin provides)", _line_of(gy, "capabilities"))

        # enhances: soft-composition edges — validated; orthogonal to requires/standalone
        enhances = d.get("enhances")
        if enhances is not None and not isinstance(enhances, list):
            err(gy, f"'enhances' must be a list (got {enhances!r})", _line_of(gy, "enhances"))
            enhances = []
        for entry in enhances or []:
            if isinstance(entry, str):
                tgt, cap = entry, None
            elif isinstance(entry, dict):
                tgt, cap = entry.get("group"), entry.get("capability")
            else:
                err(gy, f"'enhances' entry must be a group slug or a mapping (got {entry!r})", _line_of(gy, "enhances"))
                continue
            if not tgt:
                err(gy, "'enhances' entry is missing a target 'group'", _line_of(gy, "enhances"))
                continue
            if tgt not in group_slugs:  # (a) target exists
                err(gy, f"enhances target '{tgt}' is not an existing group under src/", _line_of(gy, "enhances"))
                continue
            if tgt == gd.name:  # (b) no self-enhance
                err(gy, f"enhances target '{tgt}' is the plugin itself (no self-enhance)", _line_of(gy, "enhances"))
            if tgt in requires:  # (c) enhances ∩ requires == ∅
                err(gy, f"enhances target '{tgt}' is also in requires — that is a hard dependency, not an enhancement", _line_of(gy, "enhances"))
            if cap is not None and cap not in group_caps.get(tgt, set()):  # (d) capability declared
                err(gy, f"enhances capability '{cap}' is not declared in {tgt}'s capabilities:", _line_of(gy, "enhances"))

        for sub in gd.iterdir():
            if sub.is_dir() and sub.name not in KNOWN_KIND_DIRS:
                err(sub, f"unexpected kind folder '{sub.name}' (known: {sorted(KNOWN_KIND_DIRS)})")

    for kind, (glb, name_of) in PRIMITIVE_KINDS.items():
        for path in sorted(src.glob(f"*/{glb}")):
            fm = read_frontmatter(path)
            if fm is None:
                err(path, "missing YAML frontmatter")
                continue
            if not isinstance(fm, dict):
                err(path, "frontmatter must be a mapping")
                continue
            for f in ("name", "description", "kind", "supported_hosts"):
                if f not in fm:
                    err(path, f"missing required field '{f}'", _line_of(path, f))
            if "kind" in fm and fm["kind"] not in KIND_ENUM:
                err(path, f"'kind' must be one of {sorted(KIND_ENUM)} (got {fm['kind']!r})", _line_of(path, "kind"))
            if fm.get("kind") and fm["kind"] != kind:
                err(path, f"'kind' is {fm['kind']!r} but the primitive sits under a '{kind}' folder", _line_of(path, "kind"))
            hosts = fm.get("supported_hosts")
            if hosts is not None:
                if not isinstance(hosts, list) or not hosts:
                    err(path, "'supported_hosts' must be a non-empty list", _line_of(path, "supported_hosts"))
                else:
                    bad = set(hosts) - HOST_ENUM
                    if bad:
                        err(path, f"'supported_hosts' has unknown host(s) {sorted(bad)}", _line_of(path, "supported_hosts"))
                    expressible = KIND_HOST_EXPRESSIBLE.get(kind, frozenset())
                    unexpressible = set(hosts) - bad - expressible
                    if unexpressible:
                        err(path,
                            f"'supported_hosts' claims {sorted(unexpressible)} for kind {kind!r}, "
                            f"but that host's emitter drops this kind on the floor "
                            f"(KIND_HOST_EXPRESSIBLE in src_model.py) — either add real "
                            f"emission for it, or drop the host from supported_hosts",
                            _line_of(path, "supported_hosts"))
            expected = name_of(path)
            if fm.get("name") and fm["name"] != expected:
                err(path, f"'name' is {fm['name']!r} but the primitive is named {expected!r}", _line_of(path, "name"))
            if kind == "agent":
                body = strip_frontmatter(path.read_text(encoding="utf-8"))
                for key, reason in lint_agent_tools(path, fm, body):
                    err(path, reason, _line_of(path, key))

    return errors


def main() -> int:
    if not SRC.is_dir():
        print("lint_src: no src/ directory — nothing to lint")
        return 0
    errors = lint_tree(SRC)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"\nlint_src: {len(errors)} error(s)", file=sys.stderr)
        return 1
    n_groups = len([p for p in SRC.iterdir() if p.is_dir()])
    n_prim = sum(len(list(SRC.glob(f"*/{glb}"))) for _, (glb, _) in PRIMITIVE_KINDS.items())
    print(f"lint_src: clean ({n_groups} group(s), {n_prim} primitive(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
