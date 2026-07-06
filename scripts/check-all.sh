#!/usr/bin/env bash
# check-all.sh — run the full local gate battery (the deterministic checks CI runs).
# Prints a PASS/FAIL table and exits non-zero if any gate fails. No host CLIs needed.
#
#   bash scripts/check-all.sh
#
# Mirrors CI's deterministic gates: lint_src · capability-naming · unit tests ·
# evidence-tracker self-test (61 embedded tests — the default-FAIL evidence
# contract, named- and singleton-plan aware) · generate drift ·
# dist-references (every emitted plugin's relative links + ${CLAUDE_PLUGIN_ROOT}
# paths resolve inside the emitted tree; grandfathers known pre-existing gaps) ·
# version bump · check-wiki --strict · check-syntax · hook-parity · check-no-pii ·
# board sync (graceful-skips when no .harness/project.json or no gh) ·
# tag-reachability (all tags must point to main-reachable commits; graceful-skip
# when no main branch exists).
# (Host plugin validation — `claude plugin validate` runs as a separate CI
# step in tests-linux.yml, installing @anthropic-ai/claude-code first; this
# script skips it since not every dev machine has that CLI. `agy plugin
# validate` has no CI-installable form — agy is not npm-distributed — so it
# stays dogfood-only, per wiki/reference/CI-Gates.md.)
#
# The "version bump" gate compares against origin/main by default and
# graceful-skips when that ref is unresolvable (see scripts/check-version-bump.py).
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
run "capability naming" python3 scripts/check-capability-naming.py
# AGENTM_INSTALL_PREFIX + MEMORY_VAULT_PATH: isolate resolve_plan.py's R2.5
# task 12 vault-mismatch guard from this MACHINE's own ~/.claude/.agentm-config.json
# — a real operator install can have storage.backend=vault configured and
# reachable, which would make dozens of tests that force the standalone
# .harness/ fallback (seam=None / resolver=None) spuriously hit the new
# refusal. Point the probe at a scratch path that never has a config file.
run "unit tests"     env AGENTM_INSTALL_PREFIX="$ROOT/.no-such-agentm-prefix" MEMORY_VAULT_PATH="" bash -c "cd scripts && python3 -m unittest discover -p 'test_*.py'"
run "evidence-tracker self-test" python3 src/code-review/hooks/evidence-tracker/evidence_tracker.py --mode self-test
run "generate drift" python3 scripts/generate.py check
run "dist-references" python3 scripts/check-dist-references.py
run "version bump"   python3 scripts/check-version-bump.py
run "check-wiki"     python3 src/wiki/scripts/check-wiki.py --strict
run "check-slop"     python3 scripts/check-slop.py --report wiki
run "voice-floor-parity" python3 scripts/check-voice-floor-parity.py --report
run "check-syntax"   bash scripts/check-syntax.sh
run "hook-parity"    python3 scripts/check-hook-parity.py
run "check-no-pii"   bash scripts/check-no-pii.sh --all
run "board sync"     python3 src/github-projects/scripts/check_project_sync.py
run "tag-reachability" python3 scripts/check_tag_reachability.py

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
