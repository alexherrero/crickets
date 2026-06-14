#!/usr/bin/env python3
"""Design-doc gates + storage resolution for the `/design` command (V5-10 sibling #5).

The `/design` command (`commands/design.md`) is a thin interactive prompt; the
deterministic, falsifiable pieces live here so they can be unit-tested — the
crickets idiom (cf. `resolve_plan.py` / `stage_plan.py`), a deliberate divergence
from agentm's no-Bash `Read/Write/Edit/Glob/Grep`-only skill.

Two responsibilities, both stdlib-only:

    design_doc.py gate <path>                       # the Status:final hard gate
    design_doc.py detailed-design <path>            # translate's non-empty-DD gate
    design_doc.py harness-root [--project-root <p>] # where confidential designs live

**The `final` hard gate (`require_final`).** `/design translate` and `/design
sequence` only run on a human-approved (`Status: final`) design. This is the
contract that makes the rest of the pipeline trustworthy: it preserves the
human-approval signal. The gate is *verb-neutral* (both downstream verbs call it)
and **never auto-repairs** — a malformed or non-final doc halts loudly, pointing
the operator back to `/design author`. Each non-final state gets its own message
(faithful port of agentm `harness/skills/design/SKILL.md`'s refusal contract).

**Storage resolution (`resolve_harness_root`).** Confidential designs live at
`<harness>/designs/<slug>.md` — the resolver-resolved harness root (the vault
`_harness/` in the dogfood), **never a hardcoded `.harness/`**. We compose
`resolve_plan.resolve` (the one owner of precedence / vault redirection / the
dangling-marker loud-error): resolve the singleton pair, take the parent of the
resolved `PLAN.md`. Published designs live at `wiki/designs/<slug>.md` (committed)
— a plain repo-relative path, no resolver needed.

**Frontmatter parsing is minimal + stdlib-only.** No PyYAML (it is repo-CI-only,
not on the plugin runtime — same constraint as `resolve_plan.py`). A regex lifts
the leading `---`-delimited block; only top-level `key: value` scalars are read,
which is all the gate needs (`status:`). Anything richer is ignored, not guessed.

Exit codes (aligned with the sibling helpers so the surface is transparent):
    0 — ok; `gate` → doc is final; `harness-root` → root on stdout.
    1 — graceful-skip propagated from the resolver (agentm present, no `_harness/`).
    2 — loud: non-final / malformed / missing doc, or a resolver refusal.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# One owner of active-pair resolution (precedence, vault redirect, slug-safety,
# the dangling-marker loud-error): the sibling bridge. Reuse its `_AUTO` sentinel
# verbatim so `resolver=` passes through transparently — tests inject `resolver=None`
# to force the `.harness/` fallback, or a stub Path to force the delegate branch.
import resolve_plan  # noqa: E402

_AUTO = resolve_plan._AUTO

# The design-doc lifecycle. Only `/design author` advances it (draft → review →
# final); the harness `/release` flow sets `launched`. translate + sequence gate
# on `final`.
STATUS_VALUES = ("draft", "review", "final", "launched")

# Confidential designs sit under `<harness>/designs/`; published under `wiki/designs/`
# (the crickets path — NOT agentm's `wiki/explanation/designs/`). Subdir name shared.
_DESIGNS_DIR = "designs"
_PUBLISHED_BASE = ("wiki", "designs")

# Leading `---\n … \n---` block. DOTALL so the body spans lines; non-greedy so it
# stops at the first closing fence.
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)


# ── frontmatter (minimal, stdlib-only) ─────────────────────────────────────────

def parse_frontmatter(text: str) -> dict | None:
    """The leading YAML frontmatter block as a flat dict of top-level scalars.

    Returns None when there is no `---`-delimited leading block at all (so the
    caller can distinguish "not a design doc / malformed" from "present but no
    status"). Only un-indented `key: value` lines are read; comments (`#…`),
    blank lines, and nested/structured values are skipped — the gate needs only
    `status:`, and guessing at richer YAML would be a lie, not a parse.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm: dict = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):  # nested under a parent key — not top-level
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key:
            fm[key] = val
    return fm


def read_status(path: str | os.PathLike) -> tuple[str | None, str | None]:
    """(status, error): the doc's `status:` value, or (None, reason) on failure.

    `error` is set (and status None) when the file is missing, has no frontmatter
    block, or has no `status:` key — the three "can't even tell" cases the gate
    must refuse rather than guess through.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (None, f"no design doc at {p}")
    except OSError as exc:
        return (None, f"cannot read {p}: {exc}")
    fm = parse_frontmatter(text)
    if fm is None:
        return (None, f"{p}: no YAML frontmatter found — not a design doc (or malformed). "
                      f"Not auto-repairing.")
    status = fm.get("status")
    if not status:
        return (None, f"{p}: no 'status:' field in frontmatter; cannot verify the doc is "
                      f"final. Not auto-repairing.")
    return (status, None)


# ── the final hard gate ────────────────────────────────────────────────────────

def require_final(path: str | os.PathLike) -> tuple[bool, str]:
    """(ok, reason): True iff the doc at `path` is `Status: final`.

    The shared gate behind `/design translate` and `/design sequence`. On a
    non-final / malformed / missing doc returns (False, <state-specific message>)
    and writes nothing — never auto-repairs. `reason` is "" on success. The
    messages mirror agentm's refusal contract, kept verb-neutral (both downstream
    verbs call this) and pointing back to `/design author <slug>`.
    """
    slug = Path(path).stem
    status, err = read_status(path)
    if err is not None:
        return (False, err)
    if status == "final":
        return (True, "")
    if status == "draft":
        return (False, f"Status is 'draft', not 'final'. Run /design author {slug} to "
                       f"complete authoring + the review pass first, then re-run.")
    if status == "review":
        return (False, f"Status is 'review', not 'final'. The review pass is incomplete. "
                       f"Run /design author {slug} to walk approve/revise/skip and finalize.")
    if status == "launched":
        return (False, f"Status is 'launched'. The design's parts have already been "
                       f"generated and executed; re-running would orphan the existing "
                       f"parts/. Edit the parent and manually revert Status to 'final' "
                       f"only if you truly need to re-run.")
    return (False, f"Status is {status!r}, not a recognized lifecycle state "
                   f"({'|'.join(STATUS_VALUES)}). Not auto-repairing.")


# ── the Detailed-Design non-empty gate (translate's second precondition) ─────────

# The `### Detailed Design` subsection drives translate's part-split heuristic
# (one part per top-level subsection by default), so it must carry real content
# — not just the template's italic prompt + HTML-comment scaffold.
_DETAILED_DESIGN_RE = re.compile(r"^#{3}[ \t]+Detailed Design[ \t]*$", re.MULTILINE)
# h1–h3 ends the section; `####` subsections are body (the split unit), not bounds.
_HEADING_RE = re.compile(r"^#{1,3}[ \t]+\S", re.MULTILINE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _blank_keep_newlines(s: str) -> str:
    """Replace every non-newline char with a space — masks a region while keeping
    its length + line offsets, so positions found in the masked text map 1:1 onto
    the original."""
    return re.sub(r"[^\n]", " ", s)


def _mask_noncontent(text: str) -> str:
    """A same-length copy of `text` with fenced code blocks and HTML comments
    blanked out (newlines preserved).

    Heading detection (`### Detailed Design` and the next-heading boundary) is a
    line-regex; without this, a heading *inside* a ```` ``` ```` fence reads as a
    real section, and a `##` line *inside* an HTML comment reads as the next
    heading (truncating the body). Masking these non-content regions first — then
    slicing the body from the ORIGINAL text by the masked offsets — fixes both
    while leaving the residue check (which re-strips comments) untouched.
    """
    # Comments first (DOTALL, may span lines), so a ``` or `##` inside a comment
    # can't toggle a fence or pose as a heading.
    masked = _COMMENT_RE.sub(lambda m: _blank_keep_newlines(m.group(0)), text)
    out, in_fence = [], False
    for line in masked.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(_blank_keep_newlines(line))
        elif in_fence:
            out.append(_blank_keep_newlines(line))
        else:
            out.append(line)
    return "".join(out)


def _detailed_design_body(text: str) -> str | None:
    """The raw body under `### Detailed Design`, or None if the heading is absent.

    Runs from just after the heading to the next h1–h3 heading, so `####`
    subsections (the split unit) count as body rather than as boundaries. The
    heading + boundary are located in a comment-/fence-masked copy (so a heading
    inside a code fence or a `##` inside a comment can't fool the scan), but the
    body is sliced from the original text so the residue check sees real content.
    """
    masked = _mask_noncontent(text)
    m = _DETAILED_DESIGN_RE.search(masked)
    if not m:
        return None
    start = m.end()
    nxt = _HEADING_RE.search(masked, start)
    return text[start:nxt.start()] if nxt else text[start:]


def detailed_design_nonempty(path: str | os.PathLike) -> tuple[bool, str]:
    """(ok, reason): True iff `### Detailed Design` has substantive content.

    translate's second hard gate, after `require_final`. "Substantive" = after
    stripping the template scaffold (HTML comment blocks, whole-line italic
    prompts `*…*`, and blank lines), something remains — prose, or a `####`
    subsection heading the split heuristic can hang a part on. A scaffold-only
    section halts translate (the design is too sparse to split); never
    auto-repairs. Mirrors agentm's "Detailed Design has no content" refusal.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (False, f"no design doc at {p}")
    except OSError as exc:
        return (False, f"cannot read {p}: {exc}")
    body = _detailed_design_body(text)
    if body is None:
        return (False, f"{p}: no '### Detailed Design' section found; cannot translate a "
                       f"design without one. Not auto-repairing.")
    residue = []
    for line in _COMMENT_RE.sub("", body).splitlines():
        s = line.strip()
        if not s:
            continue
        # Skip a whole-line italic prompt (template scaffold), but keep **bold**
        # and `* bullet` lines — those are real authored content.
        if len(s) >= 2 and s.startswith("*") and s.endswith("*") and not s.startswith("**"):
            continue
        residue.append(s)
    if not residue:
        return (False, f"{p}: Detailed Design has no content; design too sparse to "
                       f"translate. Author at least one Detailed Design subsection "
                       f"before re-running.")
    return (True, "")


# ── storage resolution ─────────────────────────────────────────────────────────

def resolve_harness_root(root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Resolve the harness root (the dir holding the active `PLAN.md`).

    Composed onto `resolve_plan.resolve` — we resolve the *singleton* pair and
    take the parent of the resolved `PLAN.md`. This tracks the vault redirect (in
    the dogfood the root is the vault `_harness/`, not a repo `.harness/`)
    automatically; we never re-derive it. Returns (0, root, "") on success, else
    the resolver's non-zero exit + stderr verbatim (Risk #7 — no silent fallback).
    """
    rc, out, err = resolve_plan.resolve("", root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    plan_path = out.split("\t", 1)[0].strip()
    return (0, f"{Path(plan_path).parent}\n", "")


def confidential_design_path(slug: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """The confidential design path `<harness>/designs/<slug>.md`.

    Thin compose over `resolve_harness_root`; surfaces the resolver's exit/stderr
    unchanged on failure.
    """
    rc, harness, err = resolve_harness_root(root, resolver=resolver)
    if rc != 0:
        return (rc, "", err)
    p = Path(harness.strip()) / _DESIGNS_DIR / f"{slug}.md"
    return (0, f"{p}\n", "")


def published_design_path(slug: str, root: str) -> str:
    """The published design path `<root>/wiki/designs/<slug>.md` (committed).

    No resolver — published designs are plain repo-relative files. The crickets
    path, NOT agentm's `wiki/explanation/designs/`.
    """
    return str(Path(root).joinpath(*_PUBLISHED_BASE) / f"{slug}.md")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="design_doc.py",
        description="Design-doc final-gate + harness-root resolution for /design.",
    )
    sub = p.add_subparsers(dest="mode", required=True)

    g = sub.add_parser("gate", help="exit 0 iff the design doc is Status: final, else 2 + reason")
    g.add_argument("path", help="path to the design doc")

    d = sub.add_parser(
        "detailed-design",
        help="exit 0 iff the doc's '### Detailed Design' section is non-empty, else 2 + reason",
    )
    d.add_argument("path", help="path to the design doc")

    h = sub.add_parser("harness-root", help="print the resolved harness root (holds PLAN.md)")
    h.add_argument("--project-root", default=None, help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    if ns.mode == "gate":
        ok, reason = require_final(ns.path)
        if ok:
            return 0
        sys.stderr.write(f"[design_doc] {reason}\n")
        return 2
    if ns.mode == "detailed-design":
        ok, reason = detailed_design_nonempty(ns.path)
        if ok:
            return 0
        sys.stderr.write(f"[design_doc] {reason}\n")
        return 2
    # harness-root
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    rc, out, err = resolve_harness_root(root)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
