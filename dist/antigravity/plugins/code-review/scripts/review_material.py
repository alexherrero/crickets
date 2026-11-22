#!/usr/bin/env python3
"""review_material.py — assemble what a reviewer is shown: ARTIFACT, CONTRACT, RULES.

    review_material.py [--range A..B | --worktree | --pr N | --files PATH...]
                       [--contract TEXT | --contract-file FILE]
                       [--anchor FILE] [--repo-root DIR] [--tier TIER]
                       [--max-rule-lines N] [--max-bytes N]

Prints one text to stdout, ready to pipe into cross-review.sh (or to hand an
in-process reviewer):

    === ARTIFACT ===     the change: a git range, the working tree, a PR diff,
                         or a list of files (an asset is named with its size)
    === CONTRACT ===     what the change was meant to do, as the caller states it
    === RULES ===        the rules it has to follow, one per line

The reviewer sees the thing, what it was for, and the rules it is held to. It
never sees the author's reasoning, and it is never told what bug to look for:
`RULES` states rules, and nothing here takes a suspicion as input.

Where the rules come from, in this order, until the line cap or the byte
ceiling runs out:
    1. the anchor's own rules: a spec's Rules (each with its source), else the
       `Locked design calls` and `Constraints` sections of a plan or design,
       then a `Likeness list` if there is one. These are always taken first.
    2. paragraphs of the repo's AGENTS.md and CLAUDE.md that share the most
       terms with the changed paths and identifiers (rarer terms count more),
       best first. Deterministic: the same inputs give the same RULES.

No anchor given, or the file is missing, gives an empty RULES that says why. It
is not an error: a review of a bare diff is still worth running.

The byte ceiling is the tier's (`--tier`, as cross-review.sh): the whole text
stays under it where the artifact and contract leave room. When they do not,
RULES is cut to what fits, and a note on stderr says the artifact alone is over.

No agentm, no vault, no network. Standard library only; git and gh when asked
for a range or a PR.

Exit codes: 0 text printed; 2 usage error or an input that cannot be read.
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# Material ceilings per cross-review.sh tier. test_review_material.py pins these
# to the table in cross-review.sh so the two cannot drift.
TIER_CEILINGS: Dict[str, int] = {"default": 50000, "high": 80000, "wording": 50000}

DEFAULT_MAX_RULE_LINES = 40
RULE_LINE_CHARS = 300
MIN_TERM_LEN = 3

# Words that say nothing about which rule applies.
_STOP = frozenset("""
the and for with that this from into over under when then than are was were not but
you your can will has have had its they them their there here what which who how why
all any each every some one two three use used using via per out off new old get set
self cls none true false return import def class elif else try except finally pass
raise yield lambda while break continue global print len str int list dict tuple
file files path paths line lines text name names type types data value values item
items test tests code src dist tmp
""".split())

_HEADING = re.compile(r"^(#{1,6})\s+(?P<name>.+?)\s*$")
_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(?P<text>.*\S)\s*$")
_ANCHOR_SECTIONS = ("locked design calls", "constraints", "likeness list")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]+")
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


def _load_sibling(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_review_material_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    # Registered before it runs: a dataclass looks its own module up by name.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------- terms

def _split_identifier(word: str) -> List[str]:
    """`FormatTrailer` / `format_trailer` / `format-trailer` -> format, trailer."""
    out: List[str] = []
    for piece in re.split(r"[_\-.]", word):
        out.extend(p.lower() for p in _CAMEL.findall(piece))
    return out


def terms_from(paths: Sequence[str], diff_text: str) -> List[str]:
    """The distinct terms that say what a change touches: words of its paths and
    of the identifiers on its added and removed lines. Sorted, so deterministic."""
    found = set()
    for p in paths:
        for part in re.split(r"[/\\]", p):
            for w in _split_identifier(part):
                found.add(w)
    for line in diff_text.splitlines():
        if line.startswith(("+++", "---")) or not line.startswith(("+", "-")):
            continue
        for w in _WORD.findall(line[1:]):
            for t in _split_identifier(w):
                found.add(t)
    return sorted(t for t in found if len(t) >= MIN_TERM_LEN and t not in _STOP and not t.isdigit())


def changed_paths(diff_text: str) -> List[str]:
    """The files a unified diff touches, in order of first appearance."""
    seen: List[str] = []
    for m in re.finditer(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)$", diff_text, re.MULTILINE):
        for p in (m.group("b"),):
            if p not in seen:
                seen.append(p)
    return seen


# ------------------------------------------------------------- anchor rules

def _clean(text: str) -> str:
    text = re.sub(r"\*\*|__|`", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _line(text: str, source: str) -> str:
    text = _clean(text)
    suffix = f" (source: {source})" if source else ""
    room = RULE_LINE_CHARS - len(suffix)
    if len(text) > room:
        text = text[: max(room - 1, 1)].rstrip() + "…"
    return f"- {text}{suffix}"


def _section_bullets(text: str, names: Sequence[str]) -> List[Tuple[str, str]]:
    """(section, bullet) for each bullet under a heading whose name starts with
    one of `names`. A wrapped bullet is one item."""
    out: List[Tuple[str, str]] = []
    section: Optional[str] = None
    current: Optional[List[str]] = None
    for raw in text.splitlines():
        h = _HEADING.match(raw)
        if h:
            if current is not None and section:
                out.append((section, " ".join(current)))
            current = None
            name = h.group("name").strip().lower()
            section = next((n for n in names if name.startswith(n)), None)
            continue
        if section is None:
            continue
        b = _BULLET.match(raw)
        if b:
            if current is not None:
                out.append((section, " ".join(current)))
            current = [b.group("text").strip()]
        elif raw.strip() and current is not None and raw.startswith((" ", "\t")):
            current.append(raw.strip())
        elif not raw.strip() and current is not None:
            out.append((section, " ".join(current)))
            current = None
    if current is not None and section:
        out.append((section, " ".join(current)))
    return out


def anchor_rules(anchor_text: str, anchor_name: str) -> List[str]:
    """RULES lines from an anchor, in order: a spec's Rules (with their sources),
    else Locked design calls then Constraints, then any Likeness list."""
    lines: List[str] = []
    is_spec = bool(re.search(r"^##\s+Done when\b", anchor_text, re.MULTILINE))
    if is_spec:
        spec = _load_sibling("spec_doc").parse(anchor_text)
        for r in spec.rules or []:
            lines.append(_line(r.text, r.source or anchor_name))
        names: Sequence[str] = ("likeness list",)
    else:
        names = _ANCHOR_SECTIONS
    found = _section_bullets(anchor_text, names)
    # Keep the anchor's own order of kinds: locked calls, constraints, likeness.
    for wanted in names:
        for section, bullet in found:
            if section == wanted:
                lines.append(_line(bullet, anchor_name))
    return lines


# ---------------------------------------------------------- repo-doc rules

def doc_paragraphs(repo_root: Path) -> List[Tuple[str, str]]:
    """(file, paragraph) for AGENTS.md and CLAUDE.md, in file then page order.
    Headings, import lines (`@AGENTS.md`), fences and one-word bits are skipped."""
    out: List[Tuple[str, str]] = []
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = repo_root / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        for block in re.split(r"\n\s*\n", text):
            lines = [l for l in block.splitlines()
                     if l.strip() and not l.lstrip().startswith(("#", "@", "|", ">", "<!--"))]
            para = _clean(" ".join(l.strip() for l in lines))
            if len(para) >= 40:
                out.append((name, para))
    return out


def rank_doc_rules(paragraphs: Sequence[Tuple[str, str]], terms: Sequence[str]) -> List[Tuple[float, str, str]]:
    """Paragraphs that share terms with the change, best first. A term found in
    few paragraphs counts for more than one found in many (an idf weight), so
    `commit` outweighs `the`. Ties break on file then page order."""
    if not terms or not paragraphs:
        return []
    bags = []
    for _name, para in paragraphs:
        bag = set()
        for w in _WORD.findall(para):
            bag.update(_split_identifier(w))
        bags.append(bag)
    n = len(paragraphs)
    df = {t: sum(1 for b in bags if t in b) for t in terms}
    scored = []
    for i, ((name, para), bag) in enumerate(zip(paragraphs, bags)):
        score = sum(math.log(1 + n / df[t]) for t in terms if t in bag and df[t])
        if score > 0:
            scored.append((-score, i, name, para))
    scored.sort()
    return [(-s, name, para) for s, _i, name, para in scored]


# ------------------------------------------------------------- the artifact

def _run(argv: Sequence[str], cwd: Optional[Path]) -> str:
    proc = subprocess.run(list(argv), cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise ValueError(f"`{' '.join(argv)}` failed (exit {proc.returncode}): {proc.stderr.strip()[:300]}")
    return proc.stdout


def artifact_from_range(rng: str, repo_root: Path) -> str:
    return _run(["git", "diff", "--no-color", rng], repo_root)


def artifact_from_worktree(repo_root: Path) -> str:
    return _run(["git", "diff", "--no-color", "HEAD"], repo_root)


def artifact_from_pr(number: str, repo_root: Path) -> str:
    return _run(["gh", "pr", "diff", number, "--color", "never"], repo_root)


_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".wav", ".mp3", ".ogg", ".flac",
                    ".ico", ".pdf", ".zip", ".ttf", ".otf", ".woff", ".woff2"}


def artifact_from_files(files: Sequence[str], repo_root: Path) -> Tuple[str, List[str]]:
    """File contents under `--- path ---` headers; an asset is named with its size."""
    parts: List[str] = []
    paths: List[str] = []
    for f in files:
        p = Path(f)
        full = p if p.is_absolute() else repo_root / p
        if not full.is_file():
            raise ValueError(f"file not found: {f}")
        paths.append(f)
        data = full.read_bytes()
        if full.suffix.lower() in _BINARY_SUFFIXES or b"\0" in data[:2048]:
            parts.append(f"--- {f} ---\n(binary asset, {len(data)} bytes; not shown)")
        else:
            parts.append(f"--- {f} ---\n{data.decode('utf-8', errors='replace').rstrip()}")
    return "\n\n".join(parts), paths


# ------------------------------------------------------------------ assemble

def assemble(artifact: str, contract: str, rule_lines: Sequence[str], reason: str = "") -> str:
    rules = "\n".join(rule_lines) if rule_lines else f"(none — {reason or 'no rules found'})"
    return (f"=== ARTIFACT ===\n{artifact.rstrip()}\n\n"
            f"=== CONTRACT ===\n{contract.strip() or '(none given)'}\n\n"
            f"=== RULES ===\n{rules}\n")


def build(*, artifact: str, paths: Sequence[str], contract: str = "",
          anchor_path: Optional[Path] = None, repo_root: Path = Path("."),
          max_rule_lines: int = DEFAULT_MAX_RULE_LINES, ceiling: int = TIER_CEILINGS["default"],
          diff_text: Optional[str] = None) -> Tuple[str, List[str]]:
    """The finished text and any notes for stderr. Nothing here takes the author's
    reasoning or a suspected defect; rules come from the anchor and the repo docs."""
    notes: List[str] = []
    candidates: List[str] = []
    reason = ""
    if anchor_path is None:
        reason = "no anchor was given, so there is nothing to hold the change to"
    elif not anchor_path.is_file():
        reason = f"the anchor {anchor_path} was not found"
    else:
        text = anchor_path.read_text(encoding="utf-8", errors="replace")
        candidates.extend(anchor_rules(text, anchor_path.name))
        terms = terms_from(paths, diff_text if diff_text is not None else artifact)
        for _score, name, para in rank_doc_rules(doc_paragraphs(repo_root), terms):
            candidates.append(_line(para, name))
        if not candidates:
            reason = f"the anchor {anchor_path.name} states no rules and no repo doc paragraph matches the change"

    base = len(assemble(artifact, contract, [], reason or "x").encode("utf-8"))
    budget = ceiling - base if ceiling > 0 else None
    if budget is not None and budget < 0:
        notes.append(f"review_material: the artifact and contract alone are {base} bytes, over the "
                     f"{ceiling}-byte ceiling; RULES is empty and cross-review.sh will degrade. "
                     "Review the change in parts.")
        return assemble(artifact, contract, [], "no room under the byte ceiling"), notes

    chosen: List[str] = []
    used = 0
    for cand in candidates:
        if len(chosen) >= max_rule_lines:
            notes.append(f"review_material: {len(candidates) - len(chosen)} rule line(s) dropped at the "
                         f"{max_rule_lines}-line cap")
            break
        size = len(cand.encode("utf-8")) + 1
        if budget is not None and used + size > budget:
            notes.append(f"review_material: {len(candidates) - len(chosen)} rule line(s) dropped to stay "
                         f"under the {ceiling}-byte ceiling")
            break
        chosen.append(cand)
        used += size
    return assemble(artifact, contract, chosen, reason), notes


# ----------------------------------------------------------------------- CLI

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="review_material.py", description=__doc__.splitlines()[0])
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--range", help="a git range, e.g. main..HEAD")
    src.add_argument("--worktree", action="store_true", help="the working tree against HEAD")
    src.add_argument("--pr", help="a pull request number (gh pr diff)")
    src.add_argument("--files", nargs="+", help="files or assets to review as they are")
    c = p.add_mutually_exclusive_group()
    c.add_argument("--contract", help="what the change was meant to do")
    c.add_argument("--contract-file", help="a file holding that text")
    p.add_argument("--anchor", help="the spec, plan or design the change is held to")
    p.add_argument("--repo-root", default=".", help="the repo (default: the current directory)")
    p.add_argument("--tier", default="default", choices=sorted(TIER_CEILINGS))
    p.add_argument("--max-rule-lines", type=int, default=DEFAULT_MAX_RULE_LINES)
    p.add_argument("--max-bytes", type=int, help="override the tier's byte ceiling (0 = no limit)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.repo_root)
    try:
        if args.range:
            artifact = artifact_from_range(args.range, root)
        elif args.worktree:
            artifact = artifact_from_worktree(root)
        elif args.pr:
            artifact = artifact_from_pr(args.pr, root)
        else:
            artifact, _ = artifact_from_files(args.files, root)
        paths = changed_paths(artifact) if not args.files else list(args.files)
        # A file list has no +/- lines; read its content as all-added so the
        # identifiers in it count toward the repo-doc match.
        diff_text = "\n".join("+" + l for l in artifact.splitlines()) if args.files else artifact
        contract = args.contract or ""
        if args.contract_file:
            contract = Path(args.contract_file).read_text(encoding="utf-8")
        ceiling = TIER_CEILINGS[args.tier] if args.max_bytes is None else args.max_bytes
        text, notes = build(artifact=artifact, paths=paths, contract=contract,
                            anchor_path=Path(args.anchor) if args.anchor else None,
                            repo_root=root, max_rule_lines=args.max_rule_lines, ceiling=ceiling,
                            diff_text=diff_text)
    except (OSError, ValueError) as exc:
        print(f"review_material: {exc}", file=sys.stderr)
        return 2
    for n in notes:
        print(n, file=sys.stderr)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
