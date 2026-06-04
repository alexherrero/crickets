#!/usr/bin/env pwsh
# harness-context-session-start (PowerShell) — see harness-context-session-start.sh
# for full docs. On SessionStart, injects the repo's .harness/PLAN.md + progress.md
# paths into context when both exist; silent no-op otherwise. Never blocks boot.

$ErrorActionPreference = 'SilentlyContinue'
try {
    $payload = [Console]::In.ReadToEnd()
    $cwd = ''
    if ($payload) {
        try { $cwd = [string]((ConvertFrom-Json $payload).cwd) } catch { }
    }
    if (-not $cwd) { $cwd = (Get-Location).Path }
    if (-not (Test-Path -LiteralPath $cwd -PathType Container)) { exit 0 }

    $plan = Join-Path $cwd '.harness/PLAN.md'
    $progress = Join-Path $cwd '.harness/progress.md'

    if ((Test-Path -LiteralPath $plan -PathType Leaf) -and (Test-Path -LiteralPath $progress -PathType Leaf)) {
        Write-Output "[developer-workflows] This project uses the phase-gated loop. Its state:"
        Write-Output "  PLAN.md:     $plan"
        Write-Output "  progress.md: $progress"
        Write-Output "Read PLAN.md before answering plan-status questions or running /work, /review, /release."
        [Console]::Error.WriteLine("[harness-context] injected .harness/ paths for $cwd")
    } else {
        [Console]::Error.WriteLine("[harness-context] no .harness/PLAN.md + progress.md at $cwd - skipped")
    }
} catch { }

exit 0
