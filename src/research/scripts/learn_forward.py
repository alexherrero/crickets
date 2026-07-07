#!/usr/bin/env python3
"""learn-forward -- scheduled mining onto the idea incubator/watchlist
(crickets wave-c-research, PLAN-wave-c-research-forward-learning task 1).

A thin wrapper over agentm's real approved-source forward-learning pipeline
(harness/skills/memory/scripts/forward_learning.py, PLAN-wave-e-experience
task 1) -- crickets leans BY NAME on that substrate rather than
reimplementing it (wiki/designs/crickets-research.md's "lean by name on
agentm's forward-experience substrate" contract). This module is the CLI
entry point a job manifest's `command:` would invoke -- mirrors agentm's
own templates/jobs/*.yaml convention. crickets ships no runner of its own
(confirmed at research time), so whichever repo installs this plugin
registers the actual scheduled job against ITS runner; this module is what
that job's command runs.

Strictly discovery-surfacing: findings land in the watchlist via agentm's
own write path (personal/_watchlist/) -- this module never adopts, merges,
or auto-edits anything itself. The negative assertion (nothing outside the
watchlist/cache changes) is proven in scripts/test_research_learn_forward.py.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Optional


def _load_sibling(name: str, filename: str):
    # See idea_search.py's _load_sibling for the full rationale: a private,
    # uniquely-named file-path load avoids the bare-import sys.modules
    # collision across plugins that each own their own agentm_bridge.py.
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


agentm_bridge = _load_sibling("research_agentm_bridge", "agentm_bridge.py")


def learn(vault: Path, *, fetcher=None, now: Optional[float] = None):
    """Run one forward-learning scan via agentm's real pipeline. Returns
    agentm's own ScanResult, or None if agentm is unresolvable
    (graceful-skip, not an error -- same posture as idea-search).
    `fetcher`/`now` pass straight through to agentm's
    `run_forward_learning` (test-injectable determinism; production callers
    omit both and get the real network fetcher + wall-clock time)."""
    module = agentm_bridge.load_forward_learning_module()
    if module is None:
        return None
    kwargs = {}
    if fetcher is not None:
        kwargs["fetcher"] = fetcher
    if now is not None:
        kwargs["now"] = now
    return module.run_forward_learning(vault, **kwargs)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="learn-forward -- scheduled mining onto the idea incubator/watchlist")
    parser.add_argument("--vault-path", required=True)
    args = parser.parse_args(argv)
    result = learn(Path(args.vault_path))
    if result is None:
        print(json.dumps({"error": "agentm sibling checkout unavailable"}))
        return 1
    print(
        json.dumps(
            {
                "sources_scanned": result.sources_scanned,
                "candidates_seen": result.candidates_seen,
                "written": [str(p) for p in result.written],
                "dropped_low": result.dropped_low,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
