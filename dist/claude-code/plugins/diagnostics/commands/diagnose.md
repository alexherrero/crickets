---
name: diagnose
description: Deterministic-first failure diagnosis — classify a failure, recall it via a fingerprint-first exact-match ladder (semantic fallback only on a miss), rank 2-3 hypotheses, and write one scrubbed kind:failure-incident memory entry.
kind: command
supported_hosts: [claude-code, antigravity]
version: 0.1.0
install_scope: project
argument-hint: "[--project <slug>] [--tool <name>] [--exit-code <n>] <traceback-file-or->"
---

You are running `/diagnose` — a deterministic-first failure classifier and cross-session failure-memory writer. No LLM judgment runs inside the pipeline itself (classification, fingerprinting, and recall are all mechanical); your job is to capture the failure input accurately and report the result.

**Arguments:** $ARGUMENTS

## What to do

1. **Capture the failure.** If the operator gave you a traceback/log excerpt directly in the conversation, write it to a temp file. If they referenced a command that just failed, use its actual captured stdout/stderr — never paraphrase or summarize it before diagnosis; the fingerprint normalizer needs the real text.

2. **Resolve the project slug.** Use `--project <slug>` if given; otherwise infer it from the current repo (e.g. `git remote get-url origin`'s basename), matching the vault's `projects/<slug>/...` convention.

3. **Run the pipeline.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/diagnose.py" --project <slug> [--tool <name>] [--exit-code <n>] <traceback-file>
   ```

   The script prints one JSON object to stdout:
   - `{"outcome": "layer1_hit", "path", "fingerprint", "fp_algo", "namespace"}` — this exact failure (or a recognized drifted variant) already has an incident on file. No new entry was written.
   - `{"outcome": "written", "path", "fingerprint", "fp_algo", "namespace", "hypotheses"}` — a new `kind: failure-incident` entry was written (already scrubbed of PII/secrets before it landed).

4. **Report to the operator:**
   - On `layer1_hit`: "This is a known failure (`<namespace>`) — already logged at `<path>`. No new entry written."
   - On `written`: "New `<namespace>` failure logged at `<path>`. Ranked hypotheses: `<hypotheses, numbered>`."
   - On a non-zero exit / `ERROR:` line on stderr: surface the error verbatim — do not retry silently.

## Out of scope

- This command never repairs anything — repair is a caller's job (`/bugfix`, `dependabot-fixer`). `/diagnose` only classifies, recalls, and logs.
- Scheduled/automatic health passes are not wired here — this is on-demand only.
