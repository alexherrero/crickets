# memory-recall-session-start — load MemoryVault always-load entries on session boot (Windows / pwsh).
# Mirrors memory-recall-session-start.sh.
#
# See hook.md in this directory for full documentation.

# NOTE: no `$ErrorActionPreference = 'Stop'` — graceful-skip pattern; hook must
# never block session boot. Errors are caught + swallowed inline.

$RecallPy = ".claude/skills/memory/scripts/recall.py"
if (-not (Test-Path $RecallPy)) {
    # Memory skill not installed; nothing to do. Exit 0 (graceful-skip).
    exit 0
}

# Require python3 — exit 0 if missing.
if (-not (Get-Command python3 -ErrorAction SilentlyContinue) -and
    -not (Get-Command python -ErrorAction SilentlyContinue)) {
    exit 0
}

# Prefer python3 if available, else fall back to python (Windows default).
$Py = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }

# recall.py handles MEMORY_VAULT_PATH resolution, glob, parse, filter, output,
# and the 500ms time budget internally.
& $Py $RecallPy session-start
exit $LASTEXITCODE
