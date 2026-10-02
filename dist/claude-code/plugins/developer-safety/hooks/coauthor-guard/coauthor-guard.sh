#!/usr/bin/env bash
# coauthor-guard — prepare-commit-msg hook.
#
# Deterministically strips every `Co-Authored-By: …` trailer that names an AI
# agent from the commit message before it's presented to the human. A human
# co-author's trailer is left alone. Regex/string-match only, never
# LLM-judged (mirrors content-refresh's mechanical-vs-judgment-bound split and
# the diagnostics privacy scrub's determinism discipline).
#
# A trailer names an agent when, case-insensitively, it has any of:
#   - an email at an agent vendor's domain (anthropic.com, openai.com,
#     cursor.com, aider.chat, ampcode.com, all-hands.dev, subdomains too);
#   - a GitHub App identity — `[bot]` anywhere on the line (Copilot's coding
#     agent, Jules, Devin and Gemini Code Assist commit or co-author as one);
#   - an agent product name as a whole word: Gemini, Copilot, Codex, ChatGPT,
#     GPT-<n>, Antigravity, Aider, OpenHands, Cursor Agent, or Claude followed
#     by a model or product name (Opus, Sonnet, Haiku, Fable, Code, Instant).
# A bare "Claude" with a personal email is a person, and stays. AGENT_RE is
# kept byte-identical to coauthor-guard.ps1's $agentRe (a test pins it).
#
# Additive enforcement on top of the existing floor (the commit-no-coauthor
# snippet + the host's includeCoAuthoredBy setting) — it does not replace or
# remove that floor.
#
# Installed machine-wide by install-global.sh, which points git's global
# core.hooksPath at a directory whose prepare-commit-msg runs this script on
# every commit in every repo. See hook.md § Installing.
#
# Git calls a prepare-commit-msg hook with: $1 = path to the commit-msg file,
# $2 = commit source, $3 = commit SHA1 (amend only). Only $1 is needed here.

set -uo pipefail

msg_file="${1:-}"
[[ -n "$msg_file" && -f "$msg_file" ]] || exit 0

# No backslashes in the pattern: awk -v would process escape sequences.
AGENT_RE='@([a-z0-9-]+[.])*(anthropic[.]com|openai[.]com|cursor[.]com|aider[.]chat|ampcode[.]com|all-hands[.]dev)>|[^a-z0-9](gemini|copilot|codex|chatgpt|antigravity|aider|openhands|cursor ?agent|claude (opus|sonnet|haiku|fable|code|instant))([^a-z0-9]|$)|[^a-z0-9]gpt-[0-9]'

tmp_file="${msg_file}.coauthor-guard.tmp"
awk -v agent_re="$AGENT_RE" '
    { line = tolower($0) }
    line ~ /^co-authored-by:/ && (line ~ agent_re || index(line, "[bot]") > 0) { next }
    { print }
' "$msg_file" > "$tmp_file" && mv "$tmp_file" "$msg_file" || rm -f "$tmp_file"
exit 0
