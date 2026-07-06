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

# ── Surface launched design paths (Hook 6 — paths only, bounded, ≤4) ────────────
# Inject the *paths* of governing designs (status: launched) the way PLAN.md is
# injected above — never their body (that would regress the per-call floor). /plan
# + /review resolve the specific governing design via find_governing_design.py.
DESIGNS_DIR="$EVENT_CWD/wiki/designs"
if [[ -d "$DESIGNS_DIR" ]]; then
    DESIGNS="$(grep -lE '^status:[[:space:]]*launched' "$DESIGNS_DIR"/*.md 2>/dev/null | head -4)"
    if [[ -n "$DESIGNS" ]]; then
        echo "[developer-workflows] Governing designs (launched) — /plan + /review resolve the governing one:"
        while IFS= read -r d; do
            [[ -n "$d" ]] && echo "  design: $d"
        done <<< "$DESIGNS"
    fi
fi

# ── Session-start tier + advisor nudge (PLAN-efficiency-dispatch task 7) ────────
# Compares the live session model against the active plan's next unchecked
# task's staged tier hint (task 6) and states advisor availability (task 3) —
# advisory only, never switches the session's model. Graceful-skip when
# CLAUDE_PLUGIN_ROOT is unset, the script is missing, or python3 errors.
NUDGE_PY="${CLAUDE_PLUGIN_ROOT:-}/scripts/session_start_nudge.py"
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" && -f "$NUDGE_PY" ]] && command -v python3 >/dev/null 2>&1; then
    NUDGE="$(python3 -c '
import importlib.util, json, sys
from pathlib import Path

nudge_py = sys.argv[1]
plan_path = sys.argv[2]
event_cwd = sys.argv[3]
payload = sys.argv[4]

spec = importlib.util.spec_from_file_location("session_start_nudge", nudge_py)
ssn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssn)
advisor_rider = ssn.advisor_rider

live_model = None
try:
    live_model = (json.loads(payload).get("model") or {}).get("id") or None
except Exception:
    pass

plan_hint_model = None
try:
    plan_text = Path(plan_path).read_text(encoding="utf-8")
    plan_hint_model = ssn.next_unchecked_task_tier_hint_model(plan_text)
except Exception:
    pass

advisor_model = advisor_rider.read_advisor_model(event_cwd)

print(ssn.session_start_nudge(live_model, plan_hint_model, advisor_model))
' "$NUDGE_PY" "$PLAN" "$EVENT_CWD" "$PAYLOAD" 2>/dev/null || true)"
    if [[ -n "$NUDGE" ]]; then
        echo "[developer-workflows] $NUDGE"
    fi
fi

exit 0
