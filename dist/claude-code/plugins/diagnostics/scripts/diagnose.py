#!/usr/bin/env python3
"""/diagnose: classify -> recall (fingerprint-first) -> rank hypotheses -> write.

The deterministic-first failure-diagnosis pipeline (crickets wave-c-diagnostics).
Wires fingerprint.py + classify.py + recall_ladder.py + writer.py end to end.
A same-fingerprint re-run is a Layer-1 hit -- no new entry, no LLM judgment
anywhere in this pipeline.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_sibling(label: str, filename: str):
    spec = importlib.util.spec_from_file_location(
        f"_diagnostics_internal_{label}", _HERE / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fingerprint_mod = _load_sibling("fingerprint", "fingerprint.py")
classify_mod = _load_sibling("classify", "classify.py")
recall_ladder = _load_sibling("recall_ladder", "recall_ladder.py")
writer = _load_sibling("writer", "writer.py")


def _rank_hypotheses(candidates: list, namespace: str, error_class: str) -> list:
    """Deterministic hypothesis ranking -- no LLM judgment. Existing similar
    incidents (Layer-2 candidates) rank first, highest score first; a generic
    namespace/error-class fallback fills in when memory has nothing similar."""
    hypotheses = [
        f"Similar to existing incident at {c['path']} (score {c.get('score', 0):.2f})"
        for c in sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:3]
    ]
    if not hypotheses:
        hypotheses.append(
            f"New {namespace} failure ({error_class}) -- no similar incident found in memory"
        )
    return hypotheses[:3]


def diagnose(
    *,
    vault: Path,
    project: str,
    traceback_text: str,
    exit_code: int = 1,
    tool: "str | None" = None,
    structured_output: "dict | None" = None,
) -> dict:
    """Run the full pipeline. Returns:
      {"outcome": "layer1_hit", "path", "fingerprint", "fp_algo", "namespace"}
      {"outcome": "written", "path", "fingerprint", "fp_algo", "namespace", "hypotheses"}
    """
    fp, fp_algo = fingerprint_mod.compute_fingerprint(traceback_text)
    namespace = classify_mod.classify(
        exit_code=exit_code, tool=tool, structured_output=structured_output
    )
    error_class, _frames = fingerprint_mod.extract_signature(traceback_text)

    ladder_result = recall_ladder.recall(
        vault=vault, fingerprint=fp, project=project,
        query_text=traceback_text, namespace=namespace,
    )
    if ladder_result["layer"] == 1:
        return {
            "outcome": "layer1_hit",
            "path": ladder_result["path"],
            "fingerprint": fp,
            "fp_algo": fp_algo,
            "namespace": namespace,
        }

    hypotheses = _rank_hypotheses(ladder_result["candidates"], namespace, error_class)
    target = writer.write_failure_incident(
        vault, project=project, fingerprint=fp, namespace=namespace,
        symptom=traceback_text, hypotheses=hypotheses,
    )
    return {
        "outcome": "written",
        "path": str(target.relative_to(vault)),
        "fingerprint": fp,
        "fp_algo": fp_algo,
        "namespace": namespace,
        "hypotheses": hypotheses,
    }


def _parse_args(argv: "list[str]") -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="diagnose",
        description="Deterministic-first failure diagnosis: classify -> recall -> rank -> write.",
    )
    parser.add_argument(
        "--vault-path", required=False,
        help="MemoryVault root (overrides MEMORY_VAULT_PATH env var)",
    )
    parser.add_argument("--project", required=True, help="project slug this failure belongs to")
    parser.add_argument("--exit-code", type=int, default=1)
    parser.add_argument("--tool", default=None)
    parser.add_argument(
        "traceback_file", help="path to the captured traceback/log, or '-' for stdin"
    )
    return parser.parse_args(argv)


def _resolve_vault_path(arg_vault_path: "str | None") -> Path:
    if arg_vault_path:
        return Path(arg_vault_path).expanduser()
    env_path = os.environ.get("MEMORY_VAULT_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    raise FileNotFoundError("No vault path resolved. Set --vault-path or MEMORY_VAULT_PATH.")


def main(argv: "list[str] | None" = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        vault = _resolve_vault_path(args.vault_path)
        text = (
            sys.stdin.read()
            if args.traceback_file == "-"
            else Path(args.traceback_file).read_text(encoding="utf-8")
        )
        result = diagnose(
            vault=vault, project=args.project, traceback_text=text,
            exit_code=args.exit_code, tool=args.tool,
        )
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
