#!/usr/bin/env python3
"""Section-structure checking for `/design`'s multiple rungs (crickets
wave-c-design-and-conventions, tasks 1-2).

A doc authored through a template should carry that template's H2 section
set -- this is the deterministic half of "authoring through the template
produces a doc matching the shape-spec's section structure" (task 2's own
verification wording). Reuses design_doc.py's comment/fence masking so a
heading inside a code fence or an HTML comment doesn't fool the scan --
the exact same correctness concern that module's own Detailed-Design gate
already solved.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import design_doc  # noqa: E402

_H2_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def extract_h2_sections(path: str | Path) -> list:
    """The doc's top-level (`##`) section titles, in order, comment-/fence-
    masked so a heading inside a fenced code block or an HTML comment isn't
    counted (mirrors design_doc.py's own `_mask_noncontent`)."""
    text = Path(path).read_text(encoding="utf-8")
    masked = design_doc._mask_noncontent(text)
    return _H2_RE.findall(masked)


def matches_template_sections(doc_path: str | Path, template_path: str | Path) -> dict:
    """Whether `doc_path`'s H2 section set matches `template_path`'s.

    Returns {"missing": [...], "extra": [...], "matches": bool}. `missing`
    is a template section absent from the doc; `extra` is a doc section not
    named by the template (not necessarily wrong -- authors may add a
    section -- but worth surfacing). `matches` is true iff `missing` is
    empty (an authored doc may add sections; it may not drop a required
    one)."""
    doc_sections = extract_h2_sections(doc_path)
    template_sections = extract_h2_sections(template_path)
    missing = [s for s in template_sections if s not in doc_sections]
    extra = [s for s in doc_sections if s not in template_sections]
    return {"missing": missing, "extra": extra, "matches": not missing}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check a design doc's section set against its template")
    parser.add_argument("doc_path")
    parser.add_argument("template_path")
    args = parser.parse_args(argv)
    result = matches_template_sections(args.doc_path, args.template_path)
    if not result["matches"]:
        sys.stderr.write(f"[design_template] missing required section(s): {result['missing']!r}\n")
        return 2
    print(f"[design_template] OK -- {args.doc_path} matches {args.template_path}'s section set")
    if result["extra"]:
        print(f"[design_template] note: doc adds section(s) not in the template: {result['extra']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
