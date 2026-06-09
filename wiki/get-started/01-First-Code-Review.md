<!-- mode: tutorial -->
# Installing and using the code-review plugin

> [!NOTE]
> **Goal:** Install the `code-review` plugin and run an adversarial review that catches a bug you planted — seeing, end to end, what a crickets plugin does in your editor.
> **Time:** ~10 minutes.
> **Prereqs:** Claude Code (`claude`) on your PATH; `git`. Optional: `gemini` on your PATH for the cross-model reviewer — the tutorial works without it.

You'll install one plugin, plant an obvious bug in a throwaway repo, and let `/code-review` find it. By the end you'll know how a crickets command lands in your host and what "adversarial review" actually returns.

## Step 1 — Install the code-review plugin

Add the crickets marketplace and install the plugin — it's standalone, so nothing else is needed:

```bash
claude plugin marketplace add alexherrero/crickets
claude plugin install code-review@crickets
```

Confirm it's enabled:

```bash
claude plugin list
```

You should see `code-review`. (On Antigravity the install is by path instead — see [Install crickets plugins](Install-Into-Project).)

## Step 2 — Plant a bug in a scratch repo

Create a throwaway repo whose one function contradicts its own docstring:

```bash
SCRATCH=$(mktemp -d) && cd "$SCRATCH" && git init -q
git commit -q --allow-empty -m "init"   # establish a baseline to diff against
cat > lists.py <<'PY'
def last_n(items, n):
    """Return the LAST n items of the list, in order."""
    return items[:n]   # bug: this returns the FIRST n
PY
git add lists.py
```

The staged change to `lists.py` is what the reviewer will see: the docstring promises the *last* `n`, the code returns the *first* `n`.

## Step 3 — Run the review

Open the scratch repo in Claude Code:

```bash
claude
```

In the session, run the command with no arguments — that reviews your working-tree diff:

```
/code-review
```

It resolves the diff, then dispatches the adversarial reviewer (and the cross-model reviewer first, if `gemini` is present).

## Step 4 — Read the finding

Each reviewer returns exactly one of three things: a **failing test**, a **`DEFECT: path:line`** (expected vs actual behavior + a minimal reproducer), or **`NO ISSUES FOUND`**. For your planted bug, expect a `DEFECT` on `lists.py` noting that `last_n([1, 2, 3], 2)` returns `[1, 2]` when the docstring promises `[2, 3]`.

Notice what it does *not* do: it reports, it never edits. The fix is yours.

## Step 5 — Fix it and re-review

Change the slice in `lists.py` so the code matches the docstring:

```python
def last_n(items, n):
    """Return the LAST n items of the list, in order."""
    return items[-n:]   # fixed
```

Run `/code-review` again. With the contradiction gone, you should get **`NO ISSUES FOUND`** instead of a defect.

## Step 6 — Clean up

```bash
rm -rf "$SCRATCH"
```

## What you learned

- **`code-review` is standalone** — `/code-review` reviews any diff or PR with no `/work` cycle. No argument means the working-tree diff; pass a range (`main...HEAD`), a branch, or a PR (`#123`) to review something else.
- **The review is adversarial** — the reviewer is primed to assume bugs exist, so it returns a *failing test*, a *`DEFECT: file:line`*, or *`NO ISSUES FOUND`* — never vague "looks good" prose ([why that matters](Why-Adversarial-Review)).
- **It reports, never fixes** — standalone, the fix is yours; inside a `/work` loop it becomes a follow-up task.
- **A cross-model reviewer** runs first when `gemini` is present, to escape the same-model echo chamber; without it, the in-process reviewer runs alone.

## Next

- [Run a standalone code review](Use-Code-Review) — the recipe form, once you've done this once.
- [Why adversarial review](Why-Adversarial-Review) — why "assume bugs exist" finds real ones a neutral pass misses.
- [Install more crickets plugins](Install-Into-Project) — the full six-plugin set and all three install modes.
