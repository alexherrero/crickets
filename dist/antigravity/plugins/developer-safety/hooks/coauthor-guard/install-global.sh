#!/usr/bin/env bash
# install-global — install coauthor-guard for every repo on this machine.
#
#   bash install-global.sh               install (or refresh) and set the global core.hooksPath
#   bash install-global.sh --check       exit 0 if installed and healthy, 1 if not (read-only)
#   bash install-global.sh --uninstall   unset the global core.hooksPath and remove the directory
#   --dir <path>                         hooks directory (default:
#                                        ${XDG_CONFIG_HOME:-$HOME/.config}/crickets/git-hooks)
#
# Writes git-hook-dispatch.sh into the directory once per git hook name, plus
# coauthor-guard.sh and a .crickets-managed marker, then sets
# `git config --global core.hooksPath` to it. The dispatcher hands every hook
# on to the repo's own .git/hooks/<name>, so repo hooks keep running. Refuses
# to replace a core.hooksPath it didn't set, wherever the machine's config
# sets it (system, global, or a file either includes). Idempotent: re-running
# refreshes the files in place. The directory is a copy, not a pointer into
# the plugin cache, so `claude plugin update` can't leave git pointing at a
# deleted path. --check compares every installed file with the copy shipped
# beside this script, so a replaced or stale file reads as unhealthy.
#
# Mirrored by install-global.ps1 (same files, same config, same exit codes).

set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
mode=install
dir="${XDG_CONFIG_HOME:-$HOME/.config}/crickets/git-hooks"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) mode=check ;;
        --uninstall) mode=uninstall ;;
        --dir) shift; dir="${1:?--dir needs a path}" ;;
        *) echo "install-global: unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

# The hook names git looks up in core.hooksPath (githooks(5)). Left out, so a
# repo's own hook of that name stops running while this install is active:
#   - reference-transaction and post-index-change: git fires them on every ref
#     or index update, and a shell per call turned a 40-commit rebase from
#     0.2s into 8s;
#   - push-to-checkout: its mere presence replaces git's built-in
#     updateInstead behavior;
#   - fsmonitor-watchman: configured through core.fsmonitor, not looked up here.
HOOK_NAMES=(
    applypatch-msg pre-applypatch post-applypatch
    pre-commit pre-merge-commit prepare-commit-msg commit-msg post-commit
    pre-rebase post-checkout post-merge pre-push post-rewrite
    pre-receive update proc-receive post-receive post-update
    pre-auto-gc sendemail-validate
    p4-changelist p4-prepare-changelist p4-post-changelist p4-pre-submit
)
MARKER=.crickets-managed

# Every core.hooksPath the machine's config sets outside a repo: system,
# global, and anything they [include]. The last one is the one git uses.
machine_hooks_paths() {
    (unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR; cd / && git config --includes --get-all core.hooksPath) 2>/dev/null
}
# The value in the global file itself, the one this script sets and unsets.
global_file_hooks_path() {
    git config --global --get core.hooksPath 2>/dev/null || true
}

# Compare paths by their resolved form, so ~ and symlinks don't cause a mismatch.
resolve() {
    local p="${1/#\~/$HOME}"
    if [[ -d "$p" ]]; then (cd "$p" && pwd -P); else printf '%s\n' "$p"; fi
}
is_ours() {
    [[ -n "$1" && "$(resolve "$1")" == "$(resolve "$dir")" ]]
}

all_paths=$(machine_hooks_paths)
current=$(printf '%s\n' "$all_paths" | sed -n '$p')
foreign=""
while IFS= read -r value; do
    [[ -n "$value" ]] && ! is_ours "$value" && foreign="$value"
done <<< "$all_paths"

check() {
    local problem="" name
    if [[ -z "$current" ]]; then
        problem="no core.hooksPath is set"
    elif ! is_ours "$current"; then
        problem="git uses core.hooksPath $current, not $dir"
    elif [[ ! -f "$dir/$MARKER" ]]; then
        problem="$dir is missing or not crickets-managed"
    elif ! cmp -s "$here/coauthor-guard.sh" "$dir/coauthor-guard.sh"; then
        problem="$dir/coauthor-guard.sh is missing or differs from the shipped copy"
    else
        for name in "${HOOK_NAMES[@]}"; do
            if [[ ! -x "$dir/$name" ]] || ! cmp -s "$here/git-hook-dispatch.sh" "$dir/$name"; then
                problem="$dir/$name is missing, not executable, or differs from the shipped dispatcher"
                break
            fi
        done
    fi
    if [[ -n "$problem" ]]; then
        echo "coauthor-guard: global git hooks NOT healthy — $problem" >&2
        return 1
    fi
    echo "coauthor-guard: global git hooks installed at $dir"
    # A repo-local core.hooksPath overrides the global one; name it if we're in one.
    local local_path
    local_path=$(git config --local --get core.hooksPath 2>/dev/null || true)
    if [[ -n "$local_path" ]]; then
        echo "coauthor-guard: note — this repo sets its own core.hooksPath ($local_path), which overrides the global one here"
    fi
    return 0
}

case "$mode" in
    check)
        check
        exit $?
        ;;
    uninstall)
        global_value=$(global_file_hooks_path)
        if is_ours "$global_value"; then
            git config --global --unset core.hooksPath
            echo "coauthor-guard: unset global core.hooksPath ($global_value)"
        elif [[ -n "$global_value" ]]; then
            echo "coauthor-guard: global core.hooksPath is $global_value, not $dir — left as is"
        fi
        # Delete the directory only once no config still names it: a
        # core.hooksPath pointing at a deleted directory silences every repo's hooks.
        still_named=""
        while IFS= read -r value; do
            is_ours "$value" && still_named="$value"
        done <<< "$(machine_hooks_paths)"
        if [[ -n "$still_named" ]]; then
            echo "coauthor-guard: $dir is still named by core.hooksPath ($still_named) — not removed" >&2
            exit 2
        fi
        if [[ -f "$dir/$MARKER" ]]; then
            rm -rf "$dir"
            echo "coauthor-guard: removed $dir"
        fi
        exit 0
        ;;
esac

# install
if [[ -n "$foreign" ]]; then
    echo "install-global: core.hooksPath is already set to $foreign — not replacing it." >&2
    echo "  (git config --show-origin --get-all core.hooksPath shows where.) Remove it" >&2
    echo "  first, or pass --dir $foreign only if that directory is meant to become crickets-managed." >&2
    exit 2
fi
if [[ -d "$dir" && ! -f "$dir/$MARKER" ]] && [[ -n "$(ls -A "$dir" 2>/dev/null)" ]]; then
    echo "install-global: $dir already holds files crickets didn't put there — not touching it." >&2
    exit 2
fi
for src in "$here/git-hook-dispatch.sh" "$here/coauthor-guard.sh"; do
    if [[ ! -f "$src" ]]; then
        echo "install-global: $src not found next to this script" >&2
        exit 2
    fi
done

mkdir -p "$dir" || exit 2
for name in "${HOOK_NAMES[@]}"; do
    cp "$here/git-hook-dispatch.sh" "$dir/$name" && chmod +x "$dir/$name" || exit 2
done
# Hooks an earlier version installed and this one leaves out.
for name in reference-transaction post-index-change; do
    rm -f "$dir/$name"
done
cp "$here/coauthor-guard.sh" "$dir/coauthor-guard.sh" && chmod +x "$dir/coauthor-guard.sh" || exit 2
printf 'Managed by crickets developer-safety (coauthor-guard/install-global).\nInstalled from %s\n' \
    "$here" > "$dir/$MARKER"

abs_dir=$(cd "$dir" && pwd -P)
git config --global core.hooksPath "$abs_dir" || exit 2
echo "coauthor-guard: installed ${#HOOK_NAMES[@]} hooks in $abs_dir and set global core.hooksPath"
