#!/usr/bin/env bash
# memory-recall-session-start — load MemoryVault always-load entries on session boot.
#
# Fires on Claude Code's SessionStart event. Calls the memory skill's recall.py
# helper to glob _always-load/*.md entries + emit their bodies on stdout (which
# Claude Code injects as additional session context). Transparency line on
# stderr. Hard 500ms time budget; degraded-graceful on overrun.
#
# See hook.md in this directory for full documentation.

set -uo pipefail  # NOTE: no -e — graceful-skip pattern; hook must never block session boot.

# Resolve recall.py location. The installer drops the memory skill at
# .claude/skills/memory/scripts/recall.py; this hook script runs from the
# target project root (Claude Code's cwd convention), so the path is fixed.
RECALL_PY=".claude/skills/memory/scripts/recall.py"
if [[ ! -f "$RECALL_PY" ]]; then
    # Memory skill not installed; nothing to do. Exit 0 (graceful-skip).
    exit 0
fi

# Require python3 — exit 0 if missing (graceful-skip; no blocking).
if ! command -v python3 >/dev/null 2>&1; then
    exit 0
fi

# Invoke. recall.py handles MEMORY_VAULT_PATH resolution, glob, frontmatter
# parse, filter, output, and the 500ms time budget internally.
exec python3 "$RECALL_PY" session-start
