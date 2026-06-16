# How to simplify code with /simplify

> [!NOTE]
> **Goal:** Run a targeted simplification pass over a diff, file, or directory — reduce accidental complexity without removing load-bearing structure.
> **Prereqs:** the `code-review` plugin installed ([Install crickets plugins](Install-Into-Project)); `git`.

`/simplify` is distinct from `/code-review`. `/code-review` hunts for bugs. `/simplify` hunts for accidental complexity — code that is harder to read, longer, or more indirected than the behavior requires. It applies Chesterton's Fence (understand why code exists before removing it) and the Rule of 500 (long functions and files are signals, not violations) to produce a rationalization table before it changes anything.

## Steps

1. **Invoke the command** with a target — or none, to simplify the working-tree diff:

   ```text
   /simplify                  # uncommitted working-tree diff (git diff HEAD)
   /simplify src/auth.py      # a single file
   /simplify src/             # a directory
   /simplify main...HEAD      # a commit range
   ```

2. **Read the rationalization table.** Before touching anything, `/simplify` produces a table with one row per candidate:

   | Location | Candidate | Chesterton check | Rule of 500 signal | Verdict |
   |---|---|---|---|---|
   | `file.py:42` | 3-layer wrapper | Unknown origin | function is 12 lines | investigate |
   | `util.py:88` | duplicate helper | Confirmed dead | — | remove |

   The Chesterton check column is the key column: if the origin of a piece of code is unknown, the verdict is `investigate`, not `remove`.

3. **Confirm or reject** the proposed changes. `/simplify` reports; it does not apply changes without your confirmation.

4. **After applying**, re-run any affected tests to confirm nothing behavioral changed:

   ```bash
   python3 -m pytest          # or your project's test runner
   ```

## When to use it

Run `/simplify` **after a feature lands**, not before — you need the tests green first so the simplification pass can confirm it didn't change behavior. Typical moments:

- After a sprint of fast feature work that accumulated debt
- After a refactor that left scaffolding behind
- Before opening a PR, to keep the diff reviewable

**Do not run `/simplify` instead of `/code-review`** — they are complementary. `/code-review` finds bugs; `/simplify` finds complexity. Run both.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Candidate marked `investigate` — you think it's safe to remove | Chesterton check is uncertain | Grep for callers (`grep -rn 'function_name' src/`); if genuinely dead, remove and confirm |
| Rule of 500 flags a long file that's intentionally long | Long ≠ wrong; the rule is a signal | Override: mark the finding as `load-bearing` in the reconciliation; the command skips it |
| Simplification breaks a test | Behavioral change slipped through | Revert the specific change; report via a `/code-review` pass to confirm the invariant |

## See also

- [Review a change for bugs](Use-Code-Review) — `/code-review` for adversarial bug-finding
- [In-flight decision review](Use-Doubt-Review) — `/doubt` for pre-commit decisions
- [Why adversarial review](Why-Adversarial-Review) — the adversarial framing behind the `code-review` plugin
- [Install crickets plugins](Install-Into-Project) — get the `code-review` plugin onto your host
