#!/usr/bin/env bash
# harness-context-session-start — on SessionStart, if this repo uses the
# developer-workflows loop (`.harness/PLAN.md` + `.harness/progress.md` present),
# inject their paths into session context so the agent reads PLAN.md before
# answering plan-status questions or running /work, /review, /release. Silent
# no-op otherwise.
#
# Standalone + storage-agnostic: this checks plain `.harness/` state in the repo.
# If a memory/storage layer (e.g. agentm's MemoryVault) is hosting the loop, that
# layer ships its own context hook that redirects to wherever it keeps state.
#
# Claude-only-effective: SessionStart has no Antigravity equivalent (this hook is
# declared claude-code-only, so the AG plugin never carries it).

set -uo pipefail   # NOTE: no -e — must never block session boot (graceful-skip).

# ── Read the SessionStart event JSON; prefer the event cwd over $PWD ───────────
PAYLOAD="$(cat 2>/dev/null || true)"
EVENT_CWD=""
if [[ -n "$PAYLOAD" ]] && command -v python3 >/dev/null 2>&1; then
    EVENT_CWD="$(printf '%s' "$PAYLOAD" | python3 -c '
import json, sys
try:
    print(json.loads(sys.stdin.read()).get("cwd") or "")
except Exception:
    pass
' 2>/dev/null || true)"
fi
[[ -z "$EVENT_CWD" ]] && EVENT_CWD="$(pwd)"
[[ -d "$EVENT_CWD" ]] || exit 0

PLAN="$EVENT_CWD/.harness/PLAN.md"
PROGRESS="$EVENT_CWD/.harness/progress.md"

# ── Inject only when BOTH exist on disk ────────────────────────────────────────
if [[ -f "$PLAN" && -f "$PROGRESS" ]]; then
    cat <<EOF
[developer-workflows] This project uses the phase-gated loop. Its state:
  PLAN.md:     $PLAN
  progress.md: $PROGRESS
Read PLAN.md before answering plan-status questions or running /work, /review, /release.
EOF
    echo "[harness-context] injected .harness/ paths for $EVENT_CWD" >&2
else
    echo "[harness-context] no .harness/PLAN.md + progress.md at $EVENT_CWD — skipped" >&2
fi

exit 0
