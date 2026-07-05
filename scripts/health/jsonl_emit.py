#!/usr/bin/env python3
"""jsonl_emit.py — shared JSONL check-record emitter for crickets unittest
suites (R2.1 / cricketsPluginsA#0, cricketsPluginsA#1, cricketsPluginsB#0).

Python sibling of agentm's `scripts/health/jsonl_emit.sh` (the bash suites'
shared helper) — same contract, same record schema
(`{suite, axis, check, pass, weight}`), consumed the same way by
`scripts/health/health_score.py` on the agentm side. A unittest file that
wants dashboard visibility calls `resolve_jsonl_out(sys.argv)` once, runs its
suite, then calls `emit_jsonl_check(...)` with the result — no-ops silently
when neither `--jsonl-out <path>` nor `$HEALTH_JSONL_OUT` is set, so a plain
`python3 -m unittest discover` run (check-all.sh's own invocation) is
completely unaffected.

Stdlib only.
"""
from __future__ import annotations

import json
import os


def resolve_jsonl_out(argv: list[str]) -> str | None:
    """Extract `--jsonl-out <path>` / `--jsonl-out=<path>` from argv, falling
    back to `$HEALTH_JSONL_OUT`. Does NOT mutate argv — callers that also feed
    argv to `unittest.main()` should strip the flag themselves first (see
    `strip_jsonl_out_flag`)."""
    for i, arg in enumerate(argv):
        if arg == "--jsonl-out" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--jsonl-out="):
            return arg.split("=", 1)[1]
    return os.environ.get("HEALTH_JSONL_OUT") or None


def strip_jsonl_out_flag(argv: list[str]) -> list[str]:
    """Return argv with any `--jsonl-out <path>` / `--jsonl-out=<path>` pair
    removed, so the remainder is safe to hand to `unittest.main(argv=...)`."""
    out: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--jsonl-out":
            i += 2
            continue
        if argv[i].startswith("--jsonl-out="):
            i += 1
            continue
        out.append(argv[i])
        i += 1
    return out


def emit_jsonl_check(jsonl_out: str | None, *, suite: str, check: str,
                      passed: bool | None, axis: str = "capability function",
                      weight: float = 1.0) -> None:
    """Append one check record. No-op when `jsonl_out` is falsy.

    `passed=None` marks a dark/skipped check (excluded from health_score.py's
    numerator and denominator, same treatment as a `dark: true` record).
    """
    if not jsonl_out:
        return
    record = {"suite": suite, "axis": axis, "check": check, "weight": weight}
    if passed is None:
        record["pass"] = None
        record["dark"] = True
    else:
        record["pass"] = passed
    with open(jsonl_out, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def run_module_as_health_check(module, argv: list[str], *, suite: str, check: str) -> int:
    """The shared `if __name__ == "__main__":` body for a health-visible test
    file: run `module`'s whole unittest suite (loaded directly — bypasses
    `unittest.main()`'s own argv parsing, which doesn't know `--jsonl-out`),
    emit one check record for the overall pass/fail, and return the process
    exit code (0 pass, 1 fail) — the same outcome as plain `unittest.main()`.

    One record per FILE (not per test method) — this suite's job is dashboard
    visibility for a single named regression, matching the granularity
    `validate-audit-coverage.sh` and the ledger's per-blocker IDs already use.
    """
    import unittest

    jsonl_out = resolve_jsonl_out(argv)
    runner = unittest.TextTestRunner()
    suite_obj = unittest.TestLoader().loadTestsFromModule(module)
    result = runner.run(suite_obj)
    emit_jsonl_check(jsonl_out, suite=suite, check=check, passed=result.wasSuccessful())
    return 0 if result.wasSuccessful() else 1
