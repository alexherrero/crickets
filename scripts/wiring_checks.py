"""Shared checks for the wiring tests of the build-it / create-it loop commands.

A wiring test pins what a command's prose promises about the scripts it calls
(see test_prose_pass_wiring.py). The checks below are the ones every command of
the loop shares, so each wiring test says them once instead of growing its own
regex:

    unguarded_agentm_calls(text)   a call into agentm with no stated fallback
    dispatches_without_a_model(text)   an agent dispatch that names no model

Both work on the command's markdown. They read prose, so they are heuristics
with a deliberately narrow job: catch the regression where someone adds a call
and forgets its exit-code handling, or adds a dispatch and forgets the model.
Standard library only.
"""
from __future__ import annotations

import re
from typing import List

# Scripts that ask agentm (or the bridge to it) something. A command that must
# run with no agentm and no vault may mention one only with its fallback beside it.
AGENTM_CALLS = (
    "agentm_bridge.py", "project_homes.py", "resolve_plan.py", "process_seam.py",
    "harness_memory.py", "sibling_plugin.py",
)

# What "guarded" looks like in the paragraph that makes the call: the exit code
# it handles, or the word that says the step is skipped when agentm is absent.
_GUARD = re.compile(r"exit\s*(?:code\s*)?\d|\bskip(?:s|ped)?\b|\bno vault\b|\babsent\b|\bgraceful", re.IGNORECASE)

# An agent dispatch: the Agent tool, a sub-agent by name, or "dispatch ...".
_DISPATCH = re.compile(r"\bdispatch(?:es|ed)?\b|\bAgent tool\b|\bsub-?agent\b", re.IGNORECASE)
_MODEL = re.compile(
    r"\bmodel\b.{0,40}\b(?:sonnet|opus|haiku|fable)\b|\b(?:sonnet|opus|haiku|fable)\b.{0,40}\bmodel\b"
    r"|`model:\s*\"?(?:sonnet|opus|haiku|fable)\"?`|model=\"?(?:sonnet|opus|haiku|fable)",
    re.IGNORECASE)


def _paragraphs(text: str) -> List[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def unguarded_agentm_calls(text: str) -> List[str]:
    """Paragraphs that call an agentm script and say nothing about what happens
    when agentm is absent. Empty when every call has its fallback beside it."""
    bad = []
    for para in _paragraphs(text):
        if any(call in para for call in AGENTM_CALLS) and not _GUARD.search(para):
            bad.append(para.strip().splitlines()[0][:120])
    return bad


def dispatches_without_a_model(text: str) -> List[str]:
    """Paragraphs that dispatch an agent without naming the model it runs on."""
    bad = []
    for para in _paragraphs(text):
        if _DISPATCH.search(para) and not _MODEL.search(para):
            bad.append(para.strip().splitlines()[0][:120])
    return bad
