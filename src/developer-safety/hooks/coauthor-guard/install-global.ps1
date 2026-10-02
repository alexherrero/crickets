# install-global — install coauthor-guard for every repo on this machine (pwsh).
# Mirrors install-global.sh: same hook names, same files, same global config,
# same refusals, same exit codes (0 ok · 1 --check unhealthy · 2 refused/failed).
# See install-global.sh for why some hook names are left out.
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
    'pre-auto-gc', 'sendemail-validate',
    'p4-changelist', 'p4-prepare-changelist', 'p4-post-changelist', 'p4-pre-submit'
)
$Marker = '.crickets-managed'

# Every core.hooksPath the machine's config sets outside a repo: system,
# global, and anything they [include]. The last one is the one git uses.
function Get-MachineHooksPaths {
    $saved = @{}
    foreach ($name in 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR') {
        $saved[$name] = [Environment]::GetEnvironmentVariable($name)
        [Environment]::SetEnvironmentVariable($name, $null)
    }
    try {
        $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($HOME))
        $values = @(git -C $root config --includes --get-all core.hooksPath 2>$null)
        if ($LASTEXITCODE -ne 0) { return @() }
        return @($values | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
    } finally {
        foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name]) }
    }
}

# core.hooksPath values in files an [includeIf] pulls in. Git applies them only
# in repos the condition matches, so Get-MachineHooksPaths never sees them.
function Get-ConditionalHooksPaths {
    $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($HOME))
    $raw = (@(git -C $root config --show-origin -z --get-regexp '^includeif\..*\.path$' 2>$null) -join "`n")
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return @() }
    $fields = $raw.Split([char]0)
    $found = @()
    for ($i = 0; $i + 1 -lt $fields.Count; $i += 2) {
        $origin = $fields[$i].TrimStart("`n")
        if ($origin.StartsWith('file:')) { $origin = $origin.Substring(5) }
        $entry = $fields[$i + 1]
        $value = $entry.Substring($entry.IndexOf("`n") + 1)
        if ($value.StartsWith('~')) { $value = $HOME + $value.Substring(1) }
        $file = if ([System.IO.Path]::IsPathRooted($value)) { $value } else { Join-Path ([System.IO.Path]::GetDirectoryName($origin)) $value }
        if ($IO::Exists($file)) {
            $found += @(git config --file $file --includes --get-all core.hooksPath 2>$null | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
        }
    }
    return $found
}

# The value in the global file itself, the one this script sets and unsets.
function Get-GlobalFileHooksPath {
    $value = git config --global --get core.hooksPath 2>$null
    if ($LASTEXITCODE -ne 0) { return '' }
    return "$value".Trim()
}

# Compare paths with symlinks resolved through the nearest existing parent, as
# install-global.sh does, so a deleted hooks directory under a symlinked
# ~/.config still matches the path the install recorded. Not Resolve-Path: it
# costs seconds per call under pwsh on macOS, and does not resolve symlinks.
function Resolve-Comparable([string]$p) {
    if ($p.StartsWith('~')) { $p = $HOME + $p.Substring(1) }
    $full = [System.IO.Path]::GetFullPath($p).TrimEnd('/', '\')
    if (-not $IsWindows) {
        $existing = $full; $rest = ''
        while ($existing -and -not $DirIO::Exists($existing)) {
            $rest = '/' + [System.IO.Path]::GetFileName($existing) + $rest
            $existing = [System.IO.Path]::GetDirectoryName($existing)
        }
        if ($existing) {
            $real = & /bin/sh -c 'cd -P -- "$1" 2>/dev/null && pwd -P' sh $existing
            if ($LASTEXITCODE -eq 0 -and $real) { $full = "$real".Trim().TrimEnd('/') + $rest }
        }
    }
    return $full.TrimEnd('/', '\').Replace('\', '/')
}
$dirComparable = Resolve-Comparable $Dir
function Test-Ours([string]$p) {
    return [bool]($p -and ((Resolve-Comparable $p) -eq $dirComparable))
}

function Test-SameBytes([string]$a, [string]$b) {
    if (-not ($IO::Exists($a) -and $IO::Exists($b))) { return $false }
    $x = $IO::ReadAllBytes($a); $y = $IO::ReadAllBytes($b)
    if ($x.Length -ne $y.Length) { return $false }
    for ($i = 0; $i -lt $x.Length; $i++) { if ($x[$i] -ne $y[$i]) { return $false } }
    return $true
}

$allPaths = @(Get-MachineHooksPaths)
$current = if ($allPaths.Count) { $allPaths[-1] } else { '' }
$foreign = @(@($allPaths) + @(Get-ConditionalHooksPaths) | Where-Object { -not (Test-Ours $_) }) | Select-Object -Last 1

function Test-Executable([string]$p) {
    if (-not $IO::Exists($p)) { return $false }
    if ($IsWindows) { return $true }
    return [bool]($IO::GetUnixFileMode($p) -band [System.IO.UnixFileMode]::UserExecute)
}

if ($Check) {
    $problem = ''
    if (-not $current) { $problem = 'no core.hooksPath is set' }
    elseif (-not (Test-Ours $current)) { $problem = "git uses core.hooksPath $current, not $Dir" }
    elseif (-not $IO::Exists((Join-Path $Dir $Marker))) { $problem = "$Dir is missing or not crickets-managed" }
    elseif (-not (Test-Executable (Join-Path $Dir 'coauthor-guard.sh'))) {
        $problem = "$Dir/coauthor-guard.sh is missing or not executable"
    }
    elseif (-not $IO::Exists((Join-Path $Dir 'git-hook-dispatch.sh'))) {
        $problem = "$Dir/git-hook-dispatch.sh (the reference copy) is missing"
    }
    else {
        # Each hook must be an intact copy of the dispatcher installed with it,
        # not of whichever (possibly older) copy of this script is running.
        $reference = Join-Path $Dir 'git-hook-dispatch.sh'
        foreach ($name in $HookNames) {
            $hook = Join-Path $Dir $name
            if (-not (Test-Executable $hook) -or -not (Test-SameBytes $reference $hook)) {
                $problem = "$Dir/$name is missing, not executable, or no longer the dispatcher"; break
            }
        }
    }
    if ($problem) {
        [Console]::Error.WriteLine("coauthor-guard: global git hooks NOT healthy — $problem")
        exit 1
    }
    Write-Output "coauthor-guard: global git hooks installed at $Dir"
    # Inside a repo, the core.hooksPath git uses there can still be another one:
    # the repo's own local config, or a conditional include that matches it.
    git rev-parse --git-dir *> $null
    if ($LASTEXITCODE -eq 0) {
        $herePath = "$(git config --get core.hooksPath 2>$null)".Trim()
        if ($herePath -and -not (Test-Ours $herePath)) {
            [Console]::Error.WriteLine("coauthor-guard: but this repo uses core.hooksPath $herePath (its own config or a conditional include), so the guard does not run here")
            exit 1
        }
    }
    exit 0
}

if ($Uninstall) {
    $globalValue = Get-GlobalFileHooksPath
    if (Test-Ours $globalValue) {
        git config --global --unset core.hooksPath
        Write-Output "coauthor-guard: unset global core.hooksPath ($globalValue)"
    } elseif ($globalValue) {
        Write-Output "coauthor-guard: global core.hooksPath is $globalValue, not $Dir — left as is"
    }
    # Delete the directory only once no config still names it: a core.hooksPath
    # pointing at a deleted directory silences every repo's hooks.
    $stillNamed = @(Get-MachineHooksPaths | Where-Object { Test-Ours $_ }) | Select-Object -Last 1
    if ($stillNamed) {
        [Console]::Error.WriteLine("coauthor-guard: $Dir is still named by core.hooksPath ($stillNamed) — not removed")
        exit 2
    }
    if ($IO::Exists((Join-Path $Dir $Marker))) {
        $DirIO::Delete($Dir, $true)
        Write-Output "coauthor-guard: removed $Dir"
    }
    exit 0
}

# install
if ($foreign) {
    [Console]::Error.WriteLine("install-global: core.hooksPath is already set to $foreign — not replacing it.")
    [Console]::Error.WriteLine("  (git config --show-origin --get-all core.hooksPath shows where.) Remove it")
    [Console]::Error.WriteLine("  first, or pass -Dir $foreign only if that directory is meant to become crickets-managed.")
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
    # Hooks an earlier version installed and this one leaves out.
    foreach ($name in 'reference-transaction', 'post-index-change') {
        $old = Join-Path $Dir $name
        if ($IO::Exists($old)) { $IO::Delete($old) }
    }
    $guard = Join-Path $Dir 'coauthor-guard.sh'
    $IO::Copy((Join-Path $here 'coauthor-guard.sh'), $guard, $true)
    # The reference -Check compares every hook against.
    $IO::Copy($dispatch, (Join-Path $Dir 'git-hook-dispatch.sh'), $true)
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
