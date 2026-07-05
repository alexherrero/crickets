#!/usr/bin/env bash
# steer — inject mid-run guidance from .harness/STEER.md.
#
# Fires on Claude Code's UserPromptSubmit event (matcher .*). If
# .harness/STEER.md exists in the project root, emits its contents as
# {"additionalContext": "<contents>"} JSON on stdout (Claude Code's documented
# mechanism for injecting UserPromptSubmit output into the agent's context —
# see PLAN-r2-enforcement-and-sync task 5's live-verify note below) and
# renames the file to .harness/STEER.consumed-<iso-timestamp>.md for audit
# trail.
#
# Was PreToolUse until R2.2 task 5: a live-verify fixture (a real headless
# Claude Code session, a PreToolUse hook proven to fire via an independent
# audit-log side effect, and the model explicitly asked to report ANY extra
# context it received) confirmed PreToolUse stdout is NOT injected into the
# agent's context — the mechanism this hook, hook.md, wiki/reference/Hooks.md,
# the developer-safety design, and 6+ CHANGELOG entries had asserted for
# multiple releases was never actually true. UserPromptSubmit +
# additionalContext is Claude Code's real injection surface (independently
# corroborated by this repo's own memory-recall-prompt-submit-style hooks,
# which use the identical mechanism in live sessions).
#
# Operator usage:
#   echo "Actually, do it this way..." > .harness/STEER.md
#
# The guidance now surfaces on the NEXT USER PROMPT, not the next tool call
# within the same turn (UserPromptSubmit fires once per submitted prompt) —
# this is a real behavior change from the PreToolUse-based version, not just
# a mechanism swap; see hook.md.
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

if [[ -f "$STEER_FILE" ]] && command -v python3 >/dev/null 2>&1; then
    # Emit {"additionalContext": "<contents>"} — Claude Code's UserPromptSubmit
    # injection contract. python3 owns the JSON encoding (never hand-rolled
    # string escaping — the guidance can contain quotes, newlines, backslashes).
    python3 -c '
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as fh:
    content = fh.read()
print(json.dumps({"additionalContext": content}))
' "$STEER_FILE"

    # Rename for audit trail (UTC timestamp).
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$STEER_FILE" ".harness/STEER.consumed-${ts}.md"
fi

exit 0
