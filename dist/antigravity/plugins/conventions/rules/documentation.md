---
name: documentation
description: Every wiki page is exactly one Diátaxis mode, single-mode-per-page, with a soft length ceiling per mode and a unique basename across the tree. Enforced by check-wiki.py, cited here as the objective house standard.
kind: rule
supported_hosts: [claude-code, antigravity]
version: 0.1.0
---

## Rule: documentation

The Diátaxis structure is a base standard, gate-backed by [wiki](https://github.com/alexherrero/crickets/wiki/crickets-wiki)'s `check-wiki.py` — this rule cites that gate rather than re-deriving it (the cite-don't-duplicate boundary: `wiki` tools the standard, `conventions` owns it).

**Single-mode-per-page.** Every page is exactly one of four Diátaxis modes: tutorial, how-to, reference, explanation. A page mixing modes (task-oriented steps inside an explanation, prose inside a reference) is a structural defect, not a style preference. Index/landing pages (`<!-- mode: index -->`) are shape-exempt.

**Length ceilings (soft).** A per-mode word-count ceiling triggers a warning, not a hard failure, when exceeded: tutorial 1200 words, how-to 600 words, explanation 2000 words. A soft warning is not automatically wrong — genuinely load-bearing content (worked scenarios, troubleshooting) can justify staying over the ceiling; note the trade-off explicitly (in the commit message / changelog) when you do.

**Naming style.** Every page basename is unique across the tree, case-insensitively (GitHub Wiki resolves links by basename and collides on case). When a user-facing page and a design page would collide, the user-facing page owns the clean name and the design page takes a `-design` suffix.

### What is NOT an acceptable bypass

| Stated bypass | Why it is not acceptable |
|---|---|
| "It's a little over the ceiling, I'll ignore the warning" | A soft ceiling can be exceeded with a stated reason — silently ignoring it without one is the bypass, not the length itself. |
| "I'll just reuse this basename, it's a different folder" | Basename uniqueness is case-insensitive and tree-wide by design (the GitHub Wiki URL convention) — folder separation doesn't help. |
| "This page covers two modes because splitting it felt awkward" | Single-mode-per-page is structural, not a style call — split it. |

### Enforcement

Before committing a wiki change, check:

1. Does every new/edited page declare exactly one mode (or `index`, if it's a landing page)?
2. If a soft length-ceiling warning fires, is there a stated reason to keep the content, or should it be split?
3. Does the new page's basename collide with an existing one anywhere in the tree?

`check-wiki.py --strict` is the deterministic answer to all three — run it, don't guess.

## See also

- [`reference/gate-inventory.md`](../reference/gate-inventory.md) — where `check-wiki` sits in the full gate battery.
