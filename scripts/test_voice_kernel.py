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
own step; it still skips cleanly in CI, which has no vault, and
`test_voice_kernel_layouts.py` runs it against scratch vaults there instead.

Then the kernel moved again. agentm-vault plan 05 (the memory-root trims,
2026-09-11) folded the pen's `voice-kernel.md` into the `## Voice` section of
`<vault>/standards/user-preferences.md` and deleted the old file. prose_pass
followed in #242; this suite kept looking for the old filename, so three of
its tests failed against a vault that had migrated cleanly. It now finds the
kernel in the same order prose_pass does — the preferences file first, the
retired filename behind it for a vault that never migrated — and measures
only the voice section, because the rest of that file is the operator's own.

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
# The kernel's home since the memory-root trims, and its section there.
_PREFERENCES_NAME = "user-preferences.md"
_VOICE_HEADING = "## Voice"
# The kernel's own file before them — what an unmigrated vault still holds.
_LEGACY_KERNEL_NAME = "voice-kernel.md"
_DEMOTED_GENRE_SLUGS = ("docs-prose-style", "personal-comms-style",
                        "personal-narrative-style")

# The agent's MEMORY ROOT, not the Obsidian vault root — `vault_path` joined
# with `plugins.obsidian-vault.memory_root`. Everything below addresses agent
# content, so it hangs off this one.
_VAULT = vault_layout.resolve_memory_root()


def _locate_kernel(root) -> Path | None:
    """The voice kernel's file: `standards/user-preferences.md` when the vault
    has one, else `voice-kernel.md` wherever it sits in the memory space."""
    standards = vault_layout.standards_dir_if_present(root)
    if standards is not None and (standards / _PREFERENCES_NAME).is_file():
        return standards / _PREFERENCES_NAME
    return vault_layout.find_memory_entry(root, _LEGACY_KERNEL_NAME)


def _always_load_tiers(root) -> list[Path]:
    """Every directory the session-start loader injects from, in its order:
    `standards/`, then the retired pen while it still exists. The loader reads
    the `*.md` at the top of each and never descends, so `standards/voice/`
    stays on demand. agentm's `vault_layout.always_load_dirs()` is its copy."""
    tiers = []
    standards = vault_layout.standards_dir_if_present(root)
    if standards is not None:
        tiers.append(standards)
    pen = vault_layout.resolve_existing_under_memory(root, "_always-load")
    if pen is not None:
        tiers.append(pen)
    return tiers


def _kernel_lines(text: str) -> list[str]:
    """The kernel's non-blank body lines. In the preferences file that is the
    `## Voice` section alone, up to the next heading at its level or above; a
    file with no such section, like the retired `voice-kernel.md`, is all kernel."""
    parts = text.split("---\n", 2)
    body = parts[2] if len(parts) >= 3 else text
    lines = body.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip() == _VOICE_HEADING), None)
    if start is not None:
        section = []
        for ln in lines[start + 1:]:
            if ln.startswith(("# ", "## ")):
                break
            section.append(ln)
        lines = section
    return [ln for ln in lines if ln.strip()]


@unittest.skipUnless(_VAULT is not None, "vault not reachable in this environment")
class TestVoiceKernel(unittest.TestCase):
    def test_kernel_is_locatable(self):
        """Found by the vault's own layout, wherever it currently sits.

        The kernel has had three addresses: a file at
        `_always-load/voice-kernel.md`; the same file in the dated tree
        (`memory/2026/07/`) once it graduated out of the tier; and, since the
        memory-root trims, the `## Voice` section of
        `standards/user-preferences.md`, with `voice-kernel.md` deleted. Pinning
        any one address is how first prose_pass and then this suite lost the
        kernel, so the contract worth holding is "production can find it", not
        "it sits in one place".
        """
        kernel = _locate_kernel(_VAULT)
        self.assertIsNotNone(
            kernel,
            f"no voice kernel under {_VAULT}: no {_PREFERENCES_NAME} in standards/ "
            f"and no {_LEGACY_KERNEL_NAME} anywhere in the memory space")
        self.assertTrue(kernel.is_file())

    def test_prose_pass_resolves_the_same_kernel(self):
        """The production consumer and this suite must agree on which file is
        the kernel — two lookups disagreeing is how a stale copy wins."""
        self.assertEqual(prose_pass.resolve_voice_kernel(_VAULT), _locate_kernel(_VAULT))

    def test_kernel_body_at_most_25_lines(self):
        kernel = _locate_kernel(_VAULT)
        self.assertIsNotNone(kernel, "no voice kernel to measure")
        lines = _kernel_lines(kernel.read_text(encoding="utf-8"))
        self.assertLessEqual(
            len(lines), _KERNEL_MAX_LINES,
            f"the voice kernel in {kernel.name} grew to {len(lines)} lines "
            f"(> {_KERNEL_MAX_LINES}) — genre detail is leaking into the always-on "
            f"layer, per the design's own re-audit trigger; move the detail to an "
            f"on-demand genre file instead",
        )

    def test_the_kernel_reaches_at_least_one_live_consumer(self):
        """The voice floor must actually be delivered by SOMETHING.

        Two mechanisms can deliver it: the always-load tier, which recall.py
        globs flat and injects into every session, or prose_pass, which inlines
        it into every cross-model prose pass. Which one is a design choice. The
        graduated kernel sat outside the tier and rested on prose_pass alone;
        since the memory-root trims it sits at the top of `standards/`, so on a
        migrated vault both deliver it.

        Asserting a specific mechanism would encode a guess about the operator's
        own content. Asserting that at least one works does not, and it is the
        check that would have caught the real defect: the kernel graduated out
        of the tier, prose_pass still probed only the tier, and the voice floor
        was reaching nothing at all while both halves looked individually fine.
        """
        kernel = _locate_kernel(_VAULT)
        in_tier = kernel is not None and kernel.parent in _always_load_tiers(_VAULT)
        via_prose_pass = prose_pass.resolve_voice_kernel(_VAULT) is not None
        self.assertTrue(
            in_tier or via_prose_pass,
            "the voice kernel is delivered by no live mechanism: absent from the "
            "always-load tier AND unresolvable by prose_pass. The voice floor "
            "reaches nothing.",
        )

    def test_three_heavy_files_absent_from_always_load(self):
        """Absent from the top of every tier directory, under the pen's bare
        slug or the voice library's dated name — either one there would be
        injected into every session again."""
        for tier in _always_load_tiers(_VAULT):
            for slug in _DEMOTED_GENRE_SLUGS:
                leaked = sorted(tier.glob(f"{slug}.md")) + sorted(tier.glob(f"*-{slug}.md"))
                self.assertFalse(
                    leaked,
                    f"{slug} should be demoted out of the always-load tier (task 3); "
                    f"found {[p.name for p in leaked]} in {tier}",
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
