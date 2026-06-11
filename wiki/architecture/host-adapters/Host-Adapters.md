<!-- mode: index -->
# Host adapters

_The per-host surface mapping — how one authored primitive lands in each supported host._

crickets supports two hosts: **Claude Code** and **Antigravity**. A single authored primitive emits host-specific artifacts: a skill becomes `.claude/skills/<name>/SKILL.md` on Claude Code, while commands, agents, and hooks each route to their own per-host destination. Antigravity adds workflows and rules as native primitive kinds. Some host capabilities are absent on one side; those gaps are tracked explicitly rather than papered over.

Field-level detail lives in Reference:

- [Per-Host Paths](Per-Host-Paths) — the destination table per primitive × host.
- [Compatibility](Compatibility) — which primitive kinds each host supports.
- [Antigravity Limitations](Antigravity-Limitations) — the host-gap register.

## See also

[Architecture](Architecture) · [Reference](Reference) · [Home](Home)
