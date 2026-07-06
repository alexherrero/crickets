#!/usr/bin/env python3
# promote.py — operator-gated overlay->base promotion for diataxis-author
# (wiki-maintenance part 5/5, dogfood-finale, task 2).
#
# Graduates a PROVEN overlay voice lesson — from the on-demand store the resolver
# reads (`<vault>/projects/_global/wiki-style/<date>-<trigger>.md`, per-project,
# or a per-repo `.diataxis-conventions.md`) — INTO the committed repo base
# `src/wiki/skills/diataxis-author/style/base-style-guide.md`, so
# every fresh draft inherits it without the overlay. This is the `promote` path
# SKILL.md forward-references; it closes the style-learning loop.
#
# Discipline (mirrors relocate.py / capture.py):
#   * PREVIEW-FIRST  — `--preview` prints the unified diff, writes NOTHING.
#   * SRC-ONLY       — apply edits the **src/** base, never `dist/`. The base is
#                      found by walking up to the repo's `src/` tree; an installed
#                      consumer with no `src/` sibling is REFUSED (exit 2), which
#                      enforces the design's "consumers have no write path to the
#                      dist/ base" — promotion is a maintainer-only operation.
#   * NEVER AUTO-COMMITS — apply leaves the src/ edit on disk (unstaged) for the
#                      maintainer to review + `git commit` + `generate.py build`.
#                      The non-TTY apply gate denies surprise writes (use
#                      `--mode silent` only in tests/automation you control).
#   * IDEMPOTENT     — a lesson already present in the base is a clean no-op.
# Stdlib-only; matches the established convention.

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# The committed base, relative to a crickets repo root. Resolution targets this
# under `src/` ONLY — never the `dist/` copy.
REL_BASE = Path("src/wiki/skills/diataxis-author/style/base-style-guide.md")

# Sections of base-style-guide.md a bullet can land under.
_SECTIONS = ("Voice", "Banned", "Structure")
_BANNED_RE = re.compile(r"^(\s*)banned:\s*(.*?)\s*$", re.IGNORECASE)


# ── Resolving the SRC base (and refusing when there is none) ─────────────────

def resolve_base(repo_root: str | Path | None = None, *, _starts=None) -> Path | None:
    """Resolve the committed src/ base-style-guide.md, or None if unreachable.

    With `repo_root`: target `<repo_root>/REL_BASE` (returned only if it exists).
    Without: walk up from this script's dir + CWD, returning the first ancestor
    that contains `src/wiki/.../base-style-guide.md`. Returning None
    is the *enforcement* path — an installed plugin (only `dist/`, no `src/`) has
    no maintainer src tree, so promotion is refused rather than writing `dist/`.
    """
    if repo_root is not None:
        cand = Path(repo_root).expanduser() / REL_BASE
        return cand if cand.is_file() else None
    starts = _starts if _starts is not None else [Path(__file__).resolve().parent, Path.cwd()]
    seen: set = set()
    for start in starts:
        start = Path(start).resolve()
        for anc in [start, *start.parents]:
            if anc in seen:
                continue
            seen.add(anc)
            cand = anc / REL_BASE
            if cand.is_file():
                return cand
    return None


# ── Parsing the overlay lesson ───────────────────────────────────────────────

@dataclass
class Lesson:
    """A confirmed overlay lesson: its conflict-key `trigger`, the `guidance`
    prose (the only thing the resolver injects), and any machine-checkable
    `banned:` terms it declares."""

    trigger: str | None
    guidance: str
    banned_terms: list = field(default_factory=list)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a leading `--- … ---` block into a simple key:value dict + body."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def _split_terms(raw: str) -> list:
    """Comma-split a `banned:` value into trimmed, non-empty terms."""
    return [t.strip() for t in raw.split(",") if t.strip()]


def parse_lesson(text: str) -> Lesson:
    """Parse an overlay lesson file's text into a Lesson.

    `trigger` comes from frontmatter; the guidance is the body with any `banned:`
    directive lines and recognized `key: value` convention lines removed; banned
    terms are unioned across every `banned:` line found (frontmatter or body)."""
    fm, body = _split_frontmatter(text)
    trigger = fm.get("trigger") or None
    banned: list = []
    if "banned" in fm:
        banned += _split_terms(fm["banned"])
    guidance_lines: list = []
    for line in body.splitlines():
        bm = _BANNED_RE.match(line)
        if bm:
            banned += _split_terms(bm.group(2))
            continue
        guidance_lines.append(line)
    # Dedup banned terms case-insensitively, preserving first-seen order.
    seen: set = set()
    uniq: list = []
    for t in banned:
        if t.lower() not in seen:
            seen.add(t.lower())
            uniq.append(t)
    guidance = "\n".join(guidance_lines).strip()
    return Lesson(trigger=trigger, guidance=guidance, banned_terms=uniq)


def _oneline(text: str) -> str:
    """Collapse multi-line guidance to a single bullet-safe line."""
    return " ".join(ln.strip() for ln in text.splitlines() if ln.strip())


# ── Computing the promotion ──────────────────────────────────────────────────

@dataclass
class Plan:
    """The result of computing a promotion against the current base."""

    new_text: str
    added_banned: list = field(default_factory=list)
    bullet_added: str | None = None
    notes: list = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added_banned) or self.bullet_added is not None


def merge_banned(base_terms: list, new_terms: list) -> tuple[list, list]:
    """Append `new_terms` not already in `base_terms` (case-insensitive),
    preserving base order then new-term order. Returns (merged, added)."""
    have = {t.lower() for t in base_terms}
    added: list = []
    for t in new_terms:
        if t.lower() not in have:
            have.add(t.lower())
            added.append(t)
    return base_terms + added, added


def _section_bounds(lines: list, section: str) -> tuple[int, int] | None:
    """[start, end) line indices of a `## <section>` block (heading excluded from
    the body span via start = heading index). end = next `## ` heading or EOF."""
    head = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() == f"## {section}".lower():
            head = i
            break
    if head is None:
        return None
    end = len(lines)
    for j in range(head + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return head, end


def _logical_bullets(lines: list, start: int, end: int) -> list:
    """Reconstruct the section's bullets as LOGICAL units, normalized + lowercased.

    Base bullets are hard-wrapped across multiple physical lines, so a per-physical-
    line compare would miss them (an idempotence hole — re-promoting a lesson that
    matches an existing wrapped bullet would duplicate it). A bullet opens on a
    `- `/`* ` line and absorbs subsequent non-blank, non-heading continuation lines
    until the next bullet / blank line / heading."""
    out: list = []
    cur = None
    for ln in lines[start:end]:
        s = ln.strip()
        if re.match(r"^[-*]\s", s):
            if cur is not None:
                out.append(cur)
            # strip ONLY the bullet marker ("- "/"* "), preserving leading **bold**.
            cur = re.sub(r"^[-*]\s+", "", s)
        elif not s or s.startswith("#"):
            if cur is not None:
                out.append(cur)
                cur = None
        elif cur is not None:
            cur = f"{cur} {s}"
    if cur is not None:
        out.append(cur)
    return [_oneline(b).lower() for b in out]


def _bullet_present(lines: list, start: int, end: int, bullet: str) -> bool:
    """True if the bullet already appears in the section span (as a logical,
    wrap-insensitive unit) — the idempotence check for re-promotion."""
    target = _oneline(re.sub(r"^[-*]\s+", "", bullet.strip())).lower()
    return target in _logical_bullets(lines, start, end)


def compute_promotion(
    base_text: str, lesson: Lesson, *, section: str = "Voice", add_bullet: bool = True,
) -> Plan:
    """Compute the new base text for promoting `lesson`.

    Merges the lesson's `banned:` terms into the base's `banned:` directive (if
    any are new), and appends the guidance as a bullet under `## <section>` (when
    `add_bullet` and the guidance is non-empty and not already present). Pure —
    writes nothing. Idempotent: an already-present lesson yields `changed=False`.
    """
    notes: list = []
    lines = base_text.split("\n")

    # 1. Merge banned terms into the base `banned:` directive.
    added_banned: list = []
    if lesson.banned_terms:
        bidx = next((i for i, ln in enumerate(lines) if _BANNED_RE.match(ln)), None)
        if bidx is None:
            notes.append("lesson declares banned terms but base has no `banned:` directive; skipped")
        else:
            m = _BANNED_RE.match(lines[bidx])
            indent, base_terms = m.group(1), _split_terms(m.group(2))
            merged, added_banned = merge_banned(base_terms, lesson.banned_terms)
            if added_banned:
                lines[bidx] = f"{indent}banned: {', '.join(merged)}"

    # 2. Append the guidance bullet under the chosen section.
    bullet_added: str | None = None
    if add_bullet and lesson.guidance:
        bullet = f"- {_oneline(lesson.guidance)}"
        bounds = _section_bounds(lines, section)
        if bounds is None:
            notes.append(f"section '## {section}' not found in base; bullet not added")
        elif _bullet_present(lines, bounds[0], bounds[1], bullet):
            notes.append("guidance bullet already present; not duplicated")
        else:
            start, end = bounds
            # Insert after the last non-blank line of the section body.
            insert_at = start + 1
            for k in range(end - 1, start, -1):
                if lines[k].strip():
                    insert_at = k + 1
                    break
            lines.insert(insert_at, bullet)
            bullet_added = bullet

    return Plan(new_text="\n".join(lines), added_banned=added_banned,
                bullet_added=bullet_added, notes=notes)


def unified_diff(old: str, new: str, path: str) -> str:
    """A `diff -u`-style preview of the proposed base edit."""
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}",
    ))


# ── The never-auto-commit apply gate (mirrors capture.py / agentmemory) ──────

def _approve(prompt: str, *, mode: str | None, stdin, stdout) -> bool:
    """silent -> True; auto -> TTY-only; interactive -> prompt. Denies non-TTY by
    default so a batch run never silently rewrites the committed base.

    Unlike capture.py / agentmemory_conventions.py, promote deliberately does NOT
    consult the ambient `MEMORY_REVIEW_MODE` env var. Those write reversible overlay
    files; promote rewrites the COMMITTED `src/` base, so the `silent` bypass must be
    an explicit per-invocation `--mode silent` (tests/automation you control) — never
    inherited from the environment. (An operator who set MEMORY_REVIEW_MODE=silent
    for /memory reflect must NOT thereby get a non-TTY promote that silently rewrites
    committed source.)"""
    if mode is None:
        mode = "interactive"
    if mode == "silent":
        return True
    is_tty = stdin.isatty() if hasattr(stdin, "isatty") else False
    if mode == "auto":
        if not is_tty:
            print(f"[promote] auto mode + non-TTY -> denying ({prompt})", file=sys.stderr)
            return False
        return True
    if not is_tty:
        print(f"[promote] interactive mode + non-TTY -> defaulting to deny ({prompt})", file=sys.stderr)
        return False
    print(f"Promote {prompt} into the committed base? [y/N]", file=stdout)
    stdout.flush()
    try:
        resp = stdin.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return resp in ("y", "yes")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list | None = None, *, stdin=None, stdout=None) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    p = argparse.ArgumentParser(
        prog="diataxis-promote",
        description="Promote a proven overlay voice lesson into the committed base style-guide.")
    p.add_argument("--lesson", required=True, help="path to the confirmed overlay lesson file")
    p.add_argument("--preview", action="store_true", help="dry-run: print the unified diff, write nothing")
    p.add_argument("--section", default="Voice", choices=_SECTIONS,
                   help="base section the guidance bullet lands under (default: Voice)")
    p.add_argument("--no-bullet", action="store_true",
                   help="merge banned terms only; do not add a guidance bullet")
    p.add_argument("--repo-root", default=None,
                   help="crickets repo root (default: auto-resolve the src/ base by walking up)")
    p.add_argument("--mode", default=None, choices=("interactive", "silent", "auto"),
                   help="apply confirm gate (default: interactive; non-TTY denies)")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    base_path = resolve_base(args.repo_root)
    if base_path is None:
        print("[promote] no src/ base-style-guide.md found — promotion is a maintainer "
              "operation run from the crickets source tree (installed consumers cannot "
              "write the dist/ base).", file=sys.stderr)
        return 2

    lesson_file = Path(args.lesson).expanduser()
    if not lesson_file.is_file():
        print(f"[promote] lesson not found: {lesson_file}", file=sys.stderr)
        return 1
    try:
        lesson = parse_lesson(lesson_file.read_text(encoding="utf-8"))
    except OSError as e:
        print(f"[promote] could not read lesson ({e})", file=sys.stderr)
        return 1
    if not lesson.guidance and not lesson.banned_terms:
        print("[promote] lesson has neither guidance nor banned terms — nothing to promote.",
              file=sys.stderr)
        return 1

    base_text = base_path.read_text(encoding="utf-8")
    plan = compute_promotion(base_text, lesson, section=args.section, add_bullet=not args.no_bullet)
    for note in plan.notes:
        print(f"[promote] {note}", file=sys.stderr)

    if not plan.changed:
        print("[promote] already in base; nothing to promote (idempotent no-op).")
        return 0

    rel = str(REL_BASE)
    if args.preview:
        sys.stdout.write(unified_diff(base_text, plan.new_text, rel))
        summary = []
        if plan.added_banned:
            summary.append(f"+{len(plan.added_banned)} banned term(s): {', '.join(plan.added_banned)}")
        if plan.bullet_added:
            summary.append(f"+1 bullet under ## {args.section}")
        print(f"[promote] PREVIEW only — nothing written. Would apply: {'; '.join(summary)}.",
              file=sys.stderr)
        return 0

    what = []
    if plan.added_banned:
        what.append(f"{len(plan.added_banned)} banned term(s)")
    if plan.bullet_added:
        what.append(f"a bullet under ## {args.section}")
    if not _approve(" + ".join(what) + f" (trigger: {lesson.trigger or '?'})",
                    mode=args.mode, stdin=stdin, stdout=stdout):
        print("[promote] declined — base unchanged.", file=sys.stderr)
        return 1

    base_path.write_text(plan.new_text, encoding="utf-8")
    print(f"[promote] wrote {base_path}")
    print("[promote] NEXT (maintainer): review the diff, `git commit`, then "
          "`python3 scripts/generate.py build` to re-emit dist/. Nothing was committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
