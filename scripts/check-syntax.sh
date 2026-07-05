#!/usr/bin/env bash
# check-syntax.sh — bash -n every .sh file in the repo.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

fail=0
count=0
while IFS= read -r f; do
    count=$((count + 1))
    if ! bash -n "$f" 2>&1; then
        echo "  FAIL: $f" >&2
        fail=1
    fi
done < <(find . -type f -name '*.sh' -not -path './.git/*')

# Also check src/pii/templates/hooks/pre-push (no .sh extension)
for hook in src/pii/templates/hooks/*; do
    [[ -f "$hook" ]] || continue
    # Heuristic: scripts that start with shebang
    head -1 "$hook" | grep -q '^#!' || continue
    count=$((count + 1))
    if ! bash -n "$hook" 2>&1; then
        echo "  FAIL: $hook" >&2
        fail=1
    fi
done

if [[ $fail -eq 0 ]]; then
    echo "check-syntax: $count file(s) parse cleanly."
fi
exit $fail
