# coauthor-guard — prepare-commit-msg hook (Windows / pwsh).
# Mirrors coauthor-guard.sh: deterministically strips any `Co-Authored-By: …`
# trailer from the commit message. Regex/string-match only, never LLM-judged.
# Not hardcoded to any one agent's name.
#
# No automated installer copies this in yet — an operator wires it in once
# manually via a `core.hooksPath` dir whose `prepare-commit-msg` invokes
# `pwsh -NoProfile -File coauthor-guard.ps1 <msg-file>`.
#
# Git calls a prepare-commit-msg hook with: $1 = path to the commit-msg file,
# $2 = commit source, $3 = commit SHA1 (amend only). Only the first is needed.

$ErrorActionPreference = 'Stop'

$msgFile = $args[0]
if (-not $msgFile -or -not (Test-Path -LiteralPath $msgFile -PathType Leaf)) {
    exit 0
}

$lines = Get-Content -LiteralPath $msgFile
$filtered = $lines | Where-Object { $_ -notmatch '(?i)^Co-Authored-By:' }
Set-Content -LiteralPath $msgFile -Value $filtered
