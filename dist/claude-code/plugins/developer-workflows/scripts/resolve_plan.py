#!/usr/bin/env python3
"""Resolve the active (PLAN, progress) on-disk path pair for the phase loop.

The developer-workflows phase specs (`/work`, `/plan`, `/review`) call this to
learn *which* plan pair a session owns, so they can target a named
`PLAN-<name>.md` / `progress-<name>.md` instead of only the singleton:

    resolve_plan.py [<name>] [--project-root <path>]
    # stdout: "<plan_path>\t<progress_path>"  (one tab-separated line)

**Two backends, one contract.** When an agentm source clone is installed this is
a thin **bridge** to agentm's `harness_memory.py resolve-active-plan` verb — the
single owner of precedence (explicit name → `.harness/active-plan` marker →
singleton), slug-safety, vault redirection, and the dangling-marker loud-error.
The bridge re-emits the verb's line verbatim and **propagates** its exit code; it
never re-derives resolution. When **no** agentm clone is found, developer-workflows
still works standalone via a plain `.harness/` fallback (bare → `PLAN.md` /
`progress.md`; named → `PLAN-<name>.md` / `progress-<name>.md`, flat).

**Risk #7 — no silent singleton fallback.** A *located* agentm resolver is
authoritative: if it exits non-zero (a dangling marker or an unsafe slug), the
bridge surfaces that exit + stderr and emits **no** pair. The `.harness/` fallback
fires **only** when no agentm clone exists at all — never to paper over a resolver
that ran and refused. That distinction is what keeps a worker from silently
binding to the wrong plan.

Exit codes (identical to the agentm verb, so the two backends are transparent):
    0 — resolved; the pair is on stdout.
    1 — graceful-skip: agentm present but no resolvable `_harness/` dir.
    2 — loud: dangling marker or unsafe plan slug. Never a singleton fallback.

Stdlib-only; mirrors `capability_probe.py`'s shape (pure core + injectable I/O).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Same interpreter that runs this bridge runs the agentm resolver — avoids a
# PATH `python3` that differs from the one developer-workflows was launched with.
_PY = sys.executable or "python3"

# Sentinel: `resolve(resolver=_AUTO)` (the default, and what main() uses) locates
# an agentm clone; tests pass `resolver=<stub path>` to force the delegate branch
# or `resolver=None` to force the standalone `.harness/` fallback.
_AUTO = object()


# ── filename mapping (the naming contract, not resolution logic) ───────────────

def _normalize_plan_name(name: str) -> str:
    """A plan name in any accepted form → the bare slug, or "" for the singleton.

    "" / "PLAN" / "PLAN.md" → ""  (singleton);  "foo" / "PLAN-foo" / "PLAN-foo.md"
    → "foo". This is the same surface the agentm verb accepts, kept here only so
    the standalone fallback agrees with the delegated backend on what a name means.

    Step order mirrors agentm's `_normalize_plan_name` exactly — strip `.md`, strip
    the `PLAN-` prefix, *then* test for the singleton — so an edge form like
    "PLAN-PLAN.md" reduces to the singleton on both sides rather than to a named
    "PLAN" plan here and the singleton there. (Parity fix — 2026-06-13 adversarial
    audit finding ML2; golden vectors in test_resolve_plan.py guard the agreement.)
    """
    slug = (name or "").strip()
    if slug.endswith(".md"):
        slug = slug[:-3]
    if slug.startswith("PLAN-"):
        slug = slug[len("PLAN-"):]
    if not slug or slug == "PLAN":
        return ""
    return slug


def _is_safe_plan_slug(slug: str) -> bool:
    """True iff `slug` is a single path component (no traversal, no separators).

    The fallback's only safety obligation — agentm owns the richer guard when
    present. Rejects "", ".", "..", a NUL byte, and anything containing a path
    separator. (The NUL-byte rejection matches agentm's guard — 2026-06-13
    adversarial audit finding ML2; without it a "foo\x00" slug slipped through
    here but not there.)
    """
    if not slug or slug in (".", ".."):
        return False
    if "/" in slug or "\\" in slug or "\x00" in slug:
        return False
    if os.sep in slug or (os.altsep and os.altsep in slug):
        return False
    return os.path.basename(slug) == slug


def _plan_pair(slug: str) -> tuple[str, str]:
    """Slug → (plan_filename, progress_filename). "" → the singleton pair."""
    if not slug:
        return ("PLAN.md", "progress.md")
    return (f"PLAN-{slug}.md", f"progress-{slug}.md")


# ── locating the agentm resolver (mirrors the session-start hook) ──────────────

def locate_resolver(*, config_path: str | os.PathLike | None = None,
                    home: str | os.PathLike | None = None) -> Path | None:
    """The agentm `harness_memory.py`, or None when no clone is installed.

    Mirrors the agentm session-start hook exactly: the recorded source clone in
    `~/.claude/.agentm-config.json` (`source_clones.agentm`) first, then the
    conventional `~/Antigravity/agentm/scripts/harness_memory.py` fallback.
    `config_path` and `home` are injectable for tests.
    """
    home_dir = Path(home) if home is not None else Path.home()
    cfg = (Path(config_path) if config_path is not None
           else home_dir / ".claude" / ".agentm-config.json")
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        clone = (data.get("source_clones") or {}).get("agentm") or ""
    except Exception:
        clone = ""
    if clone:
        cand = Path(clone) / "scripts" / "harness_memory.py"
        if cand.is_file():
            return cand
    cand = home_dir / "Antigravity" / "agentm" / "scripts" / "harness_memory.py"
    return cand if cand.is_file() else None


# ── the two backends ───────────────────────────────────────────────────────────

def _delegate(resolver: Path, name: str, root: str) -> tuple[int, str, str]:
    """Shell to the agentm verb and propagate (rc, stdout, stderr) verbatim."""
    cmd = [_PY, str(resolver), "resolve-active-plan", "--project-root", str(root)]
    if name:
        cmd += ["--plan", name]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except Exception as exc:  # the resolver path existed but would not run
        return (2, "", f"[resolve_plan] could not invoke agentm resolver: {exc}\n")
    return (r.returncode, r.stdout, r.stderr)


def _fallback(name: str, root: str) -> tuple[int, str, str]:
    """Standalone resolution: plain `.harness/` pair, no vault / marker / CAS."""
    slug = _normalize_plan_name(name)
    if slug and not _is_safe_plan_slug(slug):
        return (2, "", f"[resolve_plan] unsafe plan name: {name!r}\n")
    plan_fn, prog_fn = _plan_pair(slug)
    base = Path(root).expanduser() / ".harness"
    return (0, f"{base / plan_fn}\t{base / prog_fn}\n", "")


def resolve(name: str, root: str, *, resolver=_AUTO) -> tuple[int, str, str]:
    """Core: delegate to a located agentm resolver, else fall back to `.harness/`.

    `resolver` defaults to `_AUTO` (locate an agentm clone). A located resolver is
    authoritative — its result, including a non-zero exit, is returned as-is; the
    fallback fires *only* when no clone is found (`resolver is None`).
    """
    if resolver is _AUTO:
        resolver = locate_resolver()
    if resolver is None:
        return _fallback(name, root)
    return _delegate(resolver, name, root)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="resolve_plan.py",
        description="Emit the active (PLAN, progress) path pair for the phase loop.",
    )
    p.add_argument("name", nargs="?", default="",
                   help="plan name ('foo', 'PLAN-foo', 'PLAN-foo.md'); omit for the singleton")
    p.add_argument("--project-root", default=None,
                   help="project root (default: cwd)")
    return p


def main(argv: list[str]) -> int:
    ns = _build_parser().parse_args(argv[1:])
    root = ns.project_root if ns.project_root is not None else os.getcwd()
    rc, out, err = resolve(ns.name, root)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
