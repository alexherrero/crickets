#!/usr/bin/env bash
# steer — inject mid-run guidance from .harness/STEER.md.
#
# Fires on Claude Code's PreToolUse event (matcher .*). If .harness/STEER.md
# exists in the project root, prints its contents to stdout (which Claude Code
# injects into the agent's context for the upcoming tool call) and renames
# the file to .harness/STEER.consumed-<iso-timestamp>.md for audit trail.
#
# Operator usage:
#   echo "Actually, do it this way..." > .harness/STEER.md
#
# See hook.md in this directory for full documentation.

set -euo pipefail

# ── resolve the workspace root (host-portable) ──────────────────────────────
# Claude Code runs hooks from the project root + passes JSON on stdin with
# "cwd" (and sets $CLAUDE_PROJECT_DIR). Antigravity runs plugin hooks from the
# PLUGIN dir + passes the workspace on stdin as {"workspacePaths":["<root>"]}.
# Resolve an explicit workspace signal, then cd into it so the relative
# .harness/… logic below works on both hosts; fall back to cwd for manual runs.
_resolve_workspace() {
    local payload="" ws=""
    if [ ! -t 0 ]; then
        IFS= read -r -d '' -t 2 payload <&0 2>/dev/null || true
    fi
    if [ -n "$payload" ] && command -v python3 >/dev/null 2>&1; then
        # Parse with a real JSON parser (only TOP-LEVEL keys) — robust against
        # nested/decoy "cwd" tokens and pretty-printed payloads that sed can't.
        ws="$(printf '%s' "$payload" | python3 -c 'import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(d, dict):
    sys.exit(0)
wp = d.get("workspacePaths")
if isinstance(wp, list) and wp and isinstance(wp[0], str):
    print(wp[0]); sys.exit(0)
c = d.get("cwd")
if isinstance(c, str):
    print(c)' 2>/dev/null)"
    fi
    if [ -z "$ws" ]; then ws="${CLAUDE_PROJECT_DIR:-}"; fi
    if [ -z "$ws" ]; then ws="."; fi
    printf '%s' "$ws"
}
_ws="$(_resolve_workspace)"
cd "$_ws" 2>/dev/null || true

STEER_FILE=".harness/STEER.md"

if [[ -f "$STEER_FILE" ]]; then
    # Emit contents to stdout — Claude Code captures and injects.
    cat "$STEER_FILE"

    # Rename for audit trail (UTC timestamp).
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$STEER_FILE" ".harness/STEER.consumed-${ts}.md"
fi

exit 0
