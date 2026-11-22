<!-- mode: tutorial -->
# Your first code review

> [!NOTE]
> **Goal:** Install the `development-lifecycle` and `code-review` plugins, plant a bug, and see what an adversarial review returns.
> **Time:** ~10 minutes.
> **Prereqs:** Claude Code (`claude`) on your PATH; `git`. Optional: `agy` on your PATH for the cross-model reviewer. The tutorial works without it.

You'll install two plugins, commit a bug in a throwaway repo, and let `/build-it --check` find it. By the end you'll know what an adversarial review returns and what it leaves to you.

## Step 1 — Install the plugins

`/build-it` ships in `development-lifecycle`; the reviewers it calls ship in `code-review`. Add the crickets marketplace and install both:

```bash
claude plugin marketplace add alexherrero/crickets
claude plugin install development-lifecycle@crickets
claude plugin install code-review@crickets
```

Confirm they're enabled:

```bash
claude plugin list
```

You should see `development-lifecycle` and `code-review`. (On Antigravity the install is by path instead; see [Install crickets plugins](Install-Crickets-Plugins).)

## Step 2 — Commit a bug in a scratch repo

Create a throwaway repo where one function contradicts its docstring, and commit it with a message stating what it should do:

```bash
SCRATCH=$(mktemp -d) && cd "$SCRATCH" && git init -q
git commit -q --allow-empty -m "init"   # a baseline to review against
cat > lists.py <<'PY'
def last_n(items, n):
    """Return the LAST n items of the list, in order."""
    return items[:n]   # bug: this returns the FIRST n
PY
git add lists.py
git commit -q -m "Add last_n: return the last n items of a list, in order"
```

The docstring and the commit message promise the *last* `n`; the code returns the *first* `n`.

## Step 3 — Run the review

Open the scratch repo in Claude Code:

```bash
claude
```

In the session, review the last commit:

```
/build-it --check HEAD~1..HEAD --size medium
```

`--check` reviews a change that already exists. A change judged `small` runs no review passes, so `--size medium` pins the size and the correctness pass runs. With no spec and no `AGENTS.md`, the commit message is the contract, and the report says so.

## Step 4 — Read the finding

The correctness pass returns a failing test, a `DEFECT: path:line`, or `NO ISSUES FOUND`. For your planted bug, expect a real finding cited to `lists.py:3`: `last_n([1, 2, 3], 2)` returns `[1, 2]` when the contract promises `[2, 3]`. You may see a second real finding too: `last_n` has no test that would catch a regression. The correctness pass counts that as real.

Each real finding reads **OPEN**. Check mode reports and never edits. The fix is yours.

## Step 5 — Fix it and re-review

Fix the slice, add a test, and commit:

```bash
cat > lists.py <<'PY'
def last_n(items, n):
    """Return the LAST n items of the list, in order."""
    return items[-n:]
PY
cat > test_lists.py <<'PY'
from lists import last_n

def test_last_n():
    assert last_n([1, 2, 3], 2) == [2, 3]
PY
git add lists.py test_lists.py
git commit -q -m "Fix last_n to return the last n items; add a test"
```

Run the review again over both commits:

```
/build-it --check HEAD~2..HEAD --size medium
```

With the contradiction fixed and a test added, the correctness pass should return no real finding.

## Step 6 — Clean up

```bash
rm -rf "$SCRATCH"
```

## What you learned

- **`/build-it --check` reviews a change already made:** a PR number, a commit range (`A..B`) or a diff file. It reports and never fixes.
- **The review is adversarial:** the reviewer assumes a bug exists and returns a *failing test*, a *`DEFECT: file:line`*, or *`NO ISSUES FOUND`* ([why that matters](Why-Adversarial-Review)). `/build-it` sorts each finding and cites it to a line.
- **The size picks the passes:** `small` runs none, `medium` runs correctness, `large` adds simplicity. `--size` overrides it.
- **A cross-model reviewer** runs when `agy` is present, to escape the same-model echo chamber; without it, a Sonnet reviewer runs the pass and the report says so.
- **Inside `/work`, the same passes run on every step,** and there the real findings get fixed before the step ends.

## Next

- [Review an existing change](Use-Code-Review): the recipe form, after your first run.
- [Why adversarial review](Why-Adversarial-Review): why "assume bugs exist" finds real ones a neutral pass misses.
- [Install more crickets plugins](Install-Crickets-Plugins): the full plugin set and all three install modes.
