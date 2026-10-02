#!/usr/bin/env bash
# check-global — SessionStart check for the machine-wide coauthor-guard.
#
# Read-only, and silent unless something is wrong with an install the operator
# made: never sets config, never writes a file, always exits 0. Prints one
# line when
#   - the global core.hooksPath names a directory that doesn't exist (git
#     then runs no hooks at all, the repo's own included), or
#   - it names the crickets-managed directory and that install is broken, or
#   - the crickets-managed directory exists but the global core.hooksPath no
#     longer points at it.
# A machine that never ran install-global.sh hears nothing.
#
# Mirrored by check-global.ps1.

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
dir="${XDG_CONFIG_HOME:-$HOME/.config}/crickets/git-hooks"
fix="bash \"$here/install-global.sh\""

current=$(git config --global --get core.hooksPath 2>/dev/null || true)
current_expanded="${current/#\~/$HOME}"

if [[ -n "$current" && ! -d "$current_expanded" ]]; then
    echo "[developer-safety] WARNING: global git core.hooksPath ($current) does not exist, so git runs no hooks in any repo. Re-run: $fix"
elif [[ -n "$current" && -f "$current_expanded/.crickets-managed" ]]; then
    if ! bash "$here/install-global.sh" --check --dir "$current_expanded" >/dev/null 2>&1; then
        echo "[developer-safety] WARNING: the global coauthor-guard git hooks at $current are incomplete. Re-run: $fix"
    fi
elif [[ -z "$current" && -f "$dir/.crickets-managed" ]]; then
    echo "[developer-safety] WARNING: coauthor-guard is installed at $dir but the global core.hooksPath is unset, so agent Co-Authored-By trailers are not being stripped. Re-run: $fix"
fi
exit 0
