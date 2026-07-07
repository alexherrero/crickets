#!/usr/bin/env python3
"""privacy.scrub_text() -- the arbitrary-text scrub surface (PLAN-wave-d-
tokens-and-privacy task 6, "the genuine build gap" named by both
crickets-privacy.md:66 and crickets-diagnostics.md:102,110).

**Design finding (discovered during this task, not assumed going in):** the
detection *rules* this surface needs to reuse already live in agentm's
harness/skills/memory/scripts/privacy_scrub.py, landed 2026-07-05 (V6-11
extended entry_meta + hybrid filter + failure-incident scrub). That module's
own docstring explains why it ported check-no-pii.sh's pattern categories
into a self-contained *redactor* rather than crickets calling into it: the
one-way capability bridge runs crickets -> agentm only, never the reverse.
It is already wired as a MANDATORY gate inside agentm's save_entry() for
kind="failure-incident" -- so diagnostics' writer.py already gets scrubbed
writes transitively, today, via that path.

This module closes the gap from the OTHER direction: a crickets-native
`scrub_text()` entry point, reusing the exact same agentm-side rules via the
established bridge pattern (mirrors session_cost_writer.py's / agentm_
bridge.py's own path-fallback), so any crickets capability can scrub
arbitrary text -- not only the one write path that happens to gate on
kind="failure-incident" inside agentm's save.py. diagnostics' writer.py is
updated (this same task) to call scrub_text() explicitly and directly,
rather than relying solely on the implicit kind-gated scrub one layer down
-- an explicit, visible scrub at the crickets call site, not a hidden
dependency on save.py's internal kind check continuing to fire.

One rule set (agentm's privacy_scrub.scrub_pii), two entrypoints (agentm's
own mandatory kind-gated write-path scrub, and this crickets-native
call-anywhere surface) -- never a second, forked detection implementation.

Public API:

    scrub_text(text: str) -> str
        Redact every PII-shaped match. Never raises -- degrades to
        returning `text` UNCHANGED when agentm is unresolvable (graceful-
        skip, matching every other bridge in this codebase's convention).
        Callers that need a hard guarantee (a mandatory pre-write scrub)
        should check `scrub_text_available()` first and refuse to write
        unscrubbed content if it's False, mirroring save.py's own
        refuse-loud-not-silent posture for kind="failure-incident".
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_SCRUB_SCRIPTS_REL = Path("harness") / "skills" / "memory" / "scripts"

_scrub_module = None
_scrub_loaded = False


def _candidate_dirs() -> list[Path]:
    candidates = []
    env_dir = os.environ.get("AGENTM_SCRIPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.append(Path.home() / "Antigravity" / "agentm" / _SCRUB_SCRIPTS_REL)
    return candidates


def _find_scrub_scripts_dir() -> "Path | None":
    for candidate in _candidate_dirs():
        if (candidate / "privacy_scrub.py").is_file():
            return candidate
    return None


def load_scrub_module():
    """Return agentm's privacy_scrub module, loaded once and cached. None if
    agentm is unresolvable (graceful-skip, not an error)."""
    global _scrub_module, _scrub_loaded
    if _scrub_loaded:
        return _scrub_module
    _scrub_loaded = True
    scripts_dir = _find_scrub_scripts_dir()
    if scripts_dir is None:
        _scrub_module = None
        return None
    spec = importlib.util.spec_from_file_location(
        "agentm_privacy_scrub_bridge", scripts_dir / "privacy_scrub.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["agentm_privacy_scrub_bridge"] = module
    spec.loader.exec_module(module)
    _scrub_module = module
    return module


def scrub_text_available() -> bool:
    """Whether the real agentm-backed scrubber is reachable on this
    machine. Callers doing a mandatory pre-write scrub should check this and
    refuse to write unscrubbed content if False -- never silently pass
    unscrubbed text through as if it were clean."""
    return load_scrub_module() is not None


def scrub_text(text: str) -> str:
    """Redact PII-shaped matches in `text` using agentm's privacy_scrub
    rules (the same categories check-no-pii.sh scans for: email, personal
    path, API-key shape, US phone number). Never raises.

    Graceful-skip: returns `text` UNCHANGED when agentm is unresolvable --
    matching this codebase's universal bridge-unavailable convention. This
    is intentionally NOT the same posture as save.py's kind="failure-
    incident" gate (which refuses the write outright when the scrubber is
    unavailable) -- scrub_text() is a general-purpose primitive; a caller
    that needs the harder guarantee should check scrub_text_available()
    first and refuse its own write, the way writer.py now does.
    """
    module = load_scrub_module()
    if module is None:
        return text
    return module.scrub_pii(text)


def _reset_cache_for_tests() -> None:
    """Test-only: clear the module-level cache between isolated test cases."""
    global _scrub_module, _scrub_loaded
    _scrub_module = None
    _scrub_loaded = False
