#!/usr/bin/env python3
"""Tests for scripts/check-hook-parity.py — the .sh/.ps1 twin parity gate.

Most coverage exercises the pure logic (comment-stripping, the harness-reference
and workspace-resolution predicates, the per-pair violation rules) directly. Two
fixture classes build throwaway hook trees in a tmpdir to lock in the red/green
behavior of `scan()`/`main()`, and one test runs the gate against the REAL repo
so CI proves the live developer-safety twins stay paired.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _HERE / filename)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


chp = _load("check_hook_parity", "check-hook-parity.py")


# ── realistic twin snippets (kept tiny but structurally faithful) ────────────
_SH_RESOLVES = """#!/usr/bin/env bash
# kill-switch: halt when .harness/STOP exists
input=$(cat)
ws=$(printf '%s' "$input" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("workspacePaths",[d.get("cwd",".")])[0])')
cd "$ws" || exit 0
[ -f ".harness/STOP" ] && exit 2
exit 0
"""

_PS1_RESOLVES = """#!/usr/bin/env pwsh
# kill-switch (PowerShell twin)
$raw = [Console]::In.ReadToEnd()
$obj = $raw | ConvertFrom-Json
$ws = $obj.workspacePaths[0]
Set-Location -LiteralPath $ws
if (Test-Path -LiteralPath '.harness/STOP') { exit 2 }
exit 0
"""

# The bug: reads .harness but never resolves the workspace (bare cwd-relative).
_PS1_BARE = """#!/usr/bin/env pwsh
# kill-switch (PowerShell twin) — BROKEN: trusts cwd
if (Test-Path -LiteralPath '.harness/STOP') { exit 2 }
exit 0
"""

# A twin that never touches .harness at all → no resolution requirement fires.
_SH_NO_HARNESS = """#!/usr/bin/env bash
echo "nothing workspace-relative here"
exit 0
"""
_PS1_NO_HARNESS = """#!/usr/bin/env pwsh
Write-Output "nothing workspace-relative here"
exit 0
"""

# DEFECT 2: the bare cwd-relative bug DISGUISED by moving the resolution markers
# into an inline trailing comment. The markers (`workspacePaths`, and a dir-change
# verb) appear in the file text — but only inside a comment, so the code still
# never resolves the host workspace. Pre-fix these PASSED the gate (only full-line
# comments were stripped); post-fix they must FAIL it.
_PS1_DISGUISED = """#!/usr/bin/env pwsh
# kill-switch (PowerShell twin) — BROKEN: markers live only in the trailing comment
Set-Location $PSScriptRoot  # unrelated dir, not the workspace
if (Test-Path -LiteralPath '.harness/STOP') { exit 2 }  # workspacePaths resolved (a lie)
exit 0
"""

_SH_DISGUISED = """#!/usr/bin/env bash
# kill-switch (bash) — BROKEN: markers live only in the trailing comment
ref=".harness/STOP"  # workspacePaths read + cd done upstream (a lie)
test -f "$ref" && exit 2
exit 0
"""


def _make_hook(hooks_root: Path, name: str, *, sh: str | None = None, ps1: str | None = None) -> Path:
    d = hooks_root / name
    d.mkdir(parents=True)
    if sh is not None:
        (d / f"{name}.sh").write_text(sh, encoding="utf-8")
    if ps1 is not None:
        (d / f"{name}.ps1").write_text(ps1, encoding="utf-8")
    return d


# ── pure logic ───────────────────────────────────────────────────────────────
class TestStripComments(unittest.TestCase):
    def test_drops_full_line_comment(self):
        out = chp.strip_comments("# .harness in a comment\nreal code\n")
        self.assertNotIn(".harness", out)
        self.assertIn("real code", out)

    def test_drops_indented_full_line_comment(self):
        out = chp.strip_comments("    # workspacePaths note\ncode\n")
        self.assertNotIn("workspacePaths", out)

    def test_strips_inline_trailing_comment(self):
        # DEFECT 2: an inline trailing comment must be stripped too, so a marker
        # hidden in it (`workspacePaths`) no longer counts as resolution.
        out = chp.strip_comments("Set-Location $ws  # workspacePaths resolved\n")
        self.assertIn("Set-Location", out)         # the real code survives
        self.assertNotIn("workspacePaths", out)    # the comment marker is gone

    def test_preserves_code_before_inline_comment(self):
        # Stripping the comment must not eat the real code (incl. a `.harness` ref)
        # that precedes it on the same line.
        out = chp.strip_comments("Test-Path '.harness/STOP'  # trailing note\n")
        self.assertIn(".harness", out)
        self.assertNotIn("trailing note", out)

    def test_preserves_hash_inside_single_quotes(self):
        # A `#` inside a string literal is code, not a comment leader.
        out = chp.strip_comments("grep '#define' file\n")
        self.assertIn("#define", out)

    def test_preserves_hash_inside_double_quotes(self):
        out = chp.strip_comments('git commit -m "fix #123"\n')
        self.assertIn("#123", out)

    def test_preserves_hash_glued_to_token(self):
        # `$#` / `${x#prefix}` — a `#` not preceded by whitespace is not a comment
        # in either shell, so it must be left intact.
        out = chp.strip_comments("n=$#; v=${x#prefix}\n")
        self.assertIn("$#", out)
        self.assertIn("${x#prefix}", out)


class TestReferencesHarness(unittest.TestCase):
    def test_true_on_path(self):
        self.assertTrue(chp.references_harness("[ -f '.harness/STOP' ]"))

    def test_true_on_bare_token(self):
        self.assertTrue(chp.references_harness("cd .harness"))

    def test_false_when_absent(self):
        self.assertFalse(chp.references_harness("echo hello"))

    def test_word_boundary_not_a_substring(self):
        # `.harnessed` is a different token and must not trip the guard.
        self.assertFalse(chp.references_harness("echo .harnessed"))


class TestResolvesWorkspace(unittest.TestCase):
    def test_sh_needs_both_markers(self):
        self.assertTrue(chp.resolves_workspace('d["workspacePaths"]; cd "$ws"', "sh"))

    def test_sh_key_without_cd_fails(self):
        self.assertFalse(chp.resolves_workspace('d["workspacePaths"]', "sh"))

    def test_sh_cd_without_key_fails(self):
        self.assertFalse(chp.resolves_workspace('cd "$ws"', "sh"))

    def test_cd_is_not_a_substring_match(self):
        # `abcd` / `discarded` must not satisfy the `cd` verb requirement.
        self.assertFalse(chp.resolves_workspace('workspacePaths; abcd; discarded', "sh"))

    def test_ps1_needs_both_markers(self):
        self.assertTrue(chp.resolves_workspace('$obj.workspacePaths[0]; Set-Location $ws', "ps1"))

    def test_ps1_key_without_setlocation_fails(self):
        self.assertFalse(chp.resolves_workspace('$obj.workspacePaths[0]', "ps1"))

    def test_ps1_does_not_accept_cd_alias(self):
        # `cd` is a PowerShell alias for Set-Location, but the static check wants
        # the explicit cmdlet — an alias would dodge a grep-based audit. The .ps1
        # twins use Set-Location; pin that the gate insists on it.
        self.assertFalse(chp.resolves_workspace('$obj.workspacePaths[0]; cd $ws', "ps1"))


class TestTwinViolations(unittest.TestCase):
    def test_clean_pair_resolves(self):
        self.assertEqual(chp.twin_violations("k", _SH_RESOLVES, _PS1_RESOLVES), [])

    def test_clean_pair_no_harness(self):
        # Neither twin references .harness → nothing to resolve, parity-clean.
        self.assertEqual(chp.twin_violations("k", _SH_NO_HARNESS, _PS1_NO_HARNESS), [])

    def test_ps1_reads_harness_without_resolving_is_flagged(self):
        v = chp.twin_violations("kill-switch", _SH_RESOLVES, _PS1_BARE)
        self.assertEqual(len(v), 1)
        self.assertIn("kill-switch", v[0])
        self.assertIn(".ps1", v[0])

    def test_missing_ps1_twin_is_flagged(self):
        v = chp.twin_violations("steer", _SH_RESOLVES, None)
        self.assertEqual(len(v), 1)
        self.assertIn("missing .ps1 twin", v[0])

    def test_missing_sh_twin_is_flagged(self):
        v = chp.twin_violations("steer", None, _PS1_RESOLVES)
        self.assertEqual(len(v), 1)
        self.assertIn("missing .sh twin", v[0])

    def test_no_twins_at_all_is_flagged_once(self):
        v = chp.twin_violations("empty", None, None)
        self.assertEqual(len(v), 1)
        self.assertIn("no .sh or .ps1 twin", v[0])

    def test_doc_comment_mentioning_harness_does_not_trigger(self):
        # A .ps1 whose only .harness mention is a full-line comment must not be
        # forced to resolve the workspace — the comment is not code.
        ps1 = "#!/usr/bin/env pwsh\n# we check .harness/STOP elsewhere\nWrite-Output ok\n"
        self.assertEqual(chp.twin_violations("k", _SH_NO_HARNESS, ps1), [])

    # ---- DEFECT 2: the inline-comment disguise must not slip past the gate ----
    def test_ps1_disguised_by_inline_comment_is_flagged(self):
        # The bare cwd-relative bug dressed with an inline `# …workspacePaths…`
        # comment + an unrelated Set-Location. Pair with a clean .sh so the only
        # violation is the .ps1.
        v = chp.twin_violations("kill-switch", _SH_RESOLVES, _PS1_DISGUISED)
        self.assertEqual(len(v), 1, f"expected exactly the .ps1 violation, got {v}")
        self.assertIn("the .ps1 twin reads", v[0])

    def test_sh_disguised_by_inline_comment_is_flagged(self):
        # Symmetric: the same disguise in the .sh direction (bare cwd-relative read
        # + inline `# …workspacePaths… cd…` comment) must also be caught.
        v = chp.twin_violations("kill-switch", _SH_DISGUISED, _PS1_RESOLVES)
        self.assertEqual(len(v), 1, f"expected exactly the .sh violation, got {v}")
        self.assertIn("the .sh twin reads", v[0])


# ── fixture-based scan()/main() red/green ────────────────────────────────────
class TestScanFixtures(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_green_tree_scans_clean(self):
        _make_hook(self.root, "kill-switch", sh=_SH_RESOLVES, ps1=_PS1_RESOLVES)
        _make_hook(self.root, "steer", sh=_SH_NO_HARNESS, ps1=_PS1_NO_HARNESS)
        self.assertEqual(chp.scan(self.root), [])
        self.assertEqual(chp.main(["--hooks-root", str(self.root)]), 0)

    def test_red_tree_flags_the_bare_ps1(self):
        _make_hook(self.root, "kill-switch", sh=_SH_RESOLVES, ps1=_PS1_BARE)
        violations = chp.scan(self.root)
        self.assertEqual(len(violations), 1)
        self.assertEqual(chp.main(["--hooks-root", str(self.root)]), 1)

    def test_red_tree_flags_missing_twin(self):
        _make_hook(self.root, "steer", sh=_SH_RESOLVES)  # no .ps1
        self.assertEqual(chp.main(["--hooks-root", str(self.root)]), 1)

    def test_red_tree_flags_disguised_inline_comment_bug(self):
        # DEFECT 2 end-to-end: the disguised bug must drive a non-zero exit, not
        # slip through to a green gate.
        _make_hook(self.root, "kill-switch", sh=_SH_RESOLVES, ps1=_PS1_DISGUISED)
        self.assertEqual(len(chp.scan(self.root)), 1)
        self.assertEqual(chp.main(["--hooks-root", str(self.root)]), 1)

    def test_multiple_hooks_aggregate_violations(self):
        _make_hook(self.root, "kill-switch", sh=_SH_RESOLVES, ps1=_PS1_BARE)
        _make_hook(self.root, "steer", sh=_SH_RESOLVES)  # missing .ps1
        _make_hook(self.root, "commit-on-stop", sh=_SH_RESOLVES, ps1=_PS1_RESOLVES)  # clean
        self.assertEqual(len(chp.scan(self.root)), 2)

    def test_missing_root_is_noop_pass(self):
        # An absent hooks root is "nothing to check", not a failure.
        self.assertEqual(chp.main(["--hooks-root", str(self.root / "nope")]), 0)


# ── the live tree (CI's behavioral proof that the real twins stay paired) ────
class TestRealTree(unittest.TestCase):
    def test_real_developer_safety_tree_passes(self):
        self.assertEqual(chp.scan(chp.HOOKS_ROOT), [],
                         "the real developer-safety .sh/.ps1 twins must stay paired")
        self.assertEqual(chp.main([]), 0)


if __name__ == "__main__":
    unittest.main()
