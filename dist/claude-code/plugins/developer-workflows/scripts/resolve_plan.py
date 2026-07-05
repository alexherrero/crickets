#!/usr/bin/env python3
"""Resolve the active (PLAN, progress) on-disk path pair for the phase loop.

The developer-workflows phase specs (`/work`, `/plan`, `/review`) call this to
learn *which* plan pair a session owns, so they can target a named
`PLAN-<name>.md` / `progress-<name>.md` instead of only the singleton:

    resolve_plan.py [<name>] [--project-root <path>]
    # stdout: "<plan_path>\t<progress_path>"  (one tab-separated line)

**Two backends, one contract.** When agentm's process seam is discoverable this
is a thin **bridge** to `process_seam.py state-path` — the V5-4 designed
interface. The bridge makes two seam calls (plan, then progress), reassembles
the tab-separated pair, and **propagates** exit codes; it never re-derives
resolution. When the seam is **absent** (agentm not installed), developer-workflows
still works standalone via a plain `.harness/` fallback (bare → `PLAN.md` /
`progress.md`; named → `PLAN-<name>.md` / `progress-<name>.md`, flat).

**Risk #7 — no silent singleton fallback.** A *located* seam is authoritative:
if it exits non-zero (a dangling marker or an unsafe slug), the bridge surfaces
that exit + stderr and emits **no** pair. The `.harness/` fallback fires **only**
when no seam is discoverable — never to paper over a seam that ran and refused.
That distinction is what keeps a worker from silently binding to the wrong plan.

Exit codes (identical on both backends, so the two are transparent):
    0 — resolved; the pair is on stdout.
    1 — graceful-skip: seam present but no resolvable `_harness/` dir.
    2 — loud: dangling marker or unsafe plan slug. Never a singleton fallback.

Stdlib-only; mirrors `capability_probe.py`'s shape (pure core + injectable I/O).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

# Load the seam bridge from the same scripts/ directory (crickets-internal; not
# a cross-repo import — DC-2 prohibits importing agentm's process_seam.py
# directly, not find_process_seam.py which lives here in crickets).
def _load_bridge():
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "find_process_seam", here / "find_process_seam.py"
    )
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


_bridge = _load_bridge()

# Sentinel: `resolve(seam=_AUTO)` (the default, and what main() uses) locates
# the seam; tests pass `seam=<stub path>` to force the delegate branch or
# `seam=None` to force the standalone `.harness/` fallback.
_AUTO = object()


# ── filename mapping (the naming contract, not resolution logic) ───────────────

def _normalize_plan_name(name: str) -> str:
    """A plan name in any accepted form → the bare slug, or "" for the singleton.

    "" / "PLAN" / "PLAN.md" → ""  (singleton);  "foo" / "PLAN-foo" / "PLAN-foo.md"
    → "foo". This is the same surface the seam accepts, kept here only so the
    standalone fallback agrees with the delegated backend on what a name means.

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


# ── agentm-clone lookup (retained for queue_status.py; not used by resolve()) ──

def locate_resolver(*, config_path=None, home=None) -> "Path | None":
    """The agentm `harness_memory.py`, or None when no clone is installed.

    Retained for `queue_status.py`, which calls this to locate the agentm scripts
    directory (and finds `queue_status_lite.py` beside it). `resolve()` no longer
    uses this function — it discovers the process seam via `find_process_seam`.

    Mirrors the agentm session-start hook: recorded `source_clones.agentm` first,
    then the conventional `~/Antigravity/agentm/scripts/harness_memory.py` fallback.
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

def _delegate(seam: Path, name: str, root: str) -> tuple[int, str, str]:
    """Delegate to the V5-4 process seam and reassemble (rc, stdout, stderr).

    Two seam calls: `state-path plan` then `state-path progress`. The seam
    handles named-plan resolution (V5-10 aware) when agentm is present.
    """
    if _bridge is None:
        return (2, "", "[resolve_plan] internal error: bridge not loaded\n")

    slug = _normalize_plan_name(name)
    extra: list[str] = []
    if slug:
        extra += ["--plan", slug]
    extra += ["--cwd", str(root)]

    plan_out, plan_rc = _bridge.run_state_path("plan", extra, seam=seam)
    if plan_rc != 0:
        return (plan_rc, "", f"[resolve_plan] seam state-path plan failed (exit {plan_rc})\n")

    prog_out, prog_rc = _bridge.run_state_path("progress", extra, seam=seam)
    if prog_rc != 0:
        return (prog_rc, "", f"[resolve_plan] seam state-path progress failed (exit {prog_rc})\n")

    return (0, f"{plan_out}\t{prog_out}\n", "")


def _fallback(name: str, root: str) -> tuple[int, str, str]:
    """Standalone resolution: plain `.harness/` pair, no vault / marker / CAS."""
    slug = _normalize_plan_name(name)
    if slug and not _is_safe_plan_slug(slug):
        return (2, "", f"[resolve_plan] unsafe plan name: {name!r}\n")
    plan_fn, prog_fn = _plan_pair(slug)
    base = Path(root).expanduser() / ".harness"
    return (0, f"{base / plan_fn}\t{base / prog_fn}\n", "")


# ── vault-reachability probe (R2.5 task 12) ─────────────────────────────────

def _vault_configured_and_reachable(*, install_prefix: "str | os.PathLike | None" = None) -> bool:
    """True iff agentm's OWN config independently confirms a vault-backed memory
    layer is configured and reachable right now — read-only, no cross-repo import.

    This is evidence for the guard in `resolve()` below, not a resolver: it never
    re-derives resolve_plan's own path logic, and it deliberately does not import
    agentm's `backend_selection.py` / `harness_memory.py` (DC-2: siblings not
    layers — this bridge only ever proxies to agentm's CLI, never its Python).
    Instead it reads the same two facts `harness_memory.vault_path()` checks,
    directly off disk:

      1. `$MEMORY_VAULT_PATH` env set and the path exists → vault reachable.
      2. else `<install-prefix>/.agentm-config.json`'s `"storage.backend"` is
         `"vault"` and its `"plugins.obsidian-vault.vault_path"` (falling back to
         the legacy flat `"vault_path"` key) resolves to an existing directory.

    `install_prefix` mirrors `agentm_config`'s own override precedence
    (`$AGENTM_INSTALL_PREFIX`, else `~/.claude`) so this probe can never disagree
    with agentm's own resolution about *where* to look — only about whether the
    seam that reads it was discoverable.

    Any error (file missing/corrupt, wrong type, path doesn't exist) → False.
    That direction is deliberate: this only gates a REFUSAL in `resolve()`, so a
    false negative just keeps today's behavior (repo-side fallback — correct for
    a genuinely standalone install); a false positive would wrongly block a
    legitimate resolution, which this must never do.
    """
    env_vault = os.environ.get("MEMORY_VAULT_PATH", "").strip()
    if env_vault:
        return Path(os.path.expanduser(env_vault)).is_dir()

    prefix_env = os.environ.get("AGENTM_INSTALL_PREFIX", "").strip()
    prefix = (
        Path(install_prefix) if install_prefix is not None
        else (Path(prefix_env) if prefix_env else Path.home() / ".claude")
    )
    try:
        data = json.loads((prefix / ".agentm-config.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict) or data.get("storage.backend") != "vault":
        return False
    vault_dir = data.get("plugins.obsidian-vault.vault_path") or data.get("vault_path")
    if not isinstance(vault_dir, str) or not vault_dir.strip():
        return False
    return Path(os.path.expanduser(vault_dir)).is_dir()


def resolve(name: str, root: str, *, seam=_AUTO, resolver=_AUTO, vault_check=_AUTO) -> tuple[int, str, str]:
    """Core: delegate to the V5-4 process seam, else fall back to `.harness/`.

    `seam` defaults to `_AUTO` (locate the seam via find_process_seam). A located
    seam is authoritative — its result, including a non-zero exit, is returned
    as-is; the fallback fires *only* when the seam is absent (`seam is None`).

    `resolver` is a backward-compat alias for `seam` — callers that previously
    forwarded an injectable harness_memory path can now forward a process_seam
    path (or None for fallback) via the same keyword without source changes.

    **R2.5 task 12 — the activation-tier guard.** `vault_check` is injectable
    (tests only; defaults to `_vault_configured_and_reachable`). When the seam is
    absent AND `vault_check()` is True, `resolve()` refuses (exit 2) instead of
    silently returning the repo-side `.harness/` fallback: that mismatch —
    agentm's own config says a vault-backed memory layer is configured and
    reachable, yet its process seam could not be discovered here — is exactly
    the bug four separate sessions hit, landing plan state on the wrong
    `.harness/` tier with no warning. The refusal names the mismatch so the
    operator fixes *discovery* (`$AGENTM_SCRIPTS_DIR`, or the conventional
    sibling checkout) instead of silently forking plan state onto two roots.
    Per the plan's locked design call, this defaults to refuse, not
    warn-and-proceed. A genuinely standalone install (no agentm config at all)
    is unaffected — `vault_check()` reads False and the fallback proceeds
    exactly as before.
    """
    if seam is _AUTO and resolver is not _AUTO:
        seam = resolver  # backward-compat alias: resolver= → seam=
    if seam is _AUTO:
        seam = _bridge.find_seam() if _bridge is not None else None
    if seam is None:
        rc, out, err = _fallback(name, root)
        if rc == 0:
            check = _vault_configured_and_reachable if vault_check is _AUTO else vault_check
            if check():
                return (2, "", (
                    "[resolve_plan] refusing repo-side .harness/ fallback: this "
                    "install's own config declares storage.backend=vault with a "
                    "reachable vault path, but agentm's process seam was not "
                    "discoverable here (checked $AGENTM_SCRIPTS_DIR, this script's "
                    "own directory, and the conventional ~/Antigravity/agentm "
                    "sibling checkout). Writing to a repo-side .harness/ now would "
                    "silently split this plan's state onto the wrong root instead "
                    "of the vault-backed one every other session reads. Set "
                    "$AGENTM_SCRIPTS_DIR to the sibling agentm/scripts directory, "
                    "or verify the conventional checkout exists, and retry.\n"
                ))
        return rc, out, err
    return _delegate(seam, name, root)


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
