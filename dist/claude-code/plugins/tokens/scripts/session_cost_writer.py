#!/usr/bin/env python3
"""Session-cost capture — the Stop-hook half absorbed from the never-staged
`PLAN-session-cost-capture` micro-plan (2026-07-05 decision record, absorbed
verbatim into PLAN-wave-d-tokens-and-privacy task 1).

At session Stop: run analyzer.py over the closing session's transcript, group
its per-message records by model, and write one `kind: session-cost` memory
entry per model via agentm's save_entry() path — a `{model, tokens_by_kind,
cost_usd, timestamp}` record the fan-out cost gate (fanout_cost_gate.py) can
later average over via its `observed_records` param.

Capture-half only, per the decision record's scope: no dreaming-pass trend
analysis lives here (see dreaming_trend_stub.py for that gate, staged dark).

Graceful no-op contract (must never block a session close):
  - no memory backend / agentm unresolvable -> return None, no write, no raise
  - transcript unreadable / empty -> return None, no write, no raise
  - any unexpected error -> caught, logged to stderr, return None

This module is pure Python (importable + independently testable); the actual
Stop hook (session-cost-capture.sh / .ps1) is a thin shell wrapper that calls
`main()` below.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, _HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, m)
    spec.loader.exec_module(m)
    return m


analyzer = _load_sibling("analyzer")

# agentm's save_entry() lives in harness/skills/memory/scripts/save.py — same
# path-fallback convention as diagnostics/scripts/agentm_bridge.py (env
# override -> co-located install -> conventional sibling clone). Not imported
# from agentm_bridge.py directly: that module lives in the diagnostics group,
# and tokens must not depend on a sibling capability to resolve its own
# agentm bridge (each capability's bridge is self-contained).
_SAVE_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"

_save_module = None
_save_loaded = False


def _candidate_dirs() -> list[Path]:
    import os
    candidates = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(Path.home() / "Antigravity" / "agentm" / _SAVE_SCRIPTS_REL)
    return candidates


def _find_save_scripts_dir() -> "Path | None":
    for candidate in _candidate_dirs():
        if (candidate / "save.py").is_file():
            return candidate
    return None


def load_save_module():
    """Return agentm's save module, loaded once and cached. None if agentm is
    unresolvable (graceful-skip, not an error)."""
    global _save_module, _save_loaded
    if _save_loaded:
        return _save_module
    _save_loaded = True
    scripts_dir = _find_save_scripts_dir()
    if scripts_dir is None:
        _save_module = None
        return None
    spec = importlib.util.spec_from_file_location("agentm_save_bridge_tokens", scripts_dir / "save.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["agentm_save_bridge_tokens"] = module
    spec.loader.exec_module(module)
    _save_module = module
    return module


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level cache between isolated test cases."""
    global _save_module, _save_loaded
    _save_module = None
    _save_loaded = False


@dataclass(frozen=True)
class ModelCostSummary:
    model: str
    tokens_by_kind: dict  # {"input", "cache_write", "cache_read", "output"} -> int
    cost_usd: float


def summarize_by_model(messages: list) -> list[ModelCostSummary]:
    """Group analyzer.MessageRecord objects by model, summing tokens + cost."""
    by_model: dict[str, dict] = {}
    for m in messages:
        entry = by_model.setdefault(m.model, {
            "input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "cost_usd": 0.0,
        })
        entry["input"] += m.input_tokens
        entry["cache_write"] += m.cache_write_tokens
        entry["cache_read"] += m.cache_read_tokens
        entry["output"] += m.output_tokens
        entry["cost_usd"] += m.cost_usd
    return [
        ModelCostSummary(
            model=model,
            tokens_by_kind={
                "input": v["input"], "cache_write": v["cache_write"],
                "cache_read": v["cache_read"], "output": v["output"],
            },
            cost_usd=v["cost_usd"],
        )
        for model, v in by_model.items()
    ]


def _record_body(summary: ModelCostSummary, *, timestamp: str) -> str:
    """Render the session-cost entry body (plain, deterministic — no LLM)."""
    tb = summary.tokens_by_kind
    return (
        f"## Session cost — {summary.model}\n\n"
        f"- timestamp: {timestamp}\n"
        f"- model: {summary.model}\n"
        f"- cost_usd: {summary.cost_usd:.6f}\n"
        f"- input_tokens: {tb['input']}\n"
        f"- cache_write_tokens: {tb['cache_write']}\n"
        f"- cache_read_tokens: {tb['cache_read']}\n"
        f"- output_tokens: {tb['output']}\n"
    )


def capture_session_cost(
    transcript_path: "str | Path",
    *,
    vault_path: "str | Path | None",
    project: str = "personal",
) -> list[Path]:
    """Analyze `transcript_path` and write one `kind: session-cost` entry per
    model observed. Returns the list of paths written (empty on any
    graceful-skip condition). Never raises.
    """
    if not vault_path:
        return []
    vault = Path(vault_path)
    if not vault.is_dir():
        return []

    save = load_save_module()
    if save is None:
        return []

    try:
        report = analyzer.analyze_session(transcript_path)
    except (OSError, ValueError):
        return []
    if not report.messages:
        return []

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    written: list[Path] = []
    for summary in summarize_by_model(report.messages):
        slug = f"{project}-{summary.model}-{timestamp}".lower()
        # kebab-case: model ids already use hyphens/digits; project is
        # caller-controlled and expected kebab already (mirrors diagnostics'
        # own namespace-slug convention).
        try:
            target = save.save_entry(
                vault, "session-cost", slug,
                _record_body(summary, timestamp=timestamp),
                group=f"projects/{project}/session-cost",
                tags=["session-cost"],
            )
        except (ValueError, FileExistsError, FileNotFoundError):
            # Never block a session close over a write-path hiccup (a
            # same-second duplicate slug, an invalid project slug, etc.).
            continue
        written.append(target)
    return written


def _resolve_vault_path() -> "str | None":
    """env MEMORY_VAULT_PATH -> engine .agentm-config.json vault_path -> None.
    Mirrors conflict-merger-session-start.sh's own resolution chain."""
    import json
    import os

    env_path = os.environ.get("MEMORY_VAULT_PATH", "").strip()
    if env_path:
        return env_path
    cfg_path = Path(os.environ.get("AGENTM_INSTALL_PREFIX", str(Path.home() / ".claude"))) / ".agentm-config.json"
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        v = data.get("vault_path")
        if v:
            return v
    return None


def main(argv: "list[str] | None" = None) -> int:
    """CLI entry point for the Stop hook shell wrapper.

    Usage: session_cost_writer.py <transcript-path> [--project <slug>]
    Always exits 0 — a capture failure must never fail the hook / block
    session close. Diagnostic detail (if any) goes to stderr.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("transcript_path")
    parser.add_argument("--project", default="personal")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        vault_path = _resolve_vault_path()
        written = capture_session_cost(
            args.transcript_path, vault_path=vault_path, project=args.project,
        )
        if written:
            print(
                f"session-cost-capture: wrote {len(written)} record(s)",
                file=sys.stderr,
            )
    except Exception as e:  # pragma: no cover — belt-and-suspenders; must never raise
        print(f"session-cost-capture: no-op ({e})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
