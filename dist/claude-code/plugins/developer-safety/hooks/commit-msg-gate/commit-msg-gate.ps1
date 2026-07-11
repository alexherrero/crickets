# commit-msg-gate — commit-msg hook (Windows / pwsh twin).
# Mirrors commit-msg-gate.sh: rejects a commit whose subject line matches an
# internal codename pattern or this repo's own slop-pack vocabulary at
# warning-tier or above. Thin dispatch shim only -- all matching logic lives
# in the co-located commit_msg_gate.py.
#
# No automated installer wires this in yet -- an operator installs it once,
# via a `core.hooksPath` dir whose `commit-msg` (no extension) invokes:
#   pwsh -NoProfile -File <hooksPathDir>/commit-msg-gate.ps1 $args
# This script needs its co-located commit_msg_gate.py alongside it (this shim
# just dispatches to it) -- copy BOTH commit-msg-gate.ps1 and
# commit_msg_gate.py into the chosen core.hooksPath directory.
#
# Git calls a commit-msg hook with: $args[0] = path to the commit-msg file. A
# non-zero exit aborts the commit.

# NOTE: do NOT set ErrorActionPreference='Stop' -- graceful-skip pattern;
# a missing python must not crash/block the commit.
$ErrorActionPreference = 'Continue'

$msgFile = $args[0]
if (-not $msgFile) {
    exit 0
}

$python = $null
foreach ($cmd in @('python3', 'python')) {
    $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($resolved) { $python = $resolved.Source; break }
}

if (-not $python) {
    Write-Warning "commit-msg-gate: no python3/python found -- skipping codename/slop check (allowing commit)"
    exit 0
}

$here = $PSScriptRoot
& $python (Join-Path $here 'commit_msg_gate.py') $msgFile
exit $LASTEXITCODE
