#!/usr/bin/env python3
# agentmemory_conventions.py — AgentMemory read + write integration
# for the diataxis-author skill (plan #13 part 5).
#
# Read-side: globs `<vault>/personal-private/_always-load/diataxis-*.md`
# at invocation; parses simple `key: value` lines from each entry's
# frontmatter + body to build a conventions dict. Per-repo override at
# `<repo>/wiki/.diataxis-conventions.md` takes precedence when present.
#
# Write-side: `confirm_save_convention()` routes through the existing
# `permeable_boundary` helper (shipped in plan #7a part 4) for operator
# confirmation on cross-boundary writes. Same A3 contract as
# `ideas_surface.py`'s Ideas.md writer — never silent; respects
# `MEMORY_REVIEW_MODE=silent` env var.
#
# Fallback chain (lookup order):
#   1. Per-repo `.diataxis-conventions.md` (when wiki_root provided + file present)
#   2. Vault `_always-load/diataxis-*.md` (when MEMORY_VAULT_PATH or
#      --vault-path resolves)
#   3. ADR 0004 defaults (hardcoded fallbacks).
#
# Stdlib-only; matches the established convention.

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path


# Hardcoded ADR 0004 defaults — used when no operator entries exist anywhere.
_DEFAULTS = {
    "filename_style": "CamelCase-With-Dashes",
    "mode_mixed_default_split": "how-to + reference",
    "confidence_threshold": 0.7,
}

# Always-load entry slug prefix this skill writes / reads.
_ALWAYS_LOAD_PREFIX = "diataxis-"


def _resolve_vault_path(arg_path: str | None = None) -> Path | None:
    """Resolve vault path: arg → MEMORY_VAULT_PATH env → None (no vault)."""
    if arg_path:
        return Path(arg_path).expanduser()
    env_path = os.environ.get("MEMORY_VAULT_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return None


# Optional `**bold**` markdown wrapping around the key — both formats
# accepted so the same regex catches operator-curated entries (plain
# `Filename style: X`) and skill-written entries (`**Filename style**: X`).
_OPT_BOLD = r"(?:\*\*)?"


def _parse_conventions_text(text: str) -> dict:
    """Extract recognized convention keys from arbitrary markdown text.

    Recognizes (case-insensitive; with or without `**` bold wrapping;
    anywhere in the file — frontmatter or body):
      `Filename style: <value>` → `filename_style`
      `Confidence threshold: <number>` → `confidence_threshold`
      `Mode-mixed default split: <text>` → `mode_mixed_default_split`
    """
    out: dict = {}
    m = re.search(
        rf"^{_OPT_BOLD}Filename style{_OPT_BOLD}:\s*(\S.*?)\s*$",
        text, re.MULTILINE | re.IGNORECASE,
    )
    if m:
        out["filename_style"] = m.group(1).strip()
    m = re.search(
        rf"^{_OPT_BOLD}Confidence threshold{_OPT_BOLD}:\s*([\d.]+)\s*$",
        text, re.MULTILINE | re.IGNORECASE,
    )
    if m:
        try:
            out["confidence_threshold"] = float(m.group(1))
        except ValueError:
            pass
    m = re.search(
        rf"^{_OPT_BOLD}Mode-mixed default split{_OPT_BOLD}:\s*(.+)$",
        text, re.MULTILINE | re.IGNORECASE,
    )
    if m:
        out["mode_mixed_default_split"] = m.group(1).strip()
    return out


def _parse_per_repo_conventions(repo_conventions: Path) -> dict:
    if not repo_conventions.exists():
        return {}
    try:
        return _parse_conventions_text(repo_conventions.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _parse_always_load_entry(entry_path: Path) -> dict:
    if not entry_path.exists():
        return {}
    try:
        return _parse_conventions_text(entry_path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def load_conventions(
    *,
    wiki_root: Path | None = None,
    vault_path: Path | None = None,
) -> dict:
    """Build effective conventions dict via the fallback chain.

    Priority (highest to lowest):
      1. Per-repo `<wiki_root>/.diataxis-conventions.md`
      2. Vault `<vault>/personal-private/_always-load/diataxis-*.md` (any entry)
      3. ADR 0004 hardcoded defaults
    """
    # Start with defaults.
    out = dict(_DEFAULTS)
    # Vault entries (apply all matching diataxis-* files; later files
    # overwrite earlier).
    if vault_path is None:
        vault_path = _resolve_vault_path()
    if vault_path:
        always_load_dir = vault_path / "personal-private" / "_always-load"
        if always_load_dir.exists():
            for entry in sorted(always_load_dir.glob(f"{_ALWAYS_LOAD_PREFIX}*.md")):
                out.update(_parse_always_load_entry(entry))
    # Per-repo override (highest priority).
    if wiki_root is not None:
        repo_conv = wiki_root / ".diataxis-conventions.md"
        if repo_conv.exists():
            out.update(_parse_per_repo_conventions(repo_conv))
    return out


def confirm_save_convention(
    key: str,
    new_value: str,
    *,
    vault_path: Path | None = None,
    mode: str | None = None,
    stdin=sys.stdin,
    stdout=sys.stdout,
) -> Path | None:
    """Offer to save a new convention to the operator's AgentMemory.

    Routes through the existing `permeable_boundary.confirm_write_outside_
    memoryvault()` helper for A3-boundary respect (writes to `_always-load/`
    are INSIDE the MemoryVault, so technically don't need cross-boundary
    confirmation — but we use a similar interactive-confirm pattern for
    consistency + to avoid surprise saves).

    Returns Path written on operator-approved save; None if declined or
    no vault resolved.
    """
    if vault_path is None:
        vault_path = _resolve_vault_path()
    if vault_path is None:
        return None
    if not vault_path.exists() or not vault_path.is_dir():
        return None
    # Compute target path.
    slug = re.sub(r"[^a-z0-9-]", "-", key.lower()).strip("-")
    target = vault_path / "personal-private" / "_always-load" / f"{_ALWAYS_LOAD_PREFIX}{slug}.md"
    # Mode resolution (matches MEMORY_REVIEW_MODE pattern from existing scripts).
    if mode is None:
        mode = os.environ.get("MEMORY_REVIEW_MODE", "interactive").strip().lower()
    # 'silent' mode bypasses confirmation; 'auto' denies non-TTY; 'interactive' prompts.
    if mode == "silent":
        approved = True
    elif mode == "auto":
        approved = stdin.isatty() if hasattr(stdin, "isatty") else False
        if not approved:
            print(
                f"[diataxis-conv] auto mode + non-TTY → denying save of {key!r}",
                file=sys.stderr,
            )
            return None
    else:  # interactive
        if not stdin.isatty() if hasattr(stdin, "isatty") else True:
            print(
                f"[diataxis-conv] interactive mode + non-TTY → defaulting to deny",
                file=sys.stderr,
            )
            return None
        print(f"Save convention '{key}: {new_value}' to AgentMemory? [y/N]", file=stdout)
        stdout.flush()
        try:
            response = stdin.readline().strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        approved = response in ("y", "yes")
    if not approved:
        return None
    # Write the entry. Use save.save_entry if available (preferred — gives
    # us proper frontmatter shape); otherwise direct write.
    try:
        scripts_parent = Path(__file__).resolve().parent.parent.parent  # skills/
        memory_scripts = scripts_parent / "memory" / "scripts"
        if str(memory_scripts) not in sys.path:
            sys.path.insert(0, str(memory_scripts))
        import save  # type: ignore
        body = (
            f"# {key}\n\n"
            f"Operator convention captured from diataxis-author skill on {date.today().isoformat()}.\n\n"
            f"**{key.replace('_', ' ').capitalize()}**: {new_value}\n"
        )
        return save.save_entry(
            vault_path=vault_path,
            kind="convention",
            slug=f"{_ALWAYS_LOAD_PREFIX}{slug}",
            body=body,
            group="personal-private",
            always_load=True,
            tags=["diataxis", "convention", "auto-captured"],
        )
    except Exception as e:
        # Fallback to direct write if save.py unavailable or errors.
        print(f"[diataxis-conv] save.py path failed ({e}); falling back to direct write", file=sys.stderr)
        target.parent.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        content = (
            "---\n"
            f"kind: convention\n"
            f"status: active\n"
            f"created: {today}\n"
            f"updated: {today}\n"
            "tags: [diataxis, convention, auto-captured]\n"
            "group: personal-private\n"
            f"slug: {_ALWAYS_LOAD_PREFIX}{slug}\n"
            "always_load: true\n"
            "---\n"
            "\n"
            f"# {key}\n\n"
            f"Operator convention captured from diataxis-author skill on {today}.\n\n"
            f"**{key.replace('_', ' ').capitalize()}**: {new_value}\n"
        )
        target.write_bytes(content.encode("utf-8"))
        return target


# ── Edit-driven voice-lesson capture (part 3, task 3) ───────────────────────
# `confirm_save_convention()` above is the DECISION-driven path: it records a
# key:value judgment call (filename_style, …) to `_always-load/diataxis-*.md`.
# `confirm_save_lesson()` below is the EDIT-driven counterpart: it writes a VOICE
# LESSON {trigger, guidance} to the ON-DEMAND scope store the resolver reads —
# NOT `_always-load` — in `trigger:`-frontmatter + guidance-body form, so it
# round-trips with style_resolver.read_scope_lessons / _read_per_repo_lessons.

_PER_REPO_FILE = ".diataxis-conventions.md"
_VALID_SCOPES = ("global", "per-project", "per-repo")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.lower()).strip("-") or "lesson"


def _oneline(text: str, limit: int = 160) -> str:
    """Collapse to a single frontmatter-safe line (provenance only)."""
    s = " / ".join(ln.strip() for ln in text.splitlines() if ln.strip())
    return (s[: limit - 3] + "...") if len(s) > limit else s


def lesson_target(
    scope: str,
    *,
    vault_path: Path | None,
    project_slug: str | None,
    wiki_root: Path | None,
    trigger: str,
    datestamp: str,
) -> tuple[Path | None, bool]:
    """Resolve (target_path, writes_outside_vault) for a voice lesson by scope.

      global      -> <vault>/personal-private/projects/_global/wiki-style/<date>-<trigger>.md
      per-project -> <vault>/personal-private/projects/<slug>/wiki-style/<date>-<trigger>.md
      per-repo    -> <wiki_root>/.diataxis-conventions.md   (OUTSIDE the vault)

    The date-prefixed filename gives the directory scopes their recent-wins order
    (the resolver sorts by filename within a scope). Returns (None, False) when
    the scope's required context is missing.
    """
    trig = _slugify(trigger)
    if scope == "global":
        if vault_path is None:
            return None, False
        d = Path(vault_path) / "personal-private" / "projects" / "_global" / "wiki-style"
        return d / f"{datestamp}-{trig}.md", False
    if scope == "per-project":
        if vault_path is None or not project_slug:
            return None, False
        d = Path(vault_path) / "personal-private" / "projects" / project_slug / "wiki-style"
        return d / f"{datestamp}-{trig}.md", False
    if scope == "per-repo":
        if wiki_root is None:
            return None, False
        return Path(wiki_root) / _PER_REPO_FILE, True
    return None, False


def _render_dir_lesson(
    trigger: str, guidance: str, *, scope: str,
    before: str | None, after: str | None, datestamp: str,
) -> str:
    """A fresh one-lesson file for the directory scopes (global / per-project).

    `trigger:` frontmatter is the resolver's conflict key; the body is the
    guidance (the only thing the resolver injects). before/after ride along as
    frontmatter provenance — the resolver ignores them."""
    lines = ["---", f"trigger: {trigger}", f"scope: {scope}", f"updated: {datestamp}"]
    if before:
        lines.append(f"before: {_oneline(before)}")
    if after:
        lines.append(f"after: {_oneline(after)}")
    lines += ["source: diataxis-author edit-capture", "---", "", guidance.strip(), ""]
    return "\n".join(lines)


def _split_fm_raw(text: str) -> tuple[dict, str]:
    """Split a `--- … ---` frontmatter block, preserving simple key:value pairs."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def _merge_per_repo(existing: str, trigger: str, guidance: str, *, datestamp: str) -> str:
    """Per-repo voice lives in the SINGLE `.diataxis-conventions.md` the resolver
    reads as one lesson. Preserve existing content (incl. key:value conventions),
    ensure a `trigger:` in frontmatter, and append the new guidance to the body."""
    fm, body = _split_fm_raw(existing) if existing.strip() else ({}, "")
    fm["trigger"] = trigger
    fm["updated"] = datestamp
    body = body.strip()
    new_body = (body + "\n\n" if body else "") + guidance.strip()
    fm_lines = "\n".join(f"{k}: {v}" for k, v in fm.items())
    return f"---\n{fm_lines}\n---\n\n{new_body}\n"


def _approve_lesson(prompt: str, *, mode: str | None, stdin, stdout) -> bool:
    """Operator-confirm gate for a lesson write: silent → True; auto → TTY-only;
    interactive → prompt. Mirrors confirm_save_convention's mode contract."""
    if mode is None:
        mode = os.environ.get("MEMORY_REVIEW_MODE", "interactive").strip().lower()
    if mode == "silent":
        return True
    is_tty = stdin.isatty() if hasattr(stdin, "isatty") else False
    if mode == "auto":
        if not is_tty:
            print(f"[diataxis-conv] auto mode + non-TTY -> denying ({prompt})", file=sys.stderr)
            return False
        return True
    # interactive
    if not is_tty:
        print(f"[diataxis-conv] interactive mode + non-TTY -> defaulting to deny ({prompt})", file=sys.stderr)
        return False
    print(f"Save {prompt}? [y/N]", file=stdout)
    stdout.flush()
    try:
        resp = stdin.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return resp in ("y", "yes")


def _permeable_confirm(target: Path, *, stdin, stdout) -> bool:
    """Cross-boundary confirm for writes OUTSIDE the MemoryVault (the per-repo
    store). Routes through agentm's permeable_boundary helper when importable;
    absent the kernel it surfaces a degraded-mode note on stderr and proceeds —
    the capture works crickets-local, the degradation is announced not silent
    (DC-3). Returns True to proceed, False only if the kernel actively declines."""
    try:
        scripts_parent = Path(__file__).resolve().parent.parent.parent  # skills/
        memory_scripts = scripts_parent / "memory" / "scripts"
        if str(memory_scripts) not in sys.path:
            sys.path.insert(0, str(memory_scripts))
        import permeable_boundary  # type: ignore
    except Exception as e:
        print(f"[diataxis-conv] permeable_boundary unavailable ({e.__class__.__name__}); "
              f"degraded cross-boundary write to {target} (no kernel confirm)", file=sys.stderr)
        return True
    fn = getattr(permeable_boundary, "confirm_write_outside_memoryvault", None)
    if fn is None:
        return True
    try:
        return bool(fn(target))
    except Exception as e:
        print(f"[diataxis-conv] permeable_boundary confirm errored ({e}); "
              f"degraded write to {target}", file=sys.stderr)
        return True


def confirm_save_lesson(
    trigger: str,
    guidance: str,
    scope: str,
    *,
    vault_path: Path | None = None,
    project_slug: str | None = None,
    wiki_root: Path | None = None,
    before: str | None = None,
    after: str | None = None,
    mode: str | None = None,
    stdin=sys.stdin,
    stdout=sys.stdout,
    datestamp: str | None = None,
) -> Path | None:
    """Write an operator-confirmed voice lesson to its on-demand scope store.

    The edit-driven counterpart to `confirm_save_convention()`. The two operator
    gates (generality, scope) are upstream in the skill body; by the time this is
    called the lesson + scope are confirmed. This function still enforces the
    final operator-confirm gate (so nothing auto-commits) and, for per-repo writes
    (which land outside the vault), the permeable-boundary cross-boundary confirm
    with DC-3 graceful-degrade. Returns the Path written, or None when declined /
    the scope's context is missing.
    """
    if scope not in _VALID_SCOPES:
        print(f"[diataxis-conv] unknown scope {scope!r}; expected one of {_VALID_SCOPES}", file=sys.stderr)
        return None
    if vault_path is None:
        vault_path = _resolve_vault_path()
    stamp = datestamp or date.today().isoformat()
    # Canonicalize the trigger to a single-line slug BEFORE it reaches any
    # frontmatter value. An un-sanitized trigger with a newline would inject
    # extra `key: value` lines into the `--- … ---` block that the resolver then
    # parses — round-trip corruption + frontmatter-key injection. The slug form
    # round-trips exactly (the resolver lowercases on read) and is the natural
    # conflict-key shape. `before`/`after` are likewise collapsed via _oneline().
    trigger = _slugify(trigger)
    target, outside_vault = lesson_target(
        scope, vault_path=vault_path, project_slug=project_slug,
        wiki_root=wiki_root, trigger=trigger, datestamp=stamp,
    )
    if target is None:
        need = {"global": "a vault path", "per-project": "a vault path + project slug",
                "per-repo": "a wiki root"}[scope]
        print(f"[diataxis-conv] scope {scope!r} needs {need}; nothing written", file=sys.stderr)
        return None
    if not _approve_lesson(f"voice lesson '{trigger}' -> {scope} ({target})",
                           mode=mode, stdin=stdin, stdout=stdout):
        return None
    if outside_vault and not _permeable_confirm(target, stdin=stdin, stdout=stdout):
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    if scope == "per-repo":
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        content = _merge_per_repo(existing, trigger, guidance, datestamp=stamp)
    else:
        content = _render_dir_lesson(
            trigger, guidance, scope=scope, before=before, after=after, datestamp=stamp)
    target.write_bytes(content.encode("utf-8"))
    return target


def main(argv: list[str] | None = None) -> int:
    """CLI entry: dump current conventions as JSON. Operator-debug surface."""
    import argparse
    parser = argparse.ArgumentParser(prog="diataxis-conventions")
    parser.add_argument("--wiki-root", default=None)
    parser.add_argument("--vault-path", default=None)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    wiki_root = Path(args.wiki_root).expanduser() if args.wiki_root else None
    vault_path = Path(args.vault_path).expanduser() if args.vault_path else None
    conv = load_conventions(wiki_root=wiki_root, vault_path=vault_path)
    print(json.dumps(conv, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
