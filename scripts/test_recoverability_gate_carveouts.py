#!/usr/bin/env python3
"""Content-conformance guard for the recoverability-gate autonomy doctrine.

The autonomy doctrine (PLAN-developer-workflows-autonomy-autonomy-doctrine)
relaxes the *confirmation* gate on recoverable actions, but it explicitly leaves
three carve-outs untouched and keeps a load-bearing recoverable/unrecoverable
*classification body*. A future edit that quietly relaxes either — say, dropping
the mandatory `pii-scrubber` from the block, stripping the no-`Co-Authored-By`
rule from work.md's commit step, or flipping the `When uncertain, treat as
unrecoverable` default — could still pass the byte-identity drift test (the three
block copies stay identical to *each other*) while silently widening autonomy
past the locked design. This test is the complementary guard: it asserts the
doctrine's content is present in the shipped sources, not merely mutually
consistent.

Carve-outs (must stay un-relaxed):

  1. Worker-tree initiation stays operator-initiated — `/spawn-worker` +
     `/integrate-worker` keep their "Operator-initiated only" language and their
     per-file *negative-polarity* prohibition ("Never spawn a worktree
     autonomously" / "Never integrate a worker autonomously"), and the doctrine
     block names them as unchanged.
  2. The PII pre-push hook + `pii-scrubber` invocation stay mandatory — named in
     the block's carve-out clause in every execution command.
  3. The no-`Co-Authored-By` commit rule is intact — in the block's carve-out
     clause AND in work.md's standing commit-step instruction (the real
     enforcement point, outside the block, which the drift test does not cover).

Classification body (must stay un-relaxed) — the gate is recoverability not
destructiveness, the `When uncertain, treat as unrecoverable` default stands,
and the unrecoverable set (force-push of published shared history, sole-ref
delete of unmerged work, published-tag overwrite, immutable publish/deploy/
migration) still resolves to stop+confirm. Carve-out and body fragments are
matched against the *extracted block* (not the whole file), so an in-block
removal can't be masked by an out-of-block decoy.

It also asserts each execution command carries the doctrine block. Together with
the byte-identity drift test, this proves the doctrine relaxed only what it meant
to — including against a relaxation applied *uniformly* to all three copies,
which the drift test alone is blind to.

Auto-discovered by check-all's `unit tests` gate (`unittest discover -p
'test_*.py'`) — no new top-level gate; the gate count is unchanged.

Tasks 3 + 6 of PLAN-developer-workflows-autonomy-autonomy-doctrine. Task 6 (the
body-conformance test + the extracted-block / negative-polarity hardening) was
added after the task-1–5 /review surfaced the uniform-relaxation gap.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CMDS = _ROOT / "src" / "development-lifecycle" / "commands"

# The execution commands that carry the inlined doctrine block.
_EXECUTION = ("release.md", "work.md", "bugfix.md")

_BEGIN = "<!-- BEGIN recoverability-gate"
_END = "<!-- END recoverability-gate -->"

# Load-bearing carve-out fragments that MUST appear (verbatim) in the doctrine
# block of every execution command. Removing any is a relaxation, not a reword.
_CARVEOUT_FRAGMENTS = (
    # Refined (worktree-per-plan plan, task 5): authority = explicit command OR
    # durable config opt-in; silent authority-free auto-spawn still forbidden.
    "Worker-tree initiation requires operator authority — either an explicit "
    "`/spawn-worker` command or a durable `isolation.mode: worktree-per-plan` "
    "config opt-in; silent authority-free auto-spawn stays forbidden",
    "the PII pre-push hook + `pii-scrubber` invocation stay mandatory",
    "the no-`Co-Authored-By` commit rule is untouched",
)

# Load-bearing *classification body* fragments — the recoverable/unrecoverable
# rows and the conservative default. The drift test proves the three copies stay
# identical to each other; the carve-out fragments prove the carve-outs survive.
# Neither pins the body, so a relaxation applied *uniformly* to all three copies
# (e.g. `treat as unrecoverable`→`treat as recoverable`, or deleting the
# Unrecoverable row) would pass both. These fragments close that gap: the gate is
# recoverability (not destructiveness), the conservative default stands, and the
# unrecoverable set still resolves to stop+confirm. (From the task-1–5 /review.)
_DOCTRINE_BODY_FRAGMENTS = (
    "recoverability, not destructiveness or blast-radius",
    "When uncertain, treat as unrecoverable",
    "**Announce + proceed** — no confirmation wait.",
    "**Stop + confirm** — pre-announce",
    "force-push rewriting **published shared** history",
    "sole-ref delete of unmerged work",
    "**published-tag** overwrite",
    "immutable publish / deploy / migration",
)

# Per-file authority markers: what each worktree command must say about
# initiation authority. spawn-worker gained config-opt-in as a second valid
# authority form (worktree-per-plan plan, task 5); integrate-worker stays
# operator-initiated-only (config opt-in does not auto-integrate).
_WORKTREE_AUTHORITY_MARKERS = {
    "spawn-worker.md": "Operator authority required.",
    "integrate-worker.md": "Operator-initiated only.",
}

# The worktree commands must keep a *negative-polarity* prohibition, per file.
# Asserting the bare substring `"autonomous"` is polarity-blind — it matches
# "spawn ... autonomously" just as well as "never spawn ... autonomously". Pin
# the actual prohibition sentence so an inversion fails the guard.
# spawn-worker: updated to "without operator authority" since config-opt-in is
# valid authority — "autonomously" alone would incorrectly reject config spawns.
_WORKTREE_NEGATIVE_POLARITY = {
    "spawn-worker.md": "Never spawn a worktree without operator authority",
    "integrate-worker.md": "Never integrate a worker autonomously",
}

# For spawn-worker, assert the config-opt-in path is positively named — pins
# the positive case: config opt-in IS operator authority, not just explicit cmd.
_SPAWN_WORKER_CONFIG_OPT_IN = "isolation.mode: worktree-per-plan"


def _read(name: str) -> str:
    return (_CMDS / name).read_text(encoding="utf-8")


def _extract_block(text: str) -> str:
    """Return the sentinel-anchored doctrine block, BEGIN..END inclusive.

    Matching content fragments against the *block* (not the whole file) closes
    the decoy hole: an in-block carve-out can't be gutted while a stray copy of
    the fragment elsewhere in the file keeps the assertion green. Raises (via
    str.index) if either sentinel is absent — a missing block is a hard failure.
    """
    start = text.index(_BEGIN)
    end = text.index(_END) + len(_END)
    return text[start:end]


class TestRecoverabilityGateCarveouts(unittest.TestCase):
    def test_each_execution_command_carries_the_block(self):
        for name in _EXECUTION:
            text = _read(name)
            self.assertIn(_BEGIN, text, f"{name} is missing the doctrine block (BEGIN sentinel)")
            self.assertIn(_END, text, f"{name} is missing the doctrine block (END sentinel)")

    def test_block_names_all_three_carveouts(self):
        for name in _EXECUTION:
            block = _extract_block(_read(name))
            for fragment in _CARVEOUT_FRAGMENTS:
                self.assertIn(
                    fragment,
                    block,
                    f"{name}'s doctrine block no longer states the carve-out: "
                    f"{fragment!r} — the doctrine must not relax it. (Matched "
                    f"against the extracted block, so an out-of-block decoy "
                    f"can't mask an in-block removal.)",
                )

    def test_block_states_the_recoverability_classification(self):
        # The drift test proves the copies match each other; the carve-out
        # fragments prove the carve-outs survive. Neither pins the body, so a
        # uniform relaxation across all three copies passes both. This closes
        # that gap by asserting the classification body in every extracted block.
        for name in _EXECUTION:
            block = _extract_block(_read(name))
            for fragment in _DOCTRINE_BODY_FRAGMENTS:
                self.assertIn(
                    fragment,
                    block,
                    f"{name}'s doctrine block no longer states: {fragment!r} — "
                    f"the recoverable/unrecoverable classification must not be "
                    f"relaxed (even uniformly across all three copies).",
                )

    def test_no_coauthored_by_rule_intact_in_work_commit_step(self):
        # The block names it, but the load-bearing enforcement is work.md's
        # commit step — outside the block, so the drift test does not cover it.
        text = _read("work.md")
        self.assertIn(
            "Do not add a `Co-Authored-By:` trailer",
            text,
            "work.md's commit step no longer forbids the Co-Authored-By trailer.",
        )

    def test_worktree_commands_stay_operator_initiated(self):
        # Per-file authority markers: spawn-worker gained config-opt-in as a
        # second valid form; integrate-worker stays operator-initiated-only.
        for name, marker in _WORKTREE_AUTHORITY_MARKERS.items():
            text = _read(name)
            self.assertIn(
                marker,
                text,
                f"{name} lost its authority constraint ({marker!r}).",
            )
            # Negative polarity — pin the prohibition sentence so an inversion
            # from "never" to "may" fails the guard.
            prohibition = _WORKTREE_NEGATIVE_POLARITY[name]
            self.assertIn(
                prohibition,
                text,
                f"{name} lost its prohibition ({prohibition!r}) — the worktree "
                f"carve-out must not be inverted from 'never' to 'may'.",
            )

        # Positive case: spawn-worker must name the config-opt-in authority path.
        # A test that only asserts the negative (silent spawn forbidden) without
        # asserting the positive (config opt-in IS valid) would allow a future
        # edit to silently remove the config path while keeping the prohibition.
        spawn_worker = _read("spawn-worker.md")
        self.assertIn(
            _SPAWN_WORKER_CONFIG_OPT_IN,
            spawn_worker,
            f"spawn-worker.md must name the config-opt-in authority path "
            f"({_SPAWN_WORKER_CONFIG_OPT_IN!r}) — the refined invariant permits "
            f"both explicit-command AND durable-config-opt-in as operator authority.",
        )


if __name__ == "__main__":
    unittest.main()
