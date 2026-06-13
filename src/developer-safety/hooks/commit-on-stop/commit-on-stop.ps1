# commit-on-stop — non-disruptive safety snapshot at Stop (Windows / pwsh).
# Mirrors commit-on-stop.sh (incl. host-portable workspace resolution): snapshots
# the dirty working tree to the side ref refs/auto-save/<ts> via a temp index +
# commit-tree, WITHOUT switching branches, moving HEAD, or touching the working
# tree or index.
#
# See hook.md in this directory for full documentation.

$ErrorActionPreference = 'Stop'

# ── resolve the workspace root (host-portable) ──────────────────────────────
# Claude Code runs hooks from the project root + passes JSON on stdin with
# "cwd" (and sets $env:CLAUDE_PROJECT_DIR). Antigravity runs plugin hooks from
# the PLUGIN dir + passes the workspace on stdin as {"workspacePaths":["<root>"]}.
# Resolve an explicit workspace signal (TOP-LEVEL keys only — robust against
# nested/decoy "cwd" tokens and pretty-printed payloads), then Set-Location into
# it so the git snapshot below operates on the workspace repo; fall back to cwd.
function Resolve-Workspace {
    $ws = ''
    if ([Console]::IsInputRedirected) {
        try { $payload = [Console]::In.ReadToEnd() } catch { $payload = '' }
        if ($payload) {
            try { $obj = $payload | ConvertFrom-Json -ErrorAction Stop } catch { $obj = $null }
            if (($null -ne $obj) -and ($obj -isnot [array]) -and ($obj -isnot [string]) -and ($obj -isnot [valuetype])) {
                $wp = $obj.workspacePaths
                if (($wp -is [array]) -and ($wp.Count -gt 0) -and ($wp[0] -is [string]) -and $wp[0]) {
                    $ws = $wp[0]
                } elseif (($obj.cwd -is [string]) -and $obj.cwd) {
                    $ws = $obj.cwd
                }
            }
        }
    }
    if (-not $ws) { $ws = $env:CLAUDE_PROJECT_DIR }
    if (-not $ws) { $ws = '.' }
    return $ws
}
$ws = Resolve-Workspace
try { Set-Location -LiteralPath $ws } catch { }

# Skip if git unavailable.
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { exit 0 }

# Skip if not in a git work tree. (try/catch: on pwsh 7.4+ —
# where $PSNativeCommandUseErrorActionPreference defaults $true — a non-zero
# `git` exit throws under $ErrorActionPreference='Stop'. This hook inspects
# $LASTEXITCODE instead, mirroring the .sh twin's `||`/`if` guards, so the
# NON-FATAL probes opt out of the throw. $LASTEXITCODE is still set before the
# throw, so the guard stays correct either way. The snapshot-CREATING calls
# below keep throwing, so a genuine write failure still aborts — matching the
# .sh twin's `set -e`.)
try { git rev-parse --is-inside-work-tree 2>$null | Out-Null } catch { }
if ($LASTEXITCODE -ne 0) { exit 0 }

# Skip if working tree clean — nothing to save.
$porcelain = git status --porcelain
if (-not $porcelain) { exit 0 }

$ts = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
# Non-fatal probe (see the try/catch note above): a detached HEAD makes
# symbolic-ref exit non-zero (→ throw on pwsh 7.4+); fall back to the short SHA.
try { $origBranch = git symbolic-ref --short HEAD 2>$null } catch { $origBranch = '' }
if (-not $origBranch) {
    try { $origBranch = git rev-parse --short HEAD } catch { $origBranch = '' }
}
$ref = "refs/auto-save/$ts"
$msg = "auto-save: stop at $ts on branch $origBranch"

# Commit identity (scoped via env — never touches git config; commit-tree, unlike
# commit, never signs, so no gpg prompt can hang the hook).
$env:GIT_AUTHOR_NAME = 'commit-on-stop hook'
$env:GIT_AUTHOR_EMAIL = 'commit-on-stop@crickets.local'
$env:GIT_COMMITTER_NAME = 'commit-on-stop hook'
$env:GIT_COMMITTER_EMAIL = 'commit-on-stop@crickets.local'

# Build the snapshot in a TEMPORARY index so the real index + working tree are
# never touched. Seed from HEAD when it exists (else an empty tree), then stage
# every change — tracked + untracked. .gitignore is honored.
$tmpIndex = [System.IO.Path]::GetTempFileName()
try {
    # Non-fatal probe (see the try/catch note above): an unborn branch makes
    # rev-parse --verify exit 1 (→ throw on pwsh 7.4+); fall back to empty tree.
    try { $parent = git rev-parse --verify --quiet HEAD } catch { $parent = '' }
    $hasParent = ($LASTEXITCODE -eq 0) -and $parent
    $env:GIT_INDEX_FILE = $tmpIndex
    if ($hasParent) {
        git read-tree $parent | Out-Null
        git add -A | Out-Null
        $tree = (git write-tree).Trim()
        $commit = (git commit-tree $tree -p $parent -m $msg).Trim()
    } else {
        git read-tree --empty | Out-Null
        git add -A | Out-Null
        $tree = (git write-tree).Trim()
        $commit = (git commit-tree $tree -m $msg).Trim()
    }
    Remove-Item Env:\GIT_INDEX_FILE -ErrorAction SilentlyContinue

    # Atomically publish the snapshot ref. HEAD, the current branch, the real
    # index, and the working tree are all unchanged.
    git update-ref $ref $commit | Out-Null

    # Bound growth: keep only the most recent N snapshots. Best-effort — a prune
    # failure (e.g. a concurrent delete in the multi-agent case) must never abort
    # the hook; the snapshot is already published above. Mirrors the .sh twin's
    # `|| true`, and stays non-throwing under pwsh 7.4+ (see the note above).
    $keep = 10
    try { $all = @(git for-each-ref --sort=-refname --format='%(refname)' refs/auto-save) } catch { $all = @() }
    if ($all.Count -gt $keep) {
        $all[$keep..($all.Count - 1)] | ForEach-Object {
            if ($_) { try { git update-ref -d $_ 2>$null | Out-Null } catch { } }
        }
    }
}
finally {
    if (Test-Path Env:\GIT_INDEX_FILE) { Remove-Item Env:\GIT_INDEX_FILE -ErrorAction SilentlyContinue }
    if (Test-Path $tmpIndex) { Remove-Item $tmpIndex -Force -ErrorAction SilentlyContinue }
}

[Console]::Error.WriteLine("commit-on-stop: snapshot of dirty tree on '$origBranch' -> $ref. Recover: git checkout $ref -- .")
exit 0
