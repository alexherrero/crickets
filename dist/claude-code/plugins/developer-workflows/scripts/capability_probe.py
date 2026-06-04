#!/usr/bin/env python3
"""Local deterministic capability probe (crickets v3.x ④ part 5).

Answers *"is plugin <slug> installed + enabled on the current host?"* — the
conditional-dispatch half of `enhances:`. developer-workflows' `/review` calls
this to decide whether to dispatch code-review's adversarial reviewers:

    capability_probe.py <plugin-slug>     # exit 0 = available, exit 1 = not

**Deterministic + reproducible** — same install state → same answer; the check
is a CLI query, not agent-judgment. **Graceful-skip** — any failure (no host
CLI on PATH, non-zero exit, unparseable output) → exit 1 ("unavailable"), so the
caller falls back to the safe path (deterministic gates only) and never hangs.

**Host-aware:** Claude Code (detected via the `CLAUDE_PLUGIN_ROOT` env the host
sets inside a plugin) uses `claude plugin list`; otherwise `agy plugin list`.

**INTERIM LOCAL FALLBACK — agentm V5-8 hand-off.** The generalized version is the
agentm capability-discovery API: the plugin *host* aggregates installed plugins'
declared `capabilities:` and answers "is capability X available?" for any plugin
at action time. When that host feature lands (tracked on the agentm
`ROADMAP-AgentMemoryV5.md`, item V5-8), `/review` queries the host API and this
local probe **retires**. The runtime contract is identical either way — a
deterministic yes/no with graceful-skip — so the swap is transparent. Stdlib-only.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def parse_enabled_slugs(output: str) -> list[str]:
    """Parse plugin slugs from a host `plugin list` rendering: strip ANSI +
    leading list decoration, take the token before any `@<marketplace>`. Pure +
    deterministic — the unit-testable core of the probe."""
    slugs: list[str] = []
    for raw in output.splitlines():
        line = _ANSI.sub("", raw).strip().lstrip("❯>*•- \t").strip()
        if not line:
            continue
        token = line.split()[0]
        slug = token.split("@", 1)[0]
        if slug:
            slugs.append(slug)
    return slugs


def _host_cli() -> str | None:
    """The plugin-list CLI for the current host: Claude (`CLAUDE_PLUGIN_ROOT`
    set) → `claude`; else the first of `claude`/`agy` on PATH; None when neither."""
    if os.environ.get("CLAUDE_PLUGIN_ROOT") and shutil.which("claude"):
        return "claude"
    for cli in ("claude", "agy"):
        if shutil.which(cli):
            return cli
    return None


def _list_output(cli: str) -> str:
    """`<cli> plugin list` stdout, or "" on any failure (graceful)."""
    try:
        r = subprocess.run([cli, "plugin", "list"], capture_output=True,
                           text=True, timeout=10)
    except Exception:
        return ""
    return r.stdout if r.returncode == 0 else ""


def is_available(plugin_slug: str, cli: str | None = None,
                 output: str | None = None) -> bool:
    """True iff `plugin_slug` is installed + enabled on the current host.
    `output` is injectable for tests; otherwise shells out to the host CLI.
    Graceful-skip: no CLI / failure → False."""
    if output is None:
        cli = cli or _host_cli()
        if cli is None:
            return False
        output = _list_output(cli)
    return plugin_slug in parse_enabled_slugs(output)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: capability_probe.py <plugin-slug>", file=sys.stderr)
        return 2
    return 0 if is_available(argv[1]) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
