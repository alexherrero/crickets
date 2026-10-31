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

    # Worktree-slot integrity check (fake-slot guard) — mirrors the .sh twin.
    # `.claude/worktrees/<name>` is supposed to be a real, `git worktree add`-
    # created checkout; a host primitive can leave a bare directory behind a
    # slot path instead, in which case every git command silently walks up to
    # the PARENT repo's `.git` and the session unknowingly shares its
    # HEAD/index/working-tree with every other session on that checkout. The
    # signal is simply whether the slot has its OWN `.git` (a file for a real
    # worktree, a directory for a real main checkout) — `git worktree add`
    # always creates one. This deliberately avoids comparing two
    # independently-resolved absolute paths (`git rev-parse --show-toplevel`
    # vs `Resolve-Path`): those disagreed on Windows 8.3 short names
    # (`RUNNER~1` vs its long form) and produced false positives on a
    # genuinely real worktree — a plain existence check sidesteps all of that.
    if (($cwd -match [regex]::Escape([IO.Path]::DirectorySeparatorChar + '.claude' + [IO.Path]::DirectorySeparatorChar + 'worktrees' + [IO.Path]::DirectorySeparatorChar) -or $cwd -match '/\.claude/worktrees/') -and -not (Test-Path -LiteralPath (Join-Path $cwd '.git'))) {
        $wtToplevel = $null
        $gitCmd = Get-Command git -ErrorAction SilentlyContinue
        if ($gitCmd) {
            $wtToplevel = (git -C $cwd rev-parse --show-toplevel 2>$null)
        }
        Write-Output "[worktree-integrity] WARNING: this session's slot is NOT a real git worktree."
        Write-Output "  slot: $cwd"
        Write-Output "  It has no .git of its own, so every git command here silently walks up to"
        if ($wtToplevel) {
            Write-Output "  the PARENT checkout ($wtToplevel) and operates on its"
        } else {
            Write-Output "  the PARENT checkout and operates on its"
        }
        Write-Output "  shared HEAD, index, and working tree -- commits, branch switches, and"
        Write-Output "  stashes here affect (and can be clobbered by) every other session using"
        Write-Output "  it. Do not treat this session as isolated. Confirm with ``git worktree"
        Write-Output "  list --porcelain`` from the parent repo and stop to ask the operator"
        Write-Output "  before any branch switch or destructive git operation."
        [Console]::Error.WriteLine("[worktree-integrity] FAKE SLOT at $cwd (no .git of its own)")
    }

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

    # Surface launched design paths (Hook 6 — paths only, bounded, <=4). Mirrors
    # the .sh twin: inject governing-design *paths*, never their body.
    $designsDir = Join-Path $cwd 'wiki/designs'
    if (Test-Path -LiteralPath $designsDir -PathType Container) {
        $designs = Get-ChildItem -LiteralPath $designsDir -Filter '*.md' -File -ErrorAction SilentlyContinue |
            Where-Object { (Get-Content -LiteralPath $_.FullName -TotalCount 20 -ErrorAction SilentlyContinue) -match '^status:\s*launched' } |
            Select-Object -First 4
        if ($designs) {
            Write-Output "[developer-workflows] Governing designs (launched) - /plan + /review resolve the governing one:"
            foreach ($d in $designs) { Write-Output ("  design: " + $d.FullName) }
        }
    }

    # Session-start tier + advisor nudge (PLAN-efficiency-dispatch task 7).
    # Native PowerShell port of the .sh twin's Python call — compares the live
    # session model against the active plan's next unchecked task's staged
    # tier hint (task 6) and states advisor availability (task 3). Advisory
    # only — never switches the session's model.
    try {
        $liveModel = $null
        if ($payload) {
            try { $liveModel = [string]((ConvertFrom-Json $payload).model.id) } catch { }
        }

        $planHintModel = $null
        if (Test-Path -LiteralPath $plan -PathType Leaf) {
            $planText = Get-Content -LiteralPath $plan -Raw -ErrorAction SilentlyContinue
            if ($planText) {
                $blocks = [regex]::Split($planText, '(?=(?m)^###\s)')
                foreach ($block in $blocks) {
                    $statusMatch = [regex]::Match($block, '\*\*Status:\*\*\s*\[( |x)\]')
                    if (-not $statusMatch.Success) { continue }
                    if ($statusMatch.Groups[1].Value -ne ' ') { continue }
                    $hintMatch = [regex]::Match($block, "\*\*Tier hint[^:]*:\*\*\s*([^\xB7\r\n]+)\xB7\s*([^\xB7\r\n]+)\xB7")
                    if ($hintMatch.Success) { $planHintModel = $hintMatch.Groups[2].Value.Trim() }
                    break
                }
            }
        }

        $advisorModel = $null
        $projectJson = Join-Path $cwd '.harness/project.json'
        if (Test-Path -LiteralPath $projectJson -PathType Leaf) {
            try {
                $pj = Get-Content -LiteralPath $projectJson -Raw | ConvertFrom-Json
                if ($pj.advisorModel) { $advisorModel = [string]$pj.advisorModel }
            } catch { }
        }

        $nudgeParts = @()
        if ($planHintModel -and $liveModel -and ($planHintModel -ne $liveModel)) {
            $nudgeParts += "NOTE: this session is running '$liveModel', but the active plan's next task is tier-hinted for '$planHintModel'. Advisory only - never auto-switches; use /model if you want to match it."
        }
        if ($advisorModel) {
            $nudgeParts += "Advisor available: $advisorModel (escalate ad hoc - advisory only, never auto-switches)"
        }
        if ($nudgeParts.Count -gt 0) {
            Write-Output ("[developer-workflows] " + ($nudgeParts -join "`n"))
        }
    } catch { }
} catch { }

exit 0
