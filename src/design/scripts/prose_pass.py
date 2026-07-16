#!/usr/bin/env python3
"""prose_pass.py — cross-model prose pass, step 1: Gemini simplifies.

The prose sibling of code-review's cross-review.sh. A simplification pass run
by the same model that wrote the prose is an echo chamber — it can't see the
sentences only the author can parse. This script shells out to `agy`
(Antigravity's CLI; the standalone `gemini` CLI is sunset for individual
accounts) for a cross-model readability pass over a design doc or other
authored prose. Step 2 — verification and apply — belongs to the calling
agent and is codified in the `prose-pass` skill (skills/prose-pass/SKILL.md):
the caller diffs the output, verifies every fact-guard held, spot-checks
technical claims against the code, and only then deploys.

Proven by hand 2026-07-16 against agentm's capture design. Two lessons from
that run are load-bearing here:

  1. The FACT-GUARD block is mandatory. The first un-guarded pass inverted
     specific truths (e.g. turned "volatile decay only lowers retrieval rank"
     into deletion semantics). The caller must enumerate the truths that a
     simplifier could plausibly invert; the script refuses to run without
     them.
  2. The voice pack is inlined VERBATIM, never summarized. The base model's
     pull toward generic product-doc voice defeats summarized rule lists; the
     before/after examples in the operator's overlay are what hold.

Invocation mechanics mirror cross-review.sh exactly (V8 proving Lane G,
2026-07-13): the positional prompt comes FIRST, flags after it — flags placed
before the prompt silently drop it and the agent free-runs on leftover
context. agy's stdin is closed (`< /dev/null` equivalent): a
connected-but-unread pipe was observed to intermittently hang the CLI until
--print-timeout fired. The prompt is passed as a single argv element via
subprocess (no shell), so backticks in the document survive untouched — a
double-quoted $(cat) mangles them.

Usage:
  prose_pass.py <doc.md> --fact-guard <guards.txt> [options]
  prose_pass.py <doc.md> --fact-guard-text "truth one" --fact-guard-text ...

Options:
  --fact-guard <file>        file with one must-not-drift truth per line
  --fact-guard-text <line>   inline guard line (repeatable; adds to --fact-guard)
  --overlay <path>           genre voice overlay — absolute, vault-relative, or a
                             bare filename under projects/_global/wiki-style/
                             (default: 2026-06-09-design-doc-prose.md)
  --voice-kernel <path>      override the always-load voice kernel (default:
                             <vault>/personal/_always-load/voice-kernel.md)
  --vault-path <path>        vault root override (else $MEMORY_VAULT_PATH, else
                             .agentm-config.json::vault_path)
  --model <name>             agy display-string model (default: Gemini 3.1 Pro (High))
  --timeout <dur>            agy --print-timeout value (default: 480s)
  -o, --output <file>        write the revised doc here instead of stdout

Exit codes (cross-review.sh parity):
  0 — revised document produced; structural contract holds
  1 — agy missing/unauthenticated, or the voice pack unresolvable — caller
      should fall back to a Claude-only prose pass
  2 — usage error, or agy ran but violated the structural contract twice —
      caller decides

The structural contract (validated deterministically against the input):
YAML frontmatter, section headings, table structures (column layout + row
counts), and the Document History section stay byte-identical; only body
prose and table-cell text may change. Violations trigger exactly one retry
with the violations named, then a degraded exit.

Degradation is never silent: both fallback paths print a
"PROSE-PASS-DEGRADED: ..." line on stdout before exiting — a stable,
grep-able marker (see scripts/test_prose_pass.py) that callers relay
verbatim rather than paraphrase away.

No PII: the vault path is resolved at runtime and never written into output.
Stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MODEL_DEFAULT = "Gemini 3.1 Pro (High)"
TIMEOUT_DEFAULT = "480s"
VOICE_KERNEL_REL = "personal/_always-load/voice-kernel.md"
WIKI_STYLE_REL = "projects/_global/wiki-style"
OVERLAY_DEFAULT = "2026-06-09-design-doc-prose.md"

TASK_HEADER = """\
You are running a simplification/readability pass on the document below.

Rules:
- Improve the existing text. Never regenerate from scratch.
- Plain English. One idea per sentence.
- Gloss an internal name once on first use; after that, use it bare.
- Table cells stay terse.
- The YAML frontmatter, every section heading, every table's structure
  (columns and row count), and the entire Document History table stay
  byte-identical. Only body prose and table-cell text may change.
- Every line in the FACT-GUARD block is a truth this document states. Your
  revision must preserve each one exactly as stated — do not weaken, invert,
  or "clarify" them.
- Write in the voice defined by the VOICE PACK block. It is the document
  author's own style guide, quoted verbatim; its before/after examples are
  normative.
- Output the complete revised document and nothing else. No preamble, no
  commentary, no code fence around the document."""


# ── pure helpers (unit-tested without agy) ──────────────────────────────────
def frontmatter_block(text: str) -> str | None:
    """The leading `---` YAML frontmatter block, delimiters included, or None."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None
    for i, ln in enumerate(lines[1:], 1):
        if ln.strip() == "---":
            return "".join(lines[: i + 1])
    return None


def _nonfenced_lines(text: str):
    """Yield (index, line) for lines outside fenced code blocks."""
    fence = None
    for i, ln in enumerate(text.splitlines()):
        stripped = ln.lstrip()
        if fence is None and (stripped.startswith("```") or stripped.startswith("~~~")):
            fence = stripped[:3]
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        yield i, ln


def heading_lines(text: str) -> list[str]:
    """ATX heading lines outside code fences, in order, byte-exact."""
    return [ln for _, ln in _nonfenced_lines(text) if re.match(r"^#{1,6} ", ln)]


def table_structures(text: str) -> list[tuple[int, str]]:
    """One (row_count, delimiter_row) tuple per markdown table, in order.

    A table is a maximal run of consecutive non-fenced lines starting with
    `|` (after optional indent). The delimiter row (the `|---|---|` line)
    encodes the column layout; the row count catches added/dropped rows.
    Cell text is deliberately NOT captured — cells may be simplified.
    """
    tables: list[tuple[int, str]] = []
    run: list[str] = []
    prev_idx = None
    delim_re = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")

    def flush():
        if len(run) >= 2:
            delim = next((r.strip() for r in run if delim_re.match(r) and "-" in r), "")
            tables.append((len(run), delim))

    for i, ln in _nonfenced_lines(text):
        if ln.lstrip().startswith("|"):
            if prev_idx is not None and i != prev_idx + 1:
                flush()
                run = []
            run.append(ln)
            prev_idx = i
        elif run:
            flush()
            run = []
            prev_idx = None
    flush()
    return tables


def document_history_section(text: str) -> str | None:
    """The Document History section (heading through next same-or-higher
    heading, or EOF), trailing whitespace stripped, or None if absent."""
    lines = text.splitlines()
    nonfenced = dict(_nonfenced_lines(text))
    start = level = None
    for i, ln in nonfenced.items():
        m = re.match(r"^(#{1,6}) (.*)$", ln)
        if m and "document history" in m.group(2).strip().lower():
            start, level = i, len(m.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for i in range(start + 1, len(lines)):
        ln = nonfenced.get(i)
        if ln is None:
            continue
        m = re.match(r"^(#{1,6}) ", ln)
        if m and len(m.group(1)) <= level:
            end = i
            break
    return "\n".join(lines[start:end]).rstrip()


def unwrap_outer_fence(text: str) -> str:
    """Strip a single all-enclosing code fence, if the model added one."""
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text


def validate_output(original: str, revised: str) -> list[str]:
    """Structural-contract violations of `revised` vs `original` (empty == pass)."""
    violations: list[str] = []
    if not revised.strip():
        return ["empty output"]
    fm_orig = frontmatter_block(original)
    if fm_orig is not None and frontmatter_block(revised) != fm_orig:
        violations.append("YAML frontmatter changed (must be byte-identical)")
    h_orig, h_rev = heading_lines(original), heading_lines(revised)
    if h_orig != h_rev:
        violations.append("section headings changed (must be byte-identical, same order)")
    if table_structures(original) != table_structures(revised):
        violations.append("table structure changed (column layout / row counts must hold)")
    dh_orig = document_history_section(original)
    if dh_orig is not None and document_history_section(revised) != dh_orig:
        violations.append("Document History section changed (must be byte-identical)")
    return violations


def assemble_prompt(header: str, fact_guards: list[str], voice_pack: str, document: str) -> str:
    """The four-block prompt, delimited so agy can't blur the boundaries."""
    guards = "\n".join(f"- {g}" for g in fact_guards)
    return (
        f"{header}\n\n"
        f"=== FACT-GUARD (truths that must not drift) ===\n{guards}\n\n"
        f"=== VOICE PACK (the author's style guide, verbatim) ===\n{voice_pack}\n\n"
        f"=== DOCUMENT ===\n{document}"
    )


def build_agy_argv(prompt: str, model: str, timeout: str,
                    agy_cmd: list[str] | None = None) -> list[str]:
    """Prompt FIRST (via -p), flags after — flags placed before the prompt
    silently drop it and the agent free-runs on leftover context.

    `agy_cmd` is the command prefix (normally `["agy"]`, the resolved binary
    path) — a list, not a single token, so a test can substitute a direct
    `[sys.executable, "fake_agy.py"]` invocation. That matters on Windows:
    routing through a `.cmd` shim means CreateProcess hands the command line
    to cmd.exe for batch-style re-parsing, and cmd.exe's grammar has no way
    to represent a literal newline inside a single command — any multi-line
    prompt gets truncated mid-argument. A direct PE executable (a real
    `agy.exe`, or `python.exe` in tests) is CreateProcess'd straight, with
    Win32's `CommandLineToArgvW` quoting, which preserves embedded newlines
    in a quoted argument correctly."""
    return [*(agy_cmd or ["agy"]), "-p", prompt, "--model", model, "--print-timeout", timeout]


def resolve_vault_path(cli_value: str | None) -> Path | None:
    """--vault-path → $MEMORY_VAULT_PATH → .agentm-config.json::vault_path.

    Mirrors harness_memory.vault_path() without importing the agentm kernel
    (not bundled with the dist-installed plugin). Returns a real directory or
    None — never a cached literal.
    """
    for raw in (cli_value, os.environ.get("MEMORY_VAULT_PATH", "")):
        if raw and raw.strip():
            p = Path(os.path.expanduser(raw.strip()))
            return p if p.is_dir() else None
    prefix = os.environ.get("AGENTM_INSTALL_PREFIX", "").strip()
    config = (Path(os.path.expanduser(prefix)) if prefix else Path.home() / ".claude") / ".agentm-config.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    vp = data.get("vault_path") if isinstance(data, dict) else None
    if not isinstance(vp, str) or not vp.strip():
        return None
    p = Path(os.path.expanduser(vp.strip()))
    return p if p.is_dir() else None


_TEST_AGY_CMD_ENV = "PROSE_PASS_TEST_AGY_CMD"


def resolve_agy_cmd() -> list[str] | None:
    """The command prefix used to invoke agy, or None if unresolvable.

    Normally `[shutil.which("agy")]`. `$PROSE_PASS_TEST_AGY_CMD` is a
    test-only escape hatch (a JSON-encoded argv-prefix list) that lets the
    test suite point directly at a `[sys.executable, "fake_agy.py"]`
    invocation — bypassing PATH resolution and any OS-specific shim entirely,
    which matters on Windows (see build_agy_argv's docstring).
    """
    override = os.environ.get(_TEST_AGY_CMD_ENV, "").strip()
    if override:
        try:
            cmd = json.loads(override)
        except json.JSONDecodeError:
            return None
        return cmd if isinstance(cmd, list) and cmd else None
    agy_bin = shutil.which("agy")
    return [agy_bin] if agy_bin else None


def resolve_overlay(vault: Path, overlay_arg: str) -> Path:
    """Absolute path → as-is; else vault-relative; else a bare filename under
    the wiki-style overlay directory."""
    p = Path(os.path.expanduser(overlay_arg))
    if p.is_absolute():
        return p
    rel = vault / overlay_arg
    if rel.is_file():
        return rel
    return vault / WIKI_STYLE_REL / overlay_arg


# ── flow ─────────────────────────────────────────────────────────────────────
def _degraded(reason: str, diag: str) -> None:
    print(f"PROSE-PASS-DEGRADED: {reason} — fall back to a Claude-only prose pass")
    print(f"prose-pass: {diag}", file=sys.stderr)


def _call_agy(agy_cmd: list[str], prompt: str, model: str, timeout: str) -> tuple[int, str]:
    # Hard wall-clock backstop: agy's own --print-timeout plus a grace period,
    # so a wedged CLI can never hang the caller indefinitely.
    m = re.match(r"^(\d+)", timeout)
    wall = (int(m.group(1)) if m else 480) + 120
    try:
        r = subprocess.run(
            build_agy_argv(prompt, model, timeout, agy_cmd),
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=wall,
        )
    except subprocess.TimeoutExpired:
        return 124, ""
    return r.returncode, r.stdout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Cross-model prose pass, step 1: Gemini simplifies.")
    ap.add_argument("doc", help="path to the document to simplify")
    ap.add_argument("--fact-guard", help="file with one must-not-drift truth per line")
    ap.add_argument("--fact-guard-text", action="append", default=[],
                    help="inline guard line (repeatable)")
    ap.add_argument("--overlay", default=OVERLAY_DEFAULT)
    ap.add_argument("--voice-kernel")
    ap.add_argument("--vault-path")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--timeout", default=TIMEOUT_DEFAULT)
    ap.add_argument("-o", "--output")
    args = ap.parse_args(argv)

    doc_path = Path(args.doc)
    if not doc_path.is_file():
        print(f"prose-pass: document not found: {args.doc}", file=sys.stderr)
        return 2

    guards = list(args.fact_guard_text)
    if args.fact_guard:
        gp = Path(args.fact_guard)
        if not gp.is_file():
            print(f"prose-pass: fact-guard file not found: {args.fact_guard}", file=sys.stderr)
            return 2
        guards = [ln.strip().lstrip("- ") for ln in gp.read_text(encoding="utf-8").splitlines()
                  if ln.strip()] + guards
    if not guards:
        print("prose-pass: a FACT-GUARD list is required (--fact-guard or "
              "--fact-guard-text). The first un-guarded pass inverted document "
              "truths; enumerate the truths a simplifier could plausibly "
              "invert before running.", file=sys.stderr)
        return 2

    agy_cmd = resolve_agy_cmd()
    if agy_cmd is None:
        _degraded("agy CLI unavailable", "agy CLI not found — caller should fall back")
        return 1

    vault = resolve_vault_path(args.vault_path)
    if vault is None:
        _degraded("vault unresolved",
                  "no vault root (--vault-path / $MEMORY_VAULT_PATH / "
                  ".agentm-config.json::vault_path) — voice pack unreachable")
        return 1
    kernel_path = (Path(os.path.expanduser(args.voice_kernel))
                   if args.voice_kernel else vault / VOICE_KERNEL_REL)
    overlay_path = resolve_overlay(vault, args.overlay)
    missing = [p for p in (kernel_path, overlay_path) if not p.is_file()]
    if missing:
        _degraded("voice pack unresolved",
                  f"missing voice file(s): {', '.join(p.name for p in missing)}")
        return 1
    voice_pack = (kernel_path.read_text(encoding="utf-8").strip()
                  + "\n\n" + overlay_path.read_text(encoding="utf-8").strip())

    original = doc_path.read_text(encoding="utf-8")
    prompt = assemble_prompt(TASK_HEADER, guards, voice_pack, original)

    rc, out = _call_agy(agy_cmd, prompt, args.model, args.timeout)
    if rc != 0 or not out.strip():
        _degraded("agy call failed", f"agy exited {rc} with "
                  f"{'empty' if not out.strip() else 'nonzero'} result")
        return 1

    revised = unwrap_outer_fence(out)
    violations = validate_output(original, revised)
    if violations:
        nudge = ("\n\nYour previous revision violated the structural contract: "
                 + "; ".join(violations)
                 + ". Revise again. The frontmatter, headings, table structures, "
                   "and Document History must be byte-identical to the input.")
        rc, out = _call_agy(agy_cmd,
                            assemble_prompt(TASK_HEADER + nudge, guards, voice_pack, original),
                            args.model, args.timeout)
        if rc != 0 or not out.strip():
            _degraded("agy retry failed", f"agy retry exited {rc}")
            return 1
        revised = unwrap_outer_fence(out)
        violations = validate_output(original, revised)
        if violations:
            _degraded("agy revision violated the structural contract twice",
                      "violations after retry: " + "; ".join(violations))
            print(revised, file=sys.stderr)
            return 2

    if not revised.endswith("\n"):
        revised += "\n"
    if args.output:
        Path(args.output).write_text(revised, encoding="utf-8")
        print(f"prose-pass: revised document written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(revised)
    return 0


if __name__ == "__main__":
    sys.exit(main())
