# install.ps1 — crickets installer.
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
#   -NoLegacyCleanup         suppress the legacy .agent/skills/ + .gemini/agents/
#                            cleanup prompt (v0.9.0+ removed gemini-cli host;
#                            the installer detects pre-existing legacy
#                            destinations from a prior install and offers
#                            backup+remove with operator confirmation. This
#                            switch skips the prompt entirely — useful for CI
#                            / scripted installs.)
#   -NoPythonDeps            skip the pip-install step for the toolkit's
#                            Python deps (v2.0.0+: pyyaml only). Use if you
#                            manage Python deps via virtualenv / conda /
#                            system packages.
#   -NoSkillIndex            (no-op as of v2.0.0; memory skill moved to
#                            agentm; agentm's installer owns personal-skills
#                            indexing now). Flag kept as backward-compat
#                            no-op.
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
Write-Host "==> crickets install: $Target"

# ── -Update sync ──────────────────────────────────────────────────────────
# See install.sh note on .claude/agents + .gemini/agents + .claude/hooks —
# these parents are also written to by the sibling agentm installer;
# the LATER-run installer's -Update wipes the parent before recreating from
# its own source. .claude/settings.json is NOT wiped — it's user-state-merged
# and the toolkit re-merges its hook fragments idempotently via
# scripts/merge-settings-fragment.py.
$ManagedParents = @(
    '.claude/skills',
    '.agents/skills',
    '.claude/agents',
    '.claude/hooks'
)
$EmptyParentCandidates = @()

# ── legacy gemini-cli cleanup (v0.9.0+) ───────────────────────────────────
# v0.9.0 removed standalone Gemini CLI host support. Prior installs may have
# populated either:
#   - .agent/skills/<name>/ (Antigravity 1.x skill destination — v1.0.x crickets;
#                            v1.2.0 migrated to .agents/ plural per ADR 0011)
#   - .gemini/agents/<name>.md (agents installed with gemini-cli host)
# Detect pre-existing entries that match currently-managed customization
# names; offer a backup-then-remove flow with operator confirmation. Defaults
# to N (no-op unless operator opts in). -NoLegacyCleanup suppresses the
# prompt entirely (useful for CI / scripted installs). Non-interactive
# sessions also skip the prompt with a one-line notice. Never hard-deletes —
# moves to timestamped backups at <path>.crickets-bak.<ts>/ per the
# pre-push-hook backup convention. Only touches entries the installer
# recognizes as toolkit-managed (matches manifest names); leaves any
# unmanaged user files alone.
function Invoke-LegacyCleanupGeminiCli {
    if ($NoLegacyCleanup) { return }
    $hasLegacySkills = Test-Path -LiteralPath '.agent/skills' -PathType Container
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

    # Match .agent/skills/ (singular — Antigravity 1.x legacy) against known skill names.
    $matchedSkills = @()
    if ($hasLegacySkills) {
        Get-ChildItem -LiteralPath '.agent/skills' -Directory -ErrorAction SilentlyContinue |
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
    Write-Host 'crickets v0.9.0+ removed standalone Gemini CLI host support.'
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
            $bak = ".agent/skills.crickets-bak.$ts"
            Move-Item -LiteralPath '.agent/skills' -Destination $bak
            Write-Host "    moved .agent/skills/ -> $bak/"
            if ((Test-Path -LiteralPath '.agent') -and -not (Get-ChildItem -LiteralPath '.agent' -Force -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath '.agent' -Force
                Write-Host '    removed empty .agent/ directory'
            }
        }
        if ($matchedAgents.Count -gt 0) {
            $bak = ".gemini/agents.crickets-bak.$ts"
            Move-Item -LiteralPath '.gemini/agents' -Destination $bak
            Write-Host "    moved .gemini/agents/ -> $bak/"
            if ((Test-Path -LiteralPath '.gemini') -and -not (Get-ChildItem -LiteralPath '.gemini' -Force -ErrorAction SilentlyContinue)) {
                Remove-Item -LiteralPath '.gemini' -Force
                Write-Host '    removed empty .gemini/ directory'
            }
        }
    } else {
        Write-Host '    cleanup skipped — to remove manually later:'
        if ($hasLegacySkills) { Write-Host '        Remove-Item -Recurse .agent/skills/' }
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
                # agy v1.0.2+ / Antigravity 2.0 uses .agents/ (plural) per
                # ADR 0011. v1.0.x crickets used .agent/ (singular) for
                # Antigravity 1.x; legacy_cleanup handles migration on /update.
                New-Item -ItemType Directory -Path '.agents/skills' -Force | Out-Null
                Copy-ManagedDir $srcDir (Join-Path '.agents/skills' $name)
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
                # Copy any sibling Python helpers (foo.py / foo_helper.py / etc.)
                # alongside the hook script. Lets hooks ship a Python helper
                # without requiring it to live in a separate skill dir.
                # Plan #9 (evidence-tracker) introduced this pattern.
                Get-ChildItem -Path $hookDir -Filter '*.py' -File -ErrorAction SilentlyContinue | ForEach-Object {
                    Copy-ManagedFile $_.FullName (Join-Path '.claude/hooks' $_.Name)
                }
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
    # Antigravity 2.0 / agy v1.0.2+ has no first-class sub-agent slot (subagents
    # are SDK runtime constructs spawned via the built-in start_subagent tool
    # per Wave 1 task 3 research) — agents get wrapped as skills at
    # .agents/skills/<name>/SKILL.md (sub-agent-as-skill pattern). Path changed
    # from .agent/ to .agents/ in v1.2.0 per ADR 0011 — agy uses plural.
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
                $wrap = Join-Path '.agents/skills' $name
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
            Write-Host "    kept    $hookDst (already managed by crickets)"
            return
        }
        $bak = "$hookDst.crickets-bak.$([int][double]::Parse((Get-Date -UFormat %s)))"
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
            # Plan #10: contents-driven dispatch with sibling-reference resolution.
            # For each `- kind: name` in the manifest's contents:, prefer the
            # standalone toolkit location over the bundle-local copy. Bundle-local
            # is the legacy fallback (example-bundle uses it for its stub skill).
            $contentsPairs = python3 -c @"
import sys, yaml
with open(r'$bundleMd', encoding='utf-8') as f:
    text = f.read()
parts = text.split('---', 2)
if len(parts) < 3:
    sys.exit(0)
try:
    fm = yaml.safe_load(parts[1]) or {}
except yaml.YAMLError:
    sys.exit(0)
for entry in fm.get('contents', []) or []:
    if isinstance(entry, dict) and len(entry) == 1:
        kind, name = next(iter(entry.items()))
        print(f'{kind}`t{name}')
"@
            if (-not $contentsPairs) {
                Write-Warning "bundle '$bundleName' has empty/unparseable contents - skipped"
                return
            }
            foreach ($pair in $contentsPairs -split "`n") {
                $pair = $pair.Trim()
                if (-not $pair) { continue }
                $parts2 = $pair -split "`t", 2
                if ($parts2.Count -ne 2) { continue }
                $entryKind = $parts2[0]
                $entryName = $parts2[1]
                switch ($entryKind) {
                    'skill' {
                        $standalonePath = Join-Path $ToolkitRoot "skills/$entryName"
                        $bundleLocalPath = Join-Path $bundleDir "skills/$entryName"
                        if (Test-Path -LiteralPath (Join-Path $standalonePath 'SKILL.md')) {
                            Install-Skill $standalonePath $entryName $hosts
                        } elseif (Test-Path -LiteralPath (Join-Path $bundleLocalPath 'SKILL.md')) {
                            Install-Skill $bundleLocalPath $entryName $hosts
                        } else {
                            Write-Warning "bundle '$bundleName' skill '$entryName' not found at $standalonePath or $bundleLocalPath - skipped"
                        }
                    }
                    'agent' {
                        $standalonePath = Join-Path $ToolkitRoot "agents/$entryName.md"
                        $bundleLocalPath = Join-Path $bundleDir "agents/$entryName.md"
                        if (Test-Path -LiteralPath $standalonePath) {
                            Install-Agent $standalonePath $entryName $hosts
                        } elseif (Test-Path -LiteralPath $bundleLocalPath) {
                            Install-Agent $bundleLocalPath $entryName $hosts
                        } else {
                            Write-Warning "bundle '$bundleName' agent '$entryName' not found at $standalonePath or $bundleLocalPath - skipped"
                        }
                    }
                    'hook' {
                        $standalonePath = Join-Path $ToolkitRoot "hooks/$entryName"
                        $bundleLocalPath = Join-Path $bundleDir "hooks/$entryName"
                        if (Test-Path -LiteralPath (Join-Path $standalonePath 'hook.md')) {
                            Install-Hook $standalonePath $entryName $hosts
                        } elseif (Test-Path -LiteralPath (Join-Path $bundleLocalPath 'hook.md')) {
                            Install-Hook $bundleLocalPath $entryName $hosts
                        } else {
                            Write-Warning "bundle '$bundleName' hook '$entryName' not found at $standalonePath or $bundleLocalPath - skipped"
                        }
                    }
                    default {
                        Write-Warning "kind '$entryKind' is not yet supported by this installer - skipped"
                    }
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
    # v2.0.0+: pyyaml only (memory skill moved to agentm; sqlite-vec +
    # sentence-transformers are agentm's deps now). The pip-install is
    # opportunistic; the toolkit's contract is "tries to set you up but
    # never blocks the install on Python dep state." validate-manifests.py
    # gracefully skips when pyyaml is unavailable (falls back to frontmatter
    # regex parsing).
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
    # Idempotent quick-path: skip if pyyaml is already importable.
    $importCheck = & $pythonExe -c "import yaml" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host '    pyyaml already installed'
        return
    }
    Write-Host '    installing pyyaml from requirements.txt (v2.0.0+: only pyyaml needed; memory skill moved to agentm)'
    # Try --user; failure is logged + non-fatal.
    & $pythonExe -m pip install --user --quiet -r $reqFile 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host '    installed'
    } else {
        Write-Warning 'pip install failed.'
        Write-Warning '   The toolkit will graceful-skip pyyaml-dependent ops (validate-manifests.py)'
        Write-Warning '   until installed. To install manually:'
        Write-Warning "     $pythonExe -m pip install --user -r $reqFile"
        Write-Warning '   Or rerun install.ps1 with -NoPythonDeps to suppress this attempt.'
    }
}

Install-PythonDeps

# ── probe + persist install state (V4 #30 task 8) ──────────────────────────
# Mirrors agentm: detect source-clone canonical paths; persist decision to
# <target>/.claude/.agentm-install-state.json for downstream dispatch.
# Silent; best-effort.
try {
    $ToolkitVersion = (git -C $ToolkitRoot describe --tags --abbrev=0 2>$null)
    if (-not $ToolkitVersion) { $ToolkitVersion = 'dev' }
} catch {
    $ToolkitVersion = 'dev'
}
$pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $pythonCmd) { $pythonCmd = Get-Command python -ErrorAction SilentlyContinue }
$installStatePy = Join-Path $ToolkitRoot 'lib/install/python/install_state.py'
if ($pythonCmd -and (Test-Path $installStatePy)) {
    try {
        & $pythonCmd.Source $installStatePy 'persist' `
            (Join-Path $Target '.claude') `
            '--harness-version' $ToolkitVersion `
            '--installer-source' (Join-Path $ToolkitRoot 'install.ps1') *>$null
    } catch {
        # Silent failure — install proceeds; install-state.json is best-effort
    }
}

# Note: Install-PersonalSkillsIndex was removed in v2.0.0 (V4 #36). The
# personal-skills auto-indexer referenced skills/memory/scripts/index_skills.py
# which moved to agentm. agentm's installer owns this step post-reorg.
# The -NoSkillIndex switch is preserved as a no-op for backward-compat.

Write-Host ''
Write-Host 'crickets install: complete.'
