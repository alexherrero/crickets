#!/usr/bin/env python3
"""Tests for the voice kernel + on-demand genre demotion (PLAN-r3-voice-mechanism
task 3). Vault content, not repo-tracked — graceful-skips (skipUnless) when the
vault isn't reachable, matching test_check_slop.py's TestCorpusCalibration
pattern.

Addressing goes through `vault_layout`, the same resolver production uses, for
two reasons this suite learned the hard way. It had been resolving the config's
`vault_path` — the OBSIDIAN vault — and then joining agent-tree segments onto
it, landing a level too high; and it pinned `personal/` and `projects/`, two
retired memory- and project-space generations. Four of its six tests were
failing against a healthy vault. They never surfaced, because the suite skips
whenever no vault resolves and the gate battery deliberately isolates itself
from this machine's config — so the only place these could fire was a bare
local run nobody makes. `check-all.sh` now runs this module un-isolated as its
own step; it still skips cleanly in CI, which has no vault.

Never a hardcoded absolute literal — AGENTS.md's vault-path convention.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_CRICKETS_ROOT = _SCRIPTS.parent
_AGENTM_ROOT = Path(os.environ.get("AGENTM_REPO_ROOT", "").strip() or (_CRICKETS_ROOT.parent / "agentm"))

_RULE_PACK_SCRIPTS = (
    _CRICKETS_ROOT / "src" / "wiki" / "skills" / "diataxis-author" / "scripts"
)
if str(_RULE_PACK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RULE_PACK_SCRIPTS))
import style_resolver  # noqa: E402
import vault_layout  # noqa: E402

_PROSE_PASS_SCRIPTS = _CRICKETS_ROOT / "src" / "design" / "scripts"
if str(_PROSE_PASS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_PROSE_PASS_SCRIPTS))
import prose_pass  # noqa: E402

_KERNEL_MAX_LINES = 25
_KERNEL_NAME = "voice-kernel.md"
_DEMOTED_GENRE_SLUGS = ("docs-prose-style", "personal-comms-style",
                        "personal-narrative-style")

# The agent's MEMORY ROOT, not the Obsidian vault root — `vault_path` joined
# with `plugins.obsidian-vault.memory_root`. Everything below addresses agent
# content, so it hangs off this one.
_VAULT = vault_layout.resolve_memory_root()


def _kernel_body_lines(text: str) -> list[str]:
    parts = text.split("---\n", 2)
    body = parts[2] if len(parts) >= 3 else text
    return [ln for ln in body.splitlines() if ln.strip()]


@unittest.skipUnless(_VAULT is not None, "vault not reachable in this environment")
class TestVoiceKernel(unittest.TestCase):
    def test_kernel_is_locatable(self):
        """Found by the SAME lookup prose_pass uses, wherever it currently sits.

        This replaces an assertion that the kernel is a file at
        `_always-load/voice-kernel.md` carrying `always_load: true`. That is no
        longer where it lives: it graduated into the dated tree
        (`memory/2026/07/`) and is tagged `always-load-graduate`. Pinning the
        tier as the kernel's address is the very bug that had prose_pass
        running degraded, so the contract worth holding is "production can find
        it", not "it sits in one directory". Whether the tier SHOULD still hold
        it is a question about vault content, answered by
        test_the_always_load_tier_is_not_silently_empty below.
        """
        kernel = vault_layout.find_memory_entry(_VAULT, _KERNEL_NAME)
        self.assertIsNotNone(
            kernel, f"no {_KERNEL_NAME} anywhere in the memory space under {_VAULT}")
        self.assertTrue(kernel.is_file())

    def test_prose_pass_resolves_the_same_kernel(self):
        """The production consumer and this suite must agree on which file is
        the kernel — two lookups disagreeing is how a stale copy wins."""
        self.assertEqual(prose_pass.resolve_voice_kernel(_VAULT),
                         vault_layout.find_memory_entry(_VAULT, _KERNEL_NAME))

    def test_kernel_body_at_most_25_lines(self):
        kernel = vault_layout.find_memory_entry(_VAULT, _KERNEL_NAME)
        self.assertIsNotNone(kernel, f"no {_KERNEL_NAME} to measure")
        lines = _kernel_body_lines(kernel.read_text(encoding="utf-8"))
        self.assertLessEqual(
            len(lines), _KERNEL_MAX_LINES,
            f"{_KERNEL_NAME} body grew to {len(lines)} lines (> {_KERNEL_MAX_LINES}) — "
            f"genre detail is leaking into the always-on layer, per the design's own "
            f"re-audit trigger; move the detail to an on-demand genre file instead",
        )

    def test_the_kernel_reaches_at_least_one_live_consumer(self):
        """The voice floor must actually be delivered by SOMETHING.

        Two mechanisms can deliver it: the always-load tier, which recall.py
        globs flat and injects into every session, or prose_pass, which inlines
        it into every cross-model prose pass. Which one is a design choice —
        this kernel is tagged `always-load-graduate`, and the tier is currently
        empty, so on this vault delivery rests entirely on prose_pass.

        Asserting a specific mechanism would encode a guess about the operator's
        own content. Asserting that at least one works does not, and it is the
        check that would have caught the real defect: the kernel graduated out
        of the tier, prose_pass still probed only the tier, and the voice floor
        was reaching nothing at all while both halves looked individually fine.
        """
        in_tier = (vault_layout.always_load_dir(_VAULT) / _KERNEL_NAME).is_file()
        via_prose_pass = prose_pass.resolve_voice_kernel(_VAULT) is not None
        self.assertTrue(
            in_tier or via_prose_pass,
            f"{_KERNEL_NAME} is delivered by no live mechanism: absent from the "
            f"always-load tier AND unresolvable by prose_pass. The voice floor "
            f"reaches nothing.",
        )

    def test_three_heavy_files_absent_from_always_load(self):
        always_load = vault_layout.always_load_dir(_VAULT)
        for slug in _DEMOTED_GENRE_SLUGS:
            self.assertFalse(
                (always_load / f"{slug}.md").is_file(),
                f"{slug}.md should be demoted out of _always-load/ (task 3)",
            )

    def test_three_heavy_files_present_on_demand_not_always_loaded(self):
        wiki_style = vault_layout.global_wiki_style_dir(_VAULT)
        for slug in _DEMOTED_GENRE_SLUGS:
            matches = list(wiki_style.glob(f"*-{slug}.md"))
            self.assertTrue(matches, f"expected an on-demand {slug}.md under {wiki_style}")
            text = matches[0].read_text(encoding="utf-8")
            self.assertIn("always_load: false", text)
            self.assertIn(f"trigger: {slug}", text)


@unittest.skipUnless(_VAULT is not None, "vault not reachable in this environment")
class TestStyleResolverComposesDemotedGenre(unittest.TestCase):
    def test_resolves_docs_prose_style_as_a_global_lesson(self):
        resolved = style_resolver.resolve_style(vault_path=_VAULT)
        triggers = {lz.trigger for lz in resolved.lessons}
        self.assertIn("docs-prose-style", triggers,
                      f"style_resolver didn't resolve the demoted docs-prose-style "
                      f"lesson; got triggers: {triggers}")
        lesson = next(lz for lz in resolved.lessons if lz.trigger == "docs-prose-style")
        composed = style_resolver.compose_voice_block(resolved)
        self.assertIn("BASE VOICE", composed)
        self.assertIn(lesson.guidance[:40], composed)


@unittest.skipUnless(_VAULT is not None, "vault not reachable in this environment")
class TestRoleNounCarveOutWrittenInVaultStore(unittest.TestCase):
    """PLAN-r3-voice-mechanism task 5 verification 1, vault half."""

    def test_docs_prose_style_carries_the_carve_out_clause(self):
        matches = list(vault_layout.global_wiki_style_dir(_VAULT).glob("*-docs-prose-style.md"))
        self.assertTrue(matches, "expected the demoted docs-prose-style.md on-demand copy")
        content = matches[0].read_text(encoding="utf-8")
        self.assertIn("Role-noun carve-out", content)
        self.assertIn("legitimate role noun", content)


if __name__ == "__main__":
    unittest.main()
