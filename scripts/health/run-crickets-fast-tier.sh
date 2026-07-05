#!/usr/bin/env bash
# run-crickets-fast-tier.sh — run every crickets suite that emits JSONL check
# records, collect them, and print them to stdout (R2.1 / cricketsPluginsA#0,
# cricketsPluginsA#1, cricketsPluginsB#0).
#
# Usage (consumed the same way agentm's own run-fast-tier.sh is):
#   bash scripts/health/run-crickets-fast-tier.sh | python3 <path-to-agentm>/scripts/health/health_score.py
#
# Mirrors agentm's scripts/health/run-fast-tier.sh: each suite's own
# PASS/FAIL table still prints to this script's stderr unsuppressed; only the
# JSONL check records go to stdout. A suite exiting non-zero does NOT abort
# the batch — the scorecard's job is to report health, not to gate
# (check-all.sh's `unit tests` gate, which already runs all three suites via
# `unittest discover`, is the actual gate).
#
# Exit: always 0 — an individual suite's PASS/FAIL is data for the scorecard,
# not this script's own outcome.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(cd "$HERE/.." && pwd)"
PY="${PYTHON:-python3}"

JSONL_TMP="$(mktemp)"
trap 'rm -f "$JSONL_TMP"' EXIT

run_suite() {  # run_suite <label> <cmd...>
  local label="$1"; shift
  echo "run-crickets-fast-tier: running $label…" >&2
  if ! "$@" --jsonl-out "$JSONL_TMP" >&2; then
    echo "run-crickets-fast-tier: $label exited non-zero (recorded in the JSONL; batch continues)" >&2
  fi
}

run_suite "test_find_capability" "$PY" "$SCRIPTS_DIR/test_find_capability.py"
run_suite "test_finalize_unit"   "$PY" "$SCRIPTS_DIR/test_finalize_unit.py"
run_suite "test_token_audit"     "$PY" "$SCRIPTS_DIR/test_token_audit.py"

cat "$JSONL_TMP"
exit 0
