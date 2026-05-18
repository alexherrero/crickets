#!/usr/bin/env python3
# recall.py — MemoryVault read loop.
#
# Provides the recall operations invoked by:
#   - the SessionStart hook (subcommand: session-start; lands plan #7a part 2 task 1).
#   - the UserPromptSubmit hook (subcommand: prompt-submit; lands plan #7a part 2 task 2).
#   - the future /memory search sub-command (subcommand: query; lands when the
#     recall engine is wired up in plan #7a part 2 task 3).
#
# v0.1.0 (this commit, plan #7a part 2 task 1) ships ONLY the session-start
# subcommand. Tasks 2-3 of part 2 extend this module with prompt-submit + the
# query/recall engine. Subcommands deferred to later tasks raise
# `NotImplementedError` at CLI surface so the wiring stays explicit.
#
# Vault resolution chain (matches save.py / vec_index.py):
#   1. --vault-path arg (highest priority; overrides env).
#   2. MEMORY_VAULT_PATH env var.
#   3. No fallback — return None (caller decides what to do).
#
# Hook-invocation graceful-skip contract:
#   - If MEMORY_VAULT_PATH unset OR vault doesn't exist → exit 0 with no
#     stdout; stderr "no vault configured" line is optional. The hook
#     never blocks session boot for missing config.
#   - If _always-load/ directory missing → exit 0 with "Loaded 0" line.
#   - If time budget exceeded mid-load → emit partial + warn + exit 0.

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Hard time budgets per locked design call (plan #7a part 2):
#   SessionStart: 500ms
#   UserPromptSubmit: 300ms
SESSION_START_BUDGET_MS = 500
PROMPT_SUBMIT_BUDGET_MS = 300

# Path convention: always-load entries live under <vault>/personal-private/_always-load/.
# Group-scoped _always-load/ dirs (e.g. work-public/_always-load/) are reserved
# for future per-group recall; v0.1.0 hardwires personal-private/.
_ALWAYS_LOAD_REL = Path("personal-private") / "_always-load"


def _resolve_vault_path(arg_vault_path: str | None) -> Path | None:
    """Resolve vault path per the chain: --vault-path → MEMORY_VAULT_PATH env → None.

    Returns None if no path resolves. Callers should treat None as
    "graceful-skip" — exit 0 with no output.
    """
    if arg_vault_path:
        return Path(arg_vault_path).expanduser()
    env_path = os.environ.get("MEMORY_VAULT_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return None


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from a markdown file content string.

    Returns (frontmatter_dict, body). If no frontmatter present (no leading
    `---\\n`), returns ({}, content). Inline parser — handles the limited
    YAML subset that save.py / evolve.py write (string values, simple lists
    in `[a, b]` form). PyYAML is NOT a hook-time dependency.
    """
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    fm_text = content[4:end]
    body = content[end + 5:]  # skip "\n---\n"
    fm: dict[str, str] = {}
    for line in fm_text.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes if present.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        fm[key] = value
    return fm, body


def _format_entry_for_injection(slug: str, fm: dict[str, str], body: str) -> str:
    """Format a single always-load entry for stdout injection.

    Format (markdown):
        ### <slug> (kind: <kind>, tags: <tags>)
        <body>

    Keeps the formatting minimal so the agent gets the entry's content
    without ceremony. Frontmatter is summarized in the header so the agent
    can see kind + tags without the full YAML.
    """
    kind = fm.get("kind", "unknown")
    tags = fm.get("tags", "")
    header = f"### {slug} (kind: {kind}"
    if tags and tags not in {"[]", ""}:
        header += f", tags: {tags}"
    header += ")"
    return f"{header}\n\n{body.strip()}"


def session_start(
    *,
    vault: Path | None,
    budget_ms: int = SESSION_START_BUDGET_MS,
    stdout=sys.stdout,
    stderr=sys.stderr,
) -> int:
    """Load _always-load/*.md entries; emit to stdout; transparency line to stderr.

    Returns exit code:
        0 — always, even on errors (graceful-skip contract).

    Errors are surfaced to stderr but never propagated to exit code. The hook
    contract is "never block session boot".
    """
    deadline = time.monotonic() + (budget_ms / 1000.0)

    if vault is None:
        # No vault configured. Exit 0 silently — session proceeds without memory.
        return 0
    if not vault.exists():
        print(
            f"[memory-recall-session-start] vault path not found: {vault} (skipping)",
            file=stderr,
        )
        return 0

    always_load_dir = vault / _ALWAYS_LOAD_REL
    if not always_load_dir.exists() or not always_load_dir.is_dir():
        # Vault exists but no always-load entries yet.
        print(
            "[memory-recall-session-start] Loaded 0 MemoryVault always-load entries",
            file=stderr,
        )
        return 0

    # Glob *.md (top-level only; _always-load/ is flat by convention — see
    # save.py's --always-load routing comment).
    candidates = sorted(always_load_dir.glob("*.md"))

    loaded_slugs: list[str] = []
    blocks: list[str] = []
    overrun = False

    for md_path in candidates:
        # Budget check before each file.
        if time.monotonic() > deadline:
            overrun = True
            break
        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError as e:
            print(
                f"[memory-recall-session-start] warning: unreadable entry {md_path.name}: {e}",
                file=stderr,
            )
            continue
        fm, body = _parse_frontmatter(content)
        # Filter superseded entries (defense-in-depth; supersession normally
        # moves entries to _archive/, but a stale _always-load/ entry could
        # have been flagged superseded without being moved).
        if fm.get("status") == "superseded":
            continue
        slug = md_path.stem
        blocks.append(_format_entry_for_injection(slug, fm, body))
        loaded_slugs.append(slug)

    # Output assembly. Header gives the agent a clear "this is MemoryVault content" marker.
    if blocks:
        print("# MemoryVault — always-load entries", file=stdout)
        print("", file=stdout)
        print(
            "The following entries are loaded at every session start "
            "(durable preferences/workflows/fixes).",
            file=stdout,
        )
        print("", file=stdout)
        for i, block in enumerate(blocks):
            if i > 0:
                print("\n---\n", file=stdout)
            print(block, file=stdout)

    # Transparency line on stderr (shown in hook logs, not agent context).
    slug_list = ", ".join(loaded_slugs) if loaded_slugs else "(none)"
    transparency = (
        f"[memory-recall-session-start] Loaded {len(loaded_slugs)} "
        f"MemoryVault always-load entries: {slug_list}"
    )
    if overrun:
        transparency += (
            f" (WARNING: 500ms time budget exceeded; partial results — "
            f"{len(candidates) - len(loaded_slugs)} entries skipped)"
        )
    print(transparency, file=stderr)
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="memory-recall",
        description=(
            "MemoryVault recall operations. Subcommands: session-start (load "
            "_always-load/ entries; called by the SessionStart hook). "
            "prompt-submit and query subcommands land in plan #7a part 2 "
            "tasks 2-3."
        ),
    )
    parser.add_argument(
        "--vault-path",
        required=False,
        help="MemoryVault root (overrides MEMORY_VAULT_PATH env var)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    ss = sub.add_parser(
        "session-start",
        help="load _always-load/ entries + emit on stdout for session-boot injection",
    )
    ss.add_argument(
        "--budget-ms",
        type=int,
        default=SESSION_START_BUDGET_MS,
        help=f"time budget in milliseconds (default: {SESSION_START_BUDGET_MS})",
    )

    # Placeholders for future subcommands — fail fast with a clear message so
    # accidental calls don't silently no-op.
    sub.add_parser(
        "prompt-submit",
        help="(NOT YET IMPLEMENTED — lands in plan #7a part 2 task 2)",
    )
    sub.add_parser(
        "query",
        help="(NOT YET IMPLEMENTED — lands in plan #7a part 2 task 3)",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    vault = _resolve_vault_path(args.vault_path)
    if args.cmd == "session-start":
        return session_start(vault=vault, budget_ms=args.budget_ms)
    if args.cmd == "prompt-submit":
        print(
            "ERROR: prompt-submit subcommand not yet implemented "
            "(lands in plan #7a part 2 task 2)",
            file=sys.stderr,
        )
        return 2
    if args.cmd == "query":
        print(
            "ERROR: query subcommand not yet implemented "
            "(lands in plan #7a part 2 task 3)",
            file=sys.stderr,
        )
        return 2
    return 1  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
