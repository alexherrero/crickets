#!/usr/bin/env python3
# author.py — /diataxis author <slug> live authoring guidance (plan #13 part 2 task 3).
#
# Invocation entry for `/diataxis author`. Steps:
#   1. Resolve mode (explicit --mode flag, or operator-input via stdin
#      prompt, or classify intent statement via classify.classify_text).
#   2. Load the corresponding template from templates/<mode>.md.
#   3. Apply filename style (--filename-style or default from AgentMemory
#      conventions or fall-through default 'CamelCase-With-Dashes').
#   4. Compute target path <wiki-root>/<mode>/<filename>.md.
#   5. Halt if target already exists (operator picks a different slug).
#   6. Compose the voice layer (template ⊕ base style-guide ⊕ overlay) via
#      style_resolver and write the result to the target — no longer verbatim
#      (wiki-maintenance part 3 task 1). The composed house voice is injected as
#      an author-facing comment after the H1; the operator deletes it before
#      publishing. Graceful-degrades to the bare template only if the resolver /
#      committed base are unavailable.
#   7. Emit operator-facing summary (path written + template fields to fill in).
#
# Stdlib-only. Filename style + mode default are operator-tunable via
# AgentMemory `_always-load/diataxis-*.md`; the voice overlay is read on-demand
# from the three scopes the resolver knows (global / per-project / per-repo).

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# composer ships beside author.py in scripts/; it owns the manifest→page transform
# (compose_page) + the shared voice convention (compose_voice). author-wiring (this
# part) adds only the dispatch that chooses between it and the verbatim monolith path.
import composer  # noqa: E402 — sibling module, resolved via the sys.path insert above

# Templates ship alongside scripts/ at templates/<mode>.md.
_TEMPLATES_DIR = _SCRIPTS_DIR.parent / "templates"

# The six-section documentation layout has NO tutorials/ folder: a tutorial
# page folds into how-to/ (its `<!-- mode: tutorial -->` template hint is what
# makes check-wiki.py's resolve_mode still treat it as a tutorial there —
# mirrors migrate.py's already-reconciled _MODE_DIRS).
_MODE_TO_DIR = {
    "tutorial": "how-to",
    "how-to": "how-to",
    "reference": "reference",
    "explanation": "explanation",
}
_DEFAULT_FILENAME_STYLE = "CamelCase-With-Dashes"
_VALID_FILENAME_STYLES = {"CamelCase-With-Dashes", "snake_case", "kebab-case"}

# Files under templates/ that are NOT authorable page-types (docs, not pages). A
# page-type is valid iff templates/<page-type>.md exists and is not one of these —
# so the four monolith modes and the four manifest page-types are all valid, and a
# new page-type needs only a template, not an edit to a hardcoded enum
# (author-wiring 3/4 — template-driven validation replaces _VALID_MODES).
_TEMPLATE_NON_PAGES = frozenset({"README"})

# Why each recognized-but-deferred manifest page-type's placement is not wired this
# part — surfaced in the fail-closed NotImplementedError so the operator sees the
# specific reason, not just "not wired" (author-wiring 3/4 fail-closed edge (c)).
# component-overview is the one wired placement (wiki_init's universal component
# layout); these three each await their own slice (see the plan's Out of scope).
_DEFERRED_MANIFEST_REASONS = {
    "home": (
        "it collides with release-time Home.md ownership (wiki_init.render_home + "
        "the release flow own that file)"
    ),
    "section-index": (
        "its target is per-section under the live seven-section-taxonomy migration "
        "(a parallel track)"
    ),
    "plugin-home": (
        "its architecture/plugins/<Plugin>.md is a repo-specific layout, not "
        "wiki_init's universal component placement (wave-2 per its own template)"
    ),
}


def _resolve_wiki_root(arg_path: str | None) -> Path:
    """Resolve wiki root: arg → ./wiki → error."""
    if arg_path:
        return Path(arg_path).expanduser()
    candidate = Path.cwd() / "wiki"
    if candidate.is_dir():
        return candidate
    raise ValueError(
        "wiki root not found: pass --wiki-root or cd into a project with a wiki/ dir"
    )


def _apply_filename_style(slug: str, style: str) -> str:
    """Convert a slug to the chosen filename style. Returns base name (no extension)."""
    # Normalize input to lowercase words first.
    words = re.findall(r"[A-Za-z0-9]+", slug)
    if not words:
        return "Untitled"
    lower_words = [w.lower() for w in words]
    if style == "CamelCase-With-Dashes":
        return "-".join(w.capitalize() for w in lower_words)
    if style == "kebab-case":
        return "-".join(lower_words)
    if style == "snake_case":
        return "_".join(lower_words)
    raise ValueError(f"unknown filename style: {style}")


def _valid_page_types() -> list[str]:
    """The authorable page-types: every ``templates/<name>.md`` whose stem is not a
    doc (``README``). Template existence *is* the validity rule (author-wiring 3/4),
    so a new page-type needs only a template — no enum to edit. Covers the four
    monolith modes and the four manifest page-types uniformly."""
    return sorted(
        p.stem for p in _TEMPLATES_DIR.glob("*.md") if p.stem not in _TEMPLATE_NON_PAGES
    )


def _dispatch_content(
    template_text: str,
    *,
    section_names: list[str] | None = None,
    slug: str,
    resolved_style=None,  # style_resolver.ResolvedStyle | None — inject to pin voice
    wiki_root: Path | None = None,
    vault_path: Path | None = None,
    project_slug: str | None = None,
) -> str:
    """The compose-vs-verbatim dispatch — the one branch author-wiring adds.

    A manifest (``section_names`` non-empty) is assembled by
    ``composer.compose_page``; a monolith (no sections) emits today's verbatim
    template through ``composer.compose_voice`` — byte-identical to the legacy
    inline voice tail, since ``compose_voice`` mirrors it (parent Risk #2: one
    voice convention, not two parallel emit paths). ``section_names`` defaults to
    the manifest's own ``sections:`` list; ``resolved_style`` is the determinism
    seam, threaded straight through to the composer so an injected pin yields
    reproducible output."""
    if section_names is None:
        section_names = composer._parse_manifest_sections(template_text)
    if section_names:
        return composer.compose_page(
            template_text,
            title=slug,
            resolved_style=resolved_style,
            wiki_root=wiki_root,
            vault_path=vault_path,
            project_slug=project_slug,
        )
    return composer.compose_voice(
        template_text,
        resolved_style=resolved_style,
        wiki_root=wiki_root,
        vault_path=vault_path,
        project_slug=project_slug,
    )


def _voice_provenance(
    resolved_style,
    *,
    wiki_root: Path | None,
    vault_path: Path | None,
    project_slug: str | None,
) -> tuple[bool, list]:
    """Report ``(style_composed, style_scopes)`` for the operator summary.

    ``_dispatch_content`` routes voice through the composer, which returns the
    page but not whether a voice was applied or from which scopes — so the summary
    metadata is recovered here by mirroring the composer's resolve decision.
    Deterministic: an injected ``resolved_style`` is the same object the composer
    used; ``None`` re-resolves live, and ``resolve_style`` is a pure function of the
    same three scopes, so the verdict always matches what the composer emitted. Any
    failure degrades to ``(False, [])`` — the same never-fail-over-voice contract as
    ``compose_voice``."""
    try:
        resolved = resolved_style
        if resolved is None:
            import style_resolver  # type: ignore
            resolved = style_resolver.resolve_style(
                wiki_root=wiki_root,
                vault_path=vault_path,
                project_slug=project_slug,
            )
        if resolved.base_text.strip() or resolved.lessons:
            return True, list(resolved.provenance)
        return False, []
    except Exception:  # noqa: BLE001 — never fail authoring over the voice layer
        return False, []


def _manifest_target(
    mode: str,
    slug: str,
    *,
    wiki_root: Path,
    filename_style: str,
) -> Path:
    """Resolve the on-disk target for a manifest page-type.

    ``component-overview`` places at ``architecture/<kebab-slug>/<base>.md`` —
    grounded in wiki_init's universal component layout (the ``Component`` dataclass /
    ``architecture_items``, wiki_init.py:215, e.g. ``architecture/host-adapters/
    Host-Adapters.md``). The folder is always the kebab-cased slug (the component-dir
    convention); the basename follows the operator's ``filename_style`` (default
    ``CamelCase-With-Dashes``, which matches wiki_init's own basename casing). Both
    casings reuse author.py's own ``_apply_filename_style`` rather than importing
    wiki_init — the convention is small and already local, and it dodges the cross-dir
    import (parent Risk: dist/ import fragility).

    ``home`` / ``plugin-home`` / ``section-index`` are recognized-but-deferred: their
    placement is out of scope this part (``home`` collides with release-time
    ``Home.md`` ownership; ``section-index``'s target is per-section under the live
    seven-section-taxonomy migration; ``plugin-home``'s ``architecture/plugins/`` is a
    repo-specific layout, not wiki_init's universal component placement). They fail
    closed here rather than being misplaced, with the per-type reason named in the
    message (from ``_DEFERRED_MANIFEST_REASONS``)."""
    if mode == "component-overview":
        folder = _apply_filename_style(slug, "kebab-case")
        base = _apply_filename_style(slug, filename_style)
        return wiki_root / "architecture" / folder / f"{base}.md"
    reason = _DEFERRED_MANIFEST_REASONS.get(
        mode, "it is recognized but not wired this part — see the plan's Out of scope"
    )
    raise NotImplementedError(
        f"manifest placement for page-type {mode!r} is deferred in author-wiring: "
        f"{reason}. Only 'component-overview' placement is wired this part."
    )


def author_page(
    slug: str,
    mode: str,
    *,
    wiki_root: Path,
    filename_style: str = _DEFAULT_FILENAME_STYLE,
    overwrite: bool = False,
    vault_path: Path | None = None,
    project_slug: str | None = None,
    resolved_style=None,  # style_resolver.ResolvedStyle | None — inject to pin voice (proofs)
) -> dict:
    """Emit a page to its target under ``wiki_root`` — composed manifest or verbatim monolith.

    The page-type is valid iff ``templates/<mode>.md`` exists (template-driven
    validation — author-wiring 3/4, replacing the old ``_VALID_MODES`` enum). The
    loaded template's ``sections:`` frontmatter then selects the path: a manifest
    (sections present) is assembled by ``composer.compose_page``; a monolith (no
    sections) emits the template verbatim with the shared voice tail, byte-identical
    to before. Both converge on one write tail (the ``FileExistsError`` / ``overwrite``
    guard + ``write_bytes``).

    Manifest placement is wired for ``component-overview`` in Task 2; until then a
    recognized manifest page-type fails closed at target resolution
    (``_manifest_target``) rather than being misplaced.

    ``resolved_style`` is the determinism seam (inject a fixed ``ResolvedStyle`` to
    pin voice for reproducible proofs; ``None`` resolves live, as the CLI does).

    Returns: {action, target, mode, template, filename_style, filename,
    style_composed, style_scopes}.
    Raises ValueError (unknown page-type / filename style), FileNotFoundError
    (wiki root absent), FileExistsError (target exists + overwrite=False),
    NotImplementedError (a recognized manifest page-type whose placement is deferred).
    """
    if filename_style not in _VALID_FILENAME_STYLES:
        raise ValueError(
            f"filename style must be one of {sorted(_VALID_FILENAME_STYLES)}; got {filename_style!r}"
        )
    if not wiki_root.exists() or not wiki_root.is_dir():
        raise FileNotFoundError(f"wiki root not found: {wiki_root}")
    # Template-driven page-type validation: valid iff templates/<mode>.md exists
    # and is not a doc (README). Replaces the _VALID_MODES enum so a new page-type
    # needs only a template (author-wiring 3/4).
    template_path = _TEMPLATES_DIR / f"{mode}.md"
    if mode in _TEMPLATE_NON_PAGES or not template_path.exists():
        raise ValueError(
            f"unknown page-type {mode!r}; valid page-types: {', '.join(_valid_page_types())}"
        )
    template_text = template_path.read_text(encoding="utf-8")
    section_names = composer._parse_manifest_sections(template_text)
    base = _apply_filename_style(slug, filename_style)
    # Target resolution forks by page-shape: a manifest places by its own rule
    # (the Task-2 seam — fails closed until wired); a monolith uses the Diátaxis
    # mode→dir map, exactly as before.
    if section_names:
        target = _manifest_target(mode, slug, wiki_root=wiki_root, filename_style=filename_style)
    else:
        target = wiki_root / _MODE_TO_DIR[mode] / f"{base}.md"
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"target already exists: {target}; pick a different slug or pass --overwrite"
        )
    # Content dispatch: manifest → compose_page, monolith → verbatim + the shared
    # voice tail. The voice provenance (operator summary) mirrors the composer's
    # resolve decision — see _voice_provenance.
    try:
        content = _dispatch_content(
            template_text,
            section_names=section_names,
            slug=slug,
            resolved_style=resolved_style,
            wiki_root=wiki_root,
            vault_path=vault_path,
            project_slug=project_slug,
        )
    except FileNotFoundError as e:
        # A manifest named a section with no library file. Fail closed naming the
        # manifest (page-type) + the missing section — propagated from compose_page's
        # loader, never swallowed into a partial page (author-wiring 3/4 edge (b)).
        # Only the manifest path loads sections, so a FileNotFoundError here is always
        # a missing section, not the (already-read) template.
        missing = Path(e.filename).stem if e.filename else "?"
        raise FileNotFoundError(
            f"page-type {mode!r} manifest names section {missing!r}, but its library "
            f"file does not exist: {e.filename}"
        ) from e
    style_composed, style_scopes = _voice_provenance(
        resolved_style,
        wiki_root=wiki_root,
        vault_path=vault_path,
        project_slug=project_slug,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    # write_bytes for LF-only line endings (Windows portability — same
    # pattern as save.py / ideas_surface.py / adapt_skills.py).
    target.write_bytes(content.encode("utf-8"))
    return {
        "action": "authored",
        "target": str(target),
        "mode": mode,
        "template": str(template_path),
        "filename_style": filename_style,
        "filename": target.name,
        "style_composed": style_composed,
        "style_scopes": style_scopes,
    }


def _resolve_filename_style(arg_style: str | None, wiki_root: Path) -> str:
    """Filename style resolution: explicit arg → AgentMemory conventions → default."""
    if arg_style:
        return arg_style
    # Try AgentMemory conventions (per-repo wiki overrides; then vault entries).
    try:
        import agentmemory_conventions  # type: ignore
        conv = agentmemory_conventions.load_conventions(wiki_root=wiki_root)
        style = conv.get("filename_style", _DEFAULT_FILENAME_STYLE)
        if style in _VALID_FILENAME_STYLES:
            return style
    except Exception:
        pass
    return _DEFAULT_FILENAME_STYLE


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="diataxis-author",
        description=(
            "Emit a pre-filled Diátaxis template skeleton to <wiki-root>/<mode>/"
            "<filename>.md. Operator picks mode + filename style; skill loads "
            "the template + writes the skeleton; operator edits in their editor. "
            "Skill doesn't write further content after the skeleton."
        ),
    )
    parser.add_argument("slug", help="page slug (e.g. 'Install foo into a project')")
    parser.add_argument(
        "--mode", choices=_valid_page_types(), default=None,
        help="page-type to author: the four Diátaxis monoliths plus the manifest "
             "page-types (validity is template existence). Default: prompt or infer "
             "from --intent via classify.py (the classifier infers monoliths only).",
    )
    parser.add_argument(
        "--intent", default=None,
        help="one-sentence intent statement for classify.py to derive mode "
             "(used when --mode not provided)",
    )
    parser.add_argument(
        "--filename-style", default=None,
        choices=sorted(_VALID_FILENAME_STYLES),
        help=f"filename style (default: AgentMemory conventions → {_DEFAULT_FILENAME_STYLE})",
    )
    parser.add_argument(
        "--wiki-root", default=None,
        help="wiki root path (default: ./wiki)",
    )
    parser.add_argument(
        "--vault-path", default=None,
        help="AgentMemory vault path for the voice overlay "
             "(default: MEMORY_VAULT_PATH env; absent → committed base floor only)",
    )
    parser.add_argument(
        "--project-slug", default=None,
        help="project slug for the per-project voice scope "
             "(projects/<slug>/wiki-style/; absent → skip the per-project scope)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="overwrite existing target (default: refuse + ask operator to pick a different slug)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    try:
        wiki_root = _resolve_wiki_root(args.wiki_root)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    # Mode resolution: --mode > --intent (classify) > stdin prompt.
    mode = args.mode
    if not mode and args.intent:
        # Treat the intent string as a classification input; build a
        # minimal "page" with the intent as body and classify.
        import classify  # type: ignore
        c = classify.classify_text(args.intent)
        mode = c.mode
        # If the classifier thinks it's ambiguous, prompt operator.
        if c.needs_subagent:
            print(
                f"INFO: intent '{args.intent}' classified as {c.mode} with confidence "
                f"{c.confidence}; rationale: {c.rationale}",
                file=sys.stderr,
            )
            print(
                "Confidence below threshold; specify --mode explicitly to disambiguate.",
                file=sys.stderr,
            )
            return 1
    if not mode:
        print(
            "ERROR: --mode or --intent required (cannot infer Diátaxis mode without input)",
            file=sys.stderr,
        )
        return 1
    # Resolve filename style via AgentMemory conventions fallback if not
    # explicitly passed.
    resolved_style = _resolve_filename_style(args.filename_style, wiki_root)
    # Resolve the vault for the voice overlay: explicit --vault-path, else
    # MEMORY_VAULT_PATH env (absent → committed base floor only).
    if args.vault_path:
        vault_path = Path(args.vault_path).expanduser()
    else:
        try:
            import agentmemory_conventions  # type: ignore
            vault_path = agentmemory_conventions._resolve_vault_path()
        except Exception:
            vault_path = None
    try:
        result = author_page(
            slug=args.slug,
            mode=mode,
            wiki_root=wiki_root,
            filename_style=resolved_style,
            overwrite=args.overwrite,
            vault_path=vault_path,
            project_slug=args.project_slug,
        )
    except (FileNotFoundError, FileExistsError, ValueError, NotImplementedError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
