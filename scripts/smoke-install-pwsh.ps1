# smoke-install-pwsh.ps1 — install crickets into a scratch dir and assert
# the expected tree under pwsh.
#
# Used by tests-windows.yml. Invoked from repo root:
#   pwsh -NoProfile -File scripts/smoke-install-pwsh.ps1
#
# v2.0.0 (V4 #36 reorg) — surface reduced to base primitives only:
# compound skills (memory, design, diataxis-author, ship-release), memory
# hooks (memory-recall-*, memory-reflect-*), evidence-tracker hook,
# memory-idea-researcher sub-agent, plugins/, and bundles/ all moved to
# agentm. The deep functional smoke tests for those primitives moved with
# them. This file now covers only the primitives crickets still owns.

$ErrorActionPreference = 'Stop'

$ToolkitRoot = Split-Path -Parent $PSScriptRoot
$ToolkitRoot = (Resolve-Path -LiteralPath $ToolkitRoot).ProviderPath

$scratch = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-smoke-" + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch -Force | Out-Null

try {
    git -C $scratch init -q -b main | Out-Null

    Write-Host "==> fresh install into $scratch"
    pwsh -NoProfile -File (Join-Path $ToolkitRoot 'install.ps1') -NoPythonDeps -NoSkillIndex $scratch | Out-File (Join-Path $scratch '.install.log')
    if ($LASTEXITCODE -ne 0) { throw "install.ps1 returned non-zero ($LASTEXITCODE)" }

    # ── expected files ─────────────────────────────────────────────────────
    # Catalog: 2 skills (pii-scrubber, dependabot-fixer), 2 agents
    # (evaluator, diataxis-evaluator; adapt-evaluator moved to agentm in V4 #23), 3 hooks (kill-switch,
    # steer, commit-on-stop). gemini-cli host removed in v0.9.0; .agent/
    # singular → .agents/ plural in v1.2.0 per ADR 0011.
    $expected = @(
        # Standalone skill: pii-scrubber across 2 hosts
        '.claude/skills/pii-scrubber/SKILL.md',
        '.agents/skills/pii-scrubber/SKILL.md',
        # Standalone skill: dependabot-fixer across 2 hosts
        '.claude/skills/dependabot-fixer/SKILL.md',
        '.agents/skills/dependabot-fixer/SKILL.md',
        # Standalone agents: evaluator + diataxis-evaluator
        '.claude/agents/evaluator.md',
        '.agents/skills/evaluator/SKILL.md',
        '.claude/agents/diataxis-evaluator.md',
        '.agents/skills/diataxis-evaluator/SKILL.md',
        # Standalone hooks (claude-code only per ADR 0009)
        '.claude/hooks/kill-switch.ps1',
        '.claude/hooks/steer.ps1',
        '.claude/hooks/commit-on-stop.ps1',
        '.claude/settings.json',
        '.git/hooks/pre-push'
    )
    $fail = $false
    foreach ($p in $expected) {
        $full = Join-Path $scratch $p
        if (-not (Test-Path -LiteralPath $full)) {
            Write-Error "MISSING: $p"
            $fail = $true
        }
    }

    # ── negative-existence assertions ───────────────────────────────────────
    # These paths MUST NOT exist after install. Catches regressions if:
    #   - gemini-cli dispatch arms come back (v0.9.0 removed)
    #   - .agent/ singular destinations return (v1.2.0 → .agents/ plural)
    #   - v2.0.0-moved primitives accidentally re-ship from crickets
    #     (compound skills, memory hooks, evidence-tracker, memory-idea-
    #     researcher all live in agentm now per V4 #36)
    $notExpected = @(
        '.agent',
        '.gemini',
        # Compound skills moved to agentm (V4 #36)
        '.claude/skills/memory',
        '.claude/skills/design',
        '.claude/skills/diataxis-author',
        '.claude/skills/ship-release',
        '.agents/skills/memory',
        '.agents/skills/design',
        '.agents/skills/diataxis-author',
        '.agents/skills/ship-release',
        # example-skill went with example-bundle deletion (V4 #36)
        '.claude/skills/example-skill',
        '.agents/skills/example-skill',
        # memory-idea-researcher sub-agent moved to agentm (V4 #36)
        '.claude/agents/memory-idea-researcher.md',
        '.agents/skills/memory-idea-researcher',
        # Memory hooks + evidence-tracker hook moved to agentm (V4 #36)
        '.claude/hooks/memory-recall-session-start.ps1',
        '.claude/hooks/memory-recall-prompt-submit.ps1',
        '.claude/hooks/memory-reflect-stop.ps1',
        '.claude/hooks/memory-reflect-idle.ps1',
        '.claude/hooks/evidence-tracker.ps1',
        '.claude/hooks/evidence_tracker.py'
    )
    foreach ($p in $notExpected) {
        $full = Join-Path $scratch $p
        if (Test-Path -LiteralPath $full) {
            Write-Error "UNEXPECTED ($p should not exist after v2.0.0 reorg): $full"
            $fail = $true
        }
    }

    # ── installer-boundary: leak check ─────────────────────────────────────
    $leaks = @(
        'scripts/smoke-install-bash.sh',
        'scripts/check-integrity-bash.sh',
        'scripts/check-syntax.sh',
        'scripts/check-lib-parity.sh',
        'scripts/check-no-pii.sh',
        'scripts/manifest-info.py',
        'scripts/validate-manifests.py',
        'lib/install/bash/primitives.sh',
        'lib/install/pwsh/primitives.ps1',
        '.github/workflows/tests-linux.yml',
        'CONTRIBUTING.md',
        'CHANGELOG.md',
        '.gitleaks.toml'
    )
    foreach ($p in $leaks) {
        $full = Join-Path $scratch $p
        if (Test-Path -LiteralPath $full) {
            Write-Error "LEAK: $p should not be in scratch install (installer boundary)"
            $fail = $true
        }
    }

    if ($fail) { throw 'expected-files or leak check failed' }

    # ── idempotent re-run ──────────────────────────────────────────────────
    Write-Host '==> idempotent re-run'
    pwsh -NoProfile -File (Join-Path $ToolkitRoot 'install.ps1') -NoPythonDeps -NoSkillIndex $scratch | Out-File (Join-Path $scratch '.rerun.log')
    $rerun = Get-Content (Join-Path $scratch '.rerun.log') -Raw
    if ($rerun -match 'created .claude/skills/(pii-scrubber|dependabot-fixer)') {
        throw 're-run recreated a skill (should be kept)'
    }
    if ($rerun -match 'created .claude/agents/(evaluator|diataxis-evaluator)') {
        throw 're-run recreated an agent (should be kept)'
    }
    if ($rerun -match 'created .claude/hooks/(kill-switch|steer|commit-on-stop)') {
        throw 're-run recreated a hook script (should be kept)'
    }
    if ($rerun -match 'merged  .claude/settings.json') {
        throw 're-run re-merged settings.json (should report kept)'
    }
    if ($rerun -notmatch 'kept    .claude/settings.json \(fragment entries already present\)') {
        throw 're-run did not emit kept message for .claude/settings.json'
    }

    # ── --update ───────────────────────────────────────────────────────────
    Write-Host '==> --update wipe + recreate'
    pwsh -NoProfile -File (Join-Path $ToolkitRoot 'install.ps1') -Update -NoPythonDeps -NoSkillIndex $scratch | Out-File (Join-Path $scratch '.update.log')
    $update = Get-Content (Join-Path $scratch '.update.log') -Raw
    if ($update -notmatch 'removed .claude/skills/') {
        throw '-Update did not run sync wipe'
    }
    foreach ($p in $expected) {
        if (-not (Test-Path -LiteralPath (Join-Path $scratch $p))) {
            throw "-Update did not recreate $p"
        }
    }

    # ── -NoPrePushHook ─────────────────────────────────────────────────────
    Write-Host '==> -NoPrePushHook'
    $nohook = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-nohook-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $nohook -Force | Out-Null
    try {
        git -C $nohook init -q -b main | Out-Null
        pwsh -NoProfile -File (Join-Path $ToolkitRoot 'install.ps1') -NoPrePushHook -NoPythonDeps -NoSkillIndex $nohook | Out-File (Join-Path $nohook '.install.log')
        if (Test-Path -LiteralPath (Join-Path $nohook '.git/hooks/pre-push')) {
            throw '-NoPrePushHook installed the hook anyway'
        }
    } finally {
        Remove-Item -LiteralPath $nohook -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── -NoLegacyCleanup: suppresses the legacy-cleanup prompt (v1.2.0) ──
    # v1.2.0 migrated Antigravity dispatch from .agent/ singular → .agents/
    # plural per ADR 0011. Installer detects pre-existing .agent/skills/
    # from v1.0.x crickets (Antigravity 1.x convention); -NoLegacyCleanup
    # suppresses the prompt.
    Write-Host '==> -NoLegacyCleanup (v1.2.0 .agent/ singular legacy detection)'
    $legacy = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-legacy-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $legacy -Force | Out-Null
    try {
        git -C $legacy init -q -b main | Out-Null
        # Use pii-scrubber as the seed name — v2.0.0+ managed skill name.
        New-Item -ItemType Directory -Path (Join-Path $legacy '.agent/skills/pii-scrubber') -Force | Out-Null
        'fake legacy skill' | Out-File -FilePath (Join-Path $legacy '.agent/skills/pii-scrubber/SKILL.md')
        pwsh -NoProfile -File (Join-Path $ToolkitRoot 'install.ps1') -NoLegacyCleanup -NoPythonDeps -NoSkillIndex $legacy | Out-File (Join-Path $legacy '.install.log')
        $log = Get-Content (Join-Path $legacy '.install.log') -Raw
        if ($log -match 'legacy gemini-cli cleanup') {
            throw '-NoLegacyCleanup did not suppress the cleanup prompt'
        }
        if (-not (Test-Path -LiteralPath (Join-Path $legacy '.agent/skills/pii-scrubber/SKILL.md'))) {
            throw '-NoLegacyCleanup deleted/moved legacy .agent/skills/pii-scrubber/ (should leave untouched)'
        }
    } finally {
        Remove-Item -LiteralPath $legacy -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── kill-switch hook end-to-end ────────────────────────────────────────
    # Sanity-check the installed kill-switch.ps1 exits 2 when .harness/STOP
    # sentinel is present. Proves the hook script lands functional.
    Write-Host '==> kill-switch hook end-to-end'
    $kstmp = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-kstmp-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $kstmp -Force | Out-Null
    try {
        git -C $kstmp init -q -b main | Out-Null
        pwsh -NoProfile -File (Join-Path $ToolkitRoot 'install.ps1') -NoPythonDeps -NoSkillIndex $kstmp | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $kstmp '.harness') -Force | Out-Null
        New-Item -ItemType File -Path (Join-Path $kstmp '.harness/STOP') -Force | Out-Null
        Push-Location $kstmp
        try {
            pwsh -NoProfile -File (Join-Path $kstmp '.claude/hooks/kill-switch.ps1') 2>&1 | Out-Null
            $ksExit = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($ksExit -ne 2) {
            throw "kill-switch.ps1 with .harness/STOP present should exit 2; got $ksExit"
        }
    } finally {
        Remove-Item -LiteralPath $kstmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── validate-manifests negative test: gemini-cli rejected with v0.9.0 msg ─
    Write-Host '==> validate-manifests negative test (gemini-cli rejected)'
    $vneg = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-vneg-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $vneg 'skills/test-gemini-cli-rejected') -Force | Out-Null
    $vnegManifest = @"
---
name: test-gemini-cli-rejected
description: Negative-test fixture - validate-manifests must reject this manifest because gemini-cli was removed in v0.9.0.
kind: skill
supported_hosts: [claude-code, antigravity, gemini-cli]
version: 0.1.0
install_scope: project
---
"@
    $vnegManifest | Out-File -FilePath (Join-Path $vneg 'skills/test-gemini-cli-rejected/SKILL.md') -Encoding utf8
    try {
        $vnegDriver = @"
import importlib.util
spec = importlib.util.spec_from_file_location('vm', r'$($ToolkitRoot -replace '\\', '/')/scripts/validate-manifests.py')
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)
from pathlib import Path
vm.ROOT = Path(r'$($vneg -replace '\\', '/')')
p = Path(r'$($vneg -replace '\\', '/')/skills/test-gemini-cli-rejected/SKILL.md')
fm = vm.parse_frontmatter(p)
vm.require_supported_hosts(p, fm)
print('ERRORS:', len(vm.errors))
for issue in vm.errors:
    print('MSG:', issue)
"@
        $vnegOut = python3 -c $vnegDriver 2>&1 | Out-String
        if ($vnegOut -notmatch "removed host 'gemini-cli'") {
            throw "validator did not emit 'removed host gemini-cli' message. Output:`n$vnegOut"
        }
        if ($vnegOut -notmatch 'v0\.9\.0') {
            throw "validator's error message does not mention v0.9.0 (no actionable next-step). Output:`n$vnegOut"
        }
    } finally {
        Remove-Item -LiteralPath $vneg -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── post-install integrity ─────────────────────────────────────────────
    Write-Host '==> post-install integrity'
    pwsh -NoProfile -File (Join-Path $ToolkitRoot 'scripts/check-integrity-pwsh.ps1') $scratch
    if ($LASTEXITCODE -ne 0) { throw 'check-integrity-pwsh failed' }

    Write-Host '==> smoke-install-pwsh: OK'
} finally {
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
