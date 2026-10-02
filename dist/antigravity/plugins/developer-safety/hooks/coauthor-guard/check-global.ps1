# check-global — SessionStart check for the machine-wide coauthor-guard (pwsh).
# Mirrors check-global.sh: read-only, silent unless an install the operator
# made is broken, always exits 0. See check-global.sh for the three cases.

$ErrorActionPreference = 'Continue'
$PSNativeCommandUseErrorActionPreference = $false

$here = $PSScriptRoot
$configHome = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME '.config' }
$dir = Join-Path (Join-Path $configHome 'crickets') 'git-hooks'
$fix = "pwsh -NoProfile -File `"$(Join-Path $here 'install-global.ps1')`""

# The core.hooksPath git uses outside a repo: system, global, and their includes.
# [NullString]::Value, not $null: pwsh would pass $null on as "", and GIT_DIR="" breaks git.
foreach ($name in 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR') { [Environment]::SetEnvironmentVariable($name, [NullString]::Value) }
$root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($HOME))
$current = "$(git -C $root config --includes --get core.hooksPath 2>$null)".Trim()
$expanded = if ($current.StartsWith('~')) { $HOME + $current.Substring(1) } else { $current }
# A relative core.hooksPath resolves per repo; nothing to say about it from here.
if ($expanded -and -not [System.IO.Path]::IsPathRooted($expanded)) { exit 0 }

if ($current -and -not [System.IO.Directory]::Exists($expanded)) {
    Write-Output "[developer-safety] WARNING: global git core.hooksPath ($current) does not exist, so git runs no hooks in any repo. Re-run: $fix"
} elseif ($current -and [System.IO.File]::Exists((Join-Path $expanded '.crickets-managed'))) {
    # From the filesystem root, so this is the machine-level check, not the session repo's.
    & pwsh -NoProfile -WorkingDirectory $root -File (Join-Path $here 'install-global.ps1') -Check -Dir $expanded *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Output "[developer-safety] WARNING: the global coauthor-guard git hooks at $current are incomplete or out of date. Re-run: $fix"
    }
} elseif (-not $current -and [System.IO.File]::Exists((Join-Path $dir '.crickets-managed'))) {
    Write-Output "[developer-safety] WARNING: coauthor-guard is installed at $dir but the global core.hooksPath is unset, so agent Co-Authored-By trailers are not being stripped. Re-run: $fix"
}
exit 0
