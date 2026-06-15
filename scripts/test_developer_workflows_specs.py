#!/usr/bin/env python3
"""Structural specs for the developer-workflows phase commands (multi-plan writers).

These are grep-style assertions over the *source* spec prose in
`src/developer-workflows/commands/{work,plan,review}.md` — not unit tests of
Python. They lock the load-bearing facts the V5-10 "writers" plan introduced so a
later edit can't silently regress them:

  * `/work`, `/plan`, and `/review` resolve their on-disk pair by invoking
    `resolve_plan.py` (via `python3`, never `bash <pyfile>`) — they consume the
    agentm reader and never re-derive plan paths inline.
  * A uniform `--name <slug>` flag (LC-7) selects the named plan in all three
    commands — never a positional that could collide with a brief / branch /
    `task N`. Every plan read and progress append routes through the **resolved**
    pair, so a named plan writes `progress-<slug>.md`, never the shared singleton.
  * A bare invocation stays the byte-identical singleton (back-compat is the
    invariant), and a dangling binding hard-stops rather than silently falling
    back (Risk #7).

`generate.py check` (run by check-all.sh) separately proves `dist/` mirrors these
sources, so asserting the source spec is sufficient.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CMDS = _ROOT / "src" / "developer-workflows" / "commands"

# A .py file needs an interpreter; `bash <pyfile>` is the bug class these specs
# guard against (it survived only because the probe is graceful-skip).
_RESOLVE_PY = 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"'
_RESOLVE_BASH = 'bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_plan.py"'
_PROBE_BASH = 'bash "${CLAUDE_PLUGIN_ROOT}/scripts/capability_probe.py"'
_QUEUE_PY = 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/queue_status.py"'
_QUEUE_BASH = 'bash "${CLAUDE_PLUGIN_ROOT}/scripts/queue_status.py"'


def _read(name: str) -> str:
    return (_CMDS / name).read_text(encoding="utf-8")


class _NamedPlanWriterContract:
    """Assertions every named-plan-aware command spec must satisfy.

    A mixin (not a `TestCase`, so the loader never runs it directly); concrete
    subclasses set `cmd` and inherit the uniform contract. This is what makes the
    three commands a *uniform* surface — an edit that drops the contract from one
    of them fails here.
    """

    cmd: str = ""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(cls.cmd)

    def test_invokes_resolve_plan_via_python3_not_bash(self):
        # Consumes the agentm reader through the bridge — and via python3.
        self.assertIn("resolve_plan.py", self.text)
        self.assertIn(_RESOLVE_PY, self.text)
        self.assertNotIn(_RESOLVE_BASH, self.text)

    def test_consumes_does_not_reimplement_resolution(self):
        # The load-bearing user invariant: never re-derive plan paths inline.
        self.assertIn("never re-deriv", self.text)  # "re-derive" / "re-deriving"

    def test_name_flag_is_the_selector(self):
        # LC-7: one uniform `--name <slug>` flag selects the named plan in all
        # three commands (never a positional that could collide with a brief,
        # branch, commit range, or `task N`).
        self.assertIn("--name <slug>", self.text)

    def test_scoped_progress_never_singleton(self):
        # A named plan appends to progress-<slug>.md, never the shared singleton.
        self.assertIn("progress-<slug>.md", self.text)

    def test_bare_invocation_is_byte_identical_singleton(self):
        # Back-compat invariant: bare (no --name) == today's singleton behavior.
        self.assertIn("byte-identical", self.text)
        self.assertIn("singleton", self.text)

    def test_probe_uses_python3_not_bash(self):
        # Same bug class as the resolver: the capability probe is a .py file too.
        self.assertNotIn(_PROBE_BASH, self.text)


class TestWorkSpec(_NamedPlanWriterContract, unittest.TestCase):
    """`/work` resolves + works a named PLAN by consuming resolve_plan.py (T3, T4 retrofit)."""

    cmd = "work.md"

    def test_routes_reads_and_writes_through_resolved_pair(self):
        # Both the PLAN read and the progress append name the *resolved* pair.
        self.assertIn("resolved `PLAN.md`", self.text)
        self.assertIn("resolved `progress.md`", self.text)

    def test_preserves_task_selector(self):
        # `task N` still selects a specific task; the --name flag composes with it
        # (`/work --name <slug> task N` carries both).
        self.assertIn("task N", self.text)
        self.assertIn("selector keeps its meaning", self.text)

    def test_nonzero_exit_is_hard_stop_no_singleton_fallback(self):
        # Risk #7: a dangling binding hard-stops; it never silently falls back to
        # the singleton (which would bind the worker to the wrong plan).
        low = self.text.lower()
        self.assertIn("hard stop", low)
        self.assertIn("never fall back to the singleton", low)


class TestPlanSpec(_NamedPlanWriterContract, unittest.TestCase):
    """`/plan` can author a named PLAN-<slug>.md by consuming resolve_plan.py (T4)."""

    cmd = "plan.md"

    def test_authors_to_resolved_plan_path(self):
        # The PLAN write targets the resolved path — named PLAN-<slug>.md or
        # the singleton — never a re-derived one.
        self.assertIn("resolved `PLAN.md`", self.text)
        self.assertIn("PLAN-<slug>.md", self.text)


class TestReviewSpec(_NamedPlanWriterContract, unittest.TestCase):
    """`/review` reads the named pair by consuming resolve_plan.py (T4)."""

    cmd = "review.md"

    def test_reads_resolved_named_plan_for_task_context(self):
        # Review reads the resolved PLAN-<slug>.md for the task it's grading and
        # logs to the resolved progress.md.
        self.assertIn("resolved `PLAN-<slug>.md`", self.text)
        self.assertIn("resolved `progress.md`", self.text)


class TestQueueStatusLiteSpec(unittest.TestCase):
    """`/queue-status-lite` is the read-only read side of the multi-plan surface.

    Deliberately **not** a `_NamedPlanWriterContract` subclass: it takes no
    `--name`, resolves nothing inline, and writes nothing. It shells to the
    `queue_status.py` bridge and surfaces the bridge's dashboard verbatim. These
    specs lock that read-only contract so an edit can't quietly turn the glance
    into a gate.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = _read("queue-status-lite.md")

    def test_invokes_queue_status_via_python3_not_bash(self):
        # Same bug class the writer specs guard: a .py file needs an interpreter.
        self.assertIn("queue_status.py", self.text)
        self.assertIn(_QUEUE_PY, self.text)
        self.assertNotIn(_QUEUE_BASH, self.text)

    def test_surfaces_output_verbatim(self):
        # The command shows the bridge's render as-is; it never parses the rows.
        self.assertIn("verbatim", self.text.lower())

    def test_is_read_only_no_writer_tokens(self):
        # (b) Positively read-only, and free of the writer-phase mutation tokens:
        # no task-marking (`[x]`) and no scoped-progress write (`progress-<slug>.md`).
        low = self.text.lower()
        self.assertIn("read-only", low)
        self.assertIn("mutates no state", low)
        self.assertNotIn("[x]", self.text)               # never marks a task done
        self.assertNotIn("progress-<slug>.md", self.text)  # never writes progress
        self.assertNotIn("--name <slug>", self.text)       # not a named-plan selector

    def test_framed_as_coordinator_glance_not_gate(self):
        low = self.text.lower()
        self.assertIn("coordinator", low)
        self.assertIn("not a gate", low)

    def test_lands_in_both_host_command_surfaces(self):
        # (c) The command ships into both generated plugin trees. `generate.py
        # check` (in check-all) separately proves they are byte-identical to src.
        for host in ("antigravity", "claude-code"):
            p = (_ROOT / "dist" / host / "plugins" / "developer-workflows"
                 / "commands" / "queue-status-lite.md")
            self.assertTrue(p.is_file(), f"missing dist command for {host}: {p}")


class TestTagSerializationContracts(unittest.TestCase):
    """`/release` is the sole tag writer; `/work` and `/bugfix` must not create tags.

    Concurrent-release coordination guarantee: two plans landing simultaneously
    cannot race on tag creation because only `/release` tags `main` HEAD. These
    specs lock the behavioral contract so a future edit can't silently add tag
    creation to `/work` or `/bugfix`, or remove the sole-writer doc from `/release`.
    """

    @classmethod
    def setUpClass(cls):
        cls.work = _read("work.md")
        cls.bugfix = _read("bugfix.md")
        cls.release = _read("release.md")

    def test_work_does_not_create_tags(self):
        # /work must explicitly prohibit tag creation — not just be silent about it.
        low = self.work.lower()
        self.assertIn("do not create tags", low,
                      "/work must state it does not create tags")

    def test_bugfix_does_not_create_tags(self):
        low = self.bugfix.lower()
        self.assertIn("do not create tags", low,
                      "/bugfix must state it does not create tags")

    def test_release_is_sole_tag_writer(self):
        # /release must document that it is the sole tag writer in the loop.
        low = self.release.lower()
        self.assertIn("sole tag writer", low,
                      "/release must document the sole-tag-writer invariant")

    def test_release_documents_reaudit_trigger(self):
        # The escalation path (release-please/changesets) is the re-audit trigger
        # when the serialized-single-writer model's ceiling is reached.
        low = self.release.lower()
        self.assertIn("re-audit", low,
                      "/release must name the re-audit trigger for the single-writer model")
        self.assertIn("release-please", low,
                      "/release must name release-please as the escalation path")


if __name__ == "__main__":
    unittest.main()
