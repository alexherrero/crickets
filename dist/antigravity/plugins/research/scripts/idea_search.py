#!/usr/bin/env python3
"""idea-search -- read-only ranked scan over the agentm recall engine.

Surfaces existing vault/codebase entries relevant to a question before
reaching outward (crickets wave-c-research, task 1). A thin wrapper over
agentm_bridge.query_semantic: no write path is reachable from this module
(agentm_bridge.py never loads agentm's save.py).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_sibling(name: str, filename: str):
    # A private, uniquely-named file-path load -- NOT `sys.path.insert` +
    # `import agentm_bridge` by its bare module name. That bare name
    # collides across every plugin that owns its own agentm_bridge.py (e.g.
    # src/maintenance/scripts/agentm_bridge.py): whichever loads first wins
    # the sys.modules["agentm_bridge"] slot, and Python's import cache
    # returns that SAME module to every later bare `import agentm_bridge` in
    # the process regardless of sys.path order -- observed as an
    # AttributeError in a same-process, cross-plugin test run
    # (wave-c-maintenance task 3, discovered fixing forward here).
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


agentm_bridge = _load_sibling("research_agentm_bridge", "agentm_bridge.py")


def search(question: str, vault: Path, *, k: int = 5, filter_expr: "str | None" = None) -> list:
    """Rank existing vault/codebase entries against `question`. Read-only --
    delegates entirely to agentm_bridge.query_semantic, [] if agentm is
    unresolvable."""
    return agentm_bridge.query_semantic(vault, question, filter_expr=filter_expr, k=k)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="idea-search -- read-only recall-engine scan")
    parser.add_argument("question")
    parser.add_argument("--vault-path", required=True)
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--filter", dest="filter_expr", default=None)
    args = parser.parse_args(argv)
    results = search(args.question, Path(args.vault_path), k=args.k, filter_expr=args.filter_expr)
    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
