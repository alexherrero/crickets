#!/usr/bin/env bash
# check-no-pii.sh — scan for personal information that should not ship to a public repo.
#
# Modes:
#   --all              scan the entire working tree (default)
#   --staged           scan only files staged for commit
#   --diff <range>     scan only files changed in a git range (e.g. origin/main..HEAD)
#   --help, -h         print this help and exit
#
# Exit:
#   0  clean
#   1  findings (file:line:kind:match printed to stderr)
#   2  argument error
#
# Patterns caught: emails, personal paths (mac/linux/windows), API key shapes
# (OpenAI, GitHub, GitLab, AWS), US phone numbers. See ALLOWLIST_PATTERNS below
# for known-safe substrings (the public handle, RFC 2606 reserved domains, etc.).
# A phone number counts only when it stands alone, not as a run of digits inside
# a hash, a decimal or a longer number (see stands_alone below).
#
# See CONTRIBUTING.md § PII guardrails for the full pattern list and override
# protocol.

set -uo pipefail

# ── help ──────────────────────────────────────────────────────────────────
print_help() {
    cat <<'EOF'
check-no-pii.sh — scan for personal information that should not ship to a public repo.

Modes:
  --all              scan the entire working tree (default)
  --staged           scan only files staged for commit
  --diff <range>     scan only files changed in a git range (e.g. origin/main..HEAD)
  --help, -h         print this help and exit

Exit:
  0  clean
  1  findings (file:line:kind:match printed to stderr)
  2  argument error

Patterns caught: emails, personal paths, API key shapes, US phone numbers.
See CONTRIBUTING.md § PII guardrails for the override protocol.
EOF
}

# ── argument parsing ──────────────────────────────────────────────────────
MODE="all"
DIFF_RANGE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all) MODE="all"; shift ;;
        --staged) MODE="staged"; shift ;;
        --diff)
            MODE="diff"
            DIFF_RANGE="${2:-}"
            shift 2 2>/dev/null || shift
            ;;
        --help|-h) print_help; exit 0 ;;
        *) echo "check-no-pii: unknown argument: $1" >&2; print_help >&2; exit 2 ;;
    esac
done

if [[ "$MODE" == "diff" && -z "$DIFF_RANGE" ]]; then
    echo "check-no-pii: --diff requires a range argument (e.g. origin/main..HEAD)" >&2
    exit 2
fi

# ── patterns ──────────────────────────────────────────────────────────────
# Format: KIND|REGEX (KIND is for output)
PATTERNS=(
    'email|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    'personal-path-mac|/Users/[a-zA-Z][a-zA-Z0-9_-]+/'
    'personal-path-linux|/home/[a-zA-Z][a-zA-Z0-9_-]+/'
    'personal-path-windows|C:\\{1,2}Users\\{1,2}[a-zA-Z][a-zA-Z0-9_-]+'
    'openai-key|sk-[a-zA-Z0-9_-]{20,}'
    'github-token|gh[psuro]_[a-zA-Z0-9_-]{20,}'
    'gitlab-token|glpat-[a-zA-Z0-9_-]{20,}'
    'aws-access-key|AKIA[A-Z0-9]{16}'
    # phone-us: a US number in one of four shapes, written here in N for digits.
    #   (NNN) NNN-NNNN   a bracketed area code; the separators are optional
    #   NNN-NNN-NNNN     separated by spaces, dots or hyphens; NNN-NNNNNNN and
    #                    NNNNNN-NNNN count too, but not with a lone dot, which
    #                    makes a decimal
    #   1.NNN.NNN.NNNN   dotted, after the country code
    #   NNNNNNNNNN       ten bare digits, or +1 and ten
    # The first two may open with +1. A match also has to stand alone; see
    # stands_alone below.
    'phone-us|(\+1[ .-]?)?\([2-9][0-9]{2}\)[ .-]?[0-9]{3}[ .-]?[0-9]{4}|(\+1[ .-]?)?[2-9][0-9]{2}([ .-][0-9]{3}[ .-]|[ -][0-9]{3}|[0-9]{3}[ -])[0-9]{4}|1\.[2-9][0-9]{2}\.[0-9]{3}\.[0-9]{4}|(\+1)?[2-9][0-9]{9}'
)

# Substrings that are known-safe in this repo. If a match contains any of
# these patterns, the finding is suppressed.
ALLOWLIST_PATTERNS=(
    'alexherrero'                       # public GitHub handle
    '@example\.(com|org|net)'           # RFC 2606 reserved domains
    '555-01[0-9]{2}'                    # NANP reserved phone-number prefix
    'sk-abc123def456ghi789jkl'          # documentation example
    'AKIA[A-Z0-9]{0,15}EXAMPLE'         # documentation example
    '@crickets\.local'             # synthetic identity used by commit-on-stop hook
)

# Line-level allowlist: applied to the WHOLE LINE a match sits on, for cases
# where the surrounding context proves the match harmless. Kept separate from
# ALLOWLIST_PATTERNS (match-level) so broad context patterns can't mask a real
# finding that merely shares a line with allowlisted text.
LINE_ALLOWLIST_PATTERNS=(
    'uses: [A-Za-z0-9_./-]+@[0-9a-f]{40}'  # SHA-pinned GitHub Actions (public refs; digit runs inside a SHA can mimic a phone number)
    # A line holding only a sha256 key and its 64-hex digest, in JSON, YAML or
    # key = value form (about one random digest in six has a phone-shaped run).
    # Anchored at both ends, so nothing else can share the line it passes.
    '^[[:space:]]*(-[[:space:]]+)?"?sha256"?[[:space:]]*[:=][[:space:]]*"?[0-9a-f]{64}"?,?[[:space:]]*$'
    # A Git LFS pointer's oid line, as the LFS spec writes it (a trailing CR
    # allowed): a clone without the LFS objects holds the pointer in place of
    # the file. Anchored likewise.
    '^oid sha256:[0-9a-f]{64}[[:space:]]*$'
)

# ── file collection ───────────────────────────────────────────────────────
get_files() {
    case "$MODE" in
        all) git ls-files 2>/dev/null ;;
        staged) git diff --cached --name-only --diff-filter=ACMR 2>/dev/null ;;
        diff) git diff --name-only --diff-filter=ACMR "$DIFF_RANGE" 2>/dev/null ;;
    esac
}

# ── self-skip ─────────────────────────────────────────────────────────────
SELF_SKIP_PATHS=(
    'scripts/check-no-pii.sh'                # repo-root shim
    'src/privacy/scripts/check-no-pii.sh'    # canonical (R2.4 task 7 — moved into src/pii/; re-pointed to src/privacy/ at the AG Wave A rename 2)
    'dist/claude-code/plugins/privacy/scripts/check-no-pii.sh'   # generated copy
    'dist/antigravity/plugins/privacy/scripts/check-no-pii.sh'   # AG generated copy
    '.gitleaks.toml'
    'src/privacy/skills/pii-scrubber/SKILL.md'   # v3.0 SoT copy (example-PII docs)
    'dist/claude-code/plugins/privacy/skills/pii-scrubber/SKILL.md'   # v3.0 generated copy (same example-PII docs)
    'dist/antigravity/plugins/privacy/skills/pii-scrubber/SKILL.md'   # v3.0 AG generated copy (same example-PII docs)
    'src/privacy/templates/hooks/pre-push'       # canonical (R2.4 task 7 — moved into src/pii/; re-pointed to src/privacy/ at the AG Wave A rename 2)
    'dist/claude-code/plugins/privacy/templates/hooks/pre-push'  # generated copy
    'dist/antigravity/plugins/privacy/templates/hooks/pre-push'  # AG generated copy
    'CONTRIBUTING.md'
)

is_self_skip() {
    local file="$1"
    for skip in "${SELF_SKIP_PATHS[@]}"; do
        [[ "$file" == "$skip" ]] && return 0
    done
    return 1
}

# ── allowlist check ───────────────────────────────────────────────────────
is_allowed() {
    local match="$1"
    for allow in "${ALLOWLIST_PATTERNS[@]}"; do
        if echo "$match" | grep -qE "$allow"; then
            return 0
        fi
    done
    return 1
}

is_line_allowed() {
    local line="$1"
    for allow in "${LINE_ALLOWLIST_PATTERNS[@]}"; do
        if echo "$line" | grep -qE "$allow"; then
            return 0
        fi
    done
    return 1
}

# ── combined regex (one-time build) ──────────────────────────────────────
# One grep per file instead of one grep per (file, pattern) pair — the old
# per-pattern loop spawned a binary-check + 9 pattern greps per file, which
# is cheap on Linux/Mac fork() but an order of magnitude more expensive per
# spawn under Windows Git-Bash/MSYS2 (measured: this script alone was 226s
# on Windows vs 24s on Mac for an identical commit — CI wall-time diet
# investigation, 2026-07-05, PLAN-ci-walltime-diet task 1). `-I` folds the
# old separate binary-file probe into this same single grep. Classification
# (which KIND matched) still runs per-match, not per-file, via classify_kind
# below — matches are rare, so that subprocess cost stays negligible.
COMBINED_REGEX=""
for entry in "${PATTERNS[@]}"; do
    regex="${entry#*|}"
    COMBINED_REGEX="${COMBINED_REGEX:+$COMBINED_REGEX|}($regex)"
done

classify_kind() {
    local match="$1" entry kind regex
    for entry in "${PATTERNS[@]}"; do
        kind="${entry%%|*}"
        regex="${entry#*|}"
        if grep -qE "$regex" <<<"$match" 2>/dev/null; then
            printf '%s' "$kind"
            return
        fi
    done
    printf 'unknown'
}

# ── stand-alone check (phone-us) ──────────────────────────────────────────
# A phone-shaped run of digits is often part of something longer: a sha256
# digest or a Cargo.lock checksum (hex), the digits after a decimal point, or
# a longer integer. grep -E has no look-around, so a phone-us match is checked
# in a second step, by the characters on either side of it on its line:
#   - a match that starts with a digit can't follow a hex digit or a dot;
#   - no match can be followed by a hex digit, or by a dot and a digit.
# A match that opens with "(" or "+" may follow anything. A dot after a number
# with no digit after it ends a sentence, so it doesn't count.
#
# phone-us is the only pattern whose matches hold nothing but digits, spaces,
# dots, hyphens, brackets and a plus sign. That is how the scan below tells its
# matches apart without running classify_kind.
PHONE_MATCH_RE='^[-0-9 .()+]+$'

# stands_alone MATCH BEFORE AFTER: BEFORE is the character in front of MATCH
# (empty at the start of a line), AFTER the two characters after it.
stands_alone() {
    case "$1" in
        [0123456789]*)
            case "$2" in [0123456789abcdefABCDEF.]) return 1 ;; esac
            ;;
    esac
    case "$3" in
        [0123456789abcdefABCDEF]*|.[0123456789]*) return 1 ;;
    esac
    return 0
}

# grep -o reports a line's matches left to right without overlap, so each one
# is the first occurrence of its text after the match before it. locate_match
# moves along the line past MATCH and sets $before and $after for it. $rest is
# the line after the last match placed, and $prev the character before $rest.
# If MATCH isn't there, it fails and changes nothing.
locate_match() {
    local head="${rest%%"$1"*}"
    [[ ${#head} -lt ${#rest} ]] || return 1
    [[ -n "$head" ]] && prev="${head:${#head}-1:1}"
    before="$prev"
    rest="${rest:${#head}+${#1}}"
    after="${rest:0:2}"
    prev="${1:${#1}-1:1}"
}

# Reads the current match's line into $line, once, when a check needs it.
load_line() {
    if [[ $have_line -eq 0 ]]; then
        line="$(sed -n "${lineno}p" "$file")"
        have_line=1
    fi
}

# ── scan ──────────────────────────────────────────────────────────────────
findings=0

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ ! -f "$file" ]] && continue
    is_self_skip "$file" && continue

    cur_lineno=""
    while IFS=: read -r lineno match; do
        [[ -z "$lineno" ]] && continue
        if [[ "$lineno" != "$cur_lineno" ]]; then
            cur_lineno="$lineno"; have_line=0; placing=0; earlier=""
        fi
        # A line is read only once a phone-us match on it needs checking. The
        # matches before that one are kept in $earlier, then placed first.
        if [[ "$match" =~ $PHONE_MATCH_RE ]]; then
            if [[ $placing -eq 0 ]]; then
                load_line
                rest="$line"; prev=""; placing=1
                while IFS= read -r m; do
                    [[ -n "$m" ]] && locate_match "$m"
                done <<<"$earlier"
            fi
            if locate_match "$match" && ! stands_alone "$match" "$before" "$after"; then
                continue
            fi
        elif [[ $placing -eq 1 ]]; then
            locate_match "$match"
        else
            earlier="$earlier$match"$'\n'
        fi
        is_allowed "$match" && continue
        load_line
        is_line_allowed "$line" && continue
        kind="$(classify_kind "$match")"
        echo "$file:$lineno: $kind match: $match" >&2
        findings=$((findings + 1))
    done < <(grep -nEoI "$COMBINED_REGEX" "$file" 2>/dev/null || true)
done < <(get_files)

if [[ $findings -gt 0 ]]; then
    echo "" >&2
    echo "check-no-pii: $findings finding(s) in $MODE mode" >&2
    echo "  See CONTRIBUTING.md § PII guardrails for the override protocol." >&2
    exit 1
fi

echo "check-no-pii: clean ($MODE mode)"
exit 0
