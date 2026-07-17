# How to run a cross-model prose pass

> [!NOTE]
> **Goal:** Simplify a finished design doc (or any authored prose) with a second model, then verify nothing drifted before deploying the result.
> **Prereqs:** the `design` plugin installed ([Install crickets plugins](Install-Into-Project)); the `agy` CLI authenticated; a vault configured with your voice pack (`agentm_config --vault-path`).

The pass is two steps: **Gemini simplifies, Claude verifies.** A simplification pass run by the model that wrote the prose is an echo chamber — it cannot see the sentences only the author can parse. The `prose-pass` skill sends the document to Gemini (via `agy`) for the readability edit, then your agent verifies every guarded fact held before anything overwrites the original. It is the prose sibling of code-review's `cross-review.sh`.

> [!NOTE]
> **Already automatic for design docs and wiki pages.** `/design author` runs this pass for you at Step 5 (ready-for-review) and again on review-pass entry — see [Author a design](Author-A-Design). The wiki `documenter` agent runs it on every drafted page before its preview. You don't need the steps below for either flow; they already fold the pass into their own Document History bookkeeping and report the fallback if `agy` degrades. Use this page to run the pass **by hand** on other prose — a README, a doc outside those two flows, or anything you're simplifying standalone.

## Steps

1. **Settle the content first.** Run the pass on a document whose meaning is final — a design at `Status: final`, a page after a truth audit. The pass improves readability; it never decides what the document says.

2. **Write the fact-guard list.** Three to eight lines, each a truth in this document that a simplifier could plausibly invert:

   ```text
   volatile decay only lowers retrieval rank — nothing is deleted
   inbox triage auto-applies, it is not a review gate
   re-audit triggers are conditions to revisit, never commitments
   ```

   The list is mandatory — the script refuses to run without it. The first un-guarded pass introduced exactly these inversions.

3. **Run the script:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_pass.py" wiki/designs/my-design.md \
     --fact-guard guards.txt \
     -o /tmp/my-design.revised.md
   ```

   The script assembles one prompt — task rules, your fact-guards, your voice pack inlined verbatim from the vault, the document — and sends it to `agy` in a single call. Structure is enforced mechanically: frontmatter, headings, table layouts, and the Document History section must come back byte-identical, with one retry before it gives up.

4. **Verify and apply.** Diff the revision against the original and work the `prose-pass` skill's checklist: every fact-guard held, technical claims spot-checked against the code they describe, operator-authored lines restored verbatim, banned vocabulary scanned. Apply corrections to the revised file.

5. **Deploy and record.** Only after the checklist passes, copy the revision over the original and add a row to the document's Document History — one row per day, consolidated.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `PROSE-PASS-DEGRADED: agy CLI unavailable` (exit 1) | `agy` missing or unauthenticated | Install/authenticate `agy`, or run the skill's Claude-only fallback pass |
| `PROSE-PASS-DEGRADED: vault unresolved` / `voice pack unresolved` (exit 1) | No vault path configured, or the voice files moved | `agentm_config --vault-path <path>`, or pass `--vault-path` / `--voice-kernel` / `--overlay` explicitly |
| `a FACT-GUARD list is required` (exit 2) | No guards passed | Write the guard list (step 2); it is not optional |
| `structural contract violated twice` (exit 2) | The model kept rewriting structure | Re-run; if it persists, pass sections separately or fall back to the Claude-only pass |
| Revision reads generic, voice gone | Overlay didn't match the genre | Point `--overlay` at the right file under `projects/_global/wiki-style/` |

## See also

- [Author a design](Author-A-Design) — write the document this pass polishes
- [Review a change — code review](Use-Code-Review) — the code sibling of this pass
- [Record an architectural decision](Record-An-Architectural-Decision) — where meaning changes go (never through this pass)
- [Manifest schema](Manifest-Schema) — skill primitive frontmatter reference
