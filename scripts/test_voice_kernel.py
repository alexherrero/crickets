#!/usr/bin/env python3
"""Tests for the voice kernel + on-demand genre demotion (PLAN-r3-voice-mechanism
task 3). Vault content, not repo-tracked — graceful-skips (skipUnless) when the
vault isn't reachable, matching test_check_slop.py's TestCorpusCalibration
pattern. Resolves the vault path via agentm_config.py (never a hardcoded
absolute literal — AGENTS.md's vault-path convention).
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_CRICKETS_ROOT = _SCRIPTS.parent
_AGENTM_ROOT = Path(os.environ.get("AGENTM_REPO_ROOT", "").strip() or (_CRICKETS_ROOT.parent / "agentm"))

_RULE_PACK_SCRIPTS = (
    _CRICKETS_ROOT / "src" / "wiki-maintenance" / "skills" / "diataxis-author" / "scripts"
)
if str(_RULE_PACK_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RULE_PACK_SCRIPTS))
import style_resolver  # noqa: E402

_KERNEL_MAX_LINES = 25


def _resolve_vault() -> Path | None:
    config_script = _AGENTM_ROOT / "scripts" / "agentm_config.py"
    if not config_script.is_file():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(config_script), "--get", "vault_path"],
            capture_output=True, text=True, timeout=10,
        )
    except OSError:
        return None
    vault_path = result.stdout.strip()
    if result.returncode != 0 or not vault_path:
        return None
    p = Path(vault_path)
    return p if p.is_dir() else None


_VAULT = _resolve_vault()


def _kernel_body_lines(text: str) -> list[str]:
    parts = text.split("---\n", 2)
    body = parts[2] if len(parts) >= 3 else text
    return [ln for ln in body.splitlines() if ln.strip()]


@unittest.skipUnless(_VAULT is not None, "vault not reachable in this environment")
class TestVoiceKernel(unittest.TestCase):
    def test_kernel_exists_and_is_always_load(self):
        kernel = _VAULT / "personal" / "_always-load" / "voice-kernel.md"
        self.assertTrue(kernel.is_file(), f"expected {kernel}")
        text = kernel.read_text(encoding="utf-8")
        self.assertIn("always_load: true", text)

    def test_kernel_body_at_most_25_lines(self):
        kernel = _VAULT / "personal" / "_always-load" / "voice-kernel.md"
        lines = _kernel_body_lines(kernel.read_text(encoding="utf-8"))
        self.assertLessEqual(
            len(lines), _KERNEL_MAX_LINES,
            f"voice-kernel.md body grew to {len(lines)} lines (> {_KERNEL_MAX_LINES}) — "
            f"genre detail is leaking into the always-on layer, per the design's own "
            f"re-audit trigger; move the detail to an on-demand genre file instead",
        )

    def test_three_heavy_files_absent_from_always_load(self):
        always_load = _VAULT / "personal" / "_always-load"
        for slug in ("docs-prose-style", "personal-comms-style", "personal-narrative-style"):
            self.assertFalse(
                (always_load / f"{slug}.md").is_file(),
                f"{slug}.md should be demoted out of _always-load/ (task 3)",
            )

    def test_three_heavy_files_present_on_demand_not_always_loaded(self):
        wiki_style = _VAULT / "projects" / "_global" / "wiki-style"
        for slug in ("docs-prose-style", "personal-comms-style", "personal-narrative-style"):
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


if __name__ == "__main__":
    unittest.main()
