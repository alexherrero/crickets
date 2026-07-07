#!/usr/bin/env bash
# coauthor-guard — prepare-commit-msg hook.
#
# Deterministically strips any `Co-Authored-By: …` trailer from the commit
# message before it's presented to the human. Regex/string-match only, never
# LLM-judged (mirrors content-refresh's mechanical-vs-judgment-bound split and
# the diagnostics privacy scrub's determinism discipline). Not hardcoded to
# any one agent's name — it strips the trailer line regardless of who's named
# on it.
#
# Additive enforcement on top of the existing floor (the commit-no-coauthor
# snippet + the host's includeCoAuthoredBy setting) — it does not replace or
# remove that floor.
#
# No automated installer copies this in yet — an operator installs it once
# manually: `cp src/developer-safety/hooks/coauthor-guard/coauthor-guard.sh
# .git/hooks/prepare-commit-msg && chmod +x .git/hooks/prepare-commit-msg`
# (or `git config core.hooksPath` to a dir containing it).
#
# Git calls a prepare-commit-msg hook with: $1 = path to the commit-msg file,
# $2 = commit source, $3 = commit SHA1 (amend only). Only $1 is needed here.

set -uo pipefail

msg_file="${1:-}"
[[ -n "$msg_file" && -f "$msg_file" ]] || exit 0

tmp_file="${msg_file}.coauthor-guard.tmp"
awk 'tolower($0) !~ /^co-authored-by:/' "$msg_file" > "$tmp_file" && mv "$tmp_file" "$msg_file"
