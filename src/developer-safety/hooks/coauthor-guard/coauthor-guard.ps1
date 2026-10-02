# coauthor-guard — prepare-commit-msg hook (Windows / pwsh).
# Mirrors coauthor-guard.sh: deterministically strips every `Co-Authored-By: …`
# trailer that names an AI agent (vendor email domain, a `[bot]` identity, or
# an agent product name — see coauthor-guard.sh for the full rule). A human
# co-author's trailer is left alone. Regex/string-match only, never LLM-judged.
# $agentRe is kept byte-identical to coauthor-guard.sh's AGENT_RE (a test pins it).
#
# The machine-wide install (install-global.sh / install-global.ps1) runs the
# .sh twin through Git for Windows' bundled bash; this twin is for wiring the
# guard into a single repo from pwsh. See hook.md § Installing.
#
# Git calls a prepare-commit-msg hook with: $1 = path to the commit-msg file,
# $2 = commit source, $3 = commit SHA1 (amend only). Only the first is needed.

$ErrorActionPreference = 'Stop'

$msgFile = $args[0]
if (-not $msgFile -or -not (Test-Path -LiteralPath $msgFile -PathType Leaf)) {
    exit 0
}

$agentRe = '@([a-z0-9-]+[.])*(anthropic[.]com|openai[.]com|cursor[.]com|aider[.]chat|ampcode[.]com|all-hands[.]dev)>|[^a-z0-9](gemini|copilot|codex|chatgpt|antigravity|aider|openhands|cursor ?agent|claude (opus|sonnet|haiku|fable|code|instant))([^a-z0-9]|$)|[^a-z0-9]gpt-[0-9]'

$lines = @(Get-Content -LiteralPath $msgFile)
$filtered = @($lines | Where-Object {
    $line = $_.ToLowerInvariant()
    -not ($line.StartsWith('co-authored-by:') -and ($line -match $agentRe -or $line.Contains('[bot]')))
})
# Leave the file untouched when nothing named an agent.
if ($filtered.Count -ne $lines.Count) {
    Set-Content -LiteralPath $msgFile -Value $filtered
}
exit 0
