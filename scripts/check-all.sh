#!/usr/bin/env bash
# check-all.sh — run the full local gate battery (the deterministic checks CI runs).
# Prints a PASS/FAIL table and exits non-zero if any gate fails. No host CLIs needed.
#
#   bash scripts/check-all.sh
#
# Mirrors CI's deterministic gates: lint_src · unit tests · generate drift ·
# check-wiki --strict · check-syntax · check-no-pii. (Host plugin validation —
# `claude/agy plugin validate` — needs those CLIs and runs as a separate CI step.)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

names=(); results=(); fail=0
log="$(mktemp)"
trap 'rm -f "$log"' EXIT

run() {
  local name="$1"; shift
  printf '── %s …\n' "$name"
  if "$@" >"$log" 2>&1; then
    names+=("$name"); results+=("PASS")
  else
    names+=("$name"); results+=("FAIL"); fail=1
    echo "── $name FAILED ──────────────────────────────"
    cat "$log"
    echo "──────────────────────────────────────────────"
  fi
}

run "lint_src"       python3 scripts/lint_src.py
run "unit tests"     bash -c "cd scripts && python3 -m unittest discover -p 'test_*.py'"
run "generate drift" python3 scripts/generate.py check
run "check-wiki"     python3 src/wiki-maintenance/scripts/check-wiki.py --strict
run "check-syntax"   bash scripts/check-syntax.sh
run "check-no-pii"   bash scripts/check-no-pii.sh --all

echo
echo "════════════════ check-all ════════════════"
for i in "${!names[@]}"; do
  printf '  %-16s %s\n' "${names[$i]}" "${results[$i]}"
done
echo "════════════════════════════════════════════"
if [ "$fail" -ne 0 ]; then
  echo "check-all: FAIL — fix the gate(s) above."
  exit 1
fi
echo "check-all: PASS"
