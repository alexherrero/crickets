#!/usr/bin/env python3
"""review_material.py — assemble what a reviewer is shown: ARTIFACT, CONTRACT, RULES.

    review_material.py [--range A..B | --worktree | --pr N | --files PATH...]
                       [--contract TEXT | --contract-file FILE]
                       [--anchor FILE] [--design FILE]... [--repo-root DIR] [--tier TIER]
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
    2. the `Locked design calls` of each design that governs the change: a page
       in the repo's `wiki/designs/` whose `governs:` names a changed path (status
       `final`, `launched` or `active`), most specific first, then any design
       named with `--design` (a note kept outside the repo, such as a vault one).
    3. paragraphs that share the most terms with the changed paths and
       identifiers (rarer terms count more), best first: from the repo's AGENTS.md
       and CLAUDE.md, and from the `Design` section of each of those designs.
       Deterministic: the same inputs give the same RULES.

A diff (range, working tree or PR) leaves out the files the repo marks generated
with `linguist-generated` in .gitattributes, and says so on stderr: a generated
copy repeats its source and only doubles what the reviewer reads. git's output is
pinned (quoted names, a/ and b/ prefixes, no colour, no external diff), whatever
the operator's own git config says.

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
import fnmatch
import importlib.util
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
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


_C_ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


def _unquote(token: str) -> str:
    """A path as git prints it, back to its real name. git wraps a name that has a
    non-ASCII byte, a quote, a backslash or a control character in double quotes and
    writes those bytes as C escapes (octal for non-ASCII, decoded here as UTF-8)."""
    if len(token) < 2 or not (token.startswith('"') and token.endswith('"')):
        return token
    out = bytearray()
    body, i = token[1:-1], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in "01234567":
                digits = re.match(r"[0-7]{1,3}", body[i + 1:]).group(0)
                out.append(int(digits, 8) & 0xFF)
                i += 1 + len(digits)
                continue
            if nxt in _C_ESCAPES:
                out.append(_C_ESCAPES[nxt])
                i += 2
                continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", errors="replace")


def _side(text: str, prefix: str) -> str:
    """The path on a `---` / `+++` line: git puts a tab after a name with a space,
    and the a/ or b/ prefix sits inside the quotes of a quoted name."""
    # A real tab in a name forces quoting, so a trailing tab is always git's own.
    path = _unquote(text[:-1] if text.endswith("\t") else text)
    return path[len(prefix):] if path.startswith(prefix) else path


def _header_path(rest: str) -> Optional[str]:
    """The b-side of `diff --git <a> <b>`, used only when a block has no other line
    naming its file (a mode-only change, or a binary or empty file)."""
    if rest.startswith('"'):
        m = re.match(r'"(?:[^"\\]|\\.)*"', rest)
        if not m:
            return None
        b = rest[m.end():].strip()
    else:
        # Unquoted names may hold spaces: split where the two halves, minus their
        # prefixes, name the same file. A rename shows up on its own lines instead.
        b = None
        for i in range(len(rest)):
            if rest[i] == " " and rest[:i].startswith("a/") and rest[i + 1:].startswith("b/") \
                    and rest[2:i] == rest[i + 3:]:
                b = rest[i + 1:]
                break
        if b is None:
            return None
    path = _unquote(b)
    return path[2:] if path.startswith("b/") else path


def changed_paths(diff_text: str) -> List[str]:
    """The files a unified diff touches, in order of first appearance.

    Each file block is read from the lines git writes for it: `+++` (the new side),
    else `---` (a deletion), else `rename to` / `copy to`, else the `diff --git`
    header itself. Quoted names and names with spaces come back as their real names.
    """
    seen: List[str] = []
    blocks = re.split(r"^diff --git ", diff_text, flags=re.MULTILINE)[1:]
    for block in blocks:
        header, _, body = block.partition("\n")
        found: Dict[str, str] = {}
        # split on \n only: str.splitlines() also breaks at U+2028 and U+0085, which git
        # prints raw in a name when core.quotePath is false.
        for line in (l.rstrip("\r") for l in body.split("\n")):
            if line.startswith("diff --git ") or line.startswith("@@"):
                break
            for key in ("+++ ", "--- ", "rename to ", "copy to "):
                if line.startswith(key) and key not in found:
                    found[key] = line[len(key):]
        path: Optional[str] = None
        if found.get("+++ ") not in (None, "/dev/null"):
            path = _side(found["+++ "], "b/")
        elif found.get("--- ") not in (None, "/dev/null"):
            path = _side(found["--- "], "a/")
        elif "rename to " in found or "copy to " in found:
            path = _unquote(found.get("rename to ") or found["copy to "])
        else:
            path = _header_path(header.rstrip("\r"))
        if path and path not in seen:
            seen.append(path)
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


# ------------------------------------------------------- governing designs

_LIVE_DESIGN = ("final", "launched", "active")
# A design is long, and its paragraphs would crowd out AGENTS.md: at most this many
# of them reach RULES (its Locked design calls are not counted against it).
MAX_DESIGN_PARAGRAPHS = 8
# The section that holds a design's body: `Design` in a repo design, `Current design`
# in a living design written by /design.
_DESIGN_BODY = ("design", "current design")


def _frontmatter(text: str) -> str:
    m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    return m.group(1) if m else ""


def _governs(front: str) -> List[str]:
    """The `governs:` entries of a frontmatter block: an inline `[a, b]` list or
    a block of `- a` lines."""
    lines = front.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^governs:\s*(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest.startswith("["):
            items = rest.strip("[]").split(",")
        elif rest:
            items = [rest]
        else:
            items = []
            for nxt in lines[i + 1:]:
                b = re.match(r"^\s+-\s*(.*)$", nxt)
                if not b:
                    break
                items.append(b.group(1))
        return [x.strip().strip("'\"") for x in items if x.strip().strip("'\"")]
    return []


def _governs_match(entry: str, path: str) -> int:
    """How specifically one `governs:` entry covers a repo-relative path: the
    entry's length, or 0. A trailing `/` is a folder, `*?[` a glob, else a file
    or a folder named without its slash."""
    entry = entry[2:] if entry.startswith("./") else entry
    if not entry:
        return 0
    if any(c in entry for c in "*?["):
        return len(entry) if fnmatch.fnmatchcase(path, entry) else 0
    if entry.endswith("/"):
        return len(entry) if path.startswith(entry) else 0
    return len(entry) if path == entry or path.startswith(entry + "/") else 0


def _repo_relative(path: str, repo_root: Path) -> Optional[str]:
    """A changed path as the repo names it. A relative path already is one: a diff
    names its files from the repo root, and `--files` reads a relative path from
    there too. An absolute path outside the repo has none."""
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def governing_designs(repo_root: Path, paths: Sequence[str]) -> List[Path]:
    """The repo's live `wiki/designs/` pages that govern the change. Each changed
    path counts only its most specific governor(s), so a design that claims the
    whole tree (`src/**`) speaks only for files nothing narrower covers. Most
    specific first, ties by file name. None when there is no folder."""
    folder = repo_root / "wiki" / "designs"
    if not folder.is_dir():
        return []
    rel = [r for r in (_repo_relative(p, repo_root) for p in paths) if r]
    pages = []
    for page in sorted(folder.glob("*.md")):
        front = _frontmatter(page.read_text(encoding="utf-8", errors="replace"))
        status = re.search(r"(?m)^status:\s*['\"]?(\w+)", front)
        if status and status.group(1).lower() in _LIVE_DESIGN:
            pages.append((page, _governs(front)))
    best: Dict[Path, int] = {}
    for r in rel:
        scores = {page: max((_governs_match(e, r) for e in entries), default=0) for page, entries in pages}
        top = max(scores.values(), default=0)
        for page, score in scores.items():
            if top and score == top:
                best[page] = max(best.get(page, 0), score)
    return [page for page in sorted(best, key=lambda pg: (-best[pg], pg.name))]


def design_rules(text: str, name: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """From one design: its Locked design calls as RULES lines, and the
    paragraphs and bullets of its `Design` (or `Current design`) section for the
    relevance match."""
    locked = [_line(b, name) for _s, b in _section_bullets(text, ("locked design calls",))]
    body = text[len(_frontmatter(text)):] if text.startswith("---") else text
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    paras: List[Tuple[str, str]] = []
    inside = False
    block: List[str] = []

    def flush() -> None:
        para = _clean(" ".join(block))
        if len(para) >= 40:
            paras.append((name, para))
        block.clear()

    for raw in body.splitlines():
        h = _HEADING.match(raw)
        if h:
            flush()
            if len(h.group(1)) <= 2:
                inside = h.group("name").strip().lower() in _DESIGN_BODY
            continue
        if not inside:
            continue
        if not raw.strip() or raw.lstrip().startswith(("|", ">", "<!--")):
            flush()
            continue
        if _BULLET.match(raw):
            flush()
            block.append(_BULLET.match(raw).group("text"))
        else:
            block.append(raw.strip())
    flush()
    return locked, paras


# ------------------------------------------------------------- the artifact

def _run(argv: Sequence[str], cwd: Optional[Path]) -> str:
    proc = subprocess.run(list(argv), cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise ValueError(f"`{' '.join(argv)}` failed (exit {proc.returncode}): {proc.stderr.strip()[:300]}")
    return proc.stdout


# What git prints is pinned, whatever the operator's own config says: a quoted name,
# a/ and b/ prefixes, no colour, no external diff tool. changed_paths() reads that shape.
_GIT_DIFF = ["git", "-c", "core.quotePath=true", "-c", "diff.noprefix=false",
             "-c", "diff.mnemonicPrefix=false", "-c", "diff.relative=false",
             "diff", "--no-color", "--no-ext-diff"]


def artifact_from_range(rng: str, repo_root: Path) -> str:
    return _run([*_GIT_DIFF, rng], repo_root)


def _embedded_repo_block(path: str, repo_root: Path) -> str:
    """The block git would print had `git add` staged the embedded repository: a
    gitlink (`Subproject commit <sha>`). It is staged into a throwaway copy of the
    index, so the real index is untouched and git does its own quoting. A repository
    with no commit has no gitlink to show, and gives nothing."""
    index = Path(_run(["git", "rev-parse", "--path-format=absolute", "--git-path", "index"],
                      repo_root).strip())
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        if index.is_file():
            shutil.copyfile(index, env["GIT_INDEX_FILE"])
        added = subprocess.run(["git", "-c", "advice.addEmbeddedRepo=false", "add", "--", path],
                               cwd=str(repo_root), env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if added.returncode != 0:
            return ""
        proc = subprocess.run([*_GIT_DIFF, "--cached", "HEAD", "--", path], cwd=str(repo_root),
                              env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        return proc.stdout if proc.returncode == 0 else ""


def artifact_from_worktree(repo_root: Path) -> str:
    """Tracked changes against HEAD, then each untracked, non-ignored file as a new file.

    `git diff HEAD` never lists an untracked path, so a task that adds a module would
    otherwise send its reviewers nothing before the first commit.
    """
    parts = [_run([*_GIT_DIFF, "HEAD"], repo_root)]
    untracked = _run(["git", "ls-files", "--others", "--exclude-standard", "-z"], repo_root)
    for path in sorted(p for p in untracked.split("\0") if p):
        if path.endswith("/"):
            # git lists an untracked repository inside this one as `dir/`, never its files.
            parts.append(_embedded_repo_block(path.rstrip("/"), repo_root))
            continue
        # --no-index exits 1 when the two sides differ, which a new file always does.
        proc = subprocess.run([*_GIT_DIFF, "--no-index", "--", "/dev/null", path],
                              cwd=str(repo_root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode not in (0, 1):
            raise ValueError(f"`git diff --no-index /dev/null {path}` failed (exit {proc.returncode}): "
                             f"{proc.stderr.strip()[:300]}")
        parts.append(proc.stdout)
    return "".join(parts)


def drop_generated(artifact: str, repo_root: Path) -> Tuple[str, List[str]]:
    """Leave out the file blocks of a diff that the repo marks generated
    (`linguist-generated` in .gitattributes, e.g. `dist/** linguist-generated`).
    A generated copy repeats its source, so it doubles what a reviewer reads and
    adds nothing to review. Returns the artifact without them, and their paths.
    Outside a git repository, or with no such attribute, nothing is left out."""
    blocks = re.split(r"(?m)^(?=diff --git )", artifact)
    paths = [(b, changed_paths(b)) for b in blocks]
    names = sorted({ps[0] for _, ps in paths if ps})
    if not names:
        return artifact, []
    proc = subprocess.run(["git", "check-attr", "-z", "--stdin", "linguist-generated"],
                          cwd=str(repo_root), input="\0".join(names) + "\0", capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return artifact, []
    fields = proc.stdout.split("\0")
    generated = {fields[i] for i in range(0, len(fields) - 2, 3)
                 if fields[i + 2] not in ("unspecified", "unset", "false")}
    kept, dropped = [], []
    for block, ps in paths:
        if ps and ps[0] in generated:
            dropped.append(ps[0])
        else:
            kept.append(block)
    return "".join(kept), dropped


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
          designs: Sequence[Path] = (),
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
        pool = doc_paragraphs(repo_root)
        used_designs: List[str] = []
        seen = {anchor_path.resolve()}
        for design in [*governing_designs(repo_root, paths), *designs]:
            if design.resolve() in seen:
                continue
            seen.add(design.resolve())
            if not design.is_file():
                notes.append(f"review_material: the design {design} was not found; its rules are left out")
                continue
            locked, paras = design_rules(design.read_text(encoding="utf-8", errors="replace"), design.name)
            candidates.extend(locked)
            pool.extend(paras)
            used_designs.append(design.name)
        if used_designs:
            notes.append(f"review_material: rules also from the design(s) {', '.join(used_designs)}")
        terms = terms_from(paths, diff_text if diff_text is not None else artifact)
        from_designs = 0
        for _score, name, para in rank_doc_rules(pool, terms):
            if name in used_designs:
                if from_designs >= MAX_DESIGN_PARAGRAPHS:
                    continue
                from_designs += 1
            candidates.append(_line(para, name))
        candidates = list(dict.fromkeys(candidates))
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
    p.add_argument("--design", action="append", default=[],
                   help="a design the change is also held to, kept outside the repo's wiki/designs/ "
                        "(repeatable); the repo's own governing designs are found from governs:")
    p.add_argument("--repo-root", default=".", help="the repo (default: the current directory)")
    p.add_argument("--tier", default="default", choices=sorted(TIER_CEILINGS))
    p.add_argument("--max-rule-lines", type=int, default=DEFAULT_MAX_RULE_LINES)
    p.add_argument("--max-bytes", type=int, help="override the tier's byte ceiling (0 = no limit)")
    return p


def _utf8_stdio() -> None:
    """Write UTF-8 whatever the console's code page is: a Windows console's cp1252 cannot encode
    the arrows and dots this prints. A stream that cannot be reconfigured is left alone."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    _utf8_stdio()
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
        generated: List[str] = []
        if not args.files:
            artifact, generated = drop_generated(artifact, root)
        if not args.files and not artifact.strip():
            source = "the working tree" if args.worktree else (args.range or f"PR {args.pr}")
            why = (f"every file {source} changes is generated ({len(generated)}, linguist-generated)"
                   if generated else f"{source} has no changes")
            raise ValueError(f"nothing to review: {why}; a reviewer is never sent an empty artifact")
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
                            repo_root=root, designs=[Path(d) for d in args.design],
                            max_rule_lines=args.max_rule_lines, ceiling=ceiling,
                            diff_text=diff_text)
    except (OSError, ValueError) as exc:
        print(f"review_material: {exc}", file=sys.stderr)
        return 2
    if generated:
        shown = ", ".join(generated[:5]) + (f" and {len(generated) - 5} more" if len(generated) > 5 else "")
        notes.insert(0, f"review_material: left out {len(generated)} generated file(s) "
                        f"(linguist-generated in .gitattributes): {shown}")
    for n in notes:
        print(n, file=sys.stderr)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
