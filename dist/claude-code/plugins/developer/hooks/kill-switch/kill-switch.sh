#!/usr/bin/env bash
# kill-switch — operator emergency halt for long-running agent sessions.
#
# Fires on Claude Code's PreToolUse event (matcher .*). If .harness/STOP
# exists in the project root, blocks the tool call with exit code 2 and
# surfaces a halt message via stderr (which Claude Code shows to the agent).
#
# Operator usage:
#   touch .harness/STOP   # halt all tool calls
#   rm    .harness/STOP   # resume
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

if [[ -f .harness/STOP ]]; then
    echo "kill-switch: .harness/STOP present — halting tool call. Remove the file (rm .harness/STOP) to resume." >&2
    exit 2
fi

exit 0
