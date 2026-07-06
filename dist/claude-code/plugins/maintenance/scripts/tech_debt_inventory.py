#!/usr/bin/env python3
"""tech-debt-inventory -- a standing, recallable, classified debt backlog
(crickets wave-c-maintenance, task 3).

Not a one-shot report: each planted debt item is written once as a `debt`
memory entry (a convention over agentm's existing append/search/recall, no
schema change) at a deterministic slug, so a re-run against an unchanged
repo writes nothing new -- idempotent by construction via save_entry()'s own
FileExistsError-on-existing-slug guard, not a bespoke dedup index.

Two detectors for now (the task's own "e.g." list is illustrative, not
exhaustive): TODO/FIXME comments (documentation debt) and oversized
functions via ast (refactoring debt).
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from pathlib import Path


def _load_sibling(name: str, filename: str):
    # A private, uniquely-named file-path load -- NOT `sys.path.insert` +
    # `import agentm_bridge` by its bare module name. That bare name
    # collides across every plugin that owns its own agentm_bridge.py (e.g.
    # src/research/scripts/agentm_bridge.py): whichever loads first wins the
    # sys.modules["agentm_bridge"] slot, and Python's import cache returns
    # that SAME module to every later bare `import agentm_bridge` in the
    # process regardless of sys.path order -- observed as an AttributeError
    # in a same-process, cross-plugin test run (wave-c-maintenance task 3).
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


agentm_bridge = _load_sibling("maintenance_agentm_bridge", "agentm_bridge.py")

_TODO_RE = re.compile(r"#\s*(TODO|FIXME)\b\s*:?\s*(.*)")
_MAX_FUNCTION_LINES = 50
_KEBAB_INVALID = re.compile(r"[^a-z0-9]+")


def _kebab(text: str) -> str:
    text = _KEBAB_INVALID.sub("-", text.lower())
    return text.strip("-") or "x"


def _todo_items(path: Path, rel: str):
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        m = _TODO_RE.search(line)
        if m:
            yield {
                "file": rel, "line": lineno, "debt_class": "documentation",
                "detail": (m.group(2).strip() or m.group(1)),
            }


def _oversized_function_items(path: Path, rel: str, max_lines: int = _MAX_FUNCTION_LINES):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno or node.lineno
            span = end - node.lineno + 1
            if span > max_lines:
                yield {
                    "file": rel, "line": node.lineno, "debt_class": "refactoring",
                    "detail": f"{node.name} spans {span} lines (> {max_lines})",
                }


def _iter_debt_items(repo_root: Path):
    for path in sorted(repo_root.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        yield from _todo_items(path, rel)
        yield from _oversized_function_items(path, rel)


def _slug_for(item: dict) -> str:
    return f"debt-{_kebab(item['file'])}-{item['line']}-{item['debt_class']}"


def _body_for(item: dict) -> str:
    return (
        f"## Location\n{item['file']}:{item['line']}\n\n"
        f"## Detail\n{item['detail']}\n"
    )


def scan_and_record(repo_root: Path, vault: Path) -> list:
    """Scan `repo_root` for debt markers and write each as a classified
    `debt` entry in `vault`. Returns the paths newly written this run --
    empty on a re-run against an unchanged repo (already-recorded items are
    skipped, not duplicated)."""
    written = []
    for item in _iter_debt_items(repo_root):
        path = agentm_bridge.write_debt_entry(
            vault, slug=_slug_for(item), body=_body_for(item), tags=[item["debt_class"]],
        )
        if path is not None:
            written.append(path)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="tech-debt-inventory -- standing classified debt backlog")
    parser.add_argument("repo_root")
    parser.add_argument("--vault-path", required=True)
    args = parser.parse_args(argv)
    written = scan_and_record(Path(args.repo_root), Path(args.vault_path))
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
