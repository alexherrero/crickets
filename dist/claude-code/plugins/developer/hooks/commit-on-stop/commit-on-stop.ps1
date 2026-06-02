# commit-on-stop — non-disruptive safety snapshot at Stop (Windows / pwsh).
# Mirrors commit-on-stop.sh: snapshots the dirty working tree to the side ref
# refs/auto-save/<ts> via a temp index + commit-tree, WITHOUT switching branches,
# moving HEAD, or touching the working tree or index.
#
# See hook.md in this directory for full documentation.

$ErrorActionPreference = 'Stop'

# Skip if git unavailable.
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { exit 0 }

# Skip if not in a git work tree.
git rev-parse --is-inside-work-tree 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { exit 0 }

# Skip if working tree clean — nothing to save.
$porcelain = git status --porcelain
if (-not $porcelain) { exit 0 }

$ts = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$origBranch = git symbolic-ref --short HEAD 2>$null
if (-not $origBranch) { $origBranch = git rev-parse --short HEAD }
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
    $parent = git rev-parse --verify --quiet HEAD
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

    # Bound growth: keep only the most recent N snapshots (best-effort).
    $keep = 10
    $all = @(git for-each-ref --sort=-refname --format='%(refname)' refs/auto-save)
    if ($all.Count -gt $keep) {
        $all[$keep..($all.Count - 1)] | ForEach-Object {
            if ($_) { git update-ref -d $_ 2>$null | Out-Null }
        }
    }
}
finally {
    if (Test-Path Env:\GIT_INDEX_FILE) { Remove-Item Env:\GIT_INDEX_FILE -ErrorAction SilentlyContinue }
    if (Test-Path $tmpIndex) { Remove-Item $tmpIndex -Force -ErrorAction SilentlyContinue }
}

[Console]::Error.WriteLine("commit-on-stop: snapshot of dirty tree on '$origBranch' -> $ref. Recover: git checkout $ref -- .")
exit 0
