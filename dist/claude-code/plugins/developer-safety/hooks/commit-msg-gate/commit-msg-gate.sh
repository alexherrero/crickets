#!/usr/bin/env bash
# commit-msg-gate — commit-msg hook.
#
# Rejects a commit whose SUBJECT LINE (never the body) matches an internal
# codename pattern (AA/C/FIN/R/G families, "Wave A".."Wave E", PLAN-<slug>) or
# reuses this repo's own slop-pack vocabulary at warning-tier or above
# (Consolidation ruling 4 — "Commit messages, go-forward"). Conventional-
# commit prefixes (feat:/fix:/...) and a roadmap id in parentheses (e.g.
# "(V6-15)") are unaffected.
#
# Thin dispatch shim only — all matching logic lives in the co-located
# commit_msg_gate.py (it needs to read src/wiki/skills/wiki-author's JSON
# rule pack, which is far more naturally done in Python than re-parsed here;
# mirrors evidence-tracker's .sh/.py split in src/code-review/hooks/).
#
# No automated installer copies this in yet (mirrors coauthor-guard's own
# convention) — an operator installs it once per repo. Unlike coauthor-guard,
# this hook needs its co-located commit_msg_gate.py alongside it (this shim
# just dispatches to it) — copy BOTH files:
#   cp src/developer-safety/hooks/commit-msg-gate/commit-msg-gate.sh \
#     .git/hooks/commit-msg
#   cp src/developer-safety/hooks/commit-msg-gate/commit_msg_gate.py \
#     .git/hooks/commit_msg_gate.py
#   chmod +x .git/hooks/commit-msg
# (installs alongside coauthor-guard.sh's own .git/hooks/prepare-commit-msg —
# commit-msg and prepare-commit-msg are different git hook slots that fire at
# different stages and don't conflict.)
#
# Git calls a commit-msg hook with: $1 = path to the commit-msg file. A non-
# zero exit aborts the commit.

set -uo pipefail

msg_file="${1:-}"
[[ -n "$msg_file" ]] || exit 0

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python=""
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    python="$cmd"
    break
  fi
done

if [[ -z "$python" ]]; then
  echo "commit-msg-gate: no python3/python found -- skipping codename/slop check (allowing commit)" >&2
  exit 0
fi

# An installed copy of this hook is a snapshot: its commit_msg_gate.py goes stale
# when crickets moves the rule pack (v8.0.0 did). So run the gate from a crickets
# checkout when one is found, by the same ladder the gate uses for the rule pack:
# $CRICKETS_REPO_ROOT, this repo, its main checkout, then a sibling crickets/.
# The co-located copy is the fallback.
rel="src/developer-safety/hooks/commit-msg-gate/commit_msg_gate.py"
gate="$here/commit_msg_gate.py"
roots=()
[[ -n "${CRICKETS_REPO_ROOT:-}" ]] && roots+=("$CRICKETS_REPO_ROOT")
top="$(git rev-parse --show-toplevel 2>/dev/null || true)"
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
for r in "$top" "${common:+$(dirname "$common")}"; do
  [[ -n "$r" ]] && roots+=("$r" "$(dirname "$r")/crickets")
done
# ${roots[@]+...}: an empty array is "unbound" under set -u on macOS bash 3.2.
for r in ${roots[@]+"${roots[@]}"}; do
  if [[ -f "$r/$rel" ]]; then
    gate="$r/$rel"
    break
  fi
done

"$python" "$gate" "$msg_file"
exit $?
