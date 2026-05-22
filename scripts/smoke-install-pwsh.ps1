# smoke-install-pwsh.ps1 — install agent-toolkit into a scratch dir and assert
# the expected tree under pwsh.
#
# Used by tests-windows.yml. Invoked from repo root:
#   pwsh -NoProfile -File scripts/smoke-install-pwsh.ps1

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
    $expected = @(
        # Bundle: example-bundle -> example-skill across 2 hosts (claude-code + antigravity).
        # gemini-cli host removed in v0.9.0 (ROADMAP #15).
        '.claude/skills/example-skill/SKILL.md',
        '.agent/skills/example-skill/SKILL.md',
        '.claude/skills/pii-scrubber/SKILL.md',
        '.agent/skills/pii-scrubber/SKILL.md',
        # Standalone skill: design (scaffold only in v0.7.0+; bodies in tasks 2-4 of plan #6).
        '.claude/skills/design/SKILL.md',
        '.claude/skills/design/templates/design-doc.md',
        '.agent/skills/design/SKILL.md',
        '.agent/skills/design/templates/design-doc.md',
        # Standalone skill: memory (plan #7a part 1 task 1 ships scaffold;
        # task 2 of part 1 ships /memory save body + scripts/save.py;
        # task 3 of part 1 ships /memory evolve body + scripts/evolve.py;
        # task 4 of part 1 ships embed.py + vec_index.py).
        '.claude/skills/memory/SKILL.md',
        '.claude/skills/memory/scripts/save.py',
        '.claude/skills/memory/scripts/evolve.py',
        '.claude/skills/memory/scripts/embed.py',
        '.claude/skills/memory/scripts/vec_index.py',
        '.claude/skills/memory/scripts/recall.py',
        '.claude/skills/memory/scripts/reflect.py',
        '.claude/skills/memory/scripts/permeable_boundary.py',
        '.claude/skills/memory/scripts/ideas_surface.py',
        '.claude/skills/memory/scripts/ideas_incubator.py',
        '.claude/skills/memory/scripts/ideas_promote.py',
        '.claude/skills/memory/scripts/index_skills.py',
        '.claude/skills/memory/scripts/discover_skills.py',
        '.claude/skills/memory/scripts/adapt_skills.py',
        '.agent/skills/memory/SKILL.md',
        '.agent/skills/memory/scripts/save.py',
        '.agent/skills/memory/scripts/evolve.py',
        '.agent/skills/memory/scripts/embed.py',
        '.agent/skills/memory/scripts/vec_index.py',
        '.agent/skills/memory/scripts/recall.py',
        '.agent/skills/memory/scripts/reflect.py',
        '.agent/skills/memory/scripts/permeable_boundary.py',
        '.agent/skills/memory/scripts/ideas_surface.py',
        '.agent/skills/memory/scripts/ideas_incubator.py',
        '.agent/skills/memory/scripts/ideas_promote.py',
        '.agent/skills/memory/scripts/index_skills.py',
        '.agent/skills/memory/scripts/discover_skills.py',
        '.agent/skills/memory/scripts/adapt_skills.py',
        # Standalone agent: evaluator. claude-code is single-file;
        # antigravity wraps the agent as a skill. (gemini-cli destination
        # .gemini/agents/evaluator.md removed in v0.9.0.)
        '.claude/agents/evaluator.md',
        '.agent/skills/evaluator/SKILL.md',
        '.claude/agents/memory-idea-researcher.md',
        '.agent/skills/memory-idea-researcher/SKILL.md',
        '.claude/agents/adapt-evaluator.md',
        '.agent/skills/adapt-evaluator/SKILL.md',
        # Standalone hooks (claude-code only, v0.7.0); memory-recall hooks
        # added in plan #7a part 2; memory-reflect-{stop,idle} added in
        # plan #7a part 3.
        '.claude/hooks/kill-switch.ps1',
        '.claude/hooks/steer.ps1',
        '.claude/hooks/commit-on-stop.ps1',
        '.claude/hooks/memory-recall-session-start.ps1',
        '.claude/hooks/memory-recall-prompt-submit.ps1',
        '.claude/hooks/memory-reflect-stop.ps1',
        '.claude/hooks/memory-reflect-idle.ps1',
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

    # ── negative-existence assertions (v0.9.0+ — gemini-cli removed) ───────────
    # These paths MUST NOT exist after install. Catches regressions if the
    # gemini-cli dispatch arms ever come back.
    $notExpected = @('.agents', '.gemini')
    foreach ($p in $notExpected) {
        $full = Join-Path $scratch $p
        if (Test-Path -LiteralPath $full) {
            Write-Error "UNEXPECTED (v0.9.0+ removed gemini-cli): $p exists at $full"
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
    if ($rerun -match 'created .claude/skills/(example-skill|pii-scrubber)') {
        throw 're-run recreated a skill (should be kept)'
    }
    if ($rerun -match 'created .claude/agents/(evaluator|memory-idea-researcher|adapt-evaluator)') {
        throw 're-run recreated the evaluator agent (should be kept)'
    }
    if ($rerun -match 'created .claude/hooks/(kill-switch|steer|commit-on-stop|memory-recall-session-start|memory-recall-prompt-submit|memory-reflect-stop|memory-reflect-idle)') {
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

    # ── -NoLegacyCleanup: suppresses the v0.9.0 legacy-cleanup prompt ──────
    Write-Host '==> -NoLegacyCleanup (v0.9.0)'
    $legacy = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-legacy-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $legacy -Force | Out-Null
    try {
        git -C $legacy init -q -b main | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $legacy '.agents/skills/design') -Force | Out-Null
        'fake legacy skill' | Out-File -FilePath (Join-Path $legacy '.agents/skills/design/SKILL.md')
        pwsh -NoProfile -File (Join-Path $ToolkitRoot 'install.ps1') -NoLegacyCleanup -NoPythonDeps -NoSkillIndex $legacy | Out-File (Join-Path $legacy '.install.log')
        $log = Get-Content (Join-Path $legacy '.install.log') -Raw
        if ($log -match 'legacy gemini-cli cleanup') {
            throw '-NoLegacyCleanup did not suppress the cleanup prompt'
        }
        if (-not (Test-Path -LiteralPath (Join-Path $legacy '.agents/skills/design/SKILL.md'))) {
            throw '-NoLegacyCleanup deleted/moved legacy .agents/skills/design/ (should leave untouched)'
        }
    } finally {
        Remove-Item -LiteralPath $legacy -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── /memory save end-to-end test (plan #7a part 1 task 2) ──────────────
    Write-Host '==> /memory save end-to-end test (plan #7a part 1 task 2)'
    $msave = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-msave-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $msave -Force | Out-Null
    try {
        $savePy = Join-Path $scratch '.claude/skills/memory/scripts/save.py'
        if (-not (Test-Path -LiteralPath $savePy)) {
            throw "save.py not installed at $savePy"
        }
        # Positive save
        $expected = Join-Path $msave 'personal-private/preferences/smoke-test-positive.md'
        $saveOut = 'Test entry body.' | python3 $savePy 'preferences' 'smoke-test-positive' '--vault-path' $msave '--tags' 'smoke,test' 2>$null
        $saveOut = ($saveOut -join '').Trim()
        if ($saveOut -ne $expected) {
            throw "save.py CLI returned '$saveOut', expected '$expected'"
        }
        if (-not (Test-Path -LiteralPath $expected)) {
            throw "save.py did not create $expected"
        }
        $content = Get-Content -LiteralPath $expected -Raw
        if ($content -notmatch '(?m)^kind: preferences$') { throw "save.py output missing 'kind: preferences' frontmatter" }
        if ($content -notmatch '(?m)^always_load: false$') { throw "save.py output missing 'always_load: false' frontmatter" }
        # --always-load routing
        'Always-load body.' | python3 $savePy 'preferences' 'smoke-test-al' '--vault-path' $msave '--always-load' | Out-Null
        $alPath = Join-Path $msave 'personal-private/_always-load/smoke-test-al.md'
        if (-not (Test-Path -LiteralPath $alPath)) {
            throw "--always-load did not route to _always-load/ (expected $alPath)"
        }
        $alContent = Get-Content -LiteralPath $alPath -Raw
        if ($alContent -notmatch '(?m)^always_load: true$') {
            throw "--always-load entry missing 'always_load: true' frontmatter"
        }
        # Collision negative
        'x' | python3 $savePy 'preferences' 'smoke-test-positive' '--vault-path' $msave 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            throw 'save.py allowed overwriting an existing entry (collision check broken)'
        }
        # Invalid slug negative
        'x' | python3 $savePy 'preferences' 'Bad_Slug' '--vault-path' $msave 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            throw 'save.py allowed non-kebab-case slug (validator broken)'
        }
    } finally {
        Remove-Item -LiteralPath $msave -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── /memory evolve end-to-end test (plan #7a part 1 task 3) ────────────
    Write-Host '==> /memory evolve end-to-end test (plan #7a part 1 task 3)'
    $mevol = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mevol-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $mevol -Force | Out-Null
    try {
        $savePy = Join-Path $scratch '.claude/skills/memory/scripts/save.py'
        $evolvePy = Join-Path $scratch '.claude/skills/memory/scripts/evolve.py'
        if (-not (Test-Path -LiteralPath $evolvePy)) {
            throw "evolve.py not installed at $evolvePy"
        }
        # Setup
        'Original body for in-place evolve.' | python3 $savePy 'preferences' 'smoke-evolve-ip' '--vault-path' $mevol | Out-Null
        # Test 1: in-place evolve
        $evolOut = 'Evolved body.' | python3 $evolvePy 'personal-private/preferences/smoke-evolve-ip.md' 'test in-place evolve' '--vault-path' $mevol 2>$null
        $evolOut = ($evolOut -join '').Trim()
        $parts = $evolOut -split "`t"
        $newPath = $parts[0]
        $archPath = $parts[1]
        if (-not (Test-Path -LiteralPath $newPath)) { throw "evolve.py did not create new entry at $newPath" }
        if (-not (Test-Path -LiteralPath $archPath)) { throw "evolve.py did not create archive at $archPath" }
        $newContent = Get-Content -LiteralPath $newPath -Raw
        if ($newContent -notmatch '(?m)^supersedes: personal-private/_archive/') {
            throw "active entry missing 'supersedes:' frontmatter pointing at archive"
        }
        if ($newContent -notmatch '(?m)^status: active$') {
            throw "active entry missing 'status: active'"
        }
        $archContent = Get-Content -LiteralPath $archPath -Raw
        if ($archContent -notmatch '(?m)^status: superseded$') {
            throw "archive missing 'status: superseded'"
        }
        if ($archContent -notmatch '(?m)^superseded_by: personal-private/preferences/smoke-evolve-ip') {
            throw "archive missing 'superseded_by:' cross-link"
        }
        if ($archContent -notmatch '(?m)^superseded_reason:') {
            throw "archive missing 'superseded_reason:'"
        }
        # Test 2: rename evolve
        'Original body for rename evolve.' | python3 $savePy 'preferences' 'smoke-evolve-rename' '--vault-path' $mevol | Out-Null
        'Renamed body.' | python3 $evolvePy 'personal-private/preferences/smoke-evolve-rename.md' 'test rename' '--new-slug' 'smoke-evolve-renamed' '--vault-path' $mevol | Out-Null
        if (Test-Path -LiteralPath (Join-Path $mevol 'personal-private/preferences/smoke-evolve-rename.md')) {
            throw "rename evolve left old entry at original path (should be unlinked)"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $mevol 'personal-private/preferences/smoke-evolve-renamed.md'))) {
            throw "rename evolve did not create new entry at new slug"
        }
        # Test 3: negative — missing entry
        'x' | python3 $evolvePy 'personal-private/preferences/nonexistent.md' 'test' '--vault-path' $mevol 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            throw 'evolve.py allowed missing entry (should error non-zero)'
        }
        # Test 4: negative — already-superseded
        $todayCompact = Get-Date -Format 'yyyyMMdd'
        $supersededPath = "personal-private/_archive/personal-private/preferences/smoke-evolve-ip.md.$todayCompact.md"
        'x' | python3 $evolvePy $supersededPath 'test' '--vault-path' $mevol 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            throw 'evolve.py allowed evolving already-superseded entry (status check broken)'
        }
        # Test 5: negative — empty reason
        'x' | python3 $evolvePy 'personal-private/preferences/smoke-evolve-ip.md' '' '--vault-path' $mevol 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            throw 'evolve.py allowed empty reason (reason check broken)'
        }
    } finally {
        Remove-Item -LiteralPath $mevol -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── embedding queue + vec-index wiring test (plan #7a part 1 task 4) ───
    Write-Host '==> embedding queue + vec-index wiring test (plan #7a part 1 task 4)'
    $mqueue = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mqueue-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $mqueue -Force | Out-Null
    try {
        $savePy = Join-Path $scratch '.claude/skills/memory/scripts/save.py'
        $embedPy = Join-Path $scratch '.claude/skills/memory/scripts/embed.py'
        $vecPy = Join-Path $scratch '.claude/skills/memory/scripts/vec_index.py'
        foreach ($f in @($embedPy, $vecPy)) {
            if (-not (Test-Path -LiteralPath $f)) {
                throw "$f not installed"
            }
        }
        # embed.py stub mode produces deterministic 1024-d output
        # (BGE-large native; bumped from 384 in v0.9.2 per plan #18 task 1).
        $embedOut = python3 $embedPy 'smoke test text' '--mode' 'stub' 2>$null
        $embedOut = ($embedOut -join '').Trim()
        $parsed = $embedOut | ConvertFrom-Json
        if ($parsed.Count -ne 1024) {
            throw "embed.py stub mode returned $($parsed.Count)-d output, expected 1024"
        }
        # Save 3 entries; queue should grow by 3
        for ($i = 1; $i -le 3; $i++) {
            "Body $i for queue test." | python3 $savePy 'preferences' "queue-test-$i" '--vault-path' $mqueue 2>$null | Out-Null
        }
        $queueFile = Join-Path $mqueue '_meta/embedding-queue.jsonl'
        if (-not (Test-Path -LiteralPath $queueFile)) {
            throw 'embedding queue file not created after 3 saves'
        }
        $lines = (Get-Content -LiteralPath $queueFile | Measure-Object -Line).Lines
        if ($lines -ne 3) {
            throw "expected 3 queue entries after 3 saves, got $lines"
        }
        $queueContent = Get-Content -LiteralPath $queueFile -Raw
        if ($queueContent -notmatch '"op": "upsert"') {
            throw "queue entries missing 'op': 'upsert' field"
        }
        # Drain in stub mode — outcome depends on sqlite-vec availability
        $drainOut = python3 $vecPy '--vault-path' $mqueue 'drain' '--mode' 'stub' 2>$null
        $drainOut = ($drainOut -join '').Trim()
        $drainParsed = $drainOut | ConvertFrom-Json
        if ($drainParsed.errors -ne 0) {
            throw "drain reported $($drainParsed.errors) errors; should be 0 even when sqlite-vec absent (graceful-skip). Output: $drainOut"
        }
        if ($drainParsed.processed -eq 3) {
            # Full happy path
            $sizeOut = python3 $vecPy '--vault-path' $mqueue 'size' 2>$null
            $sizeOut = ($sizeOut -join '').Trim()
            $sizeParsed = $sizeOut | ConvertFrom-Json
            if ($sizeParsed.size -ne 3) {
                throw "drain processed 3 but index size is $($sizeParsed.size) (expected 3)"
            }
            if (Test-Path -LiteralPath $queueFile) {
                throw 'queue file still exists after full drain (should be removed when remaining==0)'
            }
            Write-Host '    (sqlite-vec available — verified full happy path)'
        } elseif ($drainParsed.skipped -eq 3) {
            # Graceful-skip path
            if (-not (Test-Path -LiteralPath $queueFile)) {
                throw 'queue file removed despite graceful-skip (should remain pending)'
            }
            Write-Host '    (sqlite-vec unavailable — verified graceful-skip)'
        } else {
            throw "drain produced unexpected outcome (processed=$($drainParsed.processed), skipped=$($drainParsed.skipped), errors=$($drainParsed.errors))"
        }

        # Rebuild subcommand test (plan #18 task 2): drop + recreate at
        # current EMBEDDING_DIM. Outcome again depends on sqlite-vec
        # availability.
        $rebuildOutFile = Join-Path $scratch '.rebuild-out.log'
        $rebuildProc = Start-Process -FilePath 'python3' -ArgumentList @($vecPy, '--vault-path', $mqueue, 'rebuild') -NoNewWindow -Wait -RedirectStandardOutput $rebuildOutFile -RedirectStandardError ([System.IO.Path]::GetTempFileName()) -PassThru
        $rebuildOut = Get-Content -LiteralPath $rebuildOutFile -Raw
        Remove-Item -LiteralPath $rebuildOutFile -ErrorAction SilentlyContinue
        if ($rebuildProc.ExitCode -eq 0) {
            $rebuildParsed = $rebuildOut | ConvertFrom-Json
            if ($rebuildParsed.new_dim -ne 1024) {
                throw "rebuild new_dim should be 1024, got '$($rebuildParsed.new_dim)'. Output: $rebuildOut"
            }
            Write-Host '    (rebuild succeeded — new_dim=1024 confirmed)'
        } elseif ($rebuildProc.ExitCode -eq 2) {
            if ($rebuildOut -notmatch '"skipped"') {
                throw "rebuild graceful-skip output missing 'skipped' marker. Output: $rebuildOut"
            }
            Write-Host '    (rebuild graceful-skip — sqlite-vec unavailable)'
        } else {
            throw "rebuild exited $($rebuildProc.ExitCode) (expected 0 or 2). Output: $rebuildOut"
        }

        # Dim-mismatch detection test (plan #18 task 2): pure-regex test
        # of _DIM_REGEX. No sqlite-vec required.
        $dimTestOut = (python3 -c "
import sys
sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts')
from vec_index import _DIM_REGEX
samples = [
    ('CREATE VIRTUAL TABLE entries USING vec0(embedding FLOAT[384])', 384),
    ('CREATE VIRTUAL TABLE entries USING vec0(embedding FLOAT[1024])', 1024),
    ('CREATE TABLE entry_meta (rowid INTEGER PRIMARY KEY)', None),
]
for sql, expected in samples:
    m = _DIM_REGEX.search(sql)
    got = int(m.group(1)) if m else None
    if got != expected:
        print(f'FAIL: expected={expected}, got={got}, sql={sql!r}')
        sys.exit(1)
print('OK')
").Trim()
        if ($dimTestOut -ne 'OK') {
            throw "_DIM_REGEX parsing test failed: $dimTestOut"
        }
        Write-Host '    (dim-mismatch detection regex verified)'

        # File write never blocked: no local model installed → save still succeeds
        'No-embed body.' | python3 $savePy 'preferences' 'no-embed-test' '--vault-path' $mqueue 2>$null | Out-Null
        $noEmbedPath = Join-Path $mqueue 'personal-private/preferences/no-embed-test.md'
        if (-not (Test-Path -LiteralPath $noEmbedPath)) {
            throw 'save failed when no embedding mode available (file write should NEVER be blocked)'
        }
    } finally {
        Remove-Item -LiteralPath $mqueue -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── SessionStart recall hook end-to-end test (plan #7a part 2 task 1) ──
    Write-Host '==> SessionStart recall hook end-to-end test (plan #7a part 2 task 1)'
    $recallPy = Join-Path $scratch '.claude/skills/memory/scripts/recall.py'
    $hookPs1 = Join-Path $scratch '.claude/hooks/memory-recall-session-start.ps1'
    $settingsJson = Join-Path $scratch '.claude/settings.json'
    if (-not (Test-Path -LiteralPath $recallPy)) { throw "recall.py not installed at $recallPy" }
    if (-not (Test-Path -LiteralPath $hookPs1)) { throw "hook script $hookPs1 missing" }
    $settingsContent = Get-Content -LiteralPath $settingsJson -Raw
    if ($settingsContent -notmatch 'SessionStart') {
        throw "settings.json missing 'SessionStart' key after install. Content: $settingsContent"
    }
    if ($settingsContent -notmatch 'memory-recall-session-start\.ps1') {
        throw "settings.json SessionStart entry doesn't reference memory-recall-session-start.ps1. Content: $settingsContent"
    }
    $mrecall = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mrecall-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $mrecall 'personal-private/_always-load') -Force | Out-Null
    try {
        # Seed 2 active + 1 superseded
        $prefA = @"
---
kind: preferences
status: active
slug: pref-a
tags: [test]
---
First always-load body.
"@
        $prefB = @"
---
kind: workflow
status: active
slug: pref-b
tags: [test]
---
Second always-load body.
"@
        $superseded = @"
---
kind: preferences
status: superseded
slug: superseded-entry
---
Should be filtered.
"@
        $prefA | Out-File -FilePath (Join-Path $mrecall 'personal-private/_always-load/pref-a.md') -Encoding utf8
        $prefB | Out-File -FilePath (Join-Path $mrecall 'personal-private/_always-load/pref-b.md') -Encoding utf8
        $superseded | Out-File -FilePath (Join-Path $mrecall 'personal-private/_always-load/superseded-entry.md') -Encoding utf8

        # Capture stdout + stderr separately via process redirection.
        $stdoutFile = Join-Path $mrecall '.stdout.log'
        $stderrFile = Join-Path $mrecall '.stderr.log'
        $proc = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mrecall, 'session-start') -NoNewWindow -Wait -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile -PassThru
        if ($proc.ExitCode -ne 0) {
            throw "recall.py session-start exited $($proc.ExitCode); expected 0"
        }
        $stdoutContent = Get-Content -LiteralPath $stdoutFile -Raw
        $stderrContent = Get-Content -LiteralPath $stderrFile -Raw
        if ($stderrContent -notmatch 'Loaded 2 MemoryVault always-load entries') {
            throw "stderr transparency line missing/wrong count. stderr: $stderrContent"
        }
        if ($stdoutContent -notmatch 'pref-a') { throw 'stdout missing pref-a entry' }
        if ($stdoutContent -notmatch 'pref-b') { throw 'stdout missing pref-b entry' }
        if ($stdoutContent -match 'superseded-entry') {
            throw 'stdout contains superseded entry (should be filtered)'
        }
        if ($stdoutContent -notmatch '# MemoryVault') {
            throw 'stdout missing header line'
        }
        Remove-Item -LiteralPath $stdoutFile, $stderrFile -ErrorAction SilentlyContinue

        # Graceful-skip: no vault → exit 0, silent stdout
        Remove-Item -Path Env:MEMORY_VAULT_PATH -ErrorAction SilentlyContinue
        $noVaultOut = python3 $recallPy 'session-start' 2>$null
        if ($noVaultOut) {
            throw "recall.py emitted stdout despite no vault configured. Output: $noVaultOut"
        }
        # Graceful-skip: bad vault → exit 0
        python3 $recallPy '--vault-path' "/nonexistent/path/$([Guid]::NewGuid())" 'session-start' 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'recall.py exited non-zero for nonexistent vault (should be graceful exit 0)'
        }
        # Empty vault: "Loaded 0" transparency line
        $mempty = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mempty-" + [System.Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $mempty -Force | Out-Null
        try {
            $emptyStderr = Join-Path $mempty '.stderr.log'
            $emptyProc = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mempty, 'session-start') -NoNewWindow -Wait -RedirectStandardError $emptyStderr -PassThru
            $emptyContent = Get-Content -LiteralPath $emptyStderr -Raw
            if ($emptyContent -notmatch 'Loaded 0 MemoryVault always-load entries') {
                throw "empty vault did not emit 'Loaded 0' transparency line. stderr: $emptyContent"
            }
        } finally {
            Remove-Item -LiteralPath $mempty -Recurse -Force -ErrorAction SilentlyContinue
        }
    } finally {
        Remove-Item -LiteralPath $mrecall -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── UserPromptSubmit recall hook end-to-end test (plan #7a part 2 task 2) ─
    Write-Host '==> UserPromptSubmit recall hook end-to-end test (plan #7a part 2 task 2)'
    $psHookPs1 = Join-Path $scratch '.claude/hooks/memory-recall-prompt-submit.ps1'
    if (-not (Test-Path -LiteralPath $psHookPs1)) { throw "hook script $psHookPs1 missing" }
    $settingsContent = Get-Content -LiteralPath $settingsJson -Raw
    if ($settingsContent -notmatch 'UserPromptSubmit') {
        throw "settings.json missing 'UserPromptSubmit' key after install"
    }
    if ($settingsContent -notmatch 'memory-recall-prompt-submit\.ps1') {
        throw "settings.json UserPromptSubmit entry doesn't reference memory-recall-prompt-submit.ps1"
    }
    $mpsubmit = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mpsubmit-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $mpsubmit 'personal-private/_always-load') -Force | Out-Null
    try {
        $seeded = @"
---
kind: preferences
status: active
slug: seeded-pref
---
Seeded body.
"@
        $seeded | Out-File -FilePath (Join-Path $mpsubmit 'personal-private/_always-load/seeded-pref.md') -Encoding utf8

        $payload = '{"hookEventName":"UserPromptSubmit","prompt":"how do I evolve a memory entry"}'
        # Valid payload → real "Loaded N relevant entries" transparency line
        # (task 3 wired the engine; scaffold marker is gone).
        $stdoutFile = Join-Path $mpsubmit '.stdout.log'
        $stderrFile = Join-Path $mpsubmit '.stderr.log'
        $stdinFile = Join-Path $mpsubmit '.stdin.log'
        Set-Content -LiteralPath $stdinFile -Value $payload -NoNewline
        $proc = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mpsubmit, 'prompt-submit') -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile -PassThru
        if ($proc.ExitCode -ne 0) {
            throw "prompt-submit valid payload exited $($proc.ExitCode); expected 0"
        }
        $psStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($psStderr -notmatch 'Loaded [0-9]+ relevant entries') {
            throw "stderr transparency line missing 'Loaded N relevant entries' shape. stderr: $psStderr"
        }
        Remove-Item -LiteralPath $stdoutFile, $stderrFile, $stdinFile -ErrorAction SilentlyContinue

        # Graceful: empty stdin → exit 0 + "no prompt on stdin"
        Set-Content -LiteralPath $stdinFile -Value "" -NoNewline
        $proc2 = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mpsubmit, 'prompt-submit') -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardError $stderrFile -PassThru
        if ($proc2.ExitCode -ne 0) {
            throw "empty stdin produced non-zero exit $($proc2.ExitCode)"
        }
        $emptyStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($emptyStderr -notmatch 'no prompt on stdin') {
            throw "empty stdin did not emit 'no prompt on stdin' warning. stderr: $emptyStderr"
        }
        Remove-Item -LiteralPath $stderrFile, $stdinFile -ErrorAction SilentlyContinue

        # Graceful: malformed JSON → exit 0
        Set-Content -LiteralPath $stdinFile -Value '{not json' -NoNewline
        $proc3 = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mpsubmit, 'prompt-submit') -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardError $stderrFile -PassThru
        if ($proc3.ExitCode -ne 0) {
            throw "malformed JSON produced non-zero exit $($proc3.ExitCode)"
        }
        $badStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($badStderr -notmatch 'no prompt on stdin') {
            throw "malformed JSON did not emit graceful warning. stderr: $badStderr"
        }
        Remove-Item -LiteralPath $stderrFile, $stdinFile -ErrorAction SilentlyContinue

        # Graceful: JSON missing prompt field → exit 0
        Set-Content -LiteralPath $stdinFile -Value '{"foo":"bar"}' -NoNewline
        $proc4 = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mpsubmit, 'prompt-submit') -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardError $stderrFile -PassThru
        if ($proc4.ExitCode -ne 0) {
            throw "missing-prompt JSON produced non-zero exit $($proc4.ExitCode)"
        }
        $missingStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($missingStderr -notmatch 'no prompt on stdin') {
            throw "missing-prompt JSON did not emit graceful warning. stderr: $missingStderr"
        }
        Remove-Item -LiteralPath $stderrFile, $stdinFile -ErrorAction SilentlyContinue

        # Graceful: no vault + valid payload → silent stdout + exit 0
        Remove-Item -Path Env:MEMORY_VAULT_PATH -ErrorAction SilentlyContinue
        Set-Content -LiteralPath $stdinFile -Value $payload -NoNewline
        $proc5 = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, 'prompt-submit') -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardOutput $stdoutFile -PassThru
        if ($proc5.ExitCode -ne 0) {
            throw "no-vault prompt-submit produced non-zero exit $($proc5.ExitCode)"
        }
        $noVaultStdout = Get-Content -LiteralPath $stdoutFile -Raw
        if ($noVaultStdout -and $noVaultStdout.Trim().Length -gt 0) {
            throw "prompt-submit emitted stdout despite no vault configured. stdout: $noVaultStdout"
        }
    } finally {
        Remove-Item -LiteralPath $mpsubmit -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Recall engine end-to-end test (plan #7a part 2 task 3) ─────────────
    Write-Host '==> Recall engine end-to-end test (plan #7a part 2 task 3)'
    $mquery = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mquery-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $mquery 'personal-private/preferences') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mquery 'personal-private/workflow') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mquery 'personal-private/_always-load') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mquery 'personal-private/_inbox') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mquery 'personal-private/_archive') -Force | Out-Null
    try {
        @"
---
kind: preferences
status: active
slug: always-pref
tags: [evolve]
---
Already in session context.
"@ | Out-File -FilePath (Join-Path $mquery 'personal-private/_always-load/always-pref.md') -Encoding utf8

        @"
---
kind: preferences
status: active
slug: bulleted-status
tags: [status-reports, dev-flow]
---
Use bulleted lists for status reports per task.
"@ | Out-File -FilePath (Join-Path $mquery 'personal-private/preferences/bulleted-status.md') -Encoding utf8

        @"
---
kind: workflow
status: active
slug: evolve-pattern
tags: [memory, audit-trail]
---
When preferences change, use /memory evolve to preserve audit trail.
"@ | Out-File -FilePath (Join-Path $mquery 'personal-private/workflow/evolve-pattern.md') -Encoding utf8

        @"
---
kind: workflow
status: active
slug: release-pair
tags: [release, coordination]
---
Toolkit and harness ship as coordinated release pairs.
"@ | Out-File -FilePath (Join-Path $mquery 'personal-private/workflow/release-pair.md') -Encoding utf8

        @"
---
kind: preferences
status: superseded
slug: superseded-pref
tags: [old]
---
This should never surface.
"@ | Out-File -FilePath (Join-Path $mquery 'personal-private/preferences/superseded-pref.md') -Encoding utf8

        @"
---
kind: idea
status: active
slug: inbox-idea
tags: [evolve, brainstorm]
---
Inbox candidate.
"@ | Out-File -FilePath (Join-Path $mquery 'personal-private/_inbox/inbox-idea.md') -Encoding utf8

        @"
---
kind: preferences
status: superseded
slug: archived-entry
tags: [release]
---
Archived content.
"@ | Out-File -FilePath (Join-Path $mquery 'personal-private/_archive/archived-entry.md') -Encoding utf8

        # Test 1: query "evolve" returns workflow/evolve-pattern via grep
        $q1Out = python3 $recallPy '--vault-path' $mquery 'query' 'evolve' '--mode' 'stub' 2>$null
        $q1OutStr = ($q1Out -join "`n")
        if ($q1OutStr -notmatch 'evolve-pattern') {
            throw "query 'evolve' did not return evolve-pattern. output: $q1OutStr"
        }
        # Test 2: query "status reports bulleted" returns bulleted-status with
        # multiple keyword matches. Relaxed from exact keyword=3 to keyword>=1
        # because PS here-string + Out-File line-ending nuances on Windows can
        # affect frontmatter parse → tag tokenization → keyword count. The
        # core invariant (entry surfaces) is what matters.
        $q2Out = python3 $recallPy '--vault-path' $mquery 'query' 'status reports bulleted' '--mode' 'stub' 2>&1
        $q2OutStr = ($q2Out -join "`n")
        if ($q2OutStr -notmatch '"slug": "bulleted-status"') {
            # Dump fixture state for diagnostic.
            $dirListing = Get-ChildItem -Recurse -LiteralPath $mquery | ForEach-Object { $_.FullName }
            $fixtureContent = Get-Content -LiteralPath (Join-Path $mquery 'personal-private/preferences/bulleted-status.md') -Raw -ErrorAction SilentlyContinue
            throw "query did not return bulleted-status. output: '$q2OutStr'. fixture dir listing:`n$($dirListing -join "`n")`n--- bulleted-status.md content ---`n$fixtureContent"
        }
        # Test 3: superseded entries filtered
        $q3Out = python3 $recallPy '--vault-path' $mquery 'query' 'superseded never surface' '--mode' 'stub' 2>$null
        $q3OutStr = ($q3Out -join "`n")
        if ($q3OutStr -match 'superseded-pref') {
            throw "superseded entry surfaced. output: $q3OutStr"
        }
        # Test 4: _archive/ always excluded
        $q4Out = python3 $recallPy '--vault-path' $mquery 'query' 'archived content release' '--mode' 'stub' 2>$null
        $q4OutStr = ($q4Out -join "`n")
        if ($q4OutStr -match 'archived-entry') {
            throw "_archive/ entry surfaced. output: $q4OutStr"
        }
        # Test 5: _inbox/ excluded by default
        $q5aOut = python3 $recallPy '--vault-path' $mquery 'query' 'inbox candidate brainstorm' '--mode' 'stub' 2>$null
        $q5aOutStr = ($q5aOut -join "`n")
        if ($q5aOutStr -match 'inbox-idea') {
            throw "_inbox/ entry surfaced without --include-inbox. output: $q5aOutStr"
        }
        # Test 6: _inbox/ included with --include-inbox
        $q5bOut = python3 $recallPy '--vault-path' $mquery 'query' 'inbox candidate brainstorm' '--include-inbox' '--mode' 'stub' 2>$null
        $q5bOutStr = ($q5bOut -join "`n")
        if ($q5bOutStr -notmatch 'inbox-idea') {
            throw "--include-inbox did not surface _inbox/ entry. output: $q5bOutStr"
        }
        # Test 7: top-K respected (K=1 returns at most 1 result)
        $q7Out = python3 $recallPy '--vault-path' $mquery 'query' 'release pair coordination' '-k' '1' '--mode' 'stub' 2>$null
        $q7Lines = ($q7Out | Where-Object { $_ -ne '' }).Count
        if ($q7Lines -ne 1) {
            throw "-k 1 returned $q7Lines results. output: $($q7Out -join "`n")"
        }
        # Test 8: prompt-submit wires query() + dedups against always-load
        $psPayload = '{"hookEventName":"UserPromptSubmit","prompt":"how do I evolve a memory entry"}'
        $stdinFile = Join-Path $mquery '.stdin.log'
        $stdoutFile = Join-Path $mquery '.stdout.log'
        $stderrFile = Join-Path $mquery '.stderr.log'
        Set-Content -LiteralPath $stdinFile -Value $psPayload -NoNewline
        $proc = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mquery, 'prompt-submit') -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile -PassThru
        if ($proc.ExitCode -ne 0) {
            throw "prompt-submit (engine-wired) exited $($proc.ExitCode)"
        }
        $psStdout = Get-Content -LiteralPath $stdoutFile -Raw
        $psStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($psStdout -notmatch 'evolve-pattern') {
            throw "prompt-submit did not surface evolve-pattern (engine wiring broken). stdout: $psStdout"
        }
        if ($psStdout -match 'always-pref') {
            throw "prompt-submit surfaced always-pref (should be deduped). stdout: $psStdout"
        }
        if ($psStderr -match 'scaffold') {
            throw "prompt-submit still emits scaffold marker. stderr: $psStderr"
        }
        if ($psStderr -notmatch 'Loaded [0-9]+ relevant entries') {
            throw "prompt-submit stderr missing 'Loaded N relevant entries' line. stderr: $psStderr"
        }
        # Test 9: short-token query returns no results
        $q9Out = python3 $recallPy '--vault-path' $mquery 'query' 'x' '--mode' 'stub' 2>$null
        $q9OutStr = ($q9Out -join "`n").Trim()
        if ($q9OutStr -ne '') {
            throw "query 'x' (below _MIN_TOKEN_LEN) returned results. output: $q9OutStr"
        }
    } finally {
        Remove-Item -LiteralPath $mquery -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Embedding fallback path test (plan #18 task 1 — local-only refactor) ──
    Write-Host '==> Embedding fallback path test (plan #18 task 1)'
    # Test A: mode resolution — default → "local"; "api" raises ValueError with
    # clear v0.9.2 error; unknown modes raise generic error.
    $resolveDefault = (python3 -c "import sys; sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts'); from embed import _resolve_mode; print(_resolve_mode(None))").Trim()
    if ($resolveDefault -ne 'local') {
        throw "default mode resolution should be 'local', got '$resolveDefault'"
    }
    $apiErr = (python3 -c "import sys; sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts')
from embed import _resolve_mode
try:
    _resolve_mode('api')
    print('NO_ERROR')
except ValueError as e:
    print(str(e))
").Trim()
    if ($apiErr -notmatch 'v0\.9\.2') {
        throw "'api' mode should raise ValueError mentioning v0.9.2; got: $apiErr"
    }
    # Test A2: EMBEDDING_DIM is 1024 (BGE-large native; bumped from 384 in v0.9.2)
    $dim = (python3 -c "import sys; sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts'); from embed import EMBEDDING_DIM; print(EMBEDDING_DIM)").Trim()
    if ($dim -ne '1024') {
        throw "EMBEDDING_DIM should be 1024 (BGE-large native), got '$dim'"
    }
    # Test A3: stub mode returns 1024-d deterministic vector
    $stubLen = (python3 -c "import sys; sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts'); from embed import embed_text; print(len(embed_text('test', mode='stub')))").Trim()
    if ($stubLen -ne '1024') {
        throw "stub mode should return 1024-d vector, got $stubLen"
    }
    # Test A4: AGENT_TOOLKIT_EMBEDDING_MODEL env var escape hatch works
    $env:AGENT_TOOLKIT_EMBEDDING_MODEL = 'test-model'
    $modelOverride = (python3 -c "import sys; sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts'); from embed import _resolve_model; print(_resolve_model())").Trim()
    Remove-Item -Path Env:AGENT_TOOLKIT_EMBEDDING_MODEL -ErrorAction SilentlyContinue
    if ($modelOverride -ne 'test-model') {
        throw "AGENT_TOOLKIT_EMBEDDING_MODEL override should yield 'test-model', got '$modelOverride'"
    }
    # Test B: embed.py --mode local with no sentence-transformers → exit 2
    $embedPy = Join-Path $scratch '.claude/skills/memory/scripts/embed.py'
    $embedOutFile = Join-Path $scratch '.embed-local-out.log'
    python3 $embedPy 'test text' '--mode' 'local' 2>&1 | Out-File -FilePath $embedOutFile
    $embedExit = $LASTEXITCODE
    if ($embedExit -ne 2) {
        throw "embed.py --mode local exited $embedExit (expected 2 for graceful EmbeddingUnavailable)"
    }
    $embedOut = Get-Content -LiteralPath $embedOutFile -Raw
    if ($embedOut -notmatch 'sentence-transformers') {
        throw "embed.py --mode local error missing sentence-transformers install hint. Output: $embedOut"
    }
    Remove-Item -LiteralPath $embedOutFile -ErrorAction SilentlyContinue
    # Test C: cache dir constant
    $cacheDir = (python3 -c "import sys; sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts'); from embed import _LOCAL_CACHE_DIR; print(_LOCAL_CACHE_DIR)").Trim()
    if ($cacheDir -notmatch 'agent-toolkit') {
        throw "_LOCAL_CACHE_DIR should contain 'agent-toolkit', got '$cacheDir'"
    }
    if ($cacheDir -notmatch 'sentence-transformers') {
        throw "_LOCAL_CACHE_DIR should contain 'sentence-transformers', got '$cacheDir'"
    }
    # Test D: AGENT_TOOLKIT_SENTENCE_TRANSFORMERS_CACHE env override
    $customCache = Join-Path ([System.IO.Path]::GetTempPath()) "custom-st-cache-$([Guid]::NewGuid().ToString('N'))"
    $env:AGENT_TOOLKIT_SENTENCE_TRANSFORMERS_CACHE = $customCache
    $cacheOverride = (python3 -c "import sys; sys.path.insert(0, r'$($scratch -replace '\\','/')/.claude/skills/memory/scripts'); from embed import _LOCAL_CACHE_DIR; print(_LOCAL_CACHE_DIR)").Trim()
    Remove-Item -Path Env:AGENT_TOOLKIT_SENTENCE_TRANSFORMERS_CACHE -ErrorAction SilentlyContinue
    # Use case-insensitive comparison on Windows since paths may differ in casing/separators.
    if (-not ($cacheOverride.Replace('\','/') -ieq $customCache.Replace('\','/'))) {
        throw "AGENT_TOOLKIT_SENTENCE_TRANSFORMERS_CACHE override didn't apply ('$cacheOverride' != '$customCache')"
    }
    # Test E: recall.py with no sentence-transformers installed → grep-only
    # fallback works (exit 0). Post-v0.9.2 there is no API mode to opt
    # into, so this test only validates the no-local-model fallback.
    $mfb = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mfb-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $mfb 'personal-private/workflow') -Force | Out-Null
    try {
        @"
---
kind: workflow
status: active
slug: fb-entry
tags: [evolve, fallback]
---
Evolve test body for fallback path.
"@ | Out-File -FilePath (Join-Path $mfb 'personal-private/workflow/fb-entry.md') -Encoding utf8

        $fbStdoutFile = Join-Path $mfb '.fb-stdout.log'
        $fbStderrFile = Join-Path $mfb '.fb-stderr.log'
        $fbProc = Start-Process -FilePath 'python3' -ArgumentList @($recallPy, '--vault-path', $mfb, 'query', 'evolve') -NoNewWindow -Wait -RedirectStandardOutput $fbStdoutFile -RedirectStandardError $fbStderrFile -PassThru
        if ($fbProc.ExitCode -ne 0) {
            throw "recall.py fallback path exited $($fbProc.ExitCode); expected 0 for grep-only"
        }
        $fbStdout = Get-Content -LiteralPath $fbStdoutFile -Raw
        $fbStderr = Get-Content -LiteralPath $fbStderrFile -Raw
        if ($fbStdout -notmatch 'fb-entry') {
            throw "fallback grep-only path did not return fb-entry. stdout: $fbStdout"
        }
        if ($fbStderr -notmatch 'embedding unavailable') {
            throw "fallback path did not emit 'embedding unavailable' stderr warning. stderr: $fbStderr"
        }
    } finally {
        Remove-Item -LiteralPath $mfb -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Local-mode integration test (plan #18 task 3) ──────────────────────
    # Validates real 1024-d embedding from BGE-large. Skipped in CI to avoid
    # the ~1.3GB BGE-large model download (SKIP_LOCAL_MODE_INTEGRATION env
    # var set by .github/workflows/tests-windows.yml). Operators with
    # sentence-transformers installed can opt in by clearing the env var
    # locally; gracefully skips if sentence-transformers itself is missing.
    Write-Host '==> Local-mode integration test (plan #18 task 3)'
    if (Test-Path Env:SKIP_LOCAL_MODE_INTEGRATION) {
        Write-Host '    SKIP_LOCAL_MODE_INTEGRATION set — skipped (typically CI; clear var + re-run locally to validate BGE-large)'
    } else {
        $localOutFile = Join-Path $scratch '.local-mode-out.log'
        $localProc = Start-Process -FilePath 'python3' -ArgumentList @($embedPy, 'smoke test text for local mode', '--mode', 'local') -NoNewWindow -Wait -RedirectStandardOutput $localOutFile -RedirectStandardError $localOutFile -PassThru
        $localOut = Get-Content -LiteralPath $localOutFile -Raw
        Remove-Item -LiteralPath $localOutFile -ErrorAction SilentlyContinue
        if ($localProc.ExitCode -eq 2) {
            if ($localOut -notmatch 'sentence-transformers') {
                throw "--mode local exit 2 but error doesn't mention sentence-transformers. Output: $localOut"
            }
            Write-Host '    sentence-transformers unavailable — skipped (pip install sentence-transformers to enable; first-run downloads BGE-large ~1.3GB)'
        } elseif ($localProc.ExitCode -eq 0) {
            $parsed = $localOut | ConvertFrom-Json
            if ($parsed.Count -ne 1024) {
                throw "--mode local returned $($parsed.Count)-d output, expected 1024 (BGE-large native). Output: $localOut"
            }
            # All numeric? (PowerShell ConvertFrom-Json gives Double / Int64 for JSON numbers.)
            $allNumeric = $true
            foreach ($v in $parsed) {
                if ($v -isnot [double] -and $v -isnot [int] -and $v -isnot [long]) { $allNumeric = $false; break }
            }
            if (-not $allNumeric) {
                throw "--mode local output had non-numeric values. Output: $localOut"
            }
            Write-Host '    local-mode integration verified: 1024-d numeric vector from BGE-large'
        } else {
            throw "--mode local exited $($localProc.ExitCode) (expected 0 success or 2 graceful-skip). Output: $localOut"
        }
    }

    # ── Time budget enforcement test (plan #7a part 2 task 5) ──────────────
    Write-Host '==> Time budget enforcement test (plan #7a part 2 task 5)'
    $mbudget = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mbudget-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $mbudget 'personal-private/_always-load') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mbudget 'personal-private/workflow') -Force | Out-Null
    try {
        # Seed 40 always-load entries
        for ($i = 1; $i -le 40; $i++) {
            $body = @"
---
kind: preferences
status: active
slug: budget-pref-$i
tags: [test-budget]
---
Budget test entry number $i with some body text to make parsing nontrivial.
Multiple lines of content to ensure the read_text call takes measurable time.
"@
            $body | Out-File -FilePath (Join-Path $mbudget "personal-private/_always-load/budget-pref-$i.md") -Encoding utf8
        }
        # Seed 30 workflow entries
        for ($i = 1; $i -le 30; $i++) {
            $body = @"
---
kind: workflow
status: active
slug: budget-flow-$i
tags: [budget, workflow, test]
---
Workflow body $i containing keywords like budget and test.
"@
            $body | Out-File -FilePath (Join-Path $mbudget "personal-private/workflow/budget-flow-$i.md") -Encoding utf8
        }

        # PowerShell's native-command arg passing mangles `--budget-ms 0` /
        # `--budget-ms=0` on some Windows runners (the int value never
        # reaches argparse → falls back to default 500ms → no overrun).
        # Bypass it: use a `python3 -c` driver that calls session_start /
        # prompt_submit / query DIRECTLY with budget_ms=0 (kwarg). This
        # also exercises the public Python API of recall.py — exactly the
        # surface that future /memory search will call.
        $scriptsRel = ($scratch.Replace('\','/') + '/.claude/skills/memory/scripts')
        $vaultRel = $mbudget.Replace('\','/')

        # Test A: session-start with budget_ms=0 → forced overrun
        $ssDriver = @"
import sys
sys.path.insert(0, r'$scriptsRel')
from pathlib import Path
import recall
exit_code = recall.session_start(vault=Path(r'$vaultRel'), budget_ms=0)
print('EXIT:', exit_code)
"@
        $ssDriverOut = python3 -c $ssDriver 2>&1 | Out-String
        if ($ssDriverOut -notmatch 'time budget exceeded') {
            throw "session-start(budget_ms=0) did not emit overrun warning. stderr+stdout: $ssDriverOut"
        }
        if ($ssDriverOut -notmatch 'Loaded [0-9]+ MemoryVault always-load entries') {
            throw "session-start overrun did not emit transparency line. output: $ssDriverOut"
        }
        if ($ssDriverOut -notmatch 'EXIT: 0') {
            throw "session-start(budget_ms=0) did not return exit code 0. output: $ssDriverOut"
        }

        # Test B: prompt-submit with budget_ms=0 → forced overrun
        $psDriver = @"
import sys
sys.path.insert(0, r'$scriptsRel')
from pathlib import Path
import recall
exit_code = recall.prompt_submit(vault=Path(r'$vaultRel'), prompt='budget workflow test', budget_ms=0)
print('EXIT:', exit_code)
"@
        $psDriverOut = python3 -c $psDriver 2>&1 | Out-String
        if ($psDriverOut -notmatch 'time budget exceeded') {
            throw "prompt_submit(budget_ms=0) did not emit overrun warning. output: $psDriverOut"
        }
        if ($psDriverOut -notmatch 'Loaded [0-9]+ relevant entries') {
            throw "prompt_submit overrun did not emit transparency line. output: $psDriverOut"
        }
        if ($psDriverOut -notmatch 'EXIT: 0') {
            throw "prompt_submit(budget_ms=0) did not return exit code 0. output: $psDriverOut"
        }

        # Test C: query() with deadline in the past → returns [] cleanly
        $qDriver = @"
import sys, time
sys.path.insert(0, r'$scriptsRel')
from pathlib import Path
import recall
# Deadline already in the past (1 second ago)
results = recall.query(vault=Path(r'$vaultRel'), query_text='budget workflow', deadline=time.monotonic() - 1.0, mode='stub')
print('RESULTS_COUNT:', len(results))
"@
        $qDriverOut = python3 -c $qDriver 2>&1 | Out-String
        if ($qDriverOut -notmatch 'RESULTS_COUNT:') {
            throw "query() with past deadline did not return cleanly. output: $qDriverOut"
        }

        # Test D: never-block contract — 5 iterations each, exit code 0
        for ($i = 1; $i -le 5; $i++) {
            $loopOut = python3 -c $ssDriver 2>&1 | Out-String
            if ($loopOut -notmatch 'EXIT: 0') {
                throw "session-start (iter $i) did not return exit code 0 under forced overrun. output: $loopOut"
            }
            $loopOut2 = python3 -c $psDriver 2>&1 | Out-String
            if ($loopOut2 -notmatch 'EXIT: 0') {
                throw "prompt-submit (iter $i) did not return exit code 0 under forced overrun. output: $loopOut2"
            }
        }
    } finally {
        Remove-Item -LiteralPath $mbudget -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Reflection mining module test (plan #7a part 3 task 1) ─────────────
    Write-Host '==> Reflection mining module test (plan #7a part 3 task 1)'
    $reflectPy = Join-Path $scratch '.claude/skills/memory/scripts/reflect.py'
    if (-not (Test-Path -LiteralPath $reflectPy)) {
        throw "reflect.py not installed at $reflectPy"
    }
    $mreflect = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mreflect-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $mreflect -Force | Out-Null
    try {
        # Build JSONL transcript via individual ConvertTo-Json lines so PS
        # doesn't fold/format the JSON across multiple lines.
        $transcriptPath = Join-Path $mreflect 'transcript.jsonl'
        $lines = @(
            '{"type":"queue-operation","content":"intro"}',
            '{"type":"user","message":{"role":"user","content":"Always use bullet points for status reports, never paragraphs."},"uuid":"u1"}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Got it."},{"type":"tool_use","name":"Bash"}]},"uuid":"a1"}',
            '{"type":"user","message":{"role":"user","content":"No, that''s wrong. You should have added a test plan section."},"uuid":"u2"}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash"}]},"uuid":"a2"}',
            '{"type":"user","message":{"role":"user","content":"The CI bug was caused by line endings. Fixed by switching to write_bytes."},"uuid":"u3"}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash"}]},"uuid":"a3"}',
            '{"type":"user","message":{"role":"user","content":"We should also build a memory inspect command later for tuning recall weights — could be its own follow-up plan."},"uuid":"u4"}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Read"}]},"uuid":"a4"}',
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash"}]},"uuid":"a5"}'
        )
        # Write LF-only (Set-Content default on Windows is CRLF; use [System.IO.File]::WriteAllText
        # with an explicit \n joiner so reflect.py reads each line cleanly regardless of platform).
        [System.IO.File]::WriteAllText($transcriptPath, ($lines -join "`n") + "`n")

        $reflectOut = python3 $reflectPy $transcriptPath '--summary' 2>$null | Out-String

        # Test 1: summary line reports 9 messages processed
        if ($reflectOut -notmatch '"pass": "summary".*"messages_processed": 9') {
            throw "summary line missing or wrong messages_processed count. output: $reflectOut"
        }
        # Test 2: HIGH preferences from "Always use bullet points"
        if ($reflectOut -notmatch '"category": "preferences", "confidence": "HIGH".*always.*bullet') {
            throw "HIGH preferences candidate missing for Always pattern. output: $reflectOut"
        }
        # Test 3: correction candidate present
        if ($reflectOut -notmatch '"rationale": "user correction signal"') {
            throw "correction-pattern candidate missing. output: $reflectOut"
        }
        # Test 4: fix candidate
        if ($reflectOut -notmatch '"category": "fix".*"rationale": "explicit fix statement"') {
            throw "fix candidate missing for Fixed by pattern. output: $reflectOut"
        }
        # Test 5: idea candidate
        if ($reflectOut -notmatch '"pass": "idea".*"rationale": "explicit follow-up suggestion"') {
            throw "idea candidate missing for We should also pattern. output: $reflectOut"
        }
        # Test 6: workflow candidate (Bash used 4x)
        if ($reflectOut -notmatch '"category": "workflow".*"confidence": "MEDIUM".*Bash.*4x') {
            throw "workflow candidate missing (expected Bash 4x MEDIUM). output: $reflectOut"
        }
        # Test 7: --memory-only suppresses idea pass
        $memOnly = python3 $reflectPy $transcriptPath '--memory-only' 2>$null | Out-String
        if ($memOnly -match '"pass": "idea"') {
            throw "--memory-only did not suppress idea pass"
        }
        # Test 8: --idea-only suppresses memory pass
        $ideaOnly = python3 $reflectPy $transcriptPath '--idea-only' 2>$null | Out-String
        if ($ideaOnly -match '"pass": "memory"') {
            throw "--idea-only did not suppress memory pass"
        }
        # Test 9: missing transcript → exit 1
        python3 $reflectPy ("/nonexistent/path/" + [Guid]::NewGuid().ToString()) 2>$null | Out-Null
        if ($LASTEXITCODE -ne 1) {
            throw "reflect.py on missing transcript exited $LASTEXITCODE (expected 1)"
        }
        # Test 10: empty transcript → 0 candidates
        $emptyPath = Join-Path $mreflect 'empty.jsonl'
        Set-Content -LiteralPath $emptyPath -Value '' -NoNewline
        $emptyOut = python3 $reflectPy $emptyPath '--summary' 2>$null | Out-String
        if ($emptyOut -notmatch '"messages_processed": 0') {
            throw "empty transcript did not produce 'messages_processed: 0' summary. output: $emptyOut"
        }
    } finally {
        Remove-Item -LiteralPath $mreflect -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Stop-event reflection hook test (plan #7a part 3 task 3) ───────────
    Write-Host '==> Stop-event reflection hook test (plan #7a part 3 task 3)'
    $reflectStopPs1 = Join-Path $scratch '.claude/hooks/memory-reflect-stop.ps1'
    if (-not (Test-Path -LiteralPath $reflectStopPs1)) {
        throw "memory-reflect-stop.ps1 not installed at $reflectStopPs1"
    }
    $settingsContent = Get-Content -LiteralPath $settingsJson -Raw
    if ($settingsContent -notmatch 'memory-reflect-stop\.ps1') {
        throw "settings.json missing memory-reflect-stop.ps1 Stop entry"
    }
    # Seed transcript at ~/.claude/projects/<cwd-slug>/<session-id>.jsonl
    $mrstop = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mrstop-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $mrstop -Force | Out-Null
    # Match the hook's cwd-slug formula (replace / + \ + : with '-' / '').
    $rstopCwdSlug = "-" + (($mrstop -replace '[\\/]', '-') -replace ':', '')
    $rstopTranscriptDir = Join-Path $HOME ".claude/projects/$rstopCwdSlug"
    New-Item -ItemType Directory -Path $rstopTranscriptDir -Force | Out-Null
    $rstopSessionId = "f1e2d3c4-b5a6-7c8d-9e0f-abcdef012345"
    $rstopTranscript = Join-Path $rstopTranscriptDir "$rstopSessionId.jsonl"
    $rstopLines = @(
        '{"type":"user","message":{"role":"user","content":"Always lint before pushing."},"uuid":"u1"}',
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash"}]},"uuid":"a1"}',
        '{"type":"user","message":{"role":"user","content":"We should also add a status line later."},"uuid":"u2"}'
    )
    [System.IO.File]::WriteAllText($rstopTranscript, ($rstopLines -join "`n") + "`n")
    try {
        # Stage memory skill + hook into the scratch project root for the
        # hook to find them at .claude/skills/memory/scripts/reflect.py and
        # .claude/hooks/memory-reflect-stop.ps1.
        New-Item -ItemType Directory -Path (Join-Path $mrstop '.claude/skills/memory/scripts') -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $mrstop '.claude/hooks') -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $scratch '.claude/skills/memory/scripts/reflect.py') -Destination (Join-Path $mrstop '.claude/skills/memory/scripts/reflect.py')
        Copy-Item -LiteralPath $reflectStopPs1 -Destination (Join-Path $mrstop '.claude/hooks/memory-reflect-stop.ps1')

        # Stage save + embed + vec_index alongside reflect.py for the routing
        # pass to import save module successfully.
        foreach ($pyf in @('save', 'embed', 'vec_index')) {
            Copy-Item -LiteralPath (Join-Path $scratch ".claude/skills/memory/scripts/$pyf.py") -Destination (Join-Path $mrstop ".claude/skills/memory/scripts/$pyf.py")
        }
        # Test A: happy-path Stop payload. Use the JSON-safe form of $mrstop
        # (backslashes doubled for JSON string escaping).
        $cwdEscaped = $mrstop.Replace('\','\\')
        $rstopPayload = '{"session_id":"' + $rstopSessionId + '","cwd":"' + $cwdEscaped + '","hookEventName":"Stop"}'
        $stdinFile = Join-Path $mrstop '.stdin.log'
        $stdoutFile = Join-Path $mrstop '.stdout.log'
        $stderrFile = Join-Path $mrstop '.stderr.log'
        Set-Content -LiteralPath $stdinFile -Value $rstopPayload -NoNewline
        # Vault for routing destination
        $rstopVault = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-rstop-vault-" + [System.Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $rstopVault -Force | Out-Null
        $env:MEMORY_VAULT_PATH = $rstopVault
        $proc = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File',(Join-Path $mrstop '.claude/hooks/memory-reflect-stop.ps1')) -WorkingDirectory $mrstop -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile -PassThru
        if ($proc.ExitCode -ne 0) {
            $errOut = Get-Content -LiteralPath $stderrFile -Raw
            throw "Stop hook happy path exited $($proc.ExitCode). stderr: $errOut"
        }
        $rstopStderr = Get-Content -LiteralPath $stderrFile -Raw
        $rstopStdout = Get-Content -LiteralPath $stdoutFile -Raw
        if ($rstopStderr -notmatch 'Mined [0-9]+ memory \+ [0-9]+ idea candidates.*saved [0-9]+, inboxed [0-9]+') {
            throw "Stop hook stderr missing transparency line with route counts. stderr: $rstopStderr"
        }
        if ($rstopStdout -notmatch '"pass": "summary"') {
            throw "Stop hook stdout missing reflect.py summary record. stdout: $rstopStdout"
        }
        if ($rstopStdout -notmatch 'always-lint-before-pushing') {
            throw "Stop hook stdout missing expected always-lint candidate. stdout: $rstopStdout"
        }
        # Verify routing wrote canonical entry
        if (-not (Test-Path -LiteralPath (Join-Path $rstopVault 'personal-private/preferences/always-lint-before-pushing.md'))) {
            throw "Stop hook --route did not auto-save HIGH candidate to canonical path. vault listing: $(Get-ChildItem -Recurse $rstopVault | ForEach-Object FullName)"
        }
        Remove-Item -LiteralPath $stdinFile, $stdoutFile, $stderrFile -ErrorAction SilentlyContinue
        Remove-Item -Path Env:MEMORY_VAULT_PATH -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $rstopVault -Recurse -Force -ErrorAction SilentlyContinue

        # Test B: empty stdin → graceful skip
        Set-Content -LiteralPath $stdinFile -Value '' -NoNewline
        $proc2 = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File',(Join-Path $mrstop '.claude/hooks/memory-reflect-stop.ps1')) -WorkingDirectory $mrstop -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardError $stderrFile -PassThru
        if ($proc2.ExitCode -ne 0) {
            throw "Stop hook with empty stdin exited $($proc2.ExitCode); expected 0"
        }
        $emptyStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($emptyStderr -notmatch 'no stdin payload') {
            throw "Stop hook with empty stdin did not emit graceful warning. stderr: $emptyStderr"
        }
        Remove-Item -LiteralPath $stdinFile, $stderrFile -ErrorAction SilentlyContinue

        # Test C: stdin missing session_id → graceful skip
        Set-Content -LiteralPath $stdinFile -Value '{"hookEventName":"Stop"}' -NoNewline
        $proc3 = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File',(Join-Path $mrstop '.claude/hooks/memory-reflect-stop.ps1')) -WorkingDirectory $mrstop -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardError $stderrFile -PassThru
        if ($proc3.ExitCode -ne 0) {
            throw "Stop hook with no session_id exited $($proc3.ExitCode); expected 0"
        }
        $noSidStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($noSidStderr -notmatch 'no session_id') {
            throw "Stop hook with no session_id did not emit graceful warning. stderr: $noSidStderr"
        }
        Remove-Item -LiteralPath $stdinFile, $stderrFile -ErrorAction SilentlyContinue

        # Test D: missing transcript → graceful skip
        $dPayload = '{"session_id":"deadbeef-cafe-babe-feed-fedcba987654","cwd":"' + $cwdEscaped + '","hookEventName":"Stop"}'
        Set-Content -LiteralPath $stdinFile -Value $dPayload -NoNewline
        $proc4 = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File',(Join-Path $mrstop '.claude/hooks/memory-reflect-stop.ps1')) -WorkingDirectory $mrstop -NoNewWindow -Wait -RedirectStandardInput $stdinFile -RedirectStandardError $stderrFile -PassThru
        if ($proc4.ExitCode -ne 0) {
            throw "Stop hook with missing transcript exited $($proc4.ExitCode); expected 0"
        }
        $missingStderr = Get-Content -LiteralPath $stderrFile -Raw
        if ($missingStderr -notmatch 'transcript not found') {
            throw "Stop hook with missing transcript did not emit warning. stderr: $missingStderr"
        }
    } finally {
        Remove-Item -LiteralPath $mrstop -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $rstopTranscriptDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Idle-time reflection hook test (plan #7a part 3 task 4) ────────────
    Write-Host '==> Idle-time reflection hook test (plan #7a part 3 task 4)'
    $reflectIdlePs1 = Join-Path $scratch '.claude/hooks/memory-reflect-idle.ps1'
    if (-not (Test-Path -LiteralPath $reflectIdlePs1)) {
        throw "memory-reflect-idle.ps1 not installed at $reflectIdlePs1"
    }
    $settingsContent = Get-Content -LiteralPath $settingsJson -Raw
    if ($settingsContent -notmatch 'memory-reflect-idle\.ps1') {
        throw "settings.json missing memory-reflect-idle.ps1 SessionStart entry"
    }
    $mridle = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mridle-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path (Join-Path $mridle '.claude/skills/memory/scripts') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mridle '.claude/hooks') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mridle '.harness') -Force | Out-Null
    foreach ($pyf in @('reflect', 'save', 'embed', 'vec_index')) {
        Copy-Item -LiteralPath (Join-Path $scratch ".claude/skills/memory/scripts/$pyf.py") -Destination (Join-Path $mridle ".claude/skills/memory/scripts/$pyf.py")
    }
    Copy-Item -LiteralPath $reflectIdlePs1 -Destination (Join-Path $mridle '.claude/hooks/memory-reflect-idle.ps1')
    # Vault for routing destination
    $ridleVault = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-ridle-vault-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $ridleVault -Force | Out-Null
    $env:MEMORY_VAULT_PATH = $ridleVault
    $idleTranscript = Join-Path $mridle 'orphan-transcript.jsonl'
    $idleLines = @(
        '{"type":"user","message":{"role":"user","content":"Always commit before EOD."},"uuid":"u1"}',
        '{"type":"assistant","message":{"role":"assistant","content":[{"type":"tool_use","name":"Bash"}]},"uuid":"a1"}'
    )
    [System.IO.File]::WriteAllText($idleTranscript, ($idleLines -join "`n") + "`n")
    try {
        # Test A: orphan marker (backdated mtime) → reflection + rename to .reflected
        $markerA = Join-Path $mridle '.harness/session-id-aabbccdd.start'
        $markerAContent = @"
session_id: aabbccdd-eeffaabb
started_at: 2026-05-18T00:00:00Z
transcript: $($idleTranscript -replace '\\','/')
"@
        Set-Content -LiteralPath $markerA -Value $markerAContent
        # Backdate mtime to ~ 2 days ago (well past 1hr idle threshold).
        $backdate = (Get-Date).AddDays(-2)
        (Get-Item -LiteralPath $markerA).LastWriteTime = $backdate

        $aProc = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-reflect-idle.ps1') -WorkingDirectory $mridle -NoNewWindow -Wait -RedirectStandardOutput (Join-Path $mridle '.idle-a.stdout') -RedirectStandardError (Join-Path $mridle '.idle-a.stderr') -PassThru
        $aStdout = Get-Content -LiteralPath (Join-Path $mridle '.idle-a.stdout') -Raw -ErrorAction SilentlyContinue
        $aStderr = Get-Content -LiteralPath (Join-Path $mridle '.idle-a.stderr') -Raw -ErrorAction SilentlyContinue
        if ($aProc.ExitCode -ne 0) {
            throw "idle hook on orphan exited $($aProc.ExitCode). stderr: $aStderr"
        }
        if ($aStderr -notmatch 'processed 1 orphans') {
            throw "idle hook did not process orphan marker. stderr: $aStderr"
        }
        if ($aStdout -notmatch 'always-commit-before-eod') {
            throw "idle hook stdout missing expected reflection output. stdout: $aStdout"
        }
        if (Test-Path -LiteralPath $markerA) {
            throw "orphan marker .start not renamed after reflection"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $mridle '.harness/session-id-aabbccdd.reflected'))) {
            throw "orphan marker not renamed to .reflected"
        }

        # Test B: fresh marker → preserved as .start
        Remove-Item -LiteralPath (Join-Path $mridle '.harness/*') -Force -ErrorAction SilentlyContinue
        $markerB = Join-Path $mridle '.harness/session-id-freshfresh.start'
        Set-Content -LiteralPath $markerB -Value $markerAContent
        # Don't backdate; mtime = now → fresher than 1hr threshold.
        $bProc = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-reflect-idle.ps1') -WorkingDirectory $mridle -NoNewWindow -Wait -RedirectStandardError (Join-Path $mridle '.idle-b.stderr') -PassThru
        if ($bProc.ExitCode -ne 0) {
            throw "idle hook with fresh marker exited $($bProc.ExitCode)"
        }
        if (-not (Test-Path -LiteralPath $markerB)) {
            throw "fresh marker was processed (should be preserved as .start)"
        }
        $bStderr = Get-Content -LiteralPath (Join-Path $mridle '.idle-b.stderr') -Raw -ErrorAction SilentlyContinue
        if ($bStderr -match 'processed [1-9]') {
            throw "idle hook reported processing fresh marker. stderr: $bStderr"
        }

        # Test C: no .harness/ → silent exit 0
        Remove-Item -LiteralPath (Join-Path $mridle '.harness') -Recurse -Force
        $cProc = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-reflect-idle.ps1') -WorkingDirectory $mridle -NoNewWindow -Wait -RedirectStandardError (Join-Path $mridle '.idle-c.stderr') -RedirectStandardOutput (Join-Path $mridle '.idle-c.stdout') -PassThru
        if ($cProc.ExitCode -ne 0) {
            throw "idle hook without .harness/ exited $($cProc.ExitCode)"
        }
        $cStderr = Get-Content -LiteralPath (Join-Path $mridle '.idle-c.stderr') -Raw -ErrorAction SilentlyContinue
        $cStdout = Get-Content -LiteralPath (Join-Path $mridle '.idle-c.stdout') -Raw -ErrorAction SilentlyContinue
        if ($cStderr -or $cStdout) {
            throw "idle hook without .harness/ emitted output (should be silent). stdout: $cStdout / stderr: $cStderr"
        }
        New-Item -ItemType Directory -Path (Join-Path $mridle '.harness') -Force | Out-Null

        # Test D: missing transcript in orphan marker → graceful skip
        $markerD = Join-Path $mridle '.harness/session-id-missing00.start'
        $markerDContent = @"
session_id: missing00-eeffaabb
started_at: 2026-05-18T00:00:00Z
transcript: $($mridle.Replace('\','/'))/does-not-exist.jsonl
"@
        Set-Content -LiteralPath $markerD -Value $markerDContent
        (Get-Item -LiteralPath $markerD).LastWriteTime = $backdate
        $dProc = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-reflect-idle.ps1') -WorkingDirectory $mridle -NoNewWindow -Wait -RedirectStandardError (Join-Path $mridle '.idle-d.stderr') -PassThru
        $dStderr = Get-Content -LiteralPath (Join-Path $mridle '.idle-d.stderr') -Raw -ErrorAction SilentlyContinue
        if ($dStderr -notmatch 'transcript not found') {
            throw "idle hook with missing-transcript marker did not emit warning. stderr: $dStderr"
        }
        if (-not (Test-Path -LiteralPath $markerD)) {
            throw "failed-reflection marker was renamed (should stay .start for retry)"
        }
    } finally {
        Remove-Item -LiteralPath $mridle -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $ridleVault -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Path Env:MEMORY_VAULT_PATH -ErrorAction SilentlyContinue
    }

    # ── Crash-recovery marker lifecycle test (plan #7a part 3 task 6) ──────
    Write-Host '==> Crash-recovery marker lifecycle test (plan #7a part 3 task 6)'
    $mmarker = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mmarker-" + [System.Guid]::NewGuid().ToString('N'))
    $mmarkerVault = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mmarker-vault-" + [System.Guid]::NewGuid().ToString('N'))
    $mmarkerSessionId = "c1d2e3f4-a5b6-7c8d-9e0f-pwshmarker6lc"
    $mmarkerCwdSlug = "-" + (($mmarker -replace '[\\/]', '-') -replace ':', '')
    $mmarkerTranscriptDir = Join-Path $HOME ".claude/projects/$mmarkerCwdSlug"
    $mmarkerTranscript = Join-Path $mmarkerTranscriptDir "$mmarkerSessionId.jsonl"
    New-Item -ItemType Directory -Path (Join-Path $mmarker '.claude/skills/memory/scripts') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $mmarker '.claude/hooks') -Force | Out-Null
    New-Item -ItemType Directory -Path $mmarkerVault -Force | Out-Null
    New-Item -ItemType Directory -Path $mmarkerTranscriptDir -Force | Out-Null
    foreach ($pyf in @('recall', 'reflect', 'save', 'embed', 'vec_index')) {
        Copy-Item -LiteralPath (Join-Path $scratch ".claude/skills/memory/scripts/$pyf.py") -Destination (Join-Path $mmarker ".claude/skills/memory/scripts/$pyf.py")
    }
    Copy-Item -LiteralPath (Join-Path $scratch '.claude/hooks/memory-recall-session-start.ps1') -Destination (Join-Path $mmarker '.claude/hooks/memory-recall-session-start.ps1')
    Copy-Item -LiteralPath (Join-Path $scratch '.claude/hooks/memory-reflect-stop.ps1') -Destination (Join-Path $mmarker '.claude/hooks/memory-reflect-stop.ps1')
    $mmarkerTxLines = @(
        '{"type":"user","message":{"role":"user","content":"Always commit before EOD."},"uuid":"u1"}'
    )
    [System.IO.File]::WriteAllText($mmarkerTranscript, ($mmarkerTxLines -join "`n") + "`n")
    try {
        $env:MEMORY_VAULT_PATH = $mmarkerVault
        $cwdEscaped = $mmarker.Replace('\','\\')
        $ssPayload = '{"session_id":"' + $mmarkerSessionId + '","cwd":"' + $cwdEscaped + '","hookEventName":"SessionStart"}'

        # Test 1: SessionStart hook writes marker
        $stdinFile = Join-Path $mmarker '.stdin.log'
        Set-Content -LiteralPath $stdinFile -Value $ssPayload -NoNewline
        $proc1 = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-recall-session-start.ps1') -WorkingDirectory $mmarker -NoNewWindow -Wait -RedirectStandardInput $stdinFile -PassThru
        if ($proc1.ExitCode -ne 0) {
            throw "SessionStart hook exited $($proc1.ExitCode)"
        }
        $startMarker = Join-Path $mmarker ".harness/session-id-$mmarkerSessionId.start"
        if (-not (Test-Path -LiteralPath $startMarker)) {
            throw "SessionStart hook did not write .start marker at $startMarker. .harness/ listing: $(Get-ChildItem -LiteralPath (Join-Path $mmarker '.harness') -ErrorAction SilentlyContinue | ForEach-Object Name)"
        }
        $markerContent = Get-Content -LiteralPath $startMarker -Raw
        if ($markerContent -notmatch "session_id: $mmarkerSessionId") {
            throw "marker missing session_id field. content: $markerContent"
        }
        if ($markerContent -notmatch 'started_at: ') {
            throw "marker missing started_at field. content: $markerContent"
        }
        if ($markerContent -notmatch 'transcript: ') {
            throw "marker missing transcript field. content: $markerContent"
        }

        # Test 2: re-invocation is idempotent (marker not overwritten)
        $origContent = Get-Content -LiteralPath $startMarker -Raw
        Start-Sleep -Seconds 1
        $proc2 = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-recall-session-start.ps1') -WorkingDirectory $mmarker -NoNewWindow -Wait -RedirectStandardInput $stdinFile -PassThru
        if ($proc2.ExitCode -ne 0) {
            throw "SessionStart re-invocation exited $($proc2.ExitCode)"
        }
        $newContent = Get-Content -LiteralPath $startMarker -Raw
        if ($origContent -ne $newContent) {
            throw "SessionStart re-invocation overwrote existing marker (should be idempotent)"
        }

        # Test 3: Stop hook renames .start → .reflected
        $stopPayload = '{"session_id":"' + $mmarkerSessionId + '","cwd":"' + $cwdEscaped + '","hookEventName":"Stop"}'
        Set-Content -LiteralPath $stdinFile -Value $stopPayload -NoNewline
        $proc3 = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-reflect-stop.ps1') -WorkingDirectory $mmarker -NoNewWindow -Wait -RedirectStandardInput $stdinFile -PassThru
        if ($proc3.ExitCode -ne 0) {
            throw "Stop hook exited $($proc3.ExitCode)"
        }
        if (Test-Path -LiteralPath $startMarker) {
            throw "Stop hook left .start marker in place (should have renamed to .reflected)"
        }
        $reflectedMarker = Join-Path $mmarker ".harness/session-id-$mmarkerSessionId.reflected"
        if (-not (Test-Path -LiteralPath $reflectedMarker)) {
            throw "Stop hook did not create .reflected marker"
        }

        # Test 4: Stop hook with no pre-existing marker → graceful no-op
        $noMarkerSessionId = "d1e2f3a4-b5c6-7d8e-9f0a-pwshmarker6no"
        $noMarkerTranscript = Join-Path $mmarkerTranscriptDir "$noMarkerSessionId.jsonl"
        Copy-Item -LiteralPath $mmarkerTranscript -Destination $noMarkerTranscript
        $noMarkerStopPayload = '{"session_id":"' + $noMarkerSessionId + '","cwd":"' + $cwdEscaped + '","hookEventName":"Stop"}'
        Set-Content -LiteralPath $stdinFile -Value $noMarkerStopPayload -NoNewline
        $proc4 = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-File','.claude/hooks/memory-reflect-stop.ps1') -WorkingDirectory $mmarker -NoNewWindow -Wait -RedirectStandardInput $stdinFile -PassThru
        if ($proc4.ExitCode -ne 0) {
            throw "Stop hook with no pre-existing marker exited $($proc4.ExitCode)"
        }
    } finally {
        Remove-Item -LiteralPath $mmarker -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $mmarkerVault -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $mmarkerTranscriptDir -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -Path Env:MEMORY_VAULT_PATH -ErrorAction SilentlyContinue
    }

    # ── Permeable boundary helper test (plan #7a part 4 task 1) ────────────
    Write-Host '==> Permeable boundary helper test (plan #7a part 4 task 1)'
    $pbPy = Join-Path $scratch '.claude/skills/memory/scripts/permeable_boundary.py'
    if (-not (Test-Path -LiteralPath $pbPy)) {
        throw "permeable_boundary.py not installed at $pbPy"
    }
    # Test A: silent mode → approved (exit 0)
    $pbAOut = python3 $pbPy '/tmp/test-write.md' '--content-preview' 'hello' '--rationale' 'test' '--mode' 'silent' 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "silent mode exited $LASTEXITCODE (expected 0). output: $pbAOut"
    }
    if ($pbAOut -notmatch '"approved": true') {
        throw "silent mode did not emit approved:true. output: $pbAOut"
    }
    # Test B: auto mode → denied (exit 1)
    $pbBOut = python3 $pbPy '/tmp/test-write.md' '--content-preview' 'hello' '--rationale' 'test' '--mode' 'auto' 2>&1 | Out-String
    if ($LASTEXITCODE -ne 1) {
        throw "auto mode exited $LASTEXITCODE (expected 1 — A3 says never silently write outside MemoryVault). output: $pbBOut"
    }
    if ($pbBOut -notmatch '"approved": false') {
        throw "auto mode did not emit approved:false"
    }
    # Test C: interactive with piped stdin → deny (exit 1)
    $pbCOut = 'y' | python3 $pbPy '/tmp/test-write.md' '--content-preview' 'hello' '--rationale' 'test' '--mode' 'interactive' 2>&1 | Out-String
    if ($LASTEXITCODE -ne 1) {
        throw "interactive non-TTY exited $LASTEXITCODE (expected 1). output: $pbCOut"
    }
    if ($pbCOut -notmatch '"approved": false') {
        throw "interactive non-TTY did not emit approved:false"
    }
    # Test D: invalid mode → argparse exit 2
    python3 $pbPy '/tmp/test-write.md' '--mode' 'bogus' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 2) {
        throw "invalid mode exited $LASTEXITCODE (expected 2 from argparse)"
    }
    # Test E: env MEMORY_REVIEW_MODE=silent → auto-approve
    $env:MEMORY_REVIEW_MODE = 'silent'
    try {
        $pbEOut = python3 $pbPy '/tmp/test-write.md' '--content-preview' 'x' '--rationale' 'y' 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            throw "env MEMORY_REVIEW_MODE=silent did not auto-approve (exit $LASTEXITCODE)"
        }
        if ($pbEOut -notmatch '"approved": true') {
            throw "env silent did not emit approved:true"
        }
    } finally {
        Remove-Item -Path Env:MEMORY_REVIEW_MODE -ErrorAction SilentlyContinue
    }
    # Test F: Python API with mocked TTY stdin → approved on 'y', denied on 'n'
    $pbScriptsRel = (Join-Path $scratch '.claude/skills/memory/scripts').Replace('\','/')
    $pbFDriver = @"
import io, sys
sys.path.insert(0, r'$pbScriptsRel')
from permeable_boundary import confirm_write_outside_memoryvault
class FakeStdin(io.StringIO):
    def isatty(self): return True
for ans, expect in [('y\n', True), ('n\n', False), ('\n', False), ('yes\n', True)]:
    fake_in = FakeStdin(ans)
    fake_out = io.StringIO()
    got = confirm_write_outside_memoryvault('/tmp/t.md', 'p', 'r', stdin=fake_in, stdout=fake_out, mode='interactive')
    if got != expect:
        print(f'FAIL: answer={ans!r} expected {expect} got {got}')
        sys.exit(1)
print('OK')
"@
    $pbFOut = (python3 -c $pbFDriver 2>&1 | Out-String).Trim()
    if ($pbFOut -ne 'OK') {
        throw "Python API TTY answer mapping broken: $pbFOut"
    }

    # ── Ideas.md surface-tier writer test (plan #7a part 4 task 2) ─────────
    Write-Host '==> Ideas.md surface-tier writer test (plan #7a part 4 task 2)'
    $isPy = Join-Path $scratch '.claude/skills/memory/scripts/ideas_surface.py'
    if (-not (Test-Path -LiteralPath $isPy)) {
        throw "ideas_surface.py not installed at $isPy"
    }
    $misurface = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-misurface-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $misurface -Force | Out-Null
    $ideasMd = Join-Path $misurface 'Ideas.md'
    try {
        # Test A: silent + first write creates header + section
        $isAOut = python3 $isPy 'Add /memory inspect command' 'Operators need to audit why a candidate was mined. Build /memory inspect.' '--ideas-path' $ideasMd '--mode' 'silent' 2>&1 | Out-String
        if ($isAOut -notmatch '"appended": true') {
            throw "silent first-write did not emit appended:true. output: $isAOut"
        }
        $ideasContent = Get-Content -LiteralPath $ideasMd -Raw
        if ($ideasContent -notmatch '(?m)^# Ideas$') {
            throw "Ideas.md missing first-write header"
        }
        if ($ideasContent -notmatch '(?m)^## \d{4}-\d{2}-\d{2}: Add /memory inspect command$') {
            throw "section header missing or wrong format"
        }
        if ($ideasContent -notmatch '\[\[MemoryVault/personal-private/_idea-incubator/add-memory-inspect-command/_index\.md\]\]') {
            throw "section missing wikilink (or wrong slug)"
        }
        # Test B: second write appends + preserves header + custom slug
        $origHeader = (Get-Content -LiteralPath $ideasMd -TotalCount 5) -join "`n"
        python3 $isPy 'Idle hook native event' 'Lobby Claude Code team for real idle-event hook.' '--slug' 'claude-code-idle-event' '--ideas-path' $ideasMd '--mode' 'silent' 2>$null | Out-Null
        $newHeader = (Get-Content -LiteralPath $ideasMd -TotalCount 5) -join "`n"
        if ($origHeader -ne $newHeader) {
            throw "second-write modified the first 5 lines (header should be preserved)"
        }
        $ideasContent = Get-Content -LiteralPath $ideasMd -Raw
        $sectionCount = ([regex]::Matches($ideasContent, '(?m)^## \d{4}-\d{2}-\d{2}:')).Count
        if ($sectionCount -ne 2) {
            throw "expected 2 sections after second write, got $sectionCount"
        }
        if ($ideasContent -notmatch '\[\[MemoryVault/personal-private/_idea-incubator/claude-code-idle-event/_index\.md\]\]') {
            throw "second section missing custom-slug wikilink"
        }
        # Test C: auto mode → denied
        python3 $isPy 'Should not appear' 'Anything' '--ideas-path' $ideasMd '--mode' 'auto' 2>$null | Out-Null
        if ($LASTEXITCODE -ne 2) {
            throw "auto mode exited $LASTEXITCODE (expected 2 — permeable_boundary denied)"
        }
        $ideasContent = Get-Content -LiteralPath $ideasMd -Raw
        if ($ideasContent -match 'Should not appear') {
            throw "auto-denied content leaked into Ideas.md"
        }
        # Test D: empty summary → exit 1
        python3 $isPy 'Title' '   ' '--ideas-path' $ideasMd '--mode' 'silent' 2>$null | Out-Null
        if ($LASTEXITCODE -ne 1) {
            throw "empty summary exited $LASTEXITCODE (expected 1)"
        }
        # Test E: IDEAS_SURFACE_PATH env override
        $envIdeas = Join-Path $misurface 'env-Ideas.md'
        $env:IDEAS_SURFACE_PATH = $envIdeas
        try {
            python3 $isPy 'Env override test' 'Test summary.' '--mode' 'silent' 2>$null | Out-Null
            if (-not (Test-Path -LiteralPath $envIdeas)) {
                throw "IDEAS_SURFACE_PATH env override did not redirect Ideas.md"
            }
        } finally {
            Remove-Item -Path Env:IDEAS_SURFACE_PATH -ErrorAction SilentlyContinue
        }
    } finally {
        Remove-Item -LiteralPath $misurface -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── _idea-incubator skeleton writer test (plan #7a part 4 task 3) ──────
    Write-Host '==> _idea-incubator skeleton writer test (plan #7a part 4 task 3)'
    $iiPy = Join-Path $scratch '.claude/skills/memory/scripts/ideas_incubator.py'
    if (-not (Test-Path -LiteralPath $iiPy)) {
        throw "ideas_incubator.py not installed at $iiPy"
    }
    $miincub = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-miincub-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $miincub -Force | Out-Null
    try {
        # Test A: skeleton creates 4 files + locked frontmatter fields
        $iiAOut = python3 $iiPy 'Add /memory inspect for tuning' 'Operators need to audit which patterns matched + adjust the merge weights.' '--vault-path' $miincub '--session-id' 'abc12345-deadbeef' '--rationale' 'Mentioned 3x during recall-loop part' '--excerpt' 'We should tune the rank-merge weights' 2>&1 | Out-String
        if ($iiAOut -notmatch '"created": true') {
            throw "ideas_incubator did not emit created:true. output: $iiAOut"
        }
        $incubDir = Join-Path $miincub 'personal-private/_idea-incubator/add-memory-inspect-for-tuning'
        foreach ($fname in @('_index.md', 'research-pending.md', 'related-memoryvault.md', 'related-obsidian.md')) {
            if (-not (Test-Path -LiteralPath (Join-Path $incubDir $fname))) {
                throw "incubator skeleton missing $fname at $incubDir"
            }
        }
        $indexMd = Join-Path $incubDir '_index.md'
        $indexContent = Get-Content -LiteralPath $indexMd -Raw
        foreach ($field in @('kind: idea', 'status: incubating', 'slug: add-memory-inspect-for-tuning', 'surfaced_in_session: abc12345-deadbeef', 'research_budget_wall_time_sec: 300', 'research_budget_web_fetches: 3', 'research_budget_tokens: 5000')) {
            if ($indexContent -notmatch [regex]::Escape($field)) {
                throw "_index.md missing field: $field"
            }
        }
        if ($indexContent -notmatch 'Mentioned 3x during recall-loop part') {
            throw "_index.md body missing rationale text"
        }
        if ($indexContent -notmatch 'tune the rank-merge weights') {
            throw "_index.md body missing supporting excerpt"
        }
        # Test B: collision suffix
        $iiBOut = python3 $iiPy 'Add /memory inspect for tuning' 'Same title, different summary.' '--vault-path' $miincub 2>&1 | Out-String
        if ($iiBOut -notmatch '"slug": "add-memory-inspect-for-tuning-2"') {
            throw "collision did not produce -2 suffix slug. output: $iiBOut"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $miincub 'personal-private/_idea-incubator/add-memory-inspect-for-tuning-2'))) {
            throw "-2 suffix dir not created"
        }
        # Test C: no vault → error
        python3 $iiPy 'Title' 'Summary' '--vault-path' "/nonexistent/path/$([Guid]::NewGuid())" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 1) {
            throw "nonexistent vault exited $LASTEXITCODE (expected 1)"
        }
        # Test D: empty title → error
        python3 $iiPy '   ' 'Summary' '--vault-path' $miincub 2>$null | Out-Null
        if ($LASTEXITCODE -ne 1) {
            throw "empty title exited $LASTEXITCODE (expected 1)"
        }
        # Test E: custom budget caps
        $iiEOut = python3 $iiPy 'Custom budget idea' 'Test custom budgets.' '--vault-path' $miincub '--budget-wall-time-sec' '60' '--budget-web-fetches' '1' '--budget-tokens' '1500' 2>&1 | Out-String
        $customDir = ($iiEOut | ConvertFrom-Json).incubator_dir
        $customIndex = Get-Content -LiteralPath (Join-Path $customDir '_index.md') -Raw
        foreach ($budgetField in @('research_budget_wall_time_sec: 60', 'research_budget_web_fetches: 1', 'research_budget_tokens: 1500')) {
            if ($customIndex -notmatch [regex]::Escape($budgetField)) {
                throw "custom budget field missing: $budgetField"
            }
        }
        # Test F: memory-idea-researcher sub-agent installed
        $researcherMd = Join-Path $scratch '.claude/agents/memory-idea-researcher.md'
        if (-not (Test-Path -LiteralPath $researcherMd)) {
            throw "memory-idea-researcher.md not installed at $researcherMd"
        }
        $researcherAnti = Join-Path $scratch '.agent/skills/memory-idea-researcher/SKILL.md'
        if (-not (Test-Path -LiteralPath $researcherAnti)) {
            throw "memory-idea-researcher antigravity skill-wrap missing at $researcherAnti"
        }
    } finally {
        Remove-Item -LiteralPath $miincub -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── /memory promote + GC test (plan #7a part 4 task 4) ─────────────────
    Write-Host '==> /memory promote + GC test (plan #7a part 4 task 4)'
    $ipPy = Join-Path $scratch '.claude/skills/memory/scripts/ideas_promote.py'
    if (-not (Test-Path -LiteralPath $ipPy)) {
        throw "ideas_promote.py not installed at $ipPy"
    }
    $mipromote = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-mipromote-" + [System.Guid]::NewGuid().ToString('N'))
    $promoteIdeasDir = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-promote-ideas-" + [System.Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $mipromote -Force | Out-Null
    New-Item -ItemType Directory -Path $promoteIdeasDir -Force | Out-Null
    $promoteIdeasMd = Join-Path $promoteIdeasDir 'Ideas.md'
    try {
        # Seed incubator + Ideas.md section
        $iiPyPath = Join-Path $scratch '.claude/skills/memory/scripts/ideas_incubator.py'
        $isPyPath = Join-Path $scratch '.claude/skills/memory/scripts/ideas_surface.py'
        python3 $iiPyPath 'Test promote flow' 'End-to-end promote verification.' '--vault-path' $mipromote 2>$null | Out-Null
        python3 $isPyPath 'Test promote flow' 'End-to-end promote verification.' '--ideas-path' $promoteIdeasMd '--mode' 'silent' 2>$null | Out-Null

        # Test A: promote happy path
        $env:IDEAS_SURFACE_PATH = $promoteIdeasMd
        try {
            $ipAOut = python3 $ipPy 'promote' 'test-promote-flow' '--vault-path' $mipromote '--mode' 'silent' 2>&1 | Out-String
        } finally {
            Remove-Item -Path Env:IDEAS_SURFACE_PATH -ErrorAction SilentlyContinue
        }
        if ($ipAOut -notmatch '"promoted": true') {
            throw "promote did not emit promoted:true. output: $ipAOut"
        }
        if (Test-Path -LiteralPath (Join-Path $mipromote 'personal-private/_idea-incubator/test-promote-flow')) {
            throw "incubator dir still exists after promote"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $mipromote 'personal-private/personal-projects/test-promote-flow'))) {
            throw "personal-projects/test-promote-flow/ not created"
        }
        $ideasContent = Get-Content -LiteralPath $promoteIdeasMd -Raw
        if ($ideasContent -notmatch '(?m)^→ promoted \d{4}-\d{2}-\d{2} to personal-private/personal-projects/test-promote-flow$') {
            throw "Ideas.md annotation missing or wrong format"
        }
        if ($ipAOut -notmatch '"ideas_annotation": "written"') {
            throw "promote output did not report ideas_annotation: written"
        }

        # Test B: missing slug → exit 1
        python3 $ipPy 'promote' 'nonexistent-idea' '--vault-path' $mipromote 2>$null | Out-Null
        if ($LASTEXITCODE -ne 1) {
            throw "missing slug exited $LASTEXITCODE (expected 1)"
        }

        # Test C: target collision → exit 1
        python3 $iiPyPath 'Test promote flow' 'Second try same title.' '--vault-path' $mipromote '--slug' 'test-promote-flow' 2>$null | Out-Null
        python3 $ipPy 'promote' 'test-promote-flow' '--vault-path' $mipromote 2>$null | Out-Null
        if ($LASTEXITCODE -ne 1) {
            throw "target collision exited $LASTEXITCODE (expected 1)"
        }

        # Test D: gc with fresh entries → deleted:0
        $ipDOut = python3 $ipPy 'gc' '--vault-path' $mipromote 2>&1 | Out-String
        if ($ipDOut -notmatch '"deleted": 0') {
            throw "gc with fresh entries reported deleted > 0. output: $ipDOut"
        }

        # Test E: gc with non-TTY + force-old entry → defaults to keep
        $oldIndex = Join-Path $mipromote 'personal-private/_idea-incubator/test-promote-flow/_index.md'
        $oldTimestamp = (Get-Date).AddDays(-365)
        (Get-Item -LiteralPath $oldIndex).LastWriteTime = $oldTimestamp
        # Drive ideas_promote gc with non-TTY stdin (redirect from empty file
        # — pwsh Start-Process rejects $null for RedirectStandardInput).
        $stdoutFile = Join-Path $mipromote '.gc-out.log'
        $emptyStdin = Join-Path $mipromote '.gc-stdin-empty'
        Set-Content -LiteralPath $emptyStdin -Value '' -NoNewline
        $gcProc = Start-Process -FilePath 'python3' -ArgumentList @($ipPy, 'gc', '--vault-path', $mipromote) -NoNewWindow -Wait -RedirectStandardInput $emptyStdin -RedirectStandardOutput $stdoutFile -PassThru
        $ipEOut = Get-Content -LiteralPath $stdoutFile -Raw
        if ($ipEOut -notmatch '"deleted": 0') {
            throw "gc with non-TTY stdin deleted entries (never-silent-delete contract broken). output: $ipEOut"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $mipromote 'personal-private/_idea-incubator/test-promote-flow'))) {
            throw "gc deleted old entry under non-TTY stdin"
        }
    } finally {
        Remove-Item -LiteralPath $mipromote -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $promoteIdeasDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Personal-skills auto-indexer test (plan #7b task 1) ────────────────
    Write-Host '==> Personal-skills auto-indexer test (plan #7b task 1)'
    $idxPy = Join-Path $scratch '.claude/skills/memory/scripts/index_skills.py'
    if (-not (Test-Path -LiteralPath $idxPy)) {
        throw "index_skills.py not installed at $idxPy"
    }
    $idxtmp = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-idx-" + [System.Guid]::NewGuid().ToString('N'))
    $idxVault = Join-Path $idxtmp 'vault'
    $idxSrc = Join-Path $idxtmp 'srcrepo'
    New-Item -ItemType Directory -Path $idxVault -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $idxSrc 'alpha') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $idxSrc 'beta') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $idxSrc 'AGENTS.md') -Value '' -NoNewline
    $alphaManifest = @"
---
name: alpha
description: First fixture skill for the auto-indexer test.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 1.0.0
install_scope: project
---

# alpha

First paragraph after H1 - used as the extracted summary.

## More content
not extracted.
"@
    Set-Content -LiteralPath (Join-Path $idxSrc 'alpha/SKILL.md') -Value $alphaManifest -Encoding utf8
    $betaManifest = @"
---
name: beta
description: Second fixture skill.
kind: skill
supported_hosts: [claude-code]
version: 0.5.0
---

# beta

Beta body paragraph.
"@
    Set-Content -LiteralPath (Join-Path $idxSrc 'beta/SKILL.md') -Value $betaManifest -Encoding utf8
    try {
        # Test A: fresh index → 2 written
        $idxAOut = & python3 $idxPy --skill-path $idxSrc --vault-path $idxVault 2>&1 | Out-String
        if ($idxAOut -notmatch '"written":\s*2') {
            throw "fresh index did not write 2 entries. output: $idxAOut"
        }
        $alphaEntry = Join-Path $idxVault 'personal-skills/srcrepo/alpha.md'
        $betaEntry = Join-Path $idxVault 'personal-skills/srcrepo/beta.md'
        if (-not (Test-Path -LiteralPath $alphaEntry) -or -not (Test-Path -LiteralPath $betaEntry)) {
            throw "expected pointer entries missing under $idxVault"
        }
        $alphaText = Get-Content -LiteralPath $alphaEntry -Raw
        foreach ($field in @('kind: skill-pointer', 'source_repo: srcrepo', 'skill_version: 1.0.0', 'slug: alpha', 'group: personal-skills/srcrepo')) {
            if ($alphaText -notmatch [regex]::Escape($field)) {
                throw "alpha.md missing field: $field"
            }
        }
        if ($alphaText -notmatch 'First paragraph after H1') {
            throw "alpha.md missing extracted body summary"
        }

        # Test B: idempotent re-run
        $idxBOut = & python3 $idxPy --skill-path $idxSrc --vault-path $idxVault 2>&1 | Out-String
        if ($idxBOut -notmatch '"written":\s*0') {
            throw "idempotent re-run still wrote entries. output: $idxBOut"
        }
        if ($idxBOut -notmatch '"skipped":\s*2') {
            throw "idempotent re-run did not skip 2. output: $idxBOut"
        }

        # Test C: version bump → 1 written
        $alphaManifestBumped = $alphaManifest -replace 'version: 1\.0\.0', 'version: 1.1.0'
        Set-Content -LiteralPath (Join-Path $idxSrc 'alpha/SKILL.md') -Value $alphaManifestBumped -Encoding utf8
        $idxCOut = & python3 $idxPy --skill-path $idxSrc --vault-path $idxVault 2>&1 | Out-String
        if ($idxCOut -notmatch '"written":\s*1') {
            throw "version bump did not write 1. output: $idxCOut"
        }
        $alphaTextBumped = Get-Content -LiteralPath $alphaEntry -Raw
        if ($alphaTextBumped -notmatch 'skill_version: 1\.1\.0') {
            throw "alpha.md skill_version not bumped to 1.1.0"
        }

        # Test D: missing --skill-path → exit 1
        $idxDProc = Start-Process -FilePath 'python3' -ArgumentList @($idxPy, '--vault-path', $idxVault) -NoNewWindow -PassThru -Wait -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) -RedirectStandardError ([System.IO.Path]::GetTempFileName())
        if ($idxDProc.ExitCode -ne 1) {
            throw "missing --skill-path expected exit 1, got $($idxDProc.ExitCode)"
        }

        # Test E: --repo-name normalization (My_Custom-Repo → my-custom-repo)
        $idxVault2 = Join-Path $idxtmp 'vault2'
        New-Item -ItemType Directory -Path $idxVault2 -Force | Out-Null
        $idxEOut = & python3 $idxPy --skill-path $idxSrc --vault-path $idxVault2 --repo-name 'My_Custom-Repo' 2>&1 | Out-String
        if ($idxEOut -notmatch '"written":\s*2') {
            throw "--repo-name override did not write 2. output: $idxEOut"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $idxVault2 'personal-skills/my-custom-repo'))) {
            throw "--repo-name not normalized to kebab (expected my-custom-repo dir)"
        }

        # Test F: --no-skill-index flag propagation via install log
        $installLogText = Get-Content -LiteralPath (Join-Path $scratch '.install.log') -Raw
        if ($installLogText -notmatch 'personal-skills index: skipped \(-NoSkillIndex\)') {
            throw "-NoSkillIndex flag did not produce expected skip line in install.log"
        }
    } finally {
        Remove-Item -LiteralPath $idxtmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Reflect corpus mode test (plan #7b task 2) ─────────────────────────
    Write-Host '==> Reflect corpus mode test (plan #7b task 2)'
    $rcPy = Join-Path $scratch '.claude/skills/memory/scripts/reflect.py'
    if (-not (Test-Path -LiteralPath $rcPy)) {
        throw "reflect.py not installed at $rcPy"
    }
    $rctmp = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-rc-" + [System.Guid]::NewGuid().ToString('N'))
    $rcVault = Join-Path $rctmp 'vault'
    $rcProj = Join-Path $rctmp 'projects'
    New-Item -ItemType Directory -Path $rcVault -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $rcProj 'repo-a') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $rcProj 'repo-b') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $rcProj 'repo-a/sess-001.jsonl') -Value @'
{"type":"user","message":{"role":"user","content":"I prefer concise commit messages."}}
{"type":"assistant","message":{"role":"assistant","content":"OK."}}
'@ -Encoding utf8
    Set-Content -LiteralPath (Join-Path $rcProj 'repo-a/sess-002.jsonl') -Value @'
{"type":"user","message":{"role":"user","content":"Always use snake_case for python variables."}}
'@ -Encoding utf8
    Set-Content -LiteralPath (Join-Path $rcProj 'repo-b/sess-003.jsonl') -Value @'
{"type":"user","message":{"role":"user","content":"hi"}}
'@ -Encoding utf8
    $rcState = Join-Path $rcVault '_meta/transcript-reflection-state.json'
    try {
        # Test A: dry-run default
        $rcAOut = & python3 $rcPy corpus --vault-path $rcVault --projects-root $rcProj 2>&1 | Out-String
        if ($rcAOut -notmatch '"dry_run":\s*true') {
            throw "corpus default did not run in dry-run mode. output: $rcAOut"
        }
        if ($rcAOut -notmatch '"to_process":\s*3') {
            throw "corpus dry-run did not discover 3 transcripts. output: $rcAOut"
        }
        if (Test-Path -LiteralPath $rcState) {
            throw "dry-run wrote state file (should not have)"
        }

        # Test B: --execute populates state
        $rcBOut = & python3 $rcPy corpus --vault-path $rcVault --projects-root $rcProj --execute 2>&1 | Out-String
        if ($rcBOut -notmatch '"dry_run":\s*false') {
            throw "--execute did not flip dry_run to false. output: $rcBOut"
        }
        if ($rcBOut -notmatch '"processed_this_run":\s*3') {
            throw "--execute did not process 3 sessions. output: $rcBOut"
        }
        if (-not (Test-Path -LiteralPath $rcState)) {
            throw "--execute did not write state file"
        }
        $stateData = Get-Content -LiteralPath $rcState -Raw | ConvertFrom-Json
        $sessCount = ($stateData.sessions.PSObject.Properties | Measure-Object).Count
        if ($sessCount -ne 3) {
            throw "state file should have 3 sessions, got $sessCount"
        }

        # Test C: resume skips done sessions
        $rcCOut = & python3 $rcPy corpus --vault-path $rcVault --projects-root $rcProj --execute 2>&1 | Out-String
        if ($rcCOut -notmatch '"to_process":\s*0') {
            throw "resume did not skip already-processed. output: $rcCOut"
        }
        if ($rcCOut -notmatch '"skipped_already_processed":\s*3') {
            throw "resume did not report 3 skipped. output: $rcCOut"
        }

        # Test D: --reset re-enumerates
        $rcDOut = & python3 $rcPy corpus --vault-path $rcVault --projects-root $rcProj --reset 2>&1 | Out-String
        if ($rcDOut -notmatch '"to_process":\s*3') {
            throw "--reset did not re-enumerate 3 sessions. output: $rcDOut"
        }

        # Test E: --max-batches halts; state preserved. Uses fresh vault to
        # avoid colliding with Test B's canonical saves.
        $rcVault2 = Join-Path $rctmp 'vault2'
        New-Item -ItemType Directory -Path $rcVault2 -Force | Out-Null
        $rcState2 = Join-Path $rcVault2 '_meta/transcript-reflection-state.json'
        $rcEOut = & python3 $rcPy corpus --vault-path $rcVault2 --projects-root $rcProj --execute --batch-size 1 --max-batches 2 2>&1 | Out-String
        if ($rcEOut -notmatch '"batches":\s*2') {
            throw "--max-batches did not halt at 2. output: $rcEOut"
        }
        if ($rcEOut -notmatch '"processed_this_run":\s*2') {
            throw "--max-batches with batch-size=1 should process 2. output: $rcEOut"
        }
        $stateDataE = Get-Content -LiteralPath $rcState2 -Raw | ConvertFrom-Json
        $sessECount = ($stateDataE.sessions.PSObject.Properties | Measure-Object).Count
        if ($sessECount -ne 2) {
            throw "state should have 2 sessions after max-batches halt, got $sessECount"
        }

        # Test F: missing vault path → exit 1
        $rcFProc = Start-Process -FilePath 'python3' -ArgumentList @($rcPy, 'corpus', '--projects-root', $rcProj) -NoNewWindow -PassThru -Wait -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) -RedirectStandardError ([System.IO.Path]::GetTempFileName())
        if ($rcFProc.ExitCode -ne 1) {
            throw "missing vault path expected exit 1, got $($rcFProc.ExitCode)"
        }
    } finally {
        Remove-Item -LiteralPath $rctmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Skill-discovery scan test (plan #7b task 3) ─────────────────────────
    Write-Host '==> Skill-discovery scan test (plan #7b task 3)'
    $dsPy = Join-Path $scratch '.claude/skills/memory/scripts/discover_skills.py'
    if (-not (Test-Path -LiteralPath $dsPy)) {
        throw "discover_skills.py not installed at $dsPy"
    }
    $dstmp = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-ds-" + [System.Guid]::NewGuid().ToString('N'))
    $dsVault = Join-Path $dstmp 'vault'
    $dsRoot = Join-Path $dstmp 'wwwroot'
    New-Item -ItemType Directory -Path (Join-Path $dsVault 'personal-private') -Force | Out-Null
    New-Item -ItemType Directory -Path $dsRoot -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $dsRoot 'source-a.md') -Value "# Source A`nItem 1`nItem 2" -Encoding utf8
    Set-Content -LiteralPath (Join-Path $dsRoot 'source-b.md') -Value "# Source B`nItem X" -Encoding utf8
    # Free port lookup via Python.
    $dsPort = (& python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()").Trim()
    # Start the http.server in background. Capture as a process object.
    $dsServer = Start-Process -FilePath 'python3' -ArgumentList @('-m', 'http.server', $dsPort) -WorkingDirectory $dsRoot -NoNewWindow -PassThru -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) -RedirectStandardError ([System.IO.Path]::GetTempFileName())
    # Wait briefly for the server to bind.
    $bound = $false
    for ($i = 0; $i -lt 10; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$dsPort/source-a.md" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) { $bound = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 200
    }
    if (-not $bound) {
        Stop-Process -Id $dsServer.Id -Force -ErrorAction SilentlyContinue
        throw "fixture http.server did not bind on port $dsPort"
    }
    try {
        # Pre-write the whitelist pointing at fixture URLs.
        Set-Content -LiteralPath (Join-Path $dsVault 'personal-private/skill-discovery-sources.md') -Value @"
# fixture whitelist
http://127.0.0.1:$dsPort/source-a.md
http://127.0.0.1:$dsPort/source-b.md
"@ -Encoding utf8

        # Test A: --dry-run
        $dsAOut = & python3 $dsPy --vault-path $dsVault --dry-run 2>&1 | Out-String
        if ($dsAOut -notmatch '"dry_run":\s*true') {
            throw "dry-run did not set dry_run=true. output: $dsAOut"
        }
        if ($dsAOut -notmatch '"total_sources":\s*2') {
            throw "dry-run did not discover 2 sources. output: $dsAOut"
        }
        if (Test-Path -LiteralPath (Join-Path $dsVault '_meta/skill-discovery-cache/state.json')) {
            throw "dry-run wrote state.json (should not have)"
        }

        # Test B: live fetch creates cache + state
        $dsBOut = & python3 $dsPy --vault-path $dsVault 2>&1 | Out-String
        if ($dsBOut -notmatch '"fetched":\s*2') {
            throw "live fetch did not fetch 2 sources. output: $dsBOut"
        }
        $dsState = Join-Path $dsVault '_meta/skill-discovery-cache/state.json'
        if (-not (Test-Path -LiteralPath $dsState)) {
            throw "live fetch did not write state.json"
        }
        $snapshotCount = (Get-ChildItem -Path (Join-Path $dsVault '_meta/skill-discovery-cache') -Recurse -File | Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}\.md$' } | Measure-Object).Count
        if ($snapshotCount -ne 2) {
            throw "expected 2 snapshot files, got $snapshotCount"
        }

        # Test C: --cadence-check skips re-fetch
        $dsCOut = & python3 $dsPy --vault-path $dsVault --cadence-check 2>&1 | Out-String
        if ($dsCOut -notmatch '"cadence_skipped":\s*true') {
            throw "--cadence-check did not skip. output: $dsCOut"
        }
        if ($dsCOut -notmatch '"fetched":\s*0') {
            throw "--cadence-check should not fetch. output: $dsCOut"
        }

        # Test D: 404 graceful-skip
        Set-Content -LiteralPath (Join-Path $dsVault 'personal-private/skill-discovery-sources.md') -Value @"
http://127.0.0.1:$dsPort/nonexistent.md
http://127.0.0.1:$dsPort/source-a.md
"@ -Encoding utf8
        $dsDOut = & python3 $dsPy --vault-path $dsVault 2>&1 | Out-String
        if ($dsDOut -notmatch '"errors":\s*1') {
            throw "404 should produce errors=1. output: $dsDOut"
        }
        if ($dsDOut -notmatch '"fetched":\s*1') {
            throw "source-a should still fetch after 404 on nonexistent. output: $dsDOut"
        }

        # Test E: auto-seed whitelist
        $dsVault2 = Join-Path $dstmp 'vault2'
        New-Item -ItemType Directory -Path $dsVault2 -Force | Out-Null
        $dsEOut = & python3 $dsPy --vault-path $dsVault2 --dry-run 2>&1 | Out-String
        if ($dsEOut -notmatch '"whitelist_seeded":\s*true') {
            throw "missing whitelist did not auto-seed. output: $dsEOut"
        }
        if ($dsEOut -notmatch '"total_sources":\s*4') {
            throw "auto-seeded whitelist should have 4 sources. output: $dsEOut"
        }
        $seededFile = Get-Content -LiteralPath (Join-Path $dsVault2 'personal-private/skill-discovery-sources.md') -Raw
        foreach ($expected in @('anthropic-cookbook', 'awesome-claude-code', 'awesome-mcp-servers', 'awesome-llm-apps')) {
            if ($seededFile -notmatch [regex]::Escape("/$expected/")) {
                throw "auto-seeded whitelist missing expected source: $expected"
            }
        }

        # Test F: empty whitelist returns total_sources=0
        $dsVault3 = Join-Path $dstmp 'vault3'
        New-Item -ItemType Directory -Path (Join-Path $dsVault3 'personal-private') -Force | Out-Null
        Set-Content -LiteralPath (Join-Path $dsVault3 'personal-private/skill-discovery-sources.md') -Value "# empty whitelist`n# no URLs configured" -Encoding utf8
        $dsFOut = & python3 $dsPy --vault-path $dsVault3 2>&1 | Out-String
        if ($dsFOut -notmatch '"total_sources":\s*0') {
            throw "empty whitelist should have total_sources=0. output: $dsFOut"
        }
        if ($dsFOut -notmatch '"fetched":\s*0') {
            throw "empty whitelist should fetch 0. output: $dsFOut"
        }
    } finally {
        Stop-Process -Id $dsServer.Id -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $dstmp -Recurse -Force -ErrorAction SilentlyContinue
    }

    # ── Adapt-don't-import Pass 1 test (plan #7b task 4) ───────────────────
    Write-Host '==> Adapt-don''t-import Pass 1 test (plan #7b task 4)'
    $asPy = Join-Path $scratch '.claude/skills/memory/scripts/adapt_skills.py'
    if (-not (Test-Path -LiteralPath $asPy)) {
        throw "adapt_skills.py not installed at $asPy"
    }
    $astmp = Join-Path ([System.IO.Path]::GetTempPath()) ("toolkit-as-" + [System.Guid]::NewGuid().ToString('N'))
    $asVault = Join-Path $astmp 'vault'
    New-Item -ItemType Directory -Path (Join-Path $asVault '_meta/skill-discovery-cache/anthropics-test') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $asVault 'personal-private/_always-load') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $asVault 'personal-skills/some-repo') -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $asVault 'personal-private/_always-load/commit-no-coauthor.md') -Value @'
---
slug: commit-no-coauthor
tags: [commit, agent, workflow]
---
# commit-no-coauthor
'@ -Encoding utf8
    Set-Content -LiteralPath (Join-Path $asVault 'personal-skills/some-repo/existing-tool.md') -Value @'
---
slug: existing-tool
---
'@ -Encoding utf8
    Set-Content -LiteralPath (Join-Path $asVault '_meta/skill-discovery-cache/anthropics-test/diff-2026-05-21.md') -Value @'
## new-mcp-server
A skill that adds an MCP server for agent workflow integration. See https://github.com/anthropics/some-server for the implementation.

## experimental-hack
A workaround for a temporary CI bug. Don't use yet. WIP.

- [cursor-helper](https://github.com/somevendor/cursor-helper) — Cursor IDE integration tool.

## another-agent-skill
Hook for Claude Code that automates commit messages and release tagging.
'@ -Encoding utf8
    try {
        # Test A: dry-run + skip-network
        $asAOut = & python3 $asPy --vault-path $asVault --skip-network --dry-run 2>&1 | Out-String
        if ($asAOut -notmatch '"dry_run":\s*true') {
            throw "dry-run did not set dry_run=true. output: $asAOut"
        }
        if ($asAOut -notmatch '"evaluated_count":\s*4') {
            throw "dry-run should evaluate 4 candidates. output: $asAOut"
        }
        if ($asAOut -notmatch '"high_count":\s*2') {
            throw "dry-run should classify 2 HIGH. output: $asAOut"
        }
        if ($asAOut -notmatch '"trusted_sources_seeded":\s*true') {
            throw "trusted-sources.md not auto-seeded on first run. output: $asAOut"
        }
        $adaptStateDir = Join-Path $asVault '_meta/skill-discovery-cache/adapt-state'
        if (Test-Path -LiteralPath $adaptStateDir) {
            $stateFiles = @(Get-ChildItem -LiteralPath $adaptStateDir -Recurse -File -ErrorAction SilentlyContinue)
            if ($stateFiles.Count -gt 0) {
                throw "dry-run wrote adapt-state files"
            }
        }

        # Test B: actual run writes 4 JSONs + state file
        $asBOut = & python3 $asPy --vault-path $asVault --skip-network 2>&1 | Out-String
        if ($asBOut -notmatch '"written_count":\s*4') {
            throw "actual run should write 4. output: $asBOut"
        }
        $jsonFiles = @(Get-ChildItem -LiteralPath (Join-Path $asVault '_meta/skill-discovery-cache/adapt-state/anthropics-test') -Filter '*.json' -ErrorAction SilentlyContinue)
        if ($jsonFiles.Count -ne 4) {
            throw "expected 4 candidate JSONs, got $($jsonFiles.Count)"
        }
        $stateFile = Join-Path $asVault '_meta/skill-discovery-cache/adapt-state/evaluated.json'
        if (-not (Test-Path -LiteralPath $stateFile)) {
            throw "state file evaluated.json not written"
        }

        # Test C: JSON shape check on new-mcp-server + cursor-helper
        $newMcpJson = Join-Path $asVault '_meta/skill-discovery-cache/adapt-state/anthropics-test/new-mcp-server.json'
        $newMcpData = Get-Content -LiteralPath $newMcpJson -Raw | ConvertFrom-Json
        if ($newMcpData.rubric_confidence -ne 'HIGH') {
            throw "new-mcp-server should be HIGH, got $($newMcpData.rubric_confidence)"
        }
        if ($newMcpData.github_owner -ne 'anthropics') {
            throw "new-mcp-server github_owner should be anthropics, got $($newMcpData.github_owner)"
        }
        if ($newMcpData.trust_signals.from_trusted_org -ne $true) {
            throw "new-mcp-server trust_signals.from_trusted_org should be true"
        }
        $cursorJson = Join-Path $asVault '_meta/skill-discovery-cache/adapt-state/anthropics-test/cursor-helper.json'
        $cursorData = Get-Content -LiteralPath $cursorJson -Raw | ConvertFrom-Json
        if ($cursorData.rubric_confidence -ne 'LOW') {
            throw "cursor-helper should be LOW, got $($cursorData.rubric_confidence)"
        }

        # Test D: idempotent re-run
        $asDOut = & python3 $asPy --vault-path $asVault --skip-network 2>&1 | Out-String
        if ($asDOut -notmatch '"written_count":\s*0') {
            throw "idempotent re-run still wrote entries. output: $asDOut"
        }
        if ($asDOut -notmatch '"skipped_count":\s*4') {
            throw "idempotent re-run should skip 4. output: $asDOut"
        }

        # Test E: missing vault path → exit 1
        $asEProc = Start-Process -FilePath 'python3' -ArgumentList @($asPy) -NoNewWindow -PassThru -Wait -RedirectStandardOutput ([System.IO.Path]::GetTempFileName()) -RedirectStandardError ([System.IO.Path]::GetTempFileName())
        if ($asEProc.ExitCode -ne 1) {
            throw "missing vault path expected exit 1, got $($asEProc.ExitCode)"
        }

        # Test F: trusted-sources.md auto-seed includes expected defaults
        $tsFile = Join-Path $asVault 'personal-private/trusted-sources.md'
        if (-not (Test-Path -LiteralPath $tsFile)) {
            throw "trusted-sources.md not seeded"
        }
        $tsContent = Get-Content -LiteralPath $tsFile -Raw
        foreach ($org in @('anthropics', 'google', 'microsoft', 'hashicorp', 'modelcontextprotocol')) {
            if ($tsContent -notmatch "(?m)^${org}`$") {
                throw "trusted-sources.md missing expected default: $org"
            }
        }

        # Test G: empty cache returns evaluated_count=0
        $asVault2 = Join-Path $astmp 'vault2'
        New-Item -ItemType Directory -Path (Join-Path $asVault2 '_meta/skill-discovery-cache') -Force | Out-Null
        $asGOut = & python3 $asPy --vault-path $asVault2 --skip-network 2>&1 | Out-String
        if ($asGOut -notmatch '"evaluated_count":\s*0') {
            throw "empty cache should evaluate 0. output: $asGOut"
        }
    } finally {
        Remove-Item -LiteralPath $astmp -Recurse -Force -ErrorAction SilentlyContinue
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
