#!/usr/bin/env bash
# conflict-merger-session-start — detect GDrive/DriveFS conflict files on session boot.
#
# Walks the Obsidian vault (and the DriveFS lost_and_found/ dump) for conflict +
# duplicate files across the four marker families; surfaces a one-paragraph
# operator-facing notice on stderr per pair found. Non-blocking: never freezes
# session boot waiting on operator input.
#
# Re-homed out of the agentm kernel (V5-2 task 2): the conflict-sweep helpers now
# live in this plugin's scripts/vault_conflicts.py, which imports the pure
# filename classifier _conflict_family from the present engine (LC-3). This hook
# loads vault_conflicts.py from $CLAUDE_PLUGIN_ROOT and puts the engine scripts/
# dir on sys.path so that import resolves.
#
# Graceful-skip when no vault resolves, the plugin script is missing, or the
# present engine (harness_memory.py) is unavailable.
#
# See hook.md in this directory for full documentation.

set -uo pipefail  # no -e — hook must never block session boot.

# Honor mode env var.
MODE="${HARNESS_CONFLICT_MERGER_MODE:-interactive}"
if [[ "$MODE" == "off" ]]; then
    exit 0
fi

# Resolve MEMORY_VAULT_PATH: env → engine .agentm-config.json vault_path → none.
# Claude Code does NOT inject MEMORY_VAULT_PATH into the hook env on user-scope
# installs, so an env-only check silently skipped on every real session boot and
# never ran detect_conflict_files(). LC-4: the engine config is read in place,
# never written.
_resolve_vault_path() {
    if [[ -n "${MEMORY_VAULT_PATH:-}" ]]; then
        printf '%s\n' "$MEMORY_VAULT_PATH"; return 0
    fi
    local cfg="${AGENTM_INSTALL_PREFIX:-$HOME/.claude}/.agentm-config.json"
    if [[ -f "$cfg" ]] && command -v python3 >/dev/null 2>&1; then
        local v
        v="$(python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
print(d.get("vault_path") or "")
' "$cfg" 2>/dev/null || true)"
        if [[ -n "$v" ]]; then printf '%s\n' "$v"; return 0; fi
    fi
    return 1
}
MEMORY_VAULT_PATH="$(_resolve_vault_path 2>/dev/null)" || MEMORY_VAULT_PATH=""

# Graceful-skip if no vault resolved or it doesn't exist on disk.
if [[ -z "$MEMORY_VAULT_PATH" ]]; then
    exit 0
fi
if [[ ! -d "$MEMORY_VAULT_PATH" ]]; then
    exit 0
fi

# This plugin's vault_conflicts.py — ships at $CLAUDE_PLUGIN_ROOT/scripts/.
VC_PY="${CLAUDE_PLUGIN_ROOT:-}/scripts/vault_conflicts.py"
if [[ -z "${CLAUDE_PLUGIN_ROOT:-}" || ! -f "$VC_PY" ]]; then
    # Not running as an installed plugin — graceful-skip.
    exit 0
fi

# Resolve the present engine's scripts/ dir (where harness_memory.py lives).
# vault_conflicts.py imports _conflict_family from it at module load, so the dir
# must be on sys.path before the module execs. Search the standard locations.
KERNEL_SCRIPTS=""
for candidate in \
    "$HOME/Antigravity/agentm/scripts/harness_memory.py" \
    "../agentm/scripts/harness_memory.py" \
    "../../agentm/scripts/harness_memory.py"; do
    if [[ -f "$candidate" ]]; then
        KERNEL_SCRIPTS="$(cd "$(dirname "$candidate")" && pwd)"
        break
    fi
done
if [[ -z "$KERNEL_SCRIPTS" ]]; then
    # No present engine on this device — nothing to import, graceful-skip.
    exit 0
fi

# Invoke detect-conflict-files via a small inline Python that loads the plugin
# helper. stderr is intentionally NOT redirected — the Python writes operator-
# facing findings there. Python-level errors (import / runtime) also surface —
# that's acceptable; the hook still exits 0 (never blocks session boot).
python3 - "$VC_PY" "$KERNEL_SCRIPTS" "$MEMORY_VAULT_PATH" <<'PY' || true
import importlib.util, os, sys
from pathlib import Path
vc_path, kernel_scripts, vault_root = sys.argv[1], sys.argv[2], sys.argv[3]
# vault_conflicts.py does `from harness_memory import _conflict_family` at load
# (LC-3 present-engine import) — put the engine scripts dir on sys.path first.
sys.path.insert(0, kernel_scripts)
spec = importlib.util.spec_from_file_location("vault_conflicts", vc_path)
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)
# Sweep the broadened marker set (vault) + the DriveFS lost_and_found/ dump
# (macOS/Windows; resolves to None elsewhere → no extra scan).
laf = vc.default_lost_and_found_root()
conflicts = vc.detect_conflict_files(Path(vault_root), lost_and_found_root=laf)
if not conflicts:
    sys.exit(0)
mode = os.environ.get("HARNESS_CONFLICT_MERGER_MODE", "interactive")
n_vault = sum(1 for e in conflicts if e.get("source") != "lost_and_found")
n_laf = len(conflicts) - n_vault
sys.stderr.write(
    f"\n[conflict-merger] {len(conflicts)} conflict/duplicate file(s) detected "
    f"({n_vault} in vault, {n_laf} in DriveFS lost_and_found):\n"
)
for entry in conflicts:
    tag = "lost+found" if entry.get("source") == "lost_and_found" else "vault"
    sys.stderr.write(f"    [{tag}] conflict: {entry['rel']}\n")
    base = entry.get("base")
    if base is not None:
        try:
            base_disp = base.relative_to(Path(vault_root))
        except ValueError:
            base_disp = base.name  # lost_and_found base lives outside the vault
        sys.stderr.write(f"              base:     {base_disp}\n")
if mode == "interactive":
    sys.stderr.write(
        "\n    To merge interactively: review each pair in Obsidian or via\n"
        "    `diff <base> <conflict>` and merge by hand. Run `/work` from the\n"
        "    affected repo if the conflict is in a vault-backed harness file\n"
        "    (PLAN.md, PLAN-<name>.md, progress.md, progress-<name>.md, etc.).\n"
        "    lost+found entries are orphans\n"
        "    DriveFS could not re-home — triage them by hand.\n\n"
        "    To suppress this notice for the current session, set\n"
        "    HARNESS_CONFLICT_MERGER_MODE=silent in the environment.\n\n"
    )
PY

exit 0
