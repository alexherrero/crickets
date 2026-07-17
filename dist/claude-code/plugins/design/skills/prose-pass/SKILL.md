---
name: prose-pass
description: Two-step cross-model prose pass for design docs and other authored prose — Gemini simplifies via the headless prose_pass.py script, then Claude verifies every fact-guard held and applies. The prose sibling of code-review's cross-review.sh.
kind: skill
supported_hosts: [claude-code, antigravity]
version: 0.2.0
---

You are applying the `prose-pass` skill: a two-step cross-model readability pass over a finished document. **Gemini simplifies, Claude verifies.** A simplification pass run by the model that wrote the prose is an echo chamber — it cannot see the sentences only the author can parse. A different model's read finds them; your job is to keep its edit honest.

This is the prose sibling of code-review's `cross-review.sh`, and the headless sibling of the `/design` command's interactive external-review handoff (see **Relationship to /design external review** below).

## When to run it

Run the pass on a document whose *content* is settled — a design doc at or near `Status: final`, a wiki page after a truth audit, any authored prose about to publish. The pass improves readability; it must never be the step that decides what the document says. Do not run it mid-authoring.

## Step 1 — Gemini simplifies (the script)

### Author the fact-guard list first

Before running anything, enumerate the specific truths in this document that a simplifier could plausibly invert — semantics that sound interchangeable to a reader who doesn't know the system. Three to eight lines, each a complete claim. From the proving run (2026-07-16, agentm's capture design):

- volatile decay only lowers retrieval rank — nothing is deleted
- inbox triage auto-applies, it is not a review gate
- re-audit triggers are conditions to revisit, never commitments
- single-operator system — no teams or users

The script refuses to run without a fact-guard list: the first un-guarded pass introduced exactly these inversions.

### Run the script

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_pass.py" path/to/doc.md \
  --fact-guard guards.txt \
  -o /tmp/doc.revised.md
```

The script assembles a four-block prompt — task header, your fact-guard list, the operator's voice pack (the always-load voice kernel plus the genre overlay, inlined verbatim from the vault), the document — and sends it to `agy` in one shot. For a genre other than design docs, point `--overlay` at the matching file under `projects/_global/wiki-style/`. The vault resolves at runtime; never pass a remembered absolute path.

| Exit | Meaning | What you do |
|---|---|---|
| 0 | revised document produced; structure verified | proceed to Step 2 |
| 1 | `agy` missing/unauthenticated, or voice pack unreachable | fall back to a Claude-only pass (below) |
| 2 | usage error, or structural contract violated twice | read stderr; fix the invocation or fall back |

On exit 1 or 2 the script prints a `PROSE-PASS-DEGRADED: ...` marker on stdout. Relay it verbatim — never paraphrase a degraded pass into a clean-sounding one.

The script already enforces structure mechanically: frontmatter, headings, table layout, the Document History section, and FACT-GUARD leakage (a guard line stapled into the document as new content, not just held as a truth) must come back clean, with one retry. What it cannot check is meaning — that is Step 2, and Step 2 is not optional.

If a call looks like a stream cutoff (`agy`'s print-mode misreading a literal `<thought>`/`<thinking>`/`<answer>` token in the document as its own reasoning-tag opener — a real failure mode, not hypothetical), the script does not just retry the identical call; it redirects to a section-by-section pass and reports on stderr which sections, if any, it had to leave unrevised. A stderr line naming that fallback is informational, not an error — check the diff same as any other run.

## Step 2 — Claude verifies and applies

Diff the revised document against the original, then work this checklist. Every item, every time:

1. **Fact-guards held — and not leaked as new content.** Re-read each guard line against the revised text. A guard that now reads "roughly equivalent" has drifted — restore the original sentence. Separately, check that no guard line got stapled into the document as its own new sentence: a real pass produced ~10 such insertions in one run, including the same guard verbatim in three places and a meta-sentence explaining what a re-audit trigger is. The FACT-GUARD list is verification context, not draftable prose — the script's own mechanical check catches most of this and retries, but a paraphrased insertion can still slip through.
2. **Spot-check technical claims against the code they describe.** Follow the revised text's claims into the implementation. The proving run caught Gemini asserting staging writes go through `save_entry` when the design's whole point is that they bypass it — plus a security overclaim. Plausible is not true.
3. **Operator-authored lines restored verbatim.** Hand-written sections must never be reworded, however awkward the simplifier found them. If you cannot tell whether a line is operator-authored, treat it as if it is.
4. **Banned-vocabulary scan.** Check the revision against the voice kernel's strip-on-sight list and the overlay's banned vocabulary.
5. **Table cells stayed terse; structures actually identical.** The script checked this mechanically — re-confirm on the diff before you overwrite anything.

Apply your corrections to the revised file. Then — and only then — deploy it over the original, and record the pass in the document's Document History: **one row per day, consolidated** (a second pass the same day amends that day's row rather than adding another).

## Fallback: the Claude-only pass

When the script exits 1, run the same discipline yourself: read the voice kernel and genre overlay from the vault, hold the fact-guard list in front of you, and make one simplification edit pass — improve existing sentences, never regenerate, structure untouched. You lose the cross-model read, not the standard. Say so in the Document History row ("Claude-only; agy unavailable").

## Relationship to /design external review

The `/design` command's *interactive* external-review handoff (transfer-context file → Antigravity/Gemini reshape → resume diff-review) is deferred to follow-on #5b — see the **External review is deferred (#5b)** section in `commands/design.md`. This skill is the *headless* sibling: one script call, one verify pass, no session handoff. It does not replace #5b and #5b does not replace it; when the interactive flow ships, the two share the fact-guard and voice-pack discipline defined here.

## No PII

This is a public repo pattern: the vault path is resolved at runtime (`--vault-path` → `$MEMORY_VAULT_PATH` → `.agentm-config.json`), never committed, never echoed into the revised document or the Document History row.
