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
#                         global      <projects-space>/_global/wiki-style/*.md
#                         per-project <projects-space>/<slug>/wiki-style/*.md
#                         per-repo    <wiki-root>/.diataxis-conventions.md
#                       <projects-space> is resolved per-vault by vault_layout
#                       (desk/projects → projects → personal-projects), never
#                       pinned to one layout generation.
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
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import vault_layout  # noqa: E402  (needs the sys.path insert above)

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
    genres: frozenset = frozenset()   # declared applicability; EMPTY MEANS UNIVERSAL


@dataclass
class ResolvedStyle:
    """The composed voice: committed base floor + narrowest-wins overlay lessons."""

    base_text: str
    lessons: list      # list[StyleLesson], precedence applied (narrower wins)
    provenance: list   # list[str] "<scope>:<source>" lines, in application order
    excluded: list = field(default_factory=list)  # [(trigger, sorted-genres)] held back
    genres: frozenset = frozenset()               # what was asked for; empty = no filter


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


def _parse_genres(raw) -> frozenset:
    """`[docs, design]` or `docs, design` -> {"docs", "design"}. Absent -> empty."""
    if not raw or not str(raw).strip():
        return frozenset()
    return frozenset(
        part.strip().lower()
        for part in str(raw).strip().strip("[]").split(",")
        if part.strip()
    )


def lesson_applies(lesson: StyleLesson, genres) -> bool:
    """Does this lesson belong in a draft of these genres?

    Universal lessons (no declared genre) always apply. With no genre asked for,
    everything applies — the unfiltered default. Otherwise the lesson's declared
    genres must intersect what was asked for.
    """
    if not lesson.genres or not genres:
        return True
    return bool(lesson.genres & frozenset(genres))


def parse_lesson(text: str, *, scope: str, source: str) -> StyleLesson:
    """Parse one overlay lesson file into a StyleLesson.

    A lesson may carry frontmatter `trigger:` to set its conflict key; absent
    that, the filename stem is the trigger. The body (after frontmatter) is the
    guidance. Triggers are lowercased so conflict matching is case-insensitive.

    `genres:` declares what the lesson applies to — `[docs, design]` or a bare
    comma list. AN ABSENT OR EMPTY `genres:` MEANS UNIVERSAL, not "applies to
    nothing": a lesson has to opt IN to being narrow. That asymmetry is the
    whole safety property of the filter — every lesson written before genres
    existed keeps applying everywhere, and a typo in the field name widens a
    lesson rather than silently deleting it from every draft.
    """
    fm, body = _split_frontmatter(text)
    trigger = (fm.get("trigger") or Path(source).stem).strip().lower()
    return StyleLesson(scope=scope, trigger=trigger, guidance=body.strip(),
                       source=source, genres=_parse_genres(fm.get("genres")))


def read_scope_lessons(scope_dir: Path | None, scope: str) -> list:
    """Read *.md voice lessons from a scope dir.

    Sorted by filename; within the scope a later-sorted file with the same
    trigger overrides an earlier one (recent wins — capture writes date/counter
    prefixes, so later-sorted == more recent). Missing dir → [].

    Unfiltered by design: this is the plain reader, and the round-trip checks
    that a captured lesson reads back use it. `partition_scope_lessons` is the
    genre-aware wrapper.
    """
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


def partition_scope_lessons(scope_dir: Path | None, scope: str, genres=None) -> tuple:
    """`read_scope_lessons` split into (applies, held-back) for these genres.

    The held-back ones are returned rather than dropped so the caller can name
    them. Genre matching happens AFTER the trigger merge, so a narrow lesson
    still overrides a broader one with the same trigger before either is
    considered for exclusion.
    """
    kept, excluded = [], []
    for lesson in read_scope_lessons(scope_dir, scope):
        (kept if lesson_applies(lesson, genres) else excluded).append(lesson)
    return kept, excluded


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


def _partition_per_repo_lessons(wiki_root: Path | None, genres=None) -> tuple:
    """`_read_per_repo_lessons` split into (applies, held-back)."""
    kept, excluded = [], []
    for lesson in _read_per_repo_lessons(wiki_root):
        (kept if lesson_applies(lesson, genres) else excluded).append(lesson)
    return kept, excluded


def _warn_if_no_overlay_store(vault_path: Path) -> None:
    """One stderr line when a vault has no global overlay store on any layout.

    This is the guard on the failure this resolver already shipped once: the
    voice overlays moved with the vault, the read path stayed pinned to the old
    layout, `read_scope_lessons` reported a missing directory as "no lessons",
    and every authored draft quietly lost the operator's learned voice.

    The discrimination that matters is present-but-empty vs absent-everywhere.
    A store that exists with nothing in it is a legitimate state — an operator
    who has captured no lessons yet — and says nothing. A store that exists on
    no known layout means either the vault moved again or it was never
    created, and both are worth a word at the moment of harm: the draft being
    authored right now is the one going out without the voice.

    A note, not an error. Authoring on the committed base floor alone is the
    documented fallback; it should just stop being invisible.
    """
    if vault_layout.global_wiki_style_dir_if_present(vault_path) is None:
        expected = vault_layout.global_wiki_style_dir(vault_path)
        print(
            f"style_resolver: no voice-overlay store under {vault_path} on any known "
            f"vault layout — authoring on the committed base style guide alone. "
            f"Expected {expected} (or an older layout's equivalent).",
            file=sys.stderr,
        )


def _warn_no_vault_resolved() -> None:
    """One stderr line when the caller passed no vault at all.

    The sibling of _warn_if_no_overlay_store, and the more common failure: a
    correct overlay path buys nothing if nothing ever hands the resolver a
    vault. That was the state of every ordinary authoring session — the hooks
    export `$MEMORY_VAULT_PATH`, an interactive run does not, and the resolver
    said nothing because "no vault" and "no lessons" reach the same empty list.
    """
    print(
        "style_resolver: no vault resolved (--vault-path, $MEMORY_VAULT_PATH, or "
        ".agentm-config.json) — authoring on the committed base style guide alone.",
        file=sys.stderr,
    )


def resolve_style(
    *,
    wiki_root: Path | None = None,
    vault_path: Path | None = None,
    project_slug: str | None = None,
    base_text: str | None = None,
    genres=None,
) -> ResolvedStyle:
    """Compose base style-guide ⊕ overlay lessons across the three on-demand scopes.

    Precedence (lowest → highest): global → per-project → per-repo. On a trigger
    conflict the narrower scope wins; distinct triggers accumulate. Each scope is
    independently graceful-skipped when its store is absent — with no vault and no
    overlay the result is the committed base floor alone (the documented fallback).

    `genres` narrows the overlay to lessons that apply to what is being written
    — `{"docs"}` for a wiki page, `{"design"}` for a design doc. Lessons that
    declare no genre are universal and always survive; only a lesson that opted
    into a non-matching genre is held back, and it lands in `.excluded` so the
    composed block can name it. Default `None` filters nothing.

    The heavy genre conventions are what motivate this: docs-prose-style,
    personal-comms-style and personal-narrative-style are ~52k characters
    between them, and a wiki draft was carrying the email register and the
    letter-of-recommendation register alongside the one it wanted.
    """
    base = base_text if base_text is not None else load_base_style_guide()
    wanted = frozenset(genres) if genres else frozenset()
    merged: dict = {}   # trigger -> StyleLesson; dict keeps first-insert position, replaces value
    provenance: list = []
    excluded: list = []

    def _apply(result: tuple) -> None:
        kept, held = result
        for lz in kept:
            merged[lz.trigger] = lz
            provenance.append(f"{lz.scope}:{lz.source}")
        for lz in held:
            excluded.append((lz.trigger, sorted(lz.genres)))

    if vault_path is not None:
        vp = Path(vault_path)
        # Project-keyed stores live in the vault's project space — NOT under
        # `personal/`, which is for personal, non-project-keyed data. `_global`
        # is a reserved pseudo-project for cross-project on-demand conventions.
        # See agentm ADR 0010 (vault internal taxonomy). The space itself has
        # moved between layout generations, so vault_layout probes for it
        # rather than pinning one path (see its header).
        gdir = vault_layout.global_wiki_style_dir(vp)
        _warn_if_no_overlay_store(vp)
        _apply(partition_scope_lessons(gdir, "global", wanted))
        if project_slug:
            pdir = vault_layout.project_wiki_style_dir(vp, project_slug)
            _apply(partition_scope_lessons(pdir, "per-project", wanted))
    else:
        _warn_no_vault_resolved()
    _apply(_partition_per_repo_lessons(wiki_root, wanted))

    return ResolvedStyle(base_text=base, lessons=list(merged.values()),
                         provenance=provenance, excluded=excluded, genres=wanted)


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
    if resolved.excluded:
        # Name what was held back. A filtered lesson that leaves no trace is the
        # same silent absence this resolver already shipped once — the point of
        # the genre filter is to spend fewer tokens, not to make the omission
        # unauditable. Triggers only: the guidance is what costs, and the
        # trigger is enough to notice a wrong exclusion and re-run wider.
        asked = ", ".join(sorted(resolved.genres)) or "none"
        held = "; ".join(f"{trig} (genres: {', '.join(gs)})"
                         for trig, gs in resolved.excluded)
        lines.append(f"NOT LOADED — genre filter asked for [{asked}]: {held}")
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
