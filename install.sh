#!/usr/bin/env bash
# install.sh — agent-toolkit installer.
#
# Installs personal agent customizations (skills, sub-agents, hooks, MCP
# servers, slash commands, etc.) into a target project under host-specific
# paths (.claude/, .agent/). Also installs a pre-push git hook that runs
# check-no-pii.sh against every push.
#
# Usage:
#   install.sh [OPTIONS] <target-project-path>
#
# Options:
#   --bundle <name>          install one bundle (instead of all)
#   --skill <name>           install one standalone skill (instead of all)
#   --agent <name>           install one standalone agent (instead of all)
#   --hook <name>            install one standalone hook (instead of all)
#   --all                    install everything (default)
#   --update                 true-sync; wipe and recreate managed dirs
#   --no-pre-push-hook       skip pre-push hook installation
#   --no-legacy-cleanup      suppress the legacy .agents/skills/ cleanup prompt
#                            (v0.9.0+ removed gemini-cli host; the installer
#                             detects pre-existing .agents/skills/ from a prior
#                             install and offers backup+remove with operator
#                             confirmation. This flag skips the prompt entirely
#                             — useful for CI / scripted installs.)
#   --no-python-deps         skip the pip-install step for the toolkit's
#                            Python deps (pyyaml, sqlite-vec, sentence-
#                            transformers). Use if you manage Python deps
#                            via virtualenv / conda / system packages, or
#                            in CI to avoid the ~1.3GB sentence-transformers
#                            download per workflow run.
#   --no-skill-index         skip the personal-skills auto-indexer step
#                            (plan #7b task 1). Best-effort post-install
#                            run that walks SKILL.md across the toolkit +
#                            harness sibling and writes pointer entries to
#                            MemoryVault/personal-skills/. Requires
#                            MEMORY_VAULT_PATH; silently skipped if unset.
#   --help, -h               print this help and exit

set -euo pipefail

# ── argument parsing ──────────────────────────────────────────────────────
TARGET=""
MODE_ALL=1
SELECT_BUNDLE=""
SELECT_SKILL=""
SELECT_AGENT=""
SELECT_HOOK=""
UPDATE_MODE=0
NO_PRE_PUSH_HOOK=0
NO_LEGACY_CLEANUP=0
NO_PYTHON_DEPS=0
NO_SKILL_INDEX=0

print_help() {
    sed -n '/^# install.sh/,/^[^#]/p' "$0" | sed 's|^# \?||' | head -n -1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all) MODE_ALL=1; SELECT_BUNDLE=""; SELECT_SKILL=""; SELECT_AGENT=""; SELECT_HOOK=""; shift ;;
        --bundle)
            MODE_ALL=0; SELECT_BUNDLE="${2:-}"
            [[ -z "$SELECT_BUNDLE" ]] && { echo "--bundle requires a name" >&2; exit 2; }
            shift 2
            ;;
        --skill)
            MODE_ALL=0; SELECT_SKILL="${2:-}"
            [[ -z "$SELECT_SKILL" ]] && { echo "--skill requires a name" >&2; exit 2; }
            shift 2
            ;;
        --agent)
            MODE_ALL=0; SELECT_AGENT="${2:-}"
            [[ -z "$SELECT_AGENT" ]] && { echo "--agent requires a name" >&2; exit 2; }
            shift 2
            ;;
        --hook)
            MODE_ALL=0; SELECT_HOOK="${2:-}"
            [[ -z "$SELECT_HOOK" ]] && { echo "--hook requires a name" >&2; exit 2; }
            shift 2
            ;;
        --update) UPDATE_MODE=1; shift ;;
        --no-pre-push-hook) NO_PRE_PUSH_HOOK=1; shift ;;
        --no-legacy-cleanup) NO_LEGACY_CLEANUP=1; shift ;;
        --no-python-deps) NO_PYTHON_DEPS=1; shift ;;
        --no-skill-index) NO_SKILL_INDEX=1; shift ;;
        --help|-h) print_help; exit 0 ;;
        --*) echo "Unknown option: $1" >&2; echo "" >&2; print_help >&2; exit 2 ;;
        *)
            if [[ -z "$TARGET" ]]; then
                TARGET="$1"; shift
            else
                echo "Unexpected positional argument: $1 (target already set to: $TARGET)" >&2
                exit 2
            fi
            ;;
    esac
done

if [[ -z "$TARGET" ]]; then
    echo "Error: <target-project-path> is required" >&2
    echo "" >&2
    print_help >&2
    exit 2
fi

if [[ ! -d "$TARGET" ]]; then
    echo "Error: target directory does not exist: $TARGET" >&2
    exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"

# ── locate toolkit root ───────────────────────────────────────────────────
TOOLKIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── source shared install plumbing ────────────────────────────────────────
# The lib reads two caller-set variables:
#   UPDATE_MODE     — already set above
#   BOUNDARY_ROOTS  — allowed cp source roots (everything under these)
BOUNDARY_ROOTS=(
    "$TOOLKIT_ROOT/skills"
    "$TOOLKIT_ROOT/commands"
    "$TOOLKIT_ROOT/agents"
    "$TOOLKIT_ROOT/hooks"
    "$TOOLKIT_ROOT/mcp-servers"
    "$TOOLKIT_ROOT/bundles"
    "$TOOLKIT_ROOT/status-line"
    "$TOOLKIT_ROOT/output-styles"
    "$TOOLKIT_ROOT/workflows"
    "$TOOLKIT_ROOT/rules"
    "$TOOLKIT_ROOT/snippets"
    "$TOOLKIT_ROOT/settings-fragments"
    "$TOOLKIT_ROOT/templates"
)

# shellcheck source=lib/install/bash/primitives.sh
. "$TOOLKIT_ROOT/lib/install/bash/primitives.sh"

# ── operate from inside target dir ────────────────────────────────────────
cd "$TARGET"

echo "==> agent-toolkit install: $TARGET"

# ── --update sync ─────────────────────────────────────────────────────────
# Managed parents the toolkit creates in a target. Each installed
# customization lands under one of these; wiping them on --update gives
# true-sync semantics.
#
# Note on .claude/agents, .gemini/agents, .claude/hooks: these parents are
# also written to by the sibling agentic-harness installer (for explorer /
# adversarial-reviewer / documenter; and harness-shipped hooks under --hooks
# mode). When both repos are installed into the same target, users must run
# BOTH installers (in either order) to land the full set; the LATER-run
# installer's --update wipes the parent before recreating from its own
# source. Documented in agent-toolkit/wiki/reference/Installer-CLI.md.
#
# Note: .claude/settings.json is NOT wiped on --update — it's user-state-merged
# (settings.json carries user-edits + hook event registrations from multiple
# tools). The toolkit re-merges its hook fragments idempotently via the
# Python helper scripts/merge-settings-fragment.py.
MANAGED_PARENTS=(
    .claude/skills
    .agent/skills
    .claude/agents
    .claude/hooks
)
EMPTY_PARENT_CANDIDATES=()

# ── legacy gemini-cli cleanup (v0.9.0+) ───────────────────────────────────
# v0.9.0 removed standalone Gemini CLI host support. Prior installs may have
# populated either:
#   - .agents/skills/<name>/ (skills installed with gemini-cli host)
#   - .gemini/agents/<name>.md (agents installed with gemini-cli host)
# Detect pre-existing entries that match currently-managed customization
# names; offer a backup-then-remove flow with operator confirmation. Defaults
# to N (no-op unless operator opts in). --no-legacy-cleanup suppresses the
# prompt entirely (useful for CI / scripted installs). Non-interactive stdin
# also skips the prompt with a one-line notice. Never hard-deletes — moves
# to timestamped backups at <path>.agent-toolkit-bak.<ts>/ per the
# pre-push-hook backup convention. Only touches entries the installer
# recognizes as toolkit-managed (matches manifest names); leaves any
# unmanaged user files alone.
legacy_cleanup_gemini_cli() {
    if [[ $NO_LEGACY_CLEANUP -eq 1 ]]; then
        return 0
    fi
    local has_legacy_skills=0 has_legacy_agents=0
    [[ -d .agents/skills ]] && has_legacy_skills=1
    [[ -d .gemini/agents ]] && has_legacy_agents=1
    if [[ $has_legacy_skills -eq 0 && $has_legacy_agents -eq 0 ]]; then
        return 0
    fi
    # Enumerate toolkit-managed names from manifests.
    local known_skill_names=() known_agent_names=() md
    for md in "$TOOLKIT_ROOT"/skills/*/SKILL.md; do
        [[ -f "$md" ]] || continue
        known_skill_names+=("$(basename "$(dirname "$md")")")
    done
    for md in "$TOOLKIT_ROOT"/bundles/*/skills/*/SKILL.md; do
        [[ -f "$md" ]] || continue
        known_skill_names+=("$(basename "$(dirname "$md")")")
    done
    for md in "$TOOLKIT_ROOT"/agents/*.md; do
        [[ -f "$md" ]] || continue
        known_agent_names+=("$(basename "$md" .md)")
    done
    for md in "$TOOLKIT_ROOT"/bundles/*/agents/*.md; do
        [[ -f "$md" ]] || continue
        known_agent_names+=("$(basename "$md" .md)")
    done
    # Match .agents/skills/ entries against known SKILL names.
    local matched_skills=() entry name known
    if [[ $has_legacy_skills -eq 1 ]]; then
        for entry in .agents/skills/*; do
            [[ -d "$entry" ]] || continue
            name="$(basename "$entry")"
            for known in "${known_skill_names[@]}"; do
                if [[ "$name" == "$known" ]]; then
                    matched_skills+=("$entry")
                    break
                fi
            done
        done
    fi
    # Match .gemini/agents/ entries against known AGENT names.
    local matched_agents=()
    if [[ $has_legacy_agents -eq 1 ]]; then
        for entry in .gemini/agents/*.md; do
            [[ -f "$entry" ]] || continue
            name="$(basename "$entry" .md)"
            for known in "${known_agent_names[@]}"; do
                if [[ "$name" == "$known" ]]; then
                    matched_agents+=("$entry")
                    break
                fi
            done
        done
    fi
    if [[ ${#matched_skills[@]} -eq 0 && ${#matched_agents[@]} -eq 0 ]]; then
        return 0
    fi
    echo ""
    echo "==> legacy gemini-cli cleanup"
    echo "agent-toolkit v0.9.0+ removed standalone Gemini CLI host support."
    echo "Found legacy toolkit-managed entries from a prior install:"
    local m
    if [[ ${#matched_skills[@]} -gt 0 ]]; then
        for m in "${matched_skills[@]}"; do
            echo "  - $m/  (legacy skill destination)"
        done
    fi
    if [[ ${#matched_agents[@]} -gt 0 ]]; then
        for m in "${matched_agents[@]}"; do
            echo "  - $m  (legacy agent destination)"
        done
    fi
    echo ""
    echo -n "Move to timestamped backup(s) and remove from active install paths? [y/N]: "
    local response=""
    if [[ -t 0 ]]; then
        if ! read -r response; then
            response=""
        fi
    else
        echo ""
        echo "    (non-interactive stdin — defaulting to N; pass --no-legacy-cleanup to suppress this notice)"
    fi
    if [[ "$response" =~ ^[Yy]$ ]]; then
        local ts
        ts="$(date +%Y%m%d%H%M%S)"
        if [[ ${#matched_skills[@]} -gt 0 ]]; then
            local bak=".agents/skills.agent-toolkit-bak.$ts"
            mv .agents/skills "$bak"
            echo "    moved .agents/skills/ → $bak/"
            if [[ -d .agents ]] && [[ -z "$(ls -A .agents 2>/dev/null)" ]]; then
                rmdir .agents
                echo "    removed empty .agents/ directory"
            fi
        fi
        if [[ ${#matched_agents[@]} -gt 0 ]]; then
            local bak=".gemini/agents.agent-toolkit-bak.$ts"
            mv .gemini/agents "$bak"
            echo "    moved .gemini/agents/ → $bak/"
            if [[ -d .gemini ]] && [[ -z "$(ls -A .gemini 2>/dev/null)" ]]; then
                rmdir .gemini
                echo "    removed empty .gemini/ directory"
            fi
        fi
    else
        echo "    cleanup skipped — to remove manually later:"
        [[ $has_legacy_skills -eq 1 ]] && echo "        rm -rf .agents/skills/"
        [[ $has_legacy_agents -eq 1 ]] && echo "        rm -rf .gemini/agents/"
        echo "    (or re-run with --no-legacy-cleanup to suppress this prompt)"
    fi
    echo ""
}

legacy_cleanup_gemini_cli

if [[ $UPDATE_MODE -eq 1 ]]; then
    echo "==> sync mode: wiping toolkit-managed dirs before recreate from source"
    if [[ ${#EMPTY_PARENT_CANDIDATES[@]} -gt 0 ]]; then
        sync_managed_parents \
            "${MANAGED_PARENTS[@]}" \
            -- \
            "${EMPTY_PARENT_CANDIDATES[@]}"
    else
        sync_managed_parents \
            "${MANAGED_PARENTS[@]}" \
            --
    fi
fi

# ── helpers ───────────────────────────────────────────────────────────────

# get_field <manifest-path> <field>
# Reads a YAML frontmatter field via scripts/manifest-info.py.
get_field() {
    local file="$1" field="$2"
    python3 "$TOOLKIT_ROOT/scripts/manifest-info.py" "$file" "$field"
}

# install_skill <source-dir> <skill-name> <comma-separated-hosts>
# Dispatches a skill to per-host destinations under the current dir ($TARGET).
install_skill() {
    local src_dir="$1" name="$2" hosts="$3"
    IFS=',' read -ra host_array <<< "$hosts"
    local host
    for host in "${host_array[@]}"; do
        # Strip whitespace
        host="${host// /}"
        [[ -z "$host" ]] && continue
        case "$host" in
            claude-code)
                mkdir -p .claude/skills
                cp_managed_dir "$src_dir" ".claude/skills/$name"
                ;;
            antigravity)
                mkdir -p .agent/skills
                cp_managed_dir "$src_dir" ".agent/skills/$name"
                ;;
            *)
                echo "    warning: unknown host '$host' for skill '$name' — skipped" >&2
                ;;
        esac
    done
}

# install_hook <hook-dir> <hook-name> <comma-separated-hosts>
# Dispatches a hook to per-host destinations. v0.7.0: claude-code only —
# antigravity has no first-class hook surface.
# For claude-code: copy the .sh script to .claude/hooks/<name>.sh (chmod +x)
# AND merge settings-fragment-bash.json into .claude/settings.json via the
# Python helper scripts/merge-settings-fragment.py.
install_hook() {
    local hook_dir="$1" name="$2" hosts="$3"
    IFS=',' read -ra host_array <<< "$hosts"
    local host
    for host in "${host_array[@]}"; do
        host="${host// /}"
        [[ -z "$host" ]] && continue
        case "$host" in
            claude-code)
                local script_src="$hook_dir/$name.sh"
                local fragment_src="$hook_dir/settings-fragment-bash.json"
                if [[ ! -f "$script_src" ]]; then
                    echo "    warning: hook '$name' missing $name.sh — skipped" >&2
                    continue
                fi
                if [[ ! -f "$fragment_src" ]]; then
                    echo "    warning: hook '$name' missing settings-fragment-bash.json — skipped" >&2
                    continue
                fi
                mkdir -p .claude/hooks
                cp_managed "$script_src" ".claude/hooks/$name.sh"
                chmod +x ".claude/hooks/$name.sh"
                # Copy any sibling Python helpers (foo.py / foo_helper.py / etc.)
                # alongside the hook script. Lets hooks ship a Python helper
                # without requiring it to live in a separate skill dir.
                # Plan #9 (evidence-tracker) introduced this pattern.
                shopt -s nullglob
                for py_src in "$hook_dir"/*.py; do
                    py_name="$(basename "$py_src")"
                    cp_managed "$py_src" ".claude/hooks/$py_name"
                done
                shopt -u nullglob
                mkdir -p .claude
                python3 "$TOOLKIT_ROOT/scripts/merge-settings-fragment.py" \
                    .claude/settings.json "$fragment_src"
                ;;
            antigravity)
                echo "    warning: host 'antigravity' has no first-class hook surface (v0.7.0); skipped for hook '$name'" >&2
                ;;
            *)
                echo "    warning: unknown host '$host' for hook '$name' — skipped" >&2
                ;;
        esac
    done
}

# install_agent <source-file> <agent-name> <comma-separated-hosts>
# Dispatches an agent to per-host destinations. Source is a single .md file.
# Claude Code: file-level at .claude/agents/<name>.md.
# Antigravity: no first-class sub-agent surface — agent gets wrapped as a
# skill at .agent/skills/<name>/SKILL.md per the locked per-host paths table.
install_agent() {
    local src_file="$1" name="$2" hosts="$3"
    IFS=',' read -ra host_array <<< "$hosts"
    local host
    for host in "${host_array[@]}"; do
        host="${host// /}"
        [[ -z "$host" ]] && continue
        case "$host" in
            claude-code)
                mkdir -p .claude/agents
                cp_managed "$src_file" ".claude/agents/$name.md"
                ;;
            antigravity)
                mkdir -p ".agent/skills/$name"
                cp_managed "$src_file" ".agent/skills/$name/SKILL.md"
                ;;
            *)
                echo "    warning: unknown host '$host' for agent '$name' — skipped" >&2
                ;;
        esac
    done
}

# install_pre_push_hook
# Copies templates/hooks/pre-push → <target>/.git/hooks/pre-push.
# Skips if --no-pre-push-hook or target isn't a git repo.
# Backs up any existing non-matching hook to .agent-toolkit-bak.<timestamp>.
install_pre_push_hook() {
    if [[ $NO_PRE_PUSH_HOOK -eq 1 ]]; then
        echo "  skipping pre-push hook (--no-pre-push-hook)"
        return 0
    fi
    if [[ ! -d .git ]]; then
        echo "  skipping pre-push hook (target is not a git repo)" >&2
        return 0
    fi
    local hook_src="$TOOLKIT_ROOT/templates/hooks/pre-push"
    local hook_dst=".git/hooks/pre-push"
    if [[ ! -f "$hook_src" ]]; then
        echo "  WARNING: hook template not found at $hook_src — pre-push hook not installed" >&2
        return 0
    fi
    if [[ -e "$hook_dst" ]]; then
        if cmp -s "$hook_src" "$hook_dst"; then
            echo "    kept    $hook_dst (already managed by agent-toolkit)"
            return 0
        fi
        local bak="${hook_dst}.agent-toolkit-bak.$(date +%s)"
        cp "$hook_dst" "$bak"
        echo "    backed up existing $hook_dst → $bak"
    fi
    cp "$hook_src" "$hook_dst"
    chmod +x "$hook_dst"
    echo "    installed $hook_dst"
}

# warn_unsupported_kind <kind>
warn_unsupported_kind() {
    echo "    warning: kind '$1' is not yet supported in agent-toolkit v0.1.0 — skipped" >&2
}

# ── install bundles ───────────────────────────────────────────────────────
install_bundles() {
    local bundle_md bundle_dir bundle_name hosts
    for bundle_md in "$TOOLKIT_ROOT"/bundles/*/bundle.md; do
        [[ -f "$bundle_md" ]] || continue
        bundle_dir="$(dirname "$bundle_md")"
        bundle_name="$(basename "$bundle_dir")"
        if [[ $MODE_ALL -eq 0 && -n "$SELECT_BUNDLE" && "$SELECT_BUNDLE" != "$bundle_name" ]]; then
            continue
        fi
        echo "==> installing bundle: $bundle_name"
        hosts="$(get_field "$bundle_md" supported_hosts)"
        if [[ -z "$hosts" ]]; then
            echo "    warning: bundle '$bundle_name' has no supported_hosts — skipped" >&2
            continue
        fi

        # Plan #10: contents-driven dispatch with sibling-reference resolution.
        # For each `- kind: name` in the manifest's contents:, prefer the
        # standalone toolkit location (<TOOLKIT_ROOT>/<kind>s/<name>/) over
        # the bundle-local copy (<bundle_dir>/<kind>s/<name>/). Bundle-local
        # is the legacy fallback (example-bundle uses it for its stub skill).
        # Single source of truth: each primitive lives once at the standalone
        # location; the bundle is just a manifest referencing the set.
        local contents_pairs
        contents_pairs="$(python3 - "$bundle_md" <<'PYEOF'
import sys, yaml
with open(sys.argv[1], encoding="utf-8") as f:
    text = f.read()
parts = text.split("---", 2)
if len(parts) < 3:
    sys.exit(0)
try:
    fm = yaml.safe_load(parts[1]) or {}
except yaml.YAMLError:
    sys.exit(0)
for entry in fm.get("contents", []) or []:
    if isinstance(entry, dict) and len(entry) == 1:
        kind, name = next(iter(entry.items()))
        print(f"{kind}\t{name}")
PYEOF
)"

        if [[ -z "$contents_pairs" ]]; then
            echo "    warning: bundle '$bundle_name' has empty/unparseable contents — skipped" >&2
            continue
        fi

        local entry_kind entry_name standalone_path bundle_local_path src_path
        while IFS=$'\t' read -r entry_kind entry_name; do
            [[ -z "$entry_kind" ]] && continue
            case "$entry_kind" in
                skill)
                    standalone_path="$TOOLKIT_ROOT/skills/$entry_name"
                    bundle_local_path="$bundle_dir/skills/$entry_name"
                    if [[ -f "$standalone_path/SKILL.md" ]]; then
                        src_path="$standalone_path"
                    elif [[ -f "$bundle_local_path/SKILL.md" ]]; then
                        src_path="$bundle_local_path"
                    else
                        echo "    warning: bundle '$bundle_name' skill '$entry_name' not found at $standalone_path or $bundle_local_path — skipped" >&2
                        continue
                    fi
                    install_skill "$src_path" "$entry_name" "$hosts"
                    ;;
                agent)
                    standalone_path="$TOOLKIT_ROOT/agents/$entry_name.md"
                    bundle_local_path="$bundle_dir/agents/$entry_name.md"
                    if [[ -f "$standalone_path" ]]; then
                        src_path="$standalone_path"
                    elif [[ -f "$bundle_local_path" ]]; then
                        src_path="$bundle_local_path"
                    else
                        echo "    warning: bundle '$bundle_name' agent '$entry_name' not found at $standalone_path or $bundle_local_path — skipped" >&2
                        continue
                    fi
                    install_agent "$src_path" "$entry_name" "$hosts"
                    ;;
                hook)
                    standalone_path="$TOOLKIT_ROOT/hooks/$entry_name"
                    bundle_local_path="$bundle_dir/hooks/$entry_name"
                    if [[ -f "$standalone_path/hook.md" ]]; then
                        src_path="$standalone_path"
                    elif [[ -f "$bundle_local_path/hook.md" ]]; then
                        src_path="$bundle_local_path"
                    else
                        echo "    warning: bundle '$bundle_name' hook '$entry_name' not found at $standalone_path or $bundle_local_path — skipped" >&2
                        continue
                    fi
                    install_hook "$src_path" "$entry_name" "$hosts"
                    ;;
                *)
                    warn_unsupported_kind "$entry_kind"
                    ;;
            esac
        done <<< "$contents_pairs"
    done
}

# ── install standalone skills ─────────────────────────────────────────────
install_standalone_skills() {
    local skill_md skill_dir skill_name hosts kind
    for skill_md in "$TOOLKIT_ROOT"/skills/*/SKILL.md; do
        [[ -f "$skill_md" ]] || continue
        skill_dir="$(dirname "$skill_md")"
        skill_name="$(basename "$skill_dir")"
        if [[ $MODE_ALL -eq 0 && -n "$SELECT_SKILL" && "$SELECT_SKILL" != "$skill_name" ]]; then
            continue
        fi
        kind="$(get_field "$skill_md" kind)"
        if [[ "$kind" != "skill" ]]; then
            echo "    warning: $skill_md has kind '$kind' (expected 'skill') — skipped" >&2
            continue
        fi
        hosts="$(get_field "$skill_md" supported_hosts)"
        if [[ -z "$hosts" ]]; then
            echo "    warning: skill '$skill_name' has no supported_hosts — skipped" >&2
            continue
        fi
        echo "==> installing skill: $skill_name"
        install_skill "$skill_dir" "$skill_name" "$hosts"
    done
}

# ── install standalone hooks ──────────────────────────────────────────────
install_standalone_hooks() {
    local hook_md hook_dir hook_name hosts kind
    for hook_md in "$TOOLKIT_ROOT"/hooks/*/hook.md; do
        [[ -f "$hook_md" ]] || continue
        hook_dir="$(dirname "$hook_md")"
        hook_name="$(basename "$hook_dir")"
        if [[ $MODE_ALL -eq 0 && -n "$SELECT_HOOK" && "$SELECT_HOOK" != "$hook_name" ]]; then
            continue
        fi
        kind="$(get_field "$hook_md" kind)"
        if [[ "$kind" != "hook" ]]; then
            echo "    warning: $hook_md has kind '$kind' (expected 'hook') — skipped" >&2
            continue
        fi
        hosts="$(get_field "$hook_md" supported_hosts)"
        if [[ -z "$hosts" ]]; then
            echo "    warning: hook '$hook_name' has no supported_hosts — skipped" >&2
            continue
        fi
        echo "==> installing hook: $hook_name"
        install_hook "$hook_dir" "$hook_name" "$hosts"
    done
}

# ── install standalone agents ─────────────────────────────────────────────
install_standalone_agents() {
    local agent_md agent_name hosts kind
    for agent_md in "$TOOLKIT_ROOT"/agents/*.md; do
        [[ -f "$agent_md" ]] || continue
        agent_name="$(basename "$agent_md" .md)"
        if [[ $MODE_ALL -eq 0 && -n "$SELECT_AGENT" && "$SELECT_AGENT" != "$agent_name" ]]; then
            continue
        fi
        kind="$(get_field "$agent_md" kind)"
        if [[ "$kind" != "agent" ]]; then
            echo "    warning: $agent_md has kind '$kind' (expected 'agent') — skipped" >&2
            continue
        fi
        hosts="$(get_field "$agent_md" supported_hosts)"
        if [[ -z "$hosts" ]]; then
            echo "    warning: agent '$agent_name' has no supported_hosts — skipped" >&2
            continue
        fi
        echo "==> installing agent: $agent_name"
        install_agent "$agent_md" "$agent_name" "$hosts"
    done
}

# ── warn about other unsupported kinds at top level ───────────────────────
warn_unsupported_top_level() {
    local kind
    for kind in commands mcp-servers status-line output-styles workflows rules snippets settings-fragments; do
        if [[ -d "$TOOLKIT_ROOT/$kind" ]] && find "$TOOLKIT_ROOT/$kind" -mindepth 1 -not -name '.gitkeep' -print -quit 2>/dev/null | grep -q .; then
            warn_unsupported_kind "$kind"
        fi
    done
}

# ── run ───────────────────────────────────────────────────────────────────
if [[ $MODE_ALL -eq 1 || -n "$SELECT_BUNDLE" ]]; then
    install_bundles
fi

if [[ $MODE_ALL -eq 1 || -n "$SELECT_SKILL" ]]; then
    install_standalone_skills
fi

if [[ $MODE_ALL -eq 1 || -n "$SELECT_AGENT" ]]; then
    install_standalone_agents
fi

if [[ $MODE_ALL -eq 1 || -n "$SELECT_HOOK" ]]; then
    install_standalone_hooks
fi

if [[ $MODE_ALL -eq 1 ]]; then
    warn_unsupported_top_level
fi

echo "==> pre-push hook"
install_pre_push_hook

install_python_deps() {
    # Best-effort install of the toolkit's Python deps from requirements.txt.
    # Failure is logged but does NOT fail the toolkit install — the graceful-
    # skip contracts (memory skill falls back to grep+frontmatter without
    # sentence-transformers; vec-index ops no-op without sqlite-vec) mean
    # operators can still use most functionality. The pip-install is
    # opportunistic; the toolkit's contract is "tries to set you up but
    # never blocks the install on Python dep state."
    if [[ "$NO_PYTHON_DEPS" -eq 1 ]]; then
        echo "==> python deps: skipped (--no-python-deps)"
        return 0
    fi
    if [[ ! -f "$TOOLKIT_ROOT/requirements.txt" ]]; then
        echo "WARN: requirements.txt missing at $TOOLKIT_ROOT; python deps not installed" >&2
        return 0
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        echo "WARN: python3 not found on PATH; python deps not installed" >&2
        echo "      install Python 3.9+ and re-run, or pass --no-python-deps to suppress" >&2
        return 0
    fi
    if ! python3 -m pip --version >/dev/null 2>&1; then
        echo "WARN: pip not available; python deps not installed" >&2
        return 0
    fi
    echo "==> python deps"
    # Idempotent quick-path: skip if all three are already importable.
    if python3 -c "import yaml, sqlite_vec, sentence_transformers" >/dev/null 2>&1; then
        echo "    pyyaml + sqlite-vec + sentence-transformers already installed"
        return 0
    fi
    echo "    installing pyyaml + sqlite-vec + sentence-transformers from requirements.txt"
    echo "    (sentence-transformers pulls torch + transformers + tokenizers; first install can take 2-5min)"
    # Try --user first (works on Homebrew Python, conda, most distros).
    # On PEP 668 systems (Debian 12+, recent macOS system Python), operator
    # may need --break-system-packages — surfaced as a manual fallback hint
    # if pip install fails.
    if python3 -m pip install --user --quiet -r "$TOOLKIT_ROOT/requirements.txt" 2>&1; then
        echo "    installed (note: sentence-transformers' default BGE-large model — ~1.3GB — downloads lazily on first /memory save or embed.py --mode local)"
    else
        cat >&2 << EOF
WARN: pip install failed.
      The toolkit will graceful-skip embedding + vec-index operations until
      Python deps are installed. To install manually:
        python3 -m pip install --user -r $TOOLKIT_ROOT/requirements.txt
      If on a PEP 668 system (Debian 12+, recent macOS system Python):
        python3 -m pip install --user --break-system-packages -r $TOOLKIT_ROOT/requirements.txt
      Or rerun install.sh with --no-python-deps to suppress this attempt.
EOF
    fi
}

install_python_deps

index_personal_skills() {
    # Best-effort: run the personal-skills auto-indexer against the
    # toolkit's own skills/ + the sibling agentic-harness/.claude/skills/
    # if discoverable. Pointers land in MemoryVault/personal-skills/<repo>/.
    # Requires MEMORY_VAULT_PATH to be set (we don't guess the vault path —
    # operators without a vault configured silently skip this).
    if [[ "$NO_SKILL_INDEX" -eq 1 ]]; then
        echo "==> personal-skills index: skipped (--no-skill-index)"
        return 0
    fi
    local indexer="$TOOLKIT_ROOT/skills/memory/scripts/index_skills.py"
    if [[ ! -f "$indexer" ]]; then
        # Memory skill not yet shipped to this toolkit checkout (would only
        # happen on a pre-#7b checkout). Nothing to do.
        return 0
    fi
    if [[ -z "${MEMORY_VAULT_PATH:-}" ]]; then
        echo "==> personal-skills index: skipped (MEMORY_VAULT_PATH unset)"
        return 0
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        return 0
    fi
    echo "==> personal-skills index"
    local toolkit_skills="$TOOLKIT_ROOT/skills"
    local args=("--vault-path" "$MEMORY_VAULT_PATH" "--skill-path" "$toolkit_skills")
    # Also index the sibling agentic-harness skills if present (canonical
    # clone is ~/Antigravity/agentic-harness, sibling to ~/Antigravity/
    # agent-toolkit). The toolkit + harness are deliberately co-located.
    local harness_sibling="$TOOLKIT_ROOT/../agentic-harness/.claude/skills"
    if [[ -d "$harness_sibling" ]]; then
        args+=("--skill-path" "$harness_sibling")
    fi
    if ! python3 "$indexer" "${args[@]}" 2>&1; then
        echo "WARN: personal-skills indexer exited non-zero — pointers may be incomplete" >&2
        # Non-fatal: skill-pointer entries are nice-to-have, not load-bearing.
    fi
}

index_personal_skills

echo ""
echo "agent-toolkit install: complete."
