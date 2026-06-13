# steer — inject mid-run guidance from .harness/STEER.md.
# Mirrors steer.sh (incl. host-portable workspace resolution) for
# Windows / pwsh hosts.
#
# Fires on Claude Code's PreToolUse event (matcher .*). If .harness/STEER.md
# exists in the project root, prints its contents to stdout (Claude Code
# injects into agent context) and renames it to STEER.consumed-<ts>.md.
#
# Operator usage:
#   "Actually, do it this way..." | Out-File .harness/STEER.md
#
# See hook.md in this directory for full documentation.

$ErrorActionPreference = 'Stop'

# ── resolve the workspace root (host-portable) ──────────────────────────────
# Claude Code runs hooks from the project root + passes JSON on stdin with
# "cwd" (and sets $env:CLAUDE_PROJECT_DIR). Antigravity runs plugin hooks from
# the PLUGIN dir + passes the workspace on stdin as {"workspacePaths":["<root>"]}.
# Resolve an explicit workspace signal (TOP-LEVEL keys only — robust against
# nested/decoy "cwd" tokens and pretty-printed payloads), then Set-Location into
# it so the relative .harness/… logic below works on both hosts; fall back to cwd.
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

$steerFile = '.harness/STEER.md'

if (Test-Path -LiteralPath $steerFile -PathType Leaf) {
    # Emit contents to stdout — Claude Code captures and injects.
    Get-Content -LiteralPath $steerFile -Raw

    # Rename for audit trail (UTC timestamp).
    $ts = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    Move-Item -LiteralPath $steerFile -Destination ".harness/STEER.consumed-$ts.md"
}

exit 0
