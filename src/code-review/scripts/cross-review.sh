#!/usr/bin/env bash
# cross-review.sh — adversarial review via a different model (Gemini, over
# the Antigravity CLI).
#
# The in-process adversarial-reviewer runs on the same model that wrote the
# code; same-model review is an echo chamber. This script shells out to
# `agy` (Antigravity's CLI) for a cross-model second opinion.
#
# V8 proving Lane G, 2026-07-13: retargeted from the standalone `gemini` CLI
# to `agy` -- Google discontinued Gemini CLI for individuals ("migrate to
# the Antigravity suite of products"), and `agy` is the replacement that
# still serves Gemini models. One real behavioral difference drove the
# adaptation below: `gemini -p` appended piped stdin to the prompt; `agy -p`
# does NOT (confirmed live -- piped stdin is silently ignored, verified with
# a probe that echoed a stdin-only token and got back "no extra input"). So
# the review material is now concatenated directly into the `-p` argument
# string instead of piped -- `agy`'s own stdin is closed (`< /dev/null`)
# rather than left connected, since a connected-but-unread pipe was observed
# to intermittently hang the CLI until `--print-timeout` fired.
#
# Usage:
#   cat review-material.txt | .harness/scripts/cross-review.sh
#
# The stdin "review material" is already-assembled text built by the caller
# (the adversarial-reviewer-cross sub-agent). It should include delimited
# sections: the diff, the PLAN task, and optionally AGENTS.md. This is
# cross-review.sh's OWN stdin contract with its caller -- unchanged; only the
# internal agy invocation stopped using stdin.
#
# Exit codes:
#   0 — review produced, output on stdout matches the contract
#   1 — no cross-model review this time — caller should fall back: agy is
#       not installed; agy failed, returned nothing, or ran out of its print
#       timeout; or the material is over MAX_MATERIAL_BYTES, so agy was
#       never called
#   2 — no review material on stdin, or agy ran but violated the output
#       contract twice — caller decides
#
# The contract (what stdout must match): exactly one of
#   1. A failing test inside a fenced code block
#   2. A line starting with `DEFECT: path:line`
#   3. A block starting with `NO ISSUES FOUND`
# Prose-only responses are rejected.
#
# agy's print timeout does not fail the call. agy 1.2.2 writes "[agy] print
# timeout after <duration> with turn in progress; returning partial output"
# to stderr and exits 0 with what it had, usually nothing. Until 2026-09-13
# this script sent agy's stderr to /dev/null and had no marker on that
# branch: five runs of an agentm plan review left only "agy call failed
# (exit 0)" on stderr. agy's stderr is kept now, so the reason names the
# timeout, and a cut-off answer is never passed off as a finished review.
#
# Degradation is never silent: every non-zero exit goes through degrade(),
# which prints one "CROSS-REVIEW-DEGRADED: <reason>, using same-model
# reviewer" line on stdout, and nothing else there, in addition to the
# diagnostic on stderr. A missing/broken agy CLI used to leave only a stderr
# line + the exit code as evidence -- easy to miss in a transcript, and
# invisible to anything that only captures stdout. The marker text is a
# stable, grep-able contract of its own (see
# scripts/test_cross_review_degradation.py): callers should relay it verbatim
# rather than paraphrase it away (adversarial-reviewer-cross.md's Step 4
# does exactly that).

set -uo pipefail

# Closest available match to the retired `gemini-3.1-pro-preview` pin, from
# the exact display strings `agy models` serves on this machine (confirmed
# live 2026-07-13: Gemini 3.5 Flash Low/Medium/High, Gemini 3.1 Pro Low/High,
# Claude Sonnet 4.6 (Thinking), Claude Opus 4.6 (Thinking), GPT-OSS 120B
# Medium) -- `--model` takes this string verbatim, not a short id.
MODEL="Gemini 3.1 Pro (High)"

# How long agy's print mode waits for the answer, in seconds.
PRINT_TIMEOUT_SECS=180

# Review material over this many bytes degrades before agy is called (exit
# 1): past it a review measurably outruns the print timeout, and the call
# would only burn it. Measured 2026-09-13 with this framing and model, one
# call at a time, on code diffs: 34 KB answered in 112s, 50 KB in 154s,
# 67 KB in 197s, 130 KB in 239s. Of eleven runs at 67 KB or more, the
# agentm plan 07 review's five among them, one finished inside 180s: an
# 84 KB design doc, in 146s (another, 82 KB, took 304s). 50 KB is the
# largest code review measured inside the timeout; move the two together.
# CROSS_REVIEW_MAX_BYTES overrides the ceiling; 0 turns the check off.
MAX_MATERIAL_BYTES=50000

# Use `read -r -d ''` for the heredoc assignment — `$(cat <<'EOF'...)` gets
# confused by backticks inside fenced code blocks in the prompt body.
IFS='' read -r -d '' framing <<'FRAMING_EOF' || true
You are an adversarial code reviewer. The code below likely contains bugs — your job is to find them. A review that returns "looks good" is either correct (rare) or a failure of rigor (common). Default to skepticism.

You MUST produce exactly ONE of these three forms as your entire response. No prose preamble, no prose afterword.

FORM 1 — failing test (preferred):
Start with a triple-backtick fenced code block whose first line is a path comment (// or #). Put executable test code that fails against the current implementation inside the fence.

FORM 2 — specific defect reference:
DEFECT: <path/file>:<line>
Spec says: <quote or paraphrase from the PLAN task>
Actual: <what the code does>
Minimal reproducer: <input> → <actual> ≠ <expected>

FORM 3 — explicit no-issues finding (use ONLY if you genuinely found nothing after checking all categories below):
NO ISSUES FOUND
Reviewed: <file list>
Categories checked: spec adherence, edge cases, API design, security concerns without a lint rule, dead code, regressions

Categories to check:
- Spec adherence vs. the PLAN task's Verification clause
- Edge cases not covered by existing tests (empty input, boundary values, concurrent access, error paths)
- API design — public interfaces, naming, error types
- Security concerns not caught by lints
- Dead code or half-finished branches
- Regressions in code unchanged by the diff

Prose-only critiques like "consider adding error handling" or "this could be cleaner" are NOT acceptable output. If you cannot produce one of the three forms, produce NO ISSUES FOUND — but only if you honestly checked every category.
FRAMING_EOF

# Contract validation: pattern-match the first non-whitespace content.
validate() {
  local out="$1"
  # Strip leading whitespace and any markdown fence decoration, then check
  # the first few lines for one of the three markers.
  local head
  head=$(echo "$out" | sed -n '1,30p')
  if echo "$head" | grep -qE '^[[:space:]]*NO ISSUES FOUND'; then return 0; fi
  if echo "$head" | grep -qE '^[[:space:]]*DEFECT:[[:space:]]+\S+:[0-9]+'; then return 0; fi
  # Failing-test form: a fenced code block starting with `//` or `#` path comment
  if echo "$head" | grep -qE '^[[:space:]]*```'; then
    if echo "$head" | grep -qE '^[[:space:]]*(//|#)\s*\S+'; then return 0; fi
  fi
  return 1
}

call_agy() {
  local prompt="$1"
  # Concatenate the framing + the review material into ONE prompt string
  # passed via -p -- agy does not append piped stdin to the prompt (unlike
  # gemini -p), confirmed live; see the header comment. agy's own stdin is
  # explicitly closed (a connected-but-unread pipe was observed to
  # intermittently hang until --print-timeout fired).
  local full_prompt="${prompt}"$'\n\n=== REVIEW MATERIAL ==='$'\n'"${material}"
  agy -p "$full_prompt" --model "$MODEL" --print-timeout "${PRINT_TIMEOUT_SECS}s" \
    < /dev/null 2>"$agy_stderr"
}

# degrade <exit-code> <reason> [<stderr line>...] -- the one way this script
# gives up on a cross-model review. The marker is the only line it prints on
# stdout; the remaining arguments go to stderr, one per line, verbatim.
degrade() {
  local code="$1" reason="$2"
  shift 2
  echo "CROSS-REVIEW-DEGRADED: ${reason}, using same-model reviewer"
  (( $# )) && printf '%s\n' "$@" >&2
  exit "$code"
}

# ask_agy <framing> <label> -- one agy call. Returns, with the answer in
# $output, only when agy exited 0 with output and did not report its print
# timeout; every other ending degrades with exit 1. <label> goes into the
# reason (" on retry").
ask_agy() {
  local label="$2" started=$SECONDS rc elapsed when said timed_out=""
  output=$(call_agy "$1")
  rc=$?
  elapsed=$((SECONDS - started))
  said=$(tail -n 5 "$agy_stderr")
  # agy 1.2.2: "[agy] print timeout after ..."; agy 1.1.26: "Print mode:
  # timed out after ...". A looser "timed out" could be retry chatter under a
  # finished answer.
  grep -qiE 'print timeout|print mode: timed out' "$agy_stderr" && timed_out=1

  if [[ -n "$timed_out" ]]; then
    when="exit $rc after ${elapsed}s; its ${PRINT_TIMEOUT_SECS}s print timeout fired"
  elif (( elapsed >= PRINT_TIMEOUT_SECS )); then
    when="exit $rc after ${elapsed}s; its ${PRINT_TIMEOUT_SECS}s print timeout may have fired"
  else
    when="exit $rc after ${elapsed}s, before its ${PRINT_TIMEOUT_SECS}s print timeout"
  fi

  if [[ -z "$output" ]]; then
    degrade 1 "agy returned no output${label} (${when})" \
      "cross-review: agy call${label} ended without a review (${when})" ${said:+"$said"}
  fi
  if [[ -n "$timed_out" ]]; then
    # "returning partial output": the answer was cut off, even when its
    # first lines would pass validate().
    degrade 1 "agy returned partial output${label} (${when})" \
      "cross-review: agy's print timeout cut the answer off${label}; partial output follows" \
      ${said:+"$said"} "$output"
  fi
  if (( rc != 0 )); then
    degrade 1 "agy failed${label} (exit $rc after ${elapsed}s)" \
      "cross-review: agy call${label} failed (exit $rc after ${elapsed}s); its output follows" \
      ${said:+"$said"} "$output"
  fi
}

main() {
  command -v agy >/dev/null 2>&1 \
    || degrade 1 "agy CLI unavailable" "cross-review: agy CLI not found — caller should fall back"

  material=$(cat)
  [[ -n "$material" ]] \
    || degrade 2 "no review material on stdin" "cross-review: no review material on stdin"

  local ceiling="$MAX_MATERIAL_BYTES" bytes
  case "${CROSS_REVIEW_MAX_BYTES:-}" in
    '') ;;
    *[!0-9]*) echo "cross-review: ignoring CROSS_REVIEW_MAX_BYTES='${CROSS_REVIEW_MAX_BYTES}', not a byte count" >&2 ;;
    *) ceiling=$((10#$CROSS_REVIEW_MAX_BYTES)) ;;
  esac
  bytes=$(printf '%s' "$material" | LC_ALL=C wc -c)
  bytes=$((bytes))
  if (( ceiling > 0 && bytes > ceiling )); then
    degrade 1 "review material is ${bytes} bytes, over the ${ceiling}-byte ceiling for agy's ${PRINT_TIMEOUT_SECS}s print timeout" \
      "cross-review: agy not called; review the material in parts under ${ceiling} bytes, one call each"
  fi

  agy_stderr=$(mktemp "${TMPDIR:-/tmp}/cross-review.XXXXXX") \
    || degrade 1 "no temp file for agy's stderr" "cross-review: mktemp failed"
  trap 'rm -f "$agy_stderr"' EXIT

  ask_agy "$framing" ""
  if validate "$output"; then
    printf '%s\n' "$output"
    exit 0
  fi

  # Retry once with a sharper format nudge.
  retry_nudge="Your previous response did not match the required output format. Respond again using EXACTLY ONE of the three forms (failing test, DEFECT:, or NO ISSUES FOUND). No prose preamble. No prose outside the form."
  retry_framing="${framing}"$'\n\n'"${retry_nudge}"

  ask_agy "$retry_framing" " on retry"
  if validate "$output"; then
    printf '%s\n' "$output"
    exit 0
  fi

  degrade 2 "agy response violated the output contract twice" \
    "cross-review: contract violated after retry. Raw output follows on stderr." "$output"
}

# Sourcing this file (e.g. from a test harness that wants to call validate()
# directly) must not run the agy flow — only direct execution does.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
