#!/usr/bin/env python3
"""Section-file shape v2 for the diataxis-author wiki composer.

A *section file* under `templates/sections/<name>.md` is the reusable unit the
composer assembles into a page. Its v1 shape (shipped with the section taxonomy)
is frontmatter + a scaffold + one leading `<!-- SECTION … -->` opinion comment:

    ---
    section: <name>
    reusable: true|false
    applies-to: [<page-type>, ...]
    ---
    <!-- SECTION <name> — opinion the author reads, never published -->

    ## <Heading>

    - **<Placeholder>.** <author-fill slot>.

v2 (this module) is **additive over v1** — every v1 file is a valid v2 file. It
adds two OPTIONAL frontmatter fields and pins two conventions the existing files
already follow, so the composer can treat the whole library uniformly:

  - ``optional: true|false`` (default ``false``) — a conditional section,
    included per-page only when warranted (the ``safety`` worked example).
  - ``heading-variants: [A, B, C]`` — an ordered list of allowed H2 headings for
    a section whose heading is concern-specific; absent → the single fixed
    heading the body already carries.

  - The **strip rule**: the first HTML comment in the file, *if* it opens with
    ``SECTION `` (after leading whitespace), is the opinion block. The loader
    strips exactly that one comment (plus the frontmatter); everything after is
    body. A comment *after* the opinion block is body and is preserved — the
    strip must not over-match (parent design's Data Integrity / round-trip
    invariant).
  - The **placeholder convention**: angle-bracket ``<…>`` slots are author-fill
    markers the composer leaves intact; a surviving ``<…>`` in a composed page
    is an unfilled placeholder (``enforcement``'s soft finding).

This is the contract ``compose-core`` loads against and ``enforcement`` checks.

Pure, total functions over a section file's *text* — no I/O here (the caller
passes in ``read_text()``), and a malformed file never raises: it parses to a
``SectionFile`` with defaulted fields. Deciding what is *fatally* unparseable
(a manifest naming an unknown section, an empty body) is ``author-wiring``'s
fail-closed concern, layered on top of this total parse. Mirrors ``promote.py``'s
frontmatter-parse convention (one house style for ``--- … ---`` blocks).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# The first HTML comment opening with this prefix is the opinion block (strip rule).
_OPINION_PREFIX = "SECTION "
# The first HTML comment in the text (non-greedy body; DOTALL so a multi-line
# opinion comment — most of them are — matches end to end).
_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
# An angle-bracket placeholder `<…>`: opens with neither `!` (an HTML comment
# `<!-- … -->`) nor `/` (a close tag), spans no `<`, `>`, or newline. Advisory —
# a literal `<x>` in prose can false-match; enforcement's finding-not-failure
# default (parent Risk #2) absorbs it.
_PLACEHOLDER_RE = re.compile(r"<(?![!/])[^<>\n]+>")
# A leading `--- … ---` frontmatter block + the body after it.
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


@dataclass
class SectionFile:
    """A parsed section file under ``templates/sections/<name>.md``.

    ``section`` / ``reusable`` / ``applies_to`` are v1; ``optional`` /
    ``heading_variants`` are the v2 additions (defaulted off so a v1 file parses
    unchanged). ``body`` is the text left after the frontmatter and the single
    opinion comment are stripped — what the composer concatenates under the page
    H1; it is preserved verbatim (including any body comments and ``<…>``
    placeholders), the composer owns inter-section whitespace. ``opinion`` is the
    stripped opinion comment's inner text, or ``None`` if the file has no
    ``SECTION ``-prefixed leading comment. ``frontmatter`` is the raw key→value
    dict, so a forward-compat field is readable without a parser change.
    """

    section: str
    reusable: bool = False
    applies_to: list = field(default_factory=list)
    optional: bool = False
    heading_variants: list = field(default_factory=list)
    body: str = ""
    opinion: str | None = None
    frontmatter: dict = field(default_factory=dict)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a leading ``--- … ---`` block into a simple key→value dict + body.

    Mirrors ``promote.py``'s parser (one house convention for frontmatter). No
    frontmatter → ``({}, text)``."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, m.group(2)


def _parse_bool(raw: str | None, *, default: bool = False) -> bool:
    """Parse a frontmatter boolean (``true``/``false``, case-insensitive)."""
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _parse_list(raw: str | None) -> list:
    """Parse an inline ``[a, b, c]`` frontmatter list into trimmed terms.

    Strips the surrounding brackets, then comma-splits (tolerating a bare,
    bracketless comma list too). Absent / empty → ``[]``. Order is preserved —
    ``heading-variants`` is an ordered list (the first variant is the default
    heading the fixed-heading fallback resolves to)."""
    if raw is None:
        return []
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [t.strip() for t in raw.split(",") if t.strip()]


def strip_opinion(text: str) -> tuple[str | None, str]:
    """Apply the strip rule: peel the single ``SECTION ``-prefixed opinion comment.

    Returns ``(opinion_inner_or_None, body)``. The *first* HTML comment in
    ``text`` is the opinion block only if its inner text opens with ``SECTION ``
    once leading whitespace is trimmed. If so, strip exactly that one comment and
    return the rest verbatim — any *later* comment (a body comment) is preserved,
    guarding the round-trip invariant against an over-matching strip. If the first
    comment is not ``SECTION ``-prefixed (or there is none), nothing is stripped:
    ``(None, text)``.
    """
    m = _COMMENT_RE.search(text)
    if not m:
        return None, text
    inner = m.group(1)
    if not inner.lstrip().startswith(_OPINION_PREFIX):
        # First comment is not the opinion block — leave it (over-matching it
        # would corrupt a section that opens with a non-opinion comment; the
        # strip-rule-thinness risk is flagged for enforcement to police).
        return None, text
    body = text[: m.start()] + text[m.end() :]
    return inner.strip(), body


def find_placeholders(text: str) -> list:
    """Return every angle-bracket ``<…>`` placeholder in ``text``, in order."""
    return _PLACEHOLDER_RE.findall(text)


def parse_section(text: str) -> SectionFile:
    """Parse a section file's text into a ``SectionFile`` (schema v2).

    Splits frontmatter (v1 ``section``/``reusable``/``applies-to`` + v2
    ``optional``/``heading-variants``), applies the strip rule to peel the single
    opinion comment, and leaves the body — including any body comments and
    ``<…>`` placeholders — verbatim. Additive over v1: a v1 file parses with
    ``optional=False`` and ``heading_variants=[]``. Total — never raises on the
    library's inputs.
    """
    fm, after_fm = _split_frontmatter(text)
    opinion, body = strip_opinion(after_fm)
    return SectionFile(
        section=fm.get("section", ""),
        reusable=_parse_bool(fm.get("reusable")),
        applies_to=_parse_list(fm.get("applies-to")),
        optional=_parse_bool(fm.get("optional")),
        heading_variants=_parse_list(fm.get("heading-variants")),
        body=body,
        opinion=opinion,
        frontmatter=fm,
    )
