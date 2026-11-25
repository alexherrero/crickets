---
name: create-it
description: "Make art, sound, a UI look or prose against a reference and prove it matches: spec with a reference folder and likeness list, size, direction check, make, measured asset checks, likeness then craft then voice passes, a done-report with paired images and a playtest checklist. Use for any asset or writing task graded against something that already exists."
---

**Usage:** `/create-it <what to make>  |  --spec <file>  |  --size small|medium|large  |  --prose`

You are running **create-it**: the whole loop for art, sound, UI look and prose, in one place. The loop is: **anchor → size → direction → make → free checks → focused passes → done-report.** It is `/build-it`'s sibling; where the two do the same thing this file says so and does not repeat it.

**Task from the user:** <what the user typed after /create-it>

> **Recommended model:** Sonnet 5.5 (`claude-sonnet-5-5`) for the making. The reviewers below pick their own models.

Judgment is yours: whether it looks, sounds or reads like the reference, what a finding means, what to redo. Everything a script can settle is one of these helpers:

| Helper | Where | Does |
|---|---|---|
| `spec_doc.py` | this plugin's `scripts/` | where the spec goes, whether it is well formed |
| `asset_checks.py` | this plugin's `scripts/` | measures a PNG or WAV and compares it to its reference |
| `loop_record.py` | this plugin's `scripts/` | the passes to run, each round's findings, when a pass stops, the done-report |
| `review_material.py`, `cross-review.sh` | the `code-review` plugin | what a reviewer is shown; the cross-model review |
| `prose_pass.py` | the `design` plugin | the cross-model voice pass over prose |

Reach another plugin's script with `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" <plugin> scripts/<file>`, for `code-review` (`review_material.py`, `cross-review.sh`) and `design` (`prose_pass.py`); it prints the path to run. **Exit 1** means that plugin is not installed: use the fallback named in the step, and say so. None of this needs agentm or a vault.

## Process

### 0. Set up

Slug: a short name. The record is `loop-<slug>.json` in the folder `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_doc.py" place --slug <slug> --plan <plan.md>` prints for the spec (add `--project-root <repo>` when there is no plan). Scratch files go in `${TMPDIR:-/tmp}/create-it-<slug>/`.

### 1. Anchor: the spec, the reference and the likeness list

The anchor is a spec with profile `create`: a **Reference** (the `reference/` folder the work is graded against) and a **Likeness list** of 5 to 10 lines, each one thing that must look, sound or read like the reference ("the outline is one pixel and dark", "the walk cycle has 8 frames", "sentences stay under 20 words"). Use `--spec <file>` if given, else the spec beside the plan, else run **`/spec`** and let the operator approve it once. In a run with no human, `/spec` cannot ask: stop and say the reference folder and likeness list are missing; there is nothing to match without them. Run `spec_doc.py check <spec>`; fix every line it prints before making anything.

### 2. Size

State it in one line with the reason. **small**: one touch-up to one asset. **medium**: one new asset. **large**: a set of assets, a new style, or a long piece of prose. `--size` overrides you. Then:

`loop_record.py init --record <record> --profile create --size <size> [--prose]`

Add `--prose` when the work is prose: it turns the voice pass on (`--no-voice` keeps it off). `loop_record.py passes --profile create --size <size> [--prose]` shows the order; small runs no review.

### 3. Direction check (medium and large)

Before making, write in at most 10 lines what you will make and which likeness lines each part answers. Save it as `direction.md` in the scratch folder, then run `review_material.py --files direction.md --contract-file <spec> --anchor <spec> --tier high` piped into `cross-review.sh --tier high`. Sort each finding (step 6's classes) and record it under the pass `direction`. A real finding that says the plan would not match the reference (the wrong likeness lines, the wrong medium or size) is a wrong direction: **stop and ask the operator**, even in the middle of `/work`. A real finding that is a detail inside a plan that otherwise stands: correct the plan, dispose the finding, and open the next direction round, with no stop. Do not start making until it is settled. When the operator goes ahead with a real finding still standing, record it with `loop_record.py decide --record <record> --pass direction --decision "<what they decided>"`. If `code-review` is absent, run the check yourself against the likeness list and say so.

### 4. Make

Make it. Keep every file in the folder the spec names. The spec's Not doing is a hard edge. Do not copy the reference: it is what the work is held to, not material. If the work grows past the size you stated, say so and re-size.

### 5. Free checks

For each made PNG or WAV: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/asset_checks.py" check <made> --reference <ref> --out-dir <scratch>/checks` (add `--grid 8x1` or `--frame-size 32x32` for a sprite sheet). It measures and lists differences; **exit 1 is a difference to look at, not an automatic fail**: a new colour may be what the spec asked for. Fix what is wrong, and record what is right.

- Record each pair: `loop_record.py pair --record <record> --reference <ref> --made <made>`.
- Record each Done-when line you have seen hold, with the evidence (the measurement, the file, the count): `loop_record.py requirement --record <record> --text "<line>" --status met --evidence "<what you saw>"`; `--status not-met` when it does not.
- Whatever `asset_checks.py` prints under `skipped` (a tool not installed, a format it does not read, a prose file it measured nothing of) goes in with `loop_record.py not-checked --record <record> --text "<what and why>"`. A prose file has no measurements: check the spec's countable lines (length, headings, required terms) yourself and say so.
- Add what only a person can judge to the playtest list, one line each: `loop_record.py playtest --record <record> --text "<what to try>"` (the walk loops without a hitch, the sound is not harsh on speakers, the page reads well on a phone).

A small task stops here: skip to step 7.

### 6. Focused passes

Run each pass in the order `loop_record.py passes` printed after `direction`: `likeness`, `craft`, then `voice` for prose. **One at a time, never in parallel.** Each pass is rounds: `loop_record.py open-round --record <record> --pass <name>`, review, sort and record each finding with its cited line (`loop_record.py add --record <record> --pass <name> --class <class> --line <path:LINE> --text "<finding>"`), fix, note what you did (`loop_record.py dispose --record <record> --pass <name> --round <n> --finding <i> --disposition "<what you did>"`), then `loop_record.py stop --record <record> --pass <name>`. **done** moves on; **continue** opens another round; **escalate** (exit 3, a real finding still standing in round 3) stops everything and hands the operator the open findings; record what they decide with `loop_record.py decide --record <record> --pass <name> --decision "<what they decided>"`. The classes: **real** is a place the work does not match, shown by a pair or a measurement; **tradeoff** is a difference the spec accepts; **misread** is a reviewer that got the reference or the line wrong (look again before saying so); **noise** is true and not worth changing.

**likeness** is Claude looking at the pictures. Dispatch the `evaluator` agent (it runs on model sonnet, read-only) with the paired images and the side-by-side image under `ARTIFACT:` (it can read images) and one rubric item per likeness-list line, "the made asset matches the reference on: <line>". Each FAIL is a finding; cite the likeness-list line (`<spec>:LINE`). Sound is judged from the spectrogram images and the measurements only: nobody has listened, so record that with `not-checked`, and the playtest list carries it to the operator.

**craft** is the technical quality: palette discipline, clean loops, clipping, frame consistency, file naming, or for UI and prose the structure. Write a contract file from the spec's Goal and Done-when plus the `asset_checks.py` output, build the material with `review_material.py --files <made files> --contract-file <contract> --anchor <spec> --tier default`, and pipe it into `cross-review.sh --tier default`. This reviewer reads text and measurements, never pixels or sound, so say so in the report (`not-checked`). If it prints `CROSS-REVIEW-DEGRADED:`, or `code-review` is absent, say so in one line and run the pass with a fresh read-only reviewer on model sonnet and the same material.

**voice** is for prose only, and runs on the `wording` tier: `python3 "$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sibling_plugin.py" design scripts/prose_pass.py)" <prose file> --fact-guard-text "<a truth the rewrite must not change>" --model "Gemini 4 Hydrogen (High)" -o <scratch>/voice.md`, with one fact-guard line per fact, number and name in the text and per spec Rule. Read the diff before accepting any of it. **A revision that comes back longer than the original is not accepted**; ask again or keep the original. Each change is a finding (cite the original's line): apply the ones that fix the voice, and record a rewrite that changed a fact as `misread`. If the script prints `PROSE-PASS-DEGRADED:`, or `design` is absent, say so in one line and do the pass yourself on model sonnet, with the same fact guards.

If `loop_record.py status` flags doubt theater, say so in the report rather than running more rounds.

### 7. Done-report

`loop_record.py report --record <record>` prints it: requirements met or not with evidence, every finding with what was done about it, Not checked, **Paired images** and a **Playtest checklist**. Then dispatch the `evaluator` agent (it runs on model sonnet) as the done-check, with the made files under `ARTIFACT:`, the spec under `ANCHOR:` and the record under `RECORD:`. On NEEDS_WORK fix what it names, record a `done-check` round, and ask again; the three-round limit applies.

Show the operator the report and the verdict, and ask them to play it through the checklist. **Feedback that is general** ("it feels floaty", "too clean") is not a finding: offer it as one new bullet for the spec's Likeness list, in the same one-thing-to-check style, and ask. If they agree, add it, keep the list at 10 lines or fewer (ask which line to swap when it is full), and run `spec_doc.py check <spec>` again. Never write "done" over a NOT MET requirement or an OPEN finding.

## Verification

- [ ] The spec has a Reference and 5 to 10 likeness lines, and `spec_doc.py check` passes.
- [ ] `asset_checks.py` ran on every PNG and WAV, and what it skipped is in Not checked.
- [ ] Each pass ran sequentially and ended `done` or was handed to the operator.
- [ ] Every finding has a class and a cited line; every real one has a disposition.
- [ ] The report shows the paired images, the playtest checklist and what was not checked.
