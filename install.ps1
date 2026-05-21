# install.ps1 — agent-toolkit installer.
#
# Installs personal agent customizations (skills, sub-agents, hooks, MCP
# servers, slash commands, etc.) into a target project under host-specific
# paths (.claude/, .agent/). Also installs a pre-push git hook that runs
# check-no-pii.sh against every push.
#
# Usage:
#   pwsh -NoProfile -File install.ps1 [OPTIONS] <target-project-path>
#
# Options:
#   -Bundle <name>           install one bundle (instead of all)
#   -Skill <name>            install one standalone skill (instead of all)
#   -Agent <name>            install one standalone agent (instead of all)
#   -Hook <name>             install one standalone hook (instead of all)
#   -All                     install everything (default)
#   -Update                  true-sync; wipe and recreate managed dirs
#   -NoPrePushHook           skip pre-push hook installation
#   -NoLegacyCleanup         suppress the legacy .agents/skills/ + .gemini/agents/
#                            cleanup prompt (v0.9.0+ removed gemini-cli host;
#                            the installer detects pre-existing legacy
#                            destinations from a prior install and offers
#                            backup+remove with operator confirmation. This
#                            switch skips the prompt entirely — useful for CI
#                            / scripted installs.)
#   -NoPythonDeps            skip the pip-install step for the toolkit's
#                            Python deps (pyyaml, sqlite-vec, sentence-
#                            transformers). Use if you manage Python deps
#                            via virtualenv / conda / system packages, or
#                            in CI to avoid the ~1.3GB sentence-transformers
#                            download per workflow run.
#   -NoSkillIndex            skip the personal-skills auto-indexer step
#                            (plan #7b task 1). Best-effort post-install
#                            run that walks SKILL.md across the toolkit +
#                            harness sibling and writes pointer entries to
#                            MemoryVault/personal-skills/. Requires
#                            MEMORY_VAULT_PATH; silently skipped if unset.
#   -Help                    print this help and exit

[CmdletBinding()]
param(
    [string]$Bundle,
    [string]$Skill,
    [string]$Agent,
    [string]$Hook,
    [switch]$All,
    [switch]$Update,
    [switch]$NoPrePushHook,
    [switch]$NoLegacyCleanup,
    [switch]$NoPythonDeps,
    [switch]$NoSkillIndex,
    [switch]$Help,
    [Parameter(Position=0)]
    [string]$Target
)

$ErrorActionPreference = 'Stop'

if ($Help) {
    Get-Content $PSCommandPath | Where-Object { $_ -match '^#' -or $_ -eq '' } | ForEach-Object { $_ -replace '^# ?', '' }
    exit 0
}

# ── argument validation ───────────────────────────────────────────────────
if (-not $Target) {
    Write-Error "<target-project-path> is required. Run with -Help for usage."
    exit 2
}
if (-not (Test-Path -LiteralPath $Target -PathType Container)) {
    Write-Error "target directory does not exist: $Target"
    exit 1
}
$Target = (Resolve-Path -LiteralPath $Target).ProviderPath

# Selection mode: default to All unless -Bundle, -Skill, -Agent, or -Hook given
$ModeAll = $true
if ($Bundle -or $Skill -or $Agent -or $Hook) { $ModeAll = $false }
if ($All) { $ModeAll = $true; $Bundle = ''; $Skill = ''; $Agent = ''; $Hook = '' }

# ── locate toolkit root ───────────────────────────────────────────────────
$ToolkitRoot = Split-Path -Parent $PSCommandPath
$ToolkitRoot = (Resolve-Path -LiteralPath $ToolkitRoot).ProviderPath

# ── source shared install plumbing ────────────────────────────────────────
$BoundaryRoots = @(
    (Join-Path $ToolkitRoot 'skills'),
    (Join-Path $ToolkitRoot 'commands'),
    (Join-Path $ToolkitRoot 'agents'),
    (Join-Path $ToolkitRoot 'hooks'),
    (Join-Path $ToolkitRoot 'mcp-servers'),
    (Join-Path $ToolkitRoot 'bundles'),
    (Join-Path $ToolkitRoot 'status-line'),
    (Join-Path $ToolkitRoot 'output-styles'),
    (Join-Path $ToolkitRoot 'workflows'),
    (Join-Path $ToolkitRoot 'rules'),
    (Join-Path $ToolkitRoot 'snippets'),
    (Join-Path $ToolkitRoot 'settings-fragments'),
    (Join-Path $ToolkitRoot 'templates')
)

. (Join-Path $ToolkitRoot 'lib/install/pwsh/primitives.ps1')

# ── operate from inside target dir ────────────────────────────────────────
Set-Location $Target
Write-Host "==> agent-toolkit install: $Target"

# ── -Update sync ──────────────────────────────────────────────────────────
# See install.sh note on .claude/agents + .gemini/agents + .claude/hooks —
# these parents are also written to by the sibling agentic-harness installer;
# the LATER-run installer's -Update wipes the parent before recreating from
# its own source. .claude/settings.json is NOT wiped — it's user-state-merged
# and the toolkit re-merges its hook fragments idempotently via
# scripts/merge-settings-fragment.py.
$ManagedParents = @(
    '.claude/skills',
    '.agent/skills',
    '.claude/agents',
    '.claude/hooks'
)
$EmptyParentCandidates = @()

# ── legacy gemini-cli cleanup (v0.9.0+) ───────────────────────────────────
# v0.9.0 removed standalone Gemini CLI host support. Prior installs may have
# populated either:
#   - .agents/skills/<name>/ (skills installed with gemini-cli host)
#   - .gemini/agents/<name>.md (agents installed with gemini-cli host)
# Detect pre-existing entries that match currently-managed customization
# names; offer a backup-then-remove flow with operator confirmation. Defaults
# to N (no-op unless operator opts in). -NoLegacyCleanup suppresses the
# prompt entirely (useful for CI / scripted installs). Non-interactive
# sessions also skip the prompt with a one-line notice. Never hard-deletes —
# moves to timestamped backups at <path>.agent-toolkit-bak.<ts>/ per the
# pre-push-hook backup convention. Only touches entries the installer
# recognizes as toolkit-managed (matches manifest names); leaves any
# unmanaged user files alone.
function Invoke-LegacyCleanupGeminiCli {
    if ($NoLegacyCleanup) { return }
    $hasLegacySkills = Test-Path -LiteralPath '.agents/skills' -PathType Container
    $hasLegacyAgents = Test-Path -LiteralPath '.gemini/agents' -PathType Container
    if (-not $hasLegacySkills -and -not $hasLegacyAgents) { return }

    # Enumerate toolkit-managed names from manifests.
    $knownSkillNames = @()
    $knownAgentNames = @()
    Get-ChildItem -LiteralPath (Join-Path $ToolkitRoot 'skills') -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') } |
        ForEach-Object { $knownSkillNames += $_.Name }
    Get-ChildItem -LiteralPath (Join-Path $ToolkitRoot 'bundles') -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            $bs = Join-Path $_.FullName 'skills'
            if (Test-Path -LiteralPath $bs -PathType Container) {
                Get-ChildItem -LiteralPath $bs -Directory | ForEach-Object { $knownSkillNames += $_.Name }
            }
            $ba = Join-Path $_.FullName 'agents'
            if (Test-Path -LiteralPath $ba -PathType Container) {
                Get-ChildItem -LiteralPath $ba -Filter '*.md' -File | ForEach-Object { $knownAgentNames += $_.BaseName }
            }
        }
    $agentsRoot = Join-Path $ToolkitRoot 'agents'
    if (Test-Path -LiteralPath $agentsRoot -PathType Container) {
        Get-ChildItem -LiteralPath $agentsRoot -Filter '*.md' -File -ErrorAction SilentlyContinue |
            ForEach-Object { $knownAgentNames += $_.BaseName }
    }

    # Match .agents/skills/ against known skill names.
    $matchedSkills = @()
    if ($hasLegacySkills) {
        Get-ChildItem -LiteralPath '.agents/skills' -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                if ($knownSkillNames -contains $_.Name) { $matchedSkills += $_.FullName }
            }
    }
    # Match .gemini/agents/*.md against known agent names.
    $matchedAgents = @()
    if ($hasLegacyAgents) {
        Get-ChildItem -LiteralPath '.gemini/agents' -Filter '*.md' -File -ErrorAction SilentlyContinue |
            ForEach-Object {
                if ($knownAgentNames -contains $_.BaseName) { $matchedAgents += $_.FullName }
            }
    }
    if ($matchedSkills.Count -eq 0 -and $matchedAgents.Count -eq 0) { return }

    Write-Host ''
    Write-Host '==> legacy gemini-cli cleanup'
    Write-Host 'agent-toolkit v0.9.0+ removed standalone Gemini CLI host support.'
    Write-Host 'Found legacy toolkit-managed entries from a prior install:'
    foreach ($m in $matchedSkills) { Write-Host "  - $m/  (legacy skill destination)" }
    foreach ($m in $matchedAgents) { Write-Host "  - $m  (legacy agent destination)" }
    Write-Host ''

    $response = ''
    if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
        $response = Read-Host 'Move to timestamped backup(s) and remove from active install paths? [y/N]'
    } else {
        Write-Host 'Move to timestamped backup(s) and remove from active install paths? [y/N]: '
        Write-Host '    (non-interactive session — defaulting to N; pass -NoLegacyCleanup to suppress this notice)'
    }

    if ($response -match '^[Yy]$') {
        $ts = Get-Date -Format 'yyyyMMddHHmmss'
        if ($matchedSkills.Count -gt 0) {
            $bak = ".agents/skills.agent-toolkit-bak.$ts"
            Move-Item -LiteralPath '.agents/skills' -Destination $bak
            Write-Host "    moved .agents/skills/ -> $bak/"
            if ((Test-Path -LiteralPath '.agents') -and -not (Get-ChildItem -LiteralPath '.agents' -Force -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath '.agents' -Force
                Write-Host '    removed empty .agents/ directory'
            }
        }
        if ($matchedAgents.Count -gt 0) {
            $bak = ".gemini/agents.agent-toolkit-bak.$ts"
            Move-Item -LiteralPath '.gemini/agents' -Destination $bak
            Write-Host "    moved .gemini/agents/ -> $bak/"
            if ((Test-Path -LiteralPath '.gemini') -and -not (Get-ChildItem -LiteralPath '.gemini' -Force -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath '.gemini' -Force
                Write-Host '    removed empty .gemini/ directory'
            }
        }
    } else {
        Write-Host '    cleanup skipped — to remove manually later:'
        if ($hasLegacySkills) { Write-Host '        Remove-Item -Recurse .agents/skills/' }
        if ($hasLegacyAgents) { Write-Host '        Remove-Item -Recurse .gemini/agents/' }
        Write-Host '    (or re-run with -NoLegacyCleanup to suppress this prompt)'
    }
    Write-Host ''
}

Invoke-LegacyCleanupGeminiCli

if ($Update) {
    Write-Host '==> sync mode: wiping toolkit-managed dirs before recreate from source'
    Sync-ManagedParents $ManagedParents $EmptyParentCandidates
}

# ── helpers ───────────────────────────────────────────────────────────────
function Get-Field([string]$file, [string]$field) {
    $result = python3 (Join-Path $ToolkitRoot 'scripts/manifest-info.py') $file $field 2>$null
    return ($result -join '').Trim()
}

function Install-Skill([string]$srcDir, [string]$name, [string]$hosts) {
    # Note: NOT named $host — that's a read-only PowerShell built-in (the host
    # environment). Use $hostName instead for the loop variable.
    foreach ($hostName in ($hosts -split ',')) {
        $hostName = $hostName.Trim()
        if (-not $hostName) { continue }
        switch ($hostName) {
            'claude-code' {
                New-Item -ItemType Directory -Path '.claude/skills' -Force | Out-Null
                Copy-ManagedDir $srcDir (Join-Path '.claude/skills' $name)
            }
            'antigravity' {
                New-Item -ItemType Directory -Path '.agent/skills' -Force | Out-Null
                Copy-ManagedDir $srcDir (Join-Path '.agent/skills' $name)
            }
            default {
                Write-Warning "unknown host '$hostName' for skill '$name' - skipped"
            }
        }
    }
}

function Install-Hook([string]$hookDir, [string]$name, [string]$hosts) {
    # v0.7.0: claude-code only. Antigravity has no first-class hook surface.
    foreach ($hostName in ($hosts -split ',')) {
        $hostName = $hostName.Trim()
        if (-not $hostName) { continue }
        switch ($hostName) {
            'claude-code' {
                $scriptSrc = Join-Path $hookDir "$name.ps1"
                $fragmentSrc = Join-Path $hookDir 'settings-fragment-pwsh.json'
                if (-not (Test-Path -LiteralPath $scriptSrc)) {
                    Write-Warning "hook '$name' missing $name.ps1 - skipped"
                    continue
                }
                if (-not (Test-Path -LiteralPath $fragmentSrc)) {
                    Write-Warning "hook '$name' missing settings-fragment-pwsh.json - skipped"
                    continue
                }
                New-Item -ItemType Directory -Path '.claude/hooks' -Force | Out-Null
                Copy-ManagedFile $scriptSrc (Join-Path '.claude/hooks' "$name.ps1")
                New-Item -ItemType Directory -Path '.claude' -Force | Out-Null
                python3 (Join-Path $ToolkitRoot 'scripts/merge-settings-fragment.py') `
                    '.claude/settings.json' $fragmentSrc
            }
            'antigravity' {
                Write-Warning "host 'antigravity' has no first-class hook surface (v0.7.0); skipped for hook '$name'"
            }
            default {
                Write-Warning "unknown host '$hostName' for hook '$name' - skipped"
            }
        }
    }
}

function Install-Agent([string]$srcFile, [string]$name, [string]$hosts) {
    # Agents are file-level for claude-code (.claude/agents/<name>.md).
    # Antigravity has no first-class sub-agent surface — agents get wrapped
    # as skills at .agent/skills/<name>/SKILL.md per the locked per-host paths.
    # $hostName not $host — see note above.
    foreach ($hostName in ($hosts -split ',')) {
        $hostName = $hostName.Trim()
        if (-not $hostName) { continue }
        switch ($hostName) {
            'claude-code' {
                New-Item -ItemType Directory -Path '.claude/agents' -Force | Out-Null
                Copy-ManagedFile $srcFile (Join-Path '.claude/agents' "$name.md")
            }
            'antigravity' {
                $wrap = Join-Path '.agent/skills' $name
                New-Item -ItemType Directory -Path $wrap -Force | Out-Null
                Copy-ManagedFile $srcFile (Join-Path $wrap 'SKILL.md')
            }
            default {
                Write-Warning "unknown host '$hostName' for agent '$name' - skipped"
            }
        }
    }
}

function Install-PrePushHook {
    if ($NoPrePushHook) {
        Write-Host '  skipping pre-push hook (-NoPrePushHook)'
        return
    }
    if (-not (Test-Path -LiteralPath '.git' -PathType Container)) {
        Write-Warning 'skipping pre-push hook (target is not a git repo)'
        return
    }
    $hookSrc = Join-Path $ToolkitRoot 'templates/hooks/pre-push'
    $hookDst = '.git/hooks/pre-push'
    if (-not (Test-Path -LiteralPath $hookSrc)) {
        Write-Warning "hook template not found at $hookSrc - pre-push hook not installed"
        return
    }
    if (Test-Path -LiteralPath $hookDst) {
        $a = Get-FileHash -LiteralPath $hookSrc -Algorithm SHA256
        $b = Get-FileHash -LiteralPath $hookDst -Algorithm SHA256
        if ($a.Hash -eq $b.Hash) {
            Write-Host "    kept    $hookDst (already managed by agent-toolkit)"
            return
        }
        $bak = "$hookDst.agent-toolkit-bak.$([int][double]::Parse((Get-Date -UFormat %s)))"
        Copy-Item -LiteralPath $hookDst -Destination $bak
        Write-Host "    backed up existing $hookDst -> $bak"
    }
    Copy-Item -LiteralPath $hookSrc -Destination $hookDst
    Write-Host "    installed $hookDst"
}

function Install-Bundles {
    Get-ChildItem -LiteralPath (Join-Path $ToolkitRoot 'bundles') -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            $bundleDir = $_.FullName
            $bundleName = $_.Name
            $bundleMd = Join-Path $bundleDir 'bundle.md'
            if (-not (Test-Path -LiteralPath $bundleMd)) { return }
            if (-not $ModeAll -and $Bundle -and $Bundle -ne $bundleName) { return }
            Write-Host "==> installing bundle: $bundleName"
            $hosts = Get-Field $bundleMd 'supported_hosts'
            if (-not $hosts) {
                Write-Warning "bundle '$bundleName' has no supported_hosts - skipped"
                return
            }
            $skillsDir = Join-Path $bundleDir 'skills'
            if (Test-Path -LiteralPath $skillsDir -PathType Container) {
                Get-ChildItem -LiteralPath $skillsDir -Directory | ForEach-Object {
                    Install-Skill $_.FullName $_.Name $hosts
                }
            }
            $agentsDir = Join-Path $bundleDir 'agents'
            if (Test-Path -LiteralPath $agentsDir -PathType Container) {
                Get-ChildItem -LiteralPath $agentsDir -Filter '*.md' -File | ForEach-Object {
                    Install-Agent $_.FullName $_.BaseName $hosts
                }
            }
            $hooksDir = Join-Path $bundleDir 'hooks'
            if (Test-Path -LiteralPath $hooksDir -PathType Container) {
                Get-ChildItem -LiteralPath $hooksDir -Directory | ForEach-Object {
                    $innerHookMd = Join-Path $_.FullName 'hook.md'
                    if (Test-Path -LiteralPath $innerHookMd) {
                        Install-Hook $_.FullName $_.Name $hosts
                    }
                }
            }
            foreach ($other in 'commands','mcp-servers','status-line','output-styles','workflows','rules','snippets','settings-fragments') {
                $od = Join-Path $bundleDir $other
                if ((Test-Path -LiteralPath $od -PathType Container) -and (Get-ChildItem -LiteralPath $od -Force -ErrorAction SilentlyContinue)) {
                    Write-Warning "kind '$other' is not yet supported by this installer - skipped"
                }
            }
        }
}

function Install-StandaloneSkills {
    Get-ChildItem -LiteralPath (Join-Path $ToolkitRoot 'skills') -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            $skillDir = $_.FullName
            $skillName = $_.Name
            $skillMd = Join-Path $skillDir 'SKILL.md'
            if (-not (Test-Path -LiteralPath $skillMd)) { return }
            if (-not $ModeAll -and $Skill -and $Skill -ne $skillName) { return }
            $kind = Get-Field $skillMd 'kind'
            if ($kind -ne 'skill') {
                Write-Warning "$skillMd has kind '$kind' (expected 'skill') - skipped"
                return
            }
            $hosts = Get-Field $skillMd 'supported_hosts'
            if (-not $hosts) {
                Write-Warning "skill '$skillName' has no supported_hosts - skipped"
                return
            }
            Write-Host "==> installing skill: $skillName"
            Install-Skill $skillDir $skillName $hosts
        }
}

function Install-StandaloneAgents {
    $agentsRoot = Join-Path $ToolkitRoot 'agents'
    if (-not (Test-Path -LiteralPath $agentsRoot -PathType Container)) { return }
    Get-ChildItem -LiteralPath $agentsRoot -Filter '*.md' -File -ErrorAction SilentlyContinue |
        ForEach-Object {
            $agentMd = $_.FullName
            $agentName = $_.BaseName
            if (-not $ModeAll -and $Agent -and $Agent -ne $agentName) { return }
            $kind = Get-Field $agentMd 'kind'
            if ($kind -ne 'agent') {
                Write-Warning "$agentMd has kind '$kind' (expected 'agent') - skipped"
                return
            }
            $hosts = Get-Field $agentMd 'supported_hosts'
            if (-not $hosts) {
                Write-Warning "agent '$agentName' has no supported_hosts - skipped"
                return
            }
            Write-Host "==> installing agent: $agentName"
            Install-Agent $agentMd $agentName $hosts
        }
}

function Install-StandaloneHooks {
    $hooksRoot = Join-Path $ToolkitRoot 'hooks'
    if (-not (Test-Path -LiteralPath $hooksRoot -PathType Container)) { return }
    Get-ChildItem -LiteralPath $hooksRoot -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            $hookDir = $_.FullName
            $hookName = $_.Name
            $hookMd = Join-Path $hookDir 'hook.md'
            if (-not (Test-Path -LiteralPath $hookMd)) { return }
            if (-not $ModeAll -and $Hook -and $Hook -ne $hookName) { return }
            $kind = Get-Field $hookMd 'kind'
            if ($kind -ne 'hook') {
                Write-Warning "$hookMd has kind '$kind' (expected 'hook') - skipped"
                return
            }
            $hosts = Get-Field $hookMd 'supported_hosts'
            if (-not $hosts) {
                Write-Warning "hook '$hookName' has no supported_hosts - skipped"
                return
            }
            Write-Host "==> installing hook: $hookName"
            Install-Hook $hookDir $hookName $hosts
        }
}

# ── run ───────────────────────────────────────────────────────────────────
if ($ModeAll -or $Bundle) {
    Install-Bundles
}
if ($ModeAll -or $Skill) {
    Install-StandaloneSkills
}
if ($ModeAll -or $Agent) {
    Install-StandaloneAgents
}
if ($ModeAll -or $Hook) {
    Install-StandaloneHooks
}

Write-Host '==> pre-push hook'
Install-PrePushHook

function Install-PythonDeps {
    # Best-effort install of the toolkit's Python deps from requirements.txt.
    # Failure is logged but does NOT fail the toolkit install — the graceful-
    # skip contracts (memory skill falls back to grep+frontmatter without
    # sentence-transformers; vec-index ops no-op without sqlite-vec) mean
    # operators can still use most functionality. The pip-install is
    # opportunistic.
    if ($script:NoPythonDeps) {
        Write-Host '==> python deps: skipped (-NoPythonDeps)'
        return
    }
    $reqFile = Join-Path $script:ToolkitRoot 'requirements.txt'
    if (-not (Test-Path -LiteralPath $reqFile)) {
        Write-Warning "requirements.txt missing at $script:ToolkitRoot; python deps not installed"
        return
    }
    # Resolve python executable: prefer python3 if available, else python.
    $pythonExe = $null
    foreach ($candidate in @('python3', 'python')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) { $pythonExe = $cmd.Source; break }
    }
    if (-not $pythonExe) {
        Write-Warning 'python3 / python not found on PATH; python deps not installed'
        Write-Warning '   install Python 3.9+ and re-run, or pass -NoPythonDeps to suppress'
        return
    }
    # Verify pip available.
    $pipCheck = & $pythonExe -m pip --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'pip not available; python deps not installed'
        return
    }
    Write-Host '==> python deps'
    # Idempotent quick-path: skip if all three are already importable.
    $importCheck = & $pythonExe -c "import yaml, sqlite_vec, sentence_transformers" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host '    pyyaml + sqlite-vec + sentence-transformers already installed'
        return
    }
    Write-Host '    installing pyyaml + sqlite-vec + sentence-transformers from requirements.txt'
    Write-Host '    (sentence-transformers pulls torch + transformers + tokenizers; first install can take 2-5min)'
    # Try --user; failure is logged + non-fatal.
    & $pythonExe -m pip install --user --quiet -r $reqFile 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    installed (note: sentence-transformers' default BGE-large model — ~1.3GB — downloads lazily on first /memory save or embed.py --mode local)"
    } else {
        Write-Warning 'pip install failed.'
        Write-Warning '   The toolkit will graceful-skip embedding + vec-index operations until'
        Write-Warning '   Python deps are installed. To install manually:'
        Write-Warning "     $pythonExe -m pip install --user -r $reqFile"
        Write-Warning '   Or rerun install.ps1 with -NoPythonDeps to suppress this attempt.'
    }
}

Install-PythonDeps

function Install-PersonalSkillsIndex {
    # Best-effort: run the personal-skills auto-indexer against the
    # toolkit's own skills/ + the sibling agentic-harness/.claude/skills/
    # if discoverable. Pointers land in MemoryVault/personal-skills/<repo>/.
    # Requires MEMORY_VAULT_PATH to be set (we don't guess the vault path —
    # operators without a vault configured silently skip this).
    if ($script:NoSkillIndex) {
        Write-Host '==> personal-skills index: skipped (-NoSkillIndex)'
        return
    }
    $indexer = Join-Path $script:ToolkitRoot 'skills/memory/scripts/index_skills.py'
    if (-not (Test-Path -LiteralPath $indexer)) {
        # Memory skill not yet shipped to this toolkit checkout (pre-#7b).
        return
    }
    $vaultPath = $env:MEMORY_VAULT_PATH
    if (-not $vaultPath) {
        Write-Host '==> personal-skills index: skipped (MEMORY_VAULT_PATH unset)'
        return
    }
    # Resolve python executable: prefer python3 then python.
    $pythonExe = $null
    foreach ($candidate in @('python3', 'python')) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) { $pythonExe = $cmd.Source; break }
    }
    if (-not $pythonExe) {
        return
    }
    Write-Host '==> personal-skills index'
    $toolkitSkills = Join-Path $script:ToolkitRoot 'skills'
    $argList = @('--vault-path', $vaultPath, '--skill-path', $toolkitSkills)
    # Also index sibling agentic-harness skills if present (canonical clone:
    # ~/Antigravity/agentic-harness next to ~/Antigravity/agent-toolkit).
    $harnessSibling = Join-Path $script:ToolkitRoot '../agentic-harness/.claude/skills'
    if (Test-Path -LiteralPath $harnessSibling) {
        $argList += @('--skill-path', $harnessSibling)
    }
    & $pythonExe $indexer @argList 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'personal-skills indexer exited non-zero — pointers may be incomplete'
        # Non-fatal: skill-pointer entries are nice-to-have.
    }
}

Install-PersonalSkillsIndex

Write-Host ''
Write-Host 'agent-toolkit install: complete.'
