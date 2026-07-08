# session-cost-capture.ps1 — Windows twin of the bash Stop hook.
#
# Fires on Claude Code's Stop event. Parses the stdin JSON payload for
# session_id + cwd, computes the transcript path at
# ~/.claude/projects/<cwd-slug>/<session_id>.jsonl, and invokes
# session_cost_writer.py to append one `session-cost` telemetry event per
# model to the device-local event log (PLAN-observability-ledger task 1 —
# retargeted off the vault). Capture-half only (PLAN-wave-d-tokens-and-
# privacy task 1, absorbing the 2026-07-05 decision record verbatim).
#
# Graceful no-op contract: missing script/transcript/python3 all exit 0.

$ErrorActionPreference = 'Continue'  # never block session end on hook failure

$payload = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($payload)) { exit 0 }

if (-not (Get-Command python3 -ErrorAction SilentlyContinue)) { exit 0 }

$writerPy = $null
if ($env:CLAUDE_PLUGIN_ROOT) {
    $candidate = Join-Path $env:CLAUDE_PLUGIN_ROOT 'scripts/session_cost_writer.py'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { $writerPy = $candidate }
}
if (-not $writerPy) {
    $hereDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    foreach ($rel in @('../../scripts/session_cost_writer.py', '../../../tokens/scripts/session_cost_writer.py')) {
        $candidate = Join-Path $hereDir $rel
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $writerPy = (Resolve-Path -LiteralPath $candidate).Path; break }
    }
}
if (-not $writerPy) { exit 0 }

$parseDriver = @"
import json, sys
try:
    d = json.loads(sys.stdin.read())
except Exception:
    sys.exit(0)
sid = d.get("session_id") or ""
cwd = d.get("cwd") or ""
if sid:
    print(f"{sid}\t{cwd}")
"@
$parsed = ($payload | & python3 -c $parseDriver 2>$null | Out-String).Trim()
if (-not $parsed) { exit 0 }

$parts = $parsed -split "`t"
$sessionId = $parts[0]
$cwd = if ($parts.Length -gt 1) { $parts[1] } else { '' }
if (-not $cwd) { $cwd = (Get-Location).Path }

$cwdSlug = '-' + ($cwd -replace '[\\/]', '-')
$transcript = Join-Path $HOME ".claude/projects/$cwdSlug/$sessionId.jsonl"
if (-not (Test-Path -LiteralPath $transcript -PathType Leaf)) { exit 0 }

& python3 $writerPy $transcript --session-id $sessionId 2>&1 | ForEach-Object { "[session-cost-capture] $_" } | Out-Host

exit 0
