# conflict-merger-session-start.ps1 — Windows twin of the bash hook.
#
# Detects GDrive/DriveFS conflict + duplicate files in the Obsidian vault (and the
# DriveFS lost_and_found/ dump) on SessionStart. Re-homed out of the agentm kernel
# (V5-2 task 2): loads this plugin's scripts/vault_conflicts.py from
# $CLAUDE_PLUGIN_ROOT and puts the present engine's scripts/ dir on sys.path so
# vault_conflicts.py's `from harness_memory import _conflict_family` resolves (LC-3).
#
# Graceful-skip when no vault resolves, the plugin script is missing, or the
# present engine (harness_memory.py) is unavailable. Non-blocking; emits findings
# on stderr; never freezes session boot.

$ErrorActionPreference = 'Continue'  # never block session boot on hook failure

$mode = if ($env:HARNESS_CONFLICT_MERGER_MODE) { $env:HARNESS_CONFLICT_MERGER_MODE } else { 'interactive' }
if ($mode -eq 'off') { exit 0 }

# Resolve the vault path: env -> engine .agentm-config.json vault_path -> none.
# Claude Code does not inject MEMORY_VAULT_PATH into the hook env on user-scope
# installs. LC-4: the engine config is read in place, never written. Mirrors the
# bash twin's _resolve_vault_path().
$vaultPath = $env:MEMORY_VAULT_PATH
if (-not $vaultPath) {
    $prefix = if ($env:AGENTM_INSTALL_PREFIX) { $env:AGENTM_INSTALL_PREFIX } else { (Join-Path $HOME '.claude') }
    $cfg = Join-Path $prefix '.agentm-config.json'
    if ((Test-Path -LiteralPath $cfg -PathType Leaf) -and (Get-Command python3 -ErrorAction SilentlyContinue)) {
        $resolveDriver = @"
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
print(d.get('vault_path') or '')
"@
        $v = (& python3 -c $resolveDriver $cfg 2>$null | Out-String).Trim()
        if ($v) { $vaultPath = $v }
    }
}
if (-not $vaultPath) { exit 0 }
if (-not (Test-Path -LiteralPath $vaultPath -PathType Container)) { exit 0 }

# This plugin's vault_conflicts.py — ships at $CLAUDE_PLUGIN_ROOT/scripts/.
if (-not $env:CLAUDE_PLUGIN_ROOT) { exit 0 }
$vcPy = Join-Path $env:CLAUDE_PLUGIN_ROOT 'scripts/vault_conflicts.py'
if (-not (Test-Path -LiteralPath $vcPy -PathType Leaf)) { exit 0 }

# Resolve the present engine's scripts/ dir (where harness_memory.py lives).
$candidates = @(
    (Join-Path $HOME 'Antigravity/agentm/scripts/harness_memory.py'),
    '../agentm/scripts/harness_memory.py',
    '../../agentm/scripts/harness_memory.py'
)
$kernelScripts = $null
foreach ($c in $candidates) {
    if (Test-Path -LiteralPath $c -PathType Leaf) {
        $kernelScripts = (Resolve-Path -LiteralPath (Split-Path -Parent $c)).Path
        break
    }
}
if (-not $kernelScripts) { exit 0 }

$pythonScript = @"
import importlib.util, os, sys
from pathlib import Path
vc_path, kernel_scripts, vault_root = sys.argv[1], sys.argv[2], sys.argv[3]
# vault_conflicts.py imports _conflict_family from the engine (LC-3) — put the
# engine scripts dir on sys.path before the module execs.
sys.path.insert(0, kernel_scripts)
spec = importlib.util.spec_from_file_location('vault_conflicts', vc_path)
vc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vc)
laf = vc.default_lost_and_found_root()
conflicts = vc.detect_conflict_files(Path(vault_root), lost_and_found_root=laf)
if not conflicts:
    sys.exit(0)
mode = os.environ.get('HARNESS_CONFLICT_MERGER_MODE', 'interactive')
n_vault = sum(1 for e in conflicts if e.get('source') != 'lost_and_found')
n_laf = len(conflicts) - n_vault
sys.stderr.write(
    f"\n[conflict-merger] {len(conflicts)} conflict/duplicate file(s) detected "
    f"({n_vault} in vault, {n_laf} in DriveFS lost_and_found):\n"
)
for entry in conflicts:
    tag = 'lost+found' if entry.get('source') == 'lost_and_found' else 'vault'
    sys.stderr.write(f"    [{tag}] conflict: {entry['rel']}\n")
    base = entry.get('base')
    if base is not None:
        try:
            base_disp = base.relative_to(Path(vault_root))
        except ValueError:
            base_disp = base.name
        sys.stderr.write(f"              base:     {base_disp}\n")
if mode == 'interactive':
    sys.stderr.write(
        "\n    To merge interactively: review each pair in Obsidian or via\n"
        "    diff base conflict and merge by hand. Run /work from the\n"
        "    affected repo if the conflict is in a vault-backed harness file.\n"
        "    lost+found entries are orphans DriveFS could not re-home.\n\n"
        "    To suppress this notice for the current session, set\n"
        "    HARNESS_CONFLICT_MERGER_MODE=silent in the environment.\n\n"
    )
"@

# stderr is intentionally not redirected — the Python writes findings there.
& python3 -c $pythonScript $vcPy $kernelScripts $vaultPath

exit 0
