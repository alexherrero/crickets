#!/usr/bin/env python3
"""Anti-recurrence guard: a developer-safety hook's `.sh` and `.ps1` twins must
stay behaviorally paired — neither may read a workspace-relative `.harness/…`
path without first resolving the workspace from the host's hook-input contract.

The bug this guards against (crickets v3.0 #40 follow-through): the `.sh` twins
were fixed to resolve the workspace root host-portably (read stdin JSON
`workspacePaths[0]` / `cwd`, fall back to `$CLAUDE_PROJECT_DIR`, then cwd, and
`cd`/`Set-Location` in before any relative `.harness/…` logic), but their `.ps1`
twins were left doing bare cwd-relative checks. On a Windows / pwsh host — and on
Antigravity, which runs plugin hooks from the PLUGIN dir and passes the workspace
on stdin as `{"workspacePaths":["<root>"]}` — that made the `.ps1` hooks read the
wrong `.harness/` (or none). No gate compared the twins, so the divergence went
unnoticed for the whole window between the bash fix and its PowerShell follow-up.

This gate makes that divergence impossible to land silently again.

The heuristic (static + structural, per the plan's LDC-3)
--------------------------------------------------------
For every hook directory under `src/developer-safety/hooks/*/`:

  1. **Both twins must exist.** A `.sh` without its `.ps1` (or vice versa) is a
     parity hole by construction — the developer-safety trio is dual-host.

  2. **`references_harness ⟹ resolves_workspace`, per twin.** If a twin's *code*
     (comments stripped — full-line AND inline trailing — so a comment that
     merely mentions `.harness` or `workspacePaths` proves nothing either way)
     references a workspace-relative `.harness/…` path, that same code must also
     carry the two resolution markers:
       - `workspacePaths` — the host-contract protocol key. Naming-agnostic: it
         survives a rename of the resolver function (`_resolve_workspace` →
         `Resolve-Workspace` → anything) because it is the *only* way to read
         Antigravity's workspace, so any real resolver must reference it.
       - a directory-change verb — `cd` for `.sh`, `Set-Location` for `.ps1` —
         proving the hook actually moves into the resolved root before its
         relative logic runs.

This is the "at minimum" the brief asks for; full behavioral equivalence is the
job of the per-twin behavioral mirrors (`scripts/test_developer_hooks_workspace.py`
for `.sh`, `scripts/test_developer_hooks_workspace_ps1.py` for `.ps1`). The two
layers together — static parity everywhere this gate runs, behavioral mirror on
every CI OS — are the defense.

Known limitation (acknowledged, not a bug): the marker check assumes each hook
resolves the workspace *inline*. If a future hook factors resolution out into a
sourced/dot-imported helper, `workspacePaths` would not appear in the hook's own
body and this gate would flag a false positive — at which point the marker set
should learn the helper. The fixture tests pin the intended discrimination so a
loosening/tightening is a deliberate, reviewed change.

Stdlib only; text-level parsing on purpose (it asserts what the files say, not
what a shell/PowerShell parser normalizes them into).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_ROOT = ROOT / "src" / "developer-safety" / "hooks"

# A workspace-relative harness path: `.harness/` or a bare `.harness` token.
_HARNESS_RE = re.compile(r"\.harness\b")
# The host-contract protocol key — naming-agnostic proof the hook reads the
# workspace the host passes on stdin.
_WORKSPACE_KEY = "workspacePaths"
# Directory-change verb per shell.
_DIRCHANGE = {
    "sh": re.compile(r"(?<![\w-])cd\b"),       # the `cd` builtin (not `abcd`, not `xx-cd`)
    "ps1": re.compile(r"\bSet-Location\b"),
}


# ── pure logic (unit-tested without a real tree) ────────────────────────────
def strip_comments(text: str) -> str:
    """Drop comments — full-line AND inline trailing — so a marker that appears
    only inside a comment proves nothing: a `# … workspacePaths … Set-Location …`
    comment must neither trigger the `.harness` requirement nor satisfy the
    resolution check.

    The original gate stripped only *full-line* comments, so the bare cwd-relative
    bug it exists to catch could be disguised as "resolves workspace" simply by
    moving the markers into an inline trailing comment (crickets v3.0 #40
    follow-through, DEFECT 2). Inline comments must go too.

    Quote-aware so a `#` inside a string literal is preserved as code (a `sed`
    pattern, a refname, `grep '#'`, a `"fix #123"` message) rather than mistaken
    for a comment leader. The comment leader recognized for both `bash` and
    PowerShell is an unquoted `#` that begins a token — at the start of the line
    (after optional whitespace) or immediately preceded by whitespace. A `#` glued
    to a non-space character (`$#`, `foo#bar`, `${x#prefix}`) is not a comment in
    either shell and is left intact.

    Line-oriented, with quote state tracked per line (matching this module's
    text-level philosophy): it does not model `bash` here-docs or PowerShell
    `<# … #>` block comments. On those constructs it can only ever strip *more*
    than a real parser would, never miss a comment — and the fixture + real-tree
    tests pin that the live twins stay correctly classified.
    """
    return "\n".join(_strip_line_comment(line) for line in text.splitlines())


def _strip_line_comment(line: str) -> str:
    """Return `line` with any unquoted `#` comment (whole-line or inline) removed."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line


def references_harness(code: str) -> bool:
    """True if the (comment-stripped) code reads a workspace-relative `.harness` path."""
    return bool(_HARNESS_RE.search(code))


def resolves_workspace(code: str, kind: str) -> bool:
    """True if the (comment-stripped) code carries both resolution markers for `kind`.

    `kind` is "sh" or "ps1". Requires the `workspacePaths` protocol key AND the
    shell-appropriate directory-change verb — together they prove the twin reads
    the host's workspace input and moves into it before any relative logic.
    """
    if _WORKSPACE_KEY not in code:
        return False
    verb = _DIRCHANGE.get(kind)
    return bool(verb and verb.search(code))


def twin_violations(name: str, sh_text: str | None, ps1_text: str | None) -> list[str]:
    """Return human-readable violations for one hook dir's twin pair.

    `sh_text` / `ps1_text` are the twin file contents, or None when that twin is
    absent. Empty list == the pair is parity-clean.
    """
    violations: list[str] = []

    # Rule 1: both twins must exist.
    if sh_text is None and ps1_text is None:
        violations.append(f"{name}: no .sh or .ps1 twin found in the hook dir")
        return violations
    if sh_text is None:
        violations.append(f"{name}: missing .sh twin (has .ps1) — the developer-safety trio is dual-host")
    if ps1_text is None:
        violations.append(f"{name}: missing .ps1 twin (has .sh) — the developer-safety trio is dual-host")

    # Rule 2: references_harness ⟹ resolves_workspace, per present twin.
    for kind, text in (("sh", sh_text), ("ps1", ps1_text)):
        if text is None:
            continue
        code = strip_comments(text)
        if references_harness(code) and not resolves_workspace(code, kind):
            violations.append(
                f"{name}: the .{kind} twin reads a workspace-relative .harness/… path "
                f"but does not resolve the workspace first — its code must reference "
                f"`{_WORKSPACE_KEY}` and `{'cd' if kind == 'sh' else 'Set-Location'}` "
                f"into the resolved root (mirror the .{'ps1' if kind == 'sh' else 'sh'} twin)"
            )
    return violations


# ── IO / walk plumbing ──────────────────────────────────────────────────────
def hook_dirs(hooks_root: Path) -> list[Path]:
    """Every immediate sub-directory of the developer-safety hooks root."""
    if not hooks_root.is_dir():
        return []
    return sorted(p for p in hooks_root.iterdir() if p.is_dir())


def _read_twin(hook_dir: Path, ext: str) -> str | None:
    """Read the single `*.<ext>` twin in a hook dir, or None if absent."""
    matches = sorted(hook_dir.glob(f"*.{ext}"))
    if not matches:
        return None
    return matches[0].read_text(encoding="utf-8")


def scan(hooks_root: Path) -> list[str]:
    """Collect parity violations across every hook dir under `hooks_root`."""
    found: list[str] = []
    for d in hook_dirs(hooks_root):
        found.extend(twin_violations(d.name, _read_twin(d, "sh"), _read_twin(d, "ps1")))
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--hooks-root",
        type=Path,
        default=HOOKS_ROOT,
        help="hooks root to scan (default: src/developer-safety/hooks)",
    )
    args = ap.parse_args(argv)

    if not args.hooks_root.is_dir():
        print(f"check-hook-parity: hooks root not found ({args.hooks_root}) — nothing to check.")
        return 0

    violations = scan(args.hooks_root)
    if violations:
        print("check-hook-parity: FAIL — a developer-safety hook's .sh/.ps1 twins drifted "
              "out of parity. A twin that reads a workspace-relative .harness/… path must "
              "resolve the workspace first, and both twins must exist:")
        for v in violations:
            print(f"  - {v}")
        return 1

    n = len(hook_dirs(args.hooks_root))
    print(f"check-hook-parity: OK — {n} developer-safety hook(s); .sh/.ps1 twins paired.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
