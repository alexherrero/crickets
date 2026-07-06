#!/usr/bin/env python3
"""idea-search -- read-only ranked scan over the agentm recall engine.

Surfaces existing vault/codebase entries relevant to a question before
reaching outward (crickets wave-c-research, task 1). A thin wrapper over
agentm_bridge.query_semantic: no write path is reachable from this module
(agentm_bridge.py never loads agentm's save.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agentm_bridge  # noqa: E402


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
