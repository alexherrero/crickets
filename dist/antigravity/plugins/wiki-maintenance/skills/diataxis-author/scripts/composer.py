#!/usr/bin/env python3
"""The wiki composer — manifest → assembled page (wiki-composer part 2/4, compose-core).

A *page manifest* (e.g. ``templates/component-overview.md``) lists an ordered set
of section names in its ``sections:`` frontmatter. The composer turns that list
into a page by running each section through four steps:

  1. **load**    — read ``templates/sections/<name>.md`` (``load_section_body``).
  2. **strip**   — peel the frontmatter + the single ``SECTION `` opinion comment,
                   keeping the body verbatim. Delegated to the shipped
                   ``section_schema.parse_section()`` — one strip rule, library-wide
                   tested; the composer does NOT re-implement the split.
  3. **resolve** — apply the resolved house voice (``base ⊕ overlay`` via
                   ``style_resolver``) once, after the page H1 (``compose_voice``).
  4. **concat**  — join the stripped bodies in manifest order under the page H1
                   (``compose_page``).

The four steps are pure functions of (manifest, library, resolved-voice, lang);
determinism is the point — same inputs → byte-identical output, which is what
makes the proof slice an acceptance test.

**The page H1** comes from an explicit ``title`` argument — the page identity the
caller supplies. The manifest is shared across every page of its type (one
``component-overview`` manifest, many component pages), so it cannot carry a
per-page title; ``author-wiring`` (part 3/4) derives the title from the slug, as
``author.py`` already derives the filename. The composer emits ``# {title}`` and
``style_resolver.apply_style_to_page`` anchors the voice comment to it.

**The language seam.** A section is one language-neutral file (the resolved fork:
translate downstream). ``load_section_body`` / ``compose_page`` carry a ``lang``
parameter defaulted to ``en`` — the only value the first cut supports. A
non-``en`` value is rejected, not silently honored: the translate-downstream pass
is a separate, deferred design, and ``lang`` is its reserved entry point so adding
Spanish never reshapes the section files.

Stdlib-only; sits beside ``author.py`` / ``style_resolver.py`` / ``section_schema.py``
in the skill's ``scripts/`` dir and is shipped with the skill. ``author-wiring``
adds the dispatch in ``author_page()`` that calls ``compose_page()`` for a
manifest and falls back to the verbatim monolith path otherwise; this module owns
only the transform.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import section_schema  # noqa: E402 — sibling module, resolved via the sys.path insert above

# The shipped section library: <skill-root>/templates/sections/<name>.md.
_SECTIONS_DIR = _SCRIPTS_DIR.parent / "templates" / "sections"

# The reserved translate-downstream seam: English today, the only value built.
_DEFAULT_LANG = "en"


def load_section_body(name: str, *, sections_dir: Path | None = None, lang: str = _DEFAULT_LANG) -> str:
    """Load one section file and return its stripped body (verbatim).

    Reads ``<sections_dir>/<name>.md`` and returns
    ``section_schema.parse_section(text).body`` — the frontmatter and the single
    ``SECTION `` opinion comment removed, everything else (body comments, ``<…>``
    placeholders) preserved exactly. This is step 1+2 (load · strip) of the
    pipeline; ``compose_page`` owns inter-section whitespace, so the body is
    returned *verbatim* here, not normalized.

    ``sections_dir`` defaults to the shipped library (a testable seam). ``lang``
    is the reserved translate-downstream seam — ``en`` is the only supported
    value; a non-``en`` value raises ``NotImplementedError`` rather than silently
    emitting an untranslated page (the translation pass is a deferred design).
    """
    if lang != _DEFAULT_LANG:
        raise NotImplementedError(
            f"lang={lang!r} is not supported yet; only {_DEFAULT_LANG!r} is built. "
            "The translate-downstream pass is a separate deferred design; `lang` is "
            "its reserved seam (parent design DD §1)."
        )
    directory = Path(sections_dir) if sections_dir is not None else _SECTIONS_DIR
    text = (directory / f"{name}.md").read_text(encoding="utf-8")
    return section_schema.parse_section(text).body


def compose_voice(
    page_text: str,
    *,
    resolved_style=None,  # style_resolver.ResolvedStyle | None — inject to pin voice (deterministic proofs)
    wiki_root: Path | None = None,
    vault_path: Path | None = None,
    project_slug: str | None = None,
) -> str:
    """Inject the resolved house voice once, after the page H1 — or degrade to the bare page.

    Step 3 (resolve) of the pipeline. Mirrors ``author_page()``: the composed
    voice (``base ⊕ overlay`` via ``style_resolver``) is emitted as a single
    author-facing comment after the page H1 (``apply_style_to_page`` anchors it),
    guiding the author without rewriting their prose — the ``<…>`` placeholders are
    left intact. Both emit paths — the composer here and ``author.py``'s verbatim
    monolith — share this one voice convention, so the parent's verbatim-vs-compose
    fork (Risk #2) narrows to a single injection point.

    Resolution is wrapped in the same try/except graceful-degrade ``author_page()``
    uses: an import failure, a resolver error, or an empty voice all fall back to
    ``page_text`` unchanged — voice never raises and never blocks composition.

    ``resolved_style`` is the determinism seam: pass a fixed ``ResolvedStyle`` to
    pin the voice (the proof slice does this, so it exercises the pipeline rather
    than the live vault — parent Risk #3); leave it ``None`` to resolve live across
    the three scopes (``wiki_root`` / ``vault_path`` / ``project_slug``), exactly as
    ``author_page()`` does.
    """
    try:
        import style_resolver  # type: ignore — lazy, so an import failure degrades too
        resolved = resolved_style
        if resolved is None:
            resolved = style_resolver.resolve_style(
                wiki_root=wiki_root,
                vault_path=vault_path,
                project_slug=project_slug,
            )
        # Empty voice (no committed floor, no overlay lessons) → bare page; an
        # empty comment block would be noise. Same guard as author_page().
        if not (resolved.base_text.strip() or resolved.lessons):
            return page_text
        return style_resolver.apply_style_to_page(page_text, resolved)
    except Exception as e:  # noqa: BLE001 — never fail composition over the voice layer
        print(
            f"[diataxis-author] style resolver unavailable ({e}); "
            "composing without the voice layer",
            file=sys.stderr,
        )
        return page_text
