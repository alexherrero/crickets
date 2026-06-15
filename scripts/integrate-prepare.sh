#!/usr/bin/env bash
# integrate-prepare.sh — the single-writer artifact-prepare hook the generic
# integrator (src/developer-workflows/scripts/integrate_worker.py) runs on the
# merged tree, BEFORE the gate, when this repo provides it (ADR 0030).
#
#   integrate-prepare.sh <pre-merge-sha>
#
# Thin wrapper: all logic + tests live in integrate_prepare.py (the integrator
# contract is a shell entry point; the implementation stays testable Python). The
# pre-merge SHA arrives as $1; cwd is the repo root (integrate_worker sets it), so
# integrate_prepare.py defaults --project-root to it. Forwards every arg through.
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/integrate_prepare.py" "$@"
