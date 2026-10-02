# install-global — install coauthor-guard for every repo on this machine (pwsh).
# Mirrors install-global.sh: same hook names, same files, same global config,
# same exit codes (0 ok · 1 --check unhealthy · 2 refused/failed).
#
#   pwsh -NoProfile -File install-global.ps1               install or refresh
#   pwsh -NoProfile -File install-global.ps1 -Check        read-only health check
#   pwsh -NoProfile -File install-global.ps1 -Uninstall    unset + remove
#   -Dir <path>   default: $env:XDG_CONFIG_HOME or ~/.config, then crickets/git-hooks
#
# The hooks it writes are the POSIX-sh dispatcher; Git for Windows runs them
# through its bundled sh, so one set of files serves every OS.

param(
    [switch]$Check,
    [switch]$Uninstall,
    [string]$Dir
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
# File work goes through System.IO, not the FileSystem provider cmdlets: on a
# Mac with cloud-storage mounts, New-Item / Get-ChildItem / Remove-Item each
# cost seconds to tens of seconds.
$IO = [System.IO.File]
$DirIO = [System.IO.Directory]

$here = $PSScriptRoot
if (-not $Dir) {
    $configHome = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $HOME '.config' }
    $Dir = Join-Path (Join-Path $configHome 'crickets') 'git-hooks'
}

# Keep in sync with install-global.sh's HOOK_NAMES (a test pins the two lists).
$HookNames = @(
    'applypatch-msg', 'pre-applypatch', 'post-applypatch',
    'pre-commit', 'pre-merge-commit', 'prepare-commit-msg', 'commit-msg', 'post-commit',
    'pre-rebase', 'post-checkout', 'post-merge', 'pre-push', 'post-rewrite',
    'pre-receive', 'update', 'proc-receive', 'post-receive', 'post-update',
    'reference-transaction', 'pre-auto-gc', 'sendemail-validate', 'post-index-change',
    'p4-changelist', 'p4-prepare-changelist', 'p4-post-changelist', 'p4-pre-submit'
)
$Marker = '.crickets-managed'

function Get-GlobalHooksPath {
    $value = git config --global --get core.hooksPath 2>$null
    if ($LASTEXITCODE -ne 0) { return '' }
    return "$value".Trim()
}

# Lexical comparison (GetFullPath, not Resolve-Path: the latter costs seconds
# per call under pwsh on macOS). install-global.sh compares symlink-resolved paths.
function Resolve-Comparable([string]$p) {
    if ($p.StartsWith('~')) { $p = $HOME + $p.Substring(1) }
    return [System.IO.Path]::GetFullPath($p).TrimEnd('/', '\').Replace('\', '/')
}

$current = Get-GlobalHooksPath
$pointsHere = $current -and ((Resolve-Comparable $current) -eq (Resolve-Comparable $Dir))

if ($Check) {
    $problem = ''
    if (-not $current) { $problem = 'global core.hooksPath is not set' }
    elseif (-not $pointsHere) { $problem = "global core.hooksPath is $current, not $Dir" }
    elseif (-not $IO::Exists((Join-Path $Dir $Marker))) { $problem = "$Dir is missing or not crickets-managed" }
    elseif (-not $IO::Exists((Join-Path $Dir 'coauthor-guard.sh'))) { $problem = "$Dir/coauthor-guard.sh is missing" }
    else {
        foreach ($name in $HookNames) {
            if (-not $IO::Exists((Join-Path $Dir $name))) { $problem = "$Dir/$name is missing"; break }
        }
    }
    if ($problem) {
        [Console]::Error.WriteLine("coauthor-guard: global git hooks NOT healthy — $problem")
        exit 1
    }
    Write-Output "coauthor-guard: global git hooks installed at $Dir"
    $localPath = git config --local --get core.hooksPath 2>$null
    if ($LASTEXITCODE -eq 0 -and $localPath) {
        Write-Output "coauthor-guard: note — this repo sets its own core.hooksPath ($localPath), which overrides the global one here"
    }
    exit 0
}

if ($Uninstall) {
    if ($pointsHere) {
        git config --global --unset core.hooksPath
        Write-Output "coauthor-guard: unset global core.hooksPath ($current)"
    } elseif ($current) {
        Write-Output "coauthor-guard: global core.hooksPath is $current, not $Dir — left as is"
    }
    if ($IO::Exists((Join-Path $Dir $Marker))) {
        $DirIO::Delete($Dir, $true)
        Write-Output "coauthor-guard: removed $Dir"
    }
    exit 0
}

# install
if ($current -and -not $pointsHere) {
    [Console]::Error.WriteLine("install-global: global core.hooksPath is already $current — not replacing it.")
    [Console]::Error.WriteLine("  Unset it (git config --global --unset core.hooksPath) or pass -Dir $current")
    [Console]::Error.WriteLine("  only if that directory is meant to become crickets-managed.")
    exit 2
}
if ($DirIO::Exists($Dir) -and -not $IO::Exists((Join-Path $Dir $Marker)) -and
        @($DirIO::EnumerateFileSystemEntries($Dir)).Count -gt 0) {
    [Console]::Error.WriteLine("install-global: $Dir already holds files crickets didn't put there — not touching it.")
    exit 2
}
foreach ($src in @('git-hook-dispatch.sh', 'coauthor-guard.sh')) {
    if (-not $IO::Exists((Join-Path $here $src))) {
        [Console]::Error.WriteLine("install-global: $(Join-Path $here $src) not found next to this script")
        exit 2
    }
}

try {
    $DirIO::CreateDirectory($Dir) | Out-Null
    $dispatch = Join-Path $here 'git-hook-dispatch.sh'
    $written = foreach ($name in $HookNames) {
        $dest = Join-Path $Dir $name
        $IO::Copy($dispatch, $dest, $true)
        $dest
    }
    $guard = Join-Path $Dir 'coauthor-guard.sh'
    $IO::Copy((Join-Path $here 'coauthor-guard.sh'), $guard, $true)
    # Git for Windows ignores the mode bits; everywhere else the hooks must be executable.
    if (-not $IsWindows) {
        chmod +x @($written) $guard
        if ($LASTEXITCODE -ne 0) { throw "chmod failed on $Dir" }
    }
    $IO::WriteAllLines((Join-Path $Dir $Marker), [string[]]@(
        'Managed by crickets developer-safety (coauthor-guard/install-global).',
        "Installed from $here"
    ))
} catch {
    [Console]::Error.WriteLine("install-global: $($_.Exception.Message)")
    exit 2
}

$absDir = Resolve-Comparable $Dir
git config --global core.hooksPath $absDir
if ($LASTEXITCODE -ne 0) { exit 2 }
Write-Output "coauthor-guard: installed $($HookNames.Count) hooks in $absDir and set global core.hooksPath"
exit 0
