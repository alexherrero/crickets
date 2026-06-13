# kill-switch — operator emergency halt for long-running agent sessions.
# Mirrors kill-switch.sh (incl. host-portable workspace resolution) for
# Windows / pwsh hosts.
#
# Fires on Claude Code's PreToolUse event (matcher .*). If .harness/STOP
# exists in the project root, blocks the tool call with exit code 2 and
# surfaces a halt message via stderr.
#
# Operator usage:
#   New-Item .harness/STOP -ItemType File   # halt
#   Remove-Item .harness/STOP               # resume
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

if (Test-Path -LiteralPath '.harness/STOP' -PathType Leaf) {
    [Console]::Error.WriteLine('kill-switch: .harness/STOP present — halting tool call. Remove the file (Remove-Item .harness/STOP) to resume.')
    exit 2
}

exit 0
