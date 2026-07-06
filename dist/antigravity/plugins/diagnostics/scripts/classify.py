#!/usr/bin/env python3
"""Deterministic failure classifier for /diagnose (crickets wave-c-diagnostics).

Reads exit code / emitting tool / parsed structured output into one of five
namespaces (build/test/type/lint/runtime) -- no inference, no LLM judgment.
Structured-output signals win over the tool name (a tool can emit any kind of
failure; the structured record is the more specific signal).
"""
from __future__ import annotations

_TEST_TOOLS = {"pytest", "unittest", "jest", "vitest", "go test"}
_TYPE_TOOLS = {"mypy", "pyright", "tsc"}
_LINT_TOOLS = {"eslint", "ruff", "flake8", "pylint", "shellcheck"}
_BUILD_TOOLS = {"make", "npm run build", "cargo build", "go build", "webpack"}


def classify(*, exit_code: int, tool: str | None = None, structured_output: dict | None = None) -> str:
    """Return one of: build, test, type, lint, runtime."""
    structured_output = structured_output or {}
    if "rule_id" in structured_output:
        return "lint"
    if "failing_test_id" in structured_output:
        return "test"

    tool_key = (tool or "").strip().lower()
    if tool_key in _TEST_TOOLS:
        return "test"
    if tool_key in _TYPE_TOOLS:
        return "type"
    if tool_key in _LINT_TOOLS:
        return "lint"
    if tool_key in _BUILD_TOOLS:
        return "build"
    return "runtime"
