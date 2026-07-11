---
name: dark-registry
description: Every capability that is built-but-dark (works, tested, no on-switch) or designed-but-unbuilt names a current owner, a registered future owner, and a disposition trigger — reconciled at every arc exit (owning plan flips it live, or the entry is deleted). The shared convention is the discipline, not one file format — agentm and crickets each keep their own repo-local storage.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: dark-registry

Migrated in (Consolidation arc, CONS-8) from the Consolidation-arc verdict's ruling 1 (the "built-but-never-surfaced" class, D4) and ruling 8 (arc-exit reconciliation). The verdict's own framing: a **dark registration** records a future owner for code (or a designed capability) that already exists — built and tested but with no caller, or fully specified but not yet built — without changing anything about where that code lives today. It stops a dark capability from being silently forgotten (nobody remembers why it's there) or silently deleted (a zero-caller census flags it as dead when it's actually just waiting on its owner). The registration is the fix for both failure modes: it makes the future explicit, and it puts a deadline on that future via the arc-exit reconciliation this rule's second half describes.

### The reconciliation history this rule closes

Two independent lanes of this same Consolidation arc searched for an existing dark-registry convention before this rule existed, found none, and each improvised a different mechanism because the verdict's own instruction (ruling 1) named the *pattern* without naming a canonical *storage format*:

- **agentm's `CONS-1` lane** added `scripts/health/dark-checks.jsonl` — an append-only JSONL file, one record per dark item, schema `{"suite": "dark-registry", "axis": <health-family>, "check": <description>, "pass": null, "dark": true, "weight": 1.0, "owning_plan": <plan-id>}`. This file is a **live input to agentm's health-scorecard machinery**: `scripts/health/health_score.py --dark-checks <file>` merges these records into the nightly scorecard render, excludes them from the axis score itself (dark checks aren't counted for or against the Health Index), and surfaces them in their own "Dark checks (designed, not built)" section (see agentm's `wiki/explanation/Health-Scorecard.md` and `scripts/health/README.md`).
- **crickets' `CONS-2` lane** added a markdown table ("Forward-owned library code (dark registry)") to `wiki/explanation/Repo-Layout.md` — columns Code / Current owner / Registered future owner / Note.

### The decision: two repo-local formats, one shared convention

**Both formats stay.** This rule does not migrate crickets' table into a JSONL file, and it does not ask agentm to adopt a markdown table. The reasoning:

- agentm's JSONL format earns its structure because it has a **real consumer** — `health_score.py`'s `--dark-checks` flag actually reads it, merges it into a computed scorecard, and renders it in a documented, machine-generated wiki page. The format is justified by the machinery that consumes it, not chosen for its own sake.
- crickets has **no equivalent health-scorecard consumer** — there is no `health_score.py`, no nightly scorecard workflow, and no machine-generated health page anywhere in this repo. Manufacturing a `dark-checks.jsonl` file in crickets with the same schema, but with nothing that ever reads it, would create structure with no load-bearing reason to exist — exactly the kind of scaffolding-for-its-own-sake this Consolidation arc's own "Simplicity first" principle (the `agentic-engineering` skill) rejects: *"When tempted to add a seventh phase, a third sub-agent, a new template — ask: what specific failure am I trying to prevent, and have I seen it happen? If the answer is hypothetical, don't add it."* A JSONL file with no reader is exactly that hypothetical case.
- A human-read markdown table is the right format for a repo whose dark-registry consumer is a person reading the wiki at arc-exit time, not a script computing a score.

**What is actually shared is the convention, not the file.** Both repos' dark registrations — regardless of format — must carry the same four facts:

1. **What** — the code or capability that's dark (a file path, a described capability, or both).
2. **Current owner** — who/what owns it today, unchanged, while it stays dark (e.g., "the `maintenance` plugin (crickets)," or a health family axis).
3. **Registered future owner** — the plan or milestone that will pick it up (e.g., "FRIDAY F1," "CONS-8," a specific plan id) — never a vague "someday."
4. **A disposition trigger** — what happens at the next arc exit: the owning plan ships (the entry flips to live/built, and the registration is removed since the capability is no longer dark) or it doesn't (the entry is deleted outright per the arc-exit reconciliation below, unless a genuine renewed future-owner reason is recorded).

A repo adopting a **new** dark-registry consumer in the future (a crickets health scorecard, say) is free to migrate its table into a machine-readable format at that point — the format follows the consumer, not the other way around. Until then, this rule considers agentm's JSONL and crickets' markdown table equally canonical, cross-linked from here rather than merged.

### Arc-exit reconciliation (D4)

At every arc exit (the trigger the `coalescence-gate` rule's item 6 names), walk every dark-registry entry in both repos:

- **The owning plan shipped** → the capability is no longer dark. Delete the entry (agentm: remove the JSONL line; crickets: remove the table row) — a shipped capability that still shows up as "dark" is stale bookkeeping, not a registration.
- **The owning plan has not shipped and there is still a genuine future** → leave the entry, and reaffirm (or update) the owning plan if it changed.
- **The owning plan has not shipped and there is no longer a genuine future** (the capability was superseded, descoped, or nobody actually wants it) → delete the entry. A dark registration is not a permanent parking spot; an entry with no real forward motion is exactly the kind of orphan the arc-exit orphan census (`coalescence-gate` item 7) is designed to catch.
- **Anything still dark and caller-less at arc exit with no owning plan at all** → per ruling 1's own disposition, this is deleted, not left dark indefinitely.

### What is NOT an acceptable registration

| Stated registration | Why it is not acceptable |
|---|---|
| "It's dark, I'll just leave a TODO comment in the code" | A TODO comment has no owning plan, no arc-exit reconciliation trigger, and isn't visible to a health scorecard or a repo-layout reader — it's exactly the kind of dark capability that gets silently forgotten. Use the repo's actual dark-registry (JSONL for agentm, the wiki table for crickets). |
| "I'll register it with 'future work' as the owner" | Not a plan id — unenforceable at arc exit, since there's no owning plan to check for shipped-or-not. Name the actual plan or milestone, even if it's a forward-looking one like "FRIDAY F1." |
| "It's been dark for three arcs, I'll just leave it, it's fine" | Three arc exits without reconciliation means the entry either ships, gets a real new owning plan, or is deleted — "fine to leave forever" isn't one of the three outcomes this rule allows. |

### Enforcement

Before adding a dark-registry entry, confirm:

1. Does it name the code/capability, its current owner, its registered future owner (a real plan/milestone id), and a note?
2. Is it in the repo's own canonical format (agentm: `scripts/health/dark-checks.jsonl`; crickets: `wiki/explanation/Repo-Layout.md`'s dark-registry table)?

At every arc exit, confirm every entry in both repos:

1. Has its owning plan shipped? If yes, delete the entry.
2. Is the owning plan still real and still forward-looking? If yes, leave it (updating the owner if it changed).
3. Is there no real forward motion left? If yes, delete the entry — it's an orphan, not a registration.

## See also

- [`coalescence-gate`](coalescence-gate.md) — item 6 of the arc-exit checklist, which walks this registry.
- agentm's `scripts/health/dark-checks.jsonl` + `scripts/health/README.md` + `wiki/explanation/Health-Scorecard.md` — the JSONL mechanism + its health-scorecard consumer.
- crickets' `wiki/explanation/Repo-Layout.md` ("Forward-owned library code (dark registry)") — the markdown-table mechanism.
