# check-syntax.ps1 — PowerShell AST-parse every .ps1 file in the repo.

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$fail = $false
$count = 0

Get-ChildItem -Path . -Recurse -File -Filter '*.ps1' |
    Where-Object { $_.FullName -notlike '*\.git*' } |
    ForEach-Object {
        $count++
        try {
            $null = [System.Management.Automation.Language.Parser]::ParseFile(
                $_.FullName, [ref]$null, [ref]$null
            )
        } catch {
            Write-Error "  FAIL: $($_.FullName): $($_.Exception.Message)"
            $fail = $true
        }
    }

if (-not $fail) {
    Write-Host "check-syntax: $count file(s) parse cleanly."
    exit 0
}
exit 1
