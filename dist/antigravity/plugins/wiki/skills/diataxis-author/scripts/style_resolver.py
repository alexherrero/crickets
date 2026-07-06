#!/usr/bin/env python3
# style_resolver.py — author-time voice resolver for diataxis-author
# (wiki-maintenance part 3/5, style-learning-loop, task 1).
#
# Composes  template ⊕ base style-guide ⊕ overlay  at author time. Today
# author.py wrote templates verbatim with no voice layer; this module adds one.
#
#   Base style-guide  — the committed house-voice floor (style/base-style-guide.md).
#                       Always present (ships in dist/ with the skill). A public-safe
#                       distillation of the operator's docs-prose-style voice; the
#                       full personal entry layers on at runtime as a vault overlay.
#   Overlay           — learned voice lessons read ON-DEMAND (never _always-load)
#                       from three scopes, narrower + recent wins:
#                         global      <vault>/projects/_global/wiki-style/*.md
#                         per-project <vault>/projects/<slug>/wiki-style/*.md
#                         per-repo    <wiki-root>/.diataxis-conventions.md
#                       Precedence (lowest→highest): global → project → repo. On a
#                       trigger conflict the narrower scope wins.
#
# The composed voice is injected into the authored page as an author-facing HTML
# comment block (same idiom as the per-template scaffolding comments), positioned
# after the H1 so page structure is preserved. The operator deletes it before
# publishing. The `_global` slug is the relocation target for task 4 (the
# _always-load → on-demand move); this resolver already reads it.
#
# Stdlib-only; matches the established skill convention.

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# The committed base style-guide floor — ships in dist/ alongside the skill,
# at <skill-root>/style/base-style-guide.md.
_SKILL_ROOT = _SCRIPTS_DIR.parent
_BASE_STYLE_GUIDE = _SKILL_ROOT / "style" / "base-style-guide.md"

# Scope ranks: higher = narrower = wins on a trigger conflict.
_SCOPE_RANK = {"global": 0, "per-project": 1, "per-repo": 2}

_PER_REPO_FILE = ".diataxis-conventions.md"


@dataclass(frozen=True)
class StyleLesson:
    """One learned voice lesson from an overlay scope."""

    scope: str       # global | per-project | per-repo
    trigger: str     # conflict key (lowercased) — narrower scope wins on the same trigger
    guidance: str    # the voice guidance text
    source: str      # filename it came from (provenance)


@dataclass
class ResolvedStyle:
    """The composed voice: committed base floor + narrowest-wins overlay lessons."""

    base_text: str
    lessons: list      # list[StyleLesson], precedence applied (narrower wins)
    provenance: list   # list[str] "<scope>:<source>" lines, in application order


def load_base_style_guide(path: Path | None = None) -> str:
    """Read the committed base style-guide floor. Empty string if unreadable."""
    p = path or _BASE_STYLE_GUIDE
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


_FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a `--- ... ---` frontmatter block from the body. Tolerant — only
    simple `key: value` lines are parsed; everything else is body."""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip().lower()] = v.strip()
    return fm, m.group(2)


def parse_lesson(text: str, *, scope: str, source: str) -> StyleLesson:
    """Parse one overlay lesson file into a StyleLesson.

    A lesson may carry frontmatter `trigger:` to set its conflict key; absent
    that, the filename stem is the trigger. The body (after frontmatter) is the
    guidance. Triggers are lowercased so conflict matching is case-insensitive.
    """
    fm, body = _split_frontmatter(text)
    trigger = (fm.get("trigger") or Path(source).stem).strip().lower()
    return StyleLesson(scope=scope, trigger=trigger, guidance=body.strip(), source=source)


def read_scope_lessons(scope_dir: Path | None, scope: str) -> list:
    """Read *.md voice lessons from a scope dir.

    Sorted by filename; within the scope a later-sorted file with the same
    trigger overrides an earlier one (recent wins — capture writes date/counter
    prefixes, so later-sorted == more recent). Missing dir → []."""
    if scope_dir is None or not scope_dir.is_dir():
        return []
    merged: dict = {}
    for entry in sorted(scope_dir.glob("*.md")):
        try:
            text = entry.read_text(encoding="utf-8")
        except OSError:
            continue
        lesson = parse_lesson(text, scope=scope, source=entry.name)
        merged[lesson.trigger] = lesson  # later-sorted overrides earlier
    return list(merged.values())


def _read_per_repo_lessons(wiki_root: Path | None) -> list:
    """Per-repo voice lives in the single <wiki-root>/.diataxis-conventions.md."""
    if wiki_root is None:
        return []
    f = Path(wiki_root) / _PER_REPO_FILE
    if not f.is_file():
        return []
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return []
    return [parse_lesson(text, scope="per-repo", source=f.name)]


def resolve_style(
    *,
    wiki_root: Path | None = None,
    vault_path: Path | None = None,
    project_slug: str | None = None,
    base_text: str | None = None,
) -> ResolvedStyle:
    """Compose base style-guide ⊕ overlay lessons across the three on-demand scopes.

    Precedence (lowest → highest): global → per-project → per-repo. On a trigger
    conflict the narrower scope wins; distinct triggers accumulate. Each scope is
    independently graceful-skipped when its store is absent — with no vault and no
    overlay the result is the committed base floor alone (the documented fallback).
    """
    base = base_text if base_text is not None else load_base_style_guide()
    merged: dict = {}   # trigger -> StyleLesson; dict keeps first-insert position, replaces value
    provenance: list = []

    def _apply(lessons: list) -> None:
        for lz in lessons:
            merged[lz.trigger] = lz
            provenance.append(f"{lz.scope}:{lz.source}")

    if vault_path is not None:
        vp = Path(vault_path)
        # Project-keyed stores live under the top-level `projects/` root (the
        # canonical post-V4#26 layout agentm + the live vault use) — NOT under
        # `personal/`, which is for personal, non-project-keyed data.
        # `_global` is a reserved pseudo-project for cross-project on-demand
        # conventions. See agentm ADR 0010 (vault internal taxonomy).
        gdir = vp / "projects" / "_global" / "wiki-style"
        _apply(read_scope_lessons(gdir, "global"))
        if project_slug:
            pdir = vp / "projects" / project_slug / "wiki-style"
            _apply(read_scope_lessons(pdir, "per-project"))
    _apply(_read_per_repo_lessons(wiki_root))

    return ResolvedStyle(base_text=base, lessons=list(merged.values()), provenance=provenance)


# ── Page composition ────────────────────────────────────────────────────────

_BLOCK_OPEN = "<!-- ─── house style (base ⊕ learned overlay) — author-facing; delete before publishing"
_BLOCK_CLOSE = "─── end house style ─── -->"


def _sanitize_comment(text: str) -> str:
    """Neutralize stray comment-closers so embedded content can't break the block.

    Inserts a space between the `--` and `>` of any `-->`: that breaks the only
    token that closes an HTML comment, while staying readable (author-facing)."""
    return text.replace("-->", "-- >")


def compose_voice_block(resolved: ResolvedStyle) -> str:
    """Render the composed voice as one author-facing HTML comment block."""
    lines = [_BLOCK_OPEN, ""]
    base = resolved.base_text.strip()
    if base:
        lines.append("BASE VOICE (committed floor):")
        lines.append(_sanitize_comment(base))
        lines.append("")
    if resolved.lessons:
        lines.append("LEARNED LESSONS (on-demand overlay; narrower scope wins):")
        for lz in resolved.lessons:
            g = _sanitize_comment(lz.guidance).strip()
            lines.append(f"  [{lz.scope}] {lz.trigger}: {g}")
        lines.append("")
    lines.append(_BLOCK_CLOSE)
    return "\n".join(lines)


def apply_style_to_page(template_text: str, resolved: ResolvedStyle) -> str:
    """Inject the composed voice block after the page H1 (or prepend if no H1).

    Structure is preserved — the H1 stays first, the block follows as an
    author-facing comment, the template body follows unchanged.
    """
    block = compose_voice_block(resolved)
    lines = template_text.splitlines(keepends=True)
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("# "):
            insert_idx = i + 1
            break
    block_lines = ["\n", block + "\n", "\n"]
    return "".join(lines[:insert_idx] + block_lines + lines[insert_idx:])
