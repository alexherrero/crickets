#!/usr/bin/env bash
# coauthor-guard — prepare-commit-msg hook.
#
# Deterministically strips every `Co-Authored-By: …` trailer that names an AI
# agent from the commit message before it's presented to the human. A human
# co-author's trailer is left alone. Regex/string-match only, never
# LLM-judged (mirrors content-refresh's mechanical-vs-judgment-bound split and
# the diagnostics privacy scrub's determinism discipline).
#
# A trailer is any line whose key is `Co-Authored-By` (case-insensitive, with
# optional spaces or tabs before the colon, as git itself parses it). It names
# an agent when any of these hold:
#   - DOMAIN_RE: an email at an agent vendor's domain (anthropic.com,
#     openai.com, cursor.com, aider.chat, ampcode.com, all-hands.dev,
#     subdomains too), with or without the <> around it. A person writing from
#     one of those domains counts as that vendor's agent;
#   - a GitHub App identity — `[bot]` anywhere in the value (Copilot's coding
#     agent, Jules, Devin and Gemini Code Assist commit or co-author as one);
#   - NAME_RE, matched against the name only (the part before `<`), so a
#     person's address at gemini.com never trips it: Gemini, Copilot,
#     Codex, ChatGPT, GPT-<n>, Antigravity, Aider, OpenHands, Cursor Agent, or
#     Claude followed by a model or product name (Opus, Sonnet, Haiku, Fable,
#     Code, Instant).
# A bare "Claude" with a personal email is a person, and stays. DOMAIN_RE and
# NAME_RE are kept byte-identical to coauthor-guard.ps1's (a test pins them).
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

# No backslashes in the patterns: awk -v would process escape sequences.
DOMAIN_RE='@([a-z0-9-]+[.])*(anthropic[.]com|openai[.]com|cursor[.]com|aider[.]chat|ampcode[.]com|all-hands[.]dev)([^a-z0-9.-]|$)'
NAME_RE='[^a-z0-9](gemini|copilot|codex|chatgpt|antigravity|aider|openhands|cursor ?agent|claude (opus|sonnet|haiku|fable|code|instant))([^a-z0-9]|$)|[^a-z0-9]gpt-[0-9]'

tmp_file="${msg_file}.coauthor-guard.tmp"
awk -v domain_re="$DOMAIN_RE" -v name_re="$NAME_RE" '
    { line = tolower($0) }
    line ~ /^co-authored-by[ \t]*:/ {
        value = line
        sub(/^co-authored-by[ \t]*:/, "", value)
        name = value
        lt = index(name, "<")
        if (lt > 0) name = substr(name, 1, lt - 1)
        if (value ~ domain_re || (" " name) ~ name_re || index(value, "[bot]") > 0) next
    }
    { print }
' "$msg_file" > "$tmp_file" && mv "$tmp_file" "$msg_file" || rm -f "$tmp_file"
exit 0
