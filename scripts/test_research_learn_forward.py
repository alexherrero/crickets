#!/usr/bin/env python3
"""Tests for src/research/scripts/learn_forward.py (crickets wave-c-research,
PLAN-wave-c-research-forward-learning task 1).

Integration-style (not mocked): exercises the real bridge to agentm's real
approved-source forward-learning pipeline
(harness/skills/memory/scripts/forward_learning.py, PLAN-wave-e-experience
task 1 -- confirmed shipped on agentm main before this plan activated, per
this plan's own re-verified unblock condition). learn-forward leans BY NAME
on that substrate rather than reimplementing it
(wiki/designs/crickets-research.md) -- this test proves the wiring end to
end, not a mocked Scheduler object (the plan's original guess, since
corrected: no such object exists in the real shape).

A fixture `fetcher` callable (matching agentm's own `run_forward_learning`
injection point) keeps the scan fully offline-deterministic -- no real
network call, same posture as agentm's own test_forward_learning.py.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "research" / "scripts"

# Same idiom as test_research_idea_search.py: agentm's forward_learning.py
# (and its own `from vault_lock import ...`) inserts its scripts dir onto
# sys.path and bare-imports siblings into sys.modules as a side effect of
# being loaded -- purged in tearDownClass so it doesn't leak into whatever
# test file runs next alphabetically.
#
# The leak runs the other way too: discovery imports every test file before
# any test runs, and several (test_vault_layout.py, the diataxis-author suites)
# load the wiki plugin's own vault_layout.py as `vault_layout`, a name agentm's
# forward_learning.py imports for its own module. Keeping the wiki's module
# from reaching agentm is agentm_bridge._load_module's job, so these tests go
# through it; test_research_agentm_bridge.py pins it without an agentm checkout.
_AGENTM_PATH_MARKERS = ("/agentm/harness/", "/agentm/scripts/")
_REAL_BRIDGE_SYS_PATH_MARKER = "/agentm/harness/skills/memory/scripts"


def _purge_real_bridge_sys_path():
    sys.path[:] = [p for p in sys.path if _REAL_BRIDGE_SYS_PATH_MARKER not in p]


def _purge_agentm_modules(pre_existing_names):
    for name, mod in list(sys.modules.items()):
        if name in pre_existing_names:
            continue
        f = getattr(mod, "__file__", None)
        if f and any(marker in f for marker in _AGENTM_PATH_MARKERS):
            del sys.modules[name]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


learn_forward = _load("research_learn_forward", _SRC / "learn_forward.py")


def _snapshot(vault: Path) -> dict:
    return {p.relative_to(vault).as_posix(): p.read_bytes() for p in vault.rglob("*") if p.is_file()}


def _fixture_fetcher(candidates_by_slug: dict):
    def fetcher(source):
        return candidates_by_slug.get(source.slug, [])
    return fetcher


class LearnForwardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._pre_existing_modules = set(sys.modules)
        learn_forward.agentm_bridge._reset_cache_for_tests()
        if learn_forward.agentm_bridge.load_forward_learning_module() is None:
            raise unittest.SkipTest("agentm sibling checkout unavailable -- real-bridge test skipped")

    @classmethod
    def tearDownClass(cls):
        _purge_real_bridge_sys_path()
        _purge_agentm_modules(cls._pre_existing_modules)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name) / "vault"
        self.vault.mkdir()
        # agentm keeps the fetch cache in its machine-scoped engine dir
        # (filing-v2 2a); a scan must never read this machine's real one.
        self._engine_env = mock.patch.dict(
            os.environ, {"AGENTM_STATE_DIR": str(Path(self._tmp.name) / "engine-state")})
        self._engine_env.start()
        fl = learn_forward.agentm_bridge.load_forward_learning_module()
        # The whitelist goes where the current agentm keeps it, in its own
        # project; the retired `standards/` spelling it still reads is agentm's
        # to test, not a home this suite leans on.
        sources_path = self.vault / "Projects" / "agentm" / "forward-learning-sources.json"
        sources_path.parent.mkdir(parents=True, exist_ok=True)
        sources_path.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "slug": "trusted-feed",
                            "kind": "idea",
                            "type": "feed",
                            "url": "https://example.com/trusted",
                            "trusted": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.fl = fl

    def tearDown(self):
        self._engine_env.stop()
        self._tmp.cleanup()

    def test_a_scan_cycle_produces_watchlist_entries(self):
        fetcher = _fixture_fetcher(
            {
                "trusted-feed": [
                    self.fl.Candidate(
                        slug="trusted-feed",
                        title="A genuinely new technique",
                        body=(
                            "trusted-feed describes a genuinely new technique worth adopting, "
                            "with enough detail here to clear the substantiveness floor."
                        ),
                        url="https://example.com/trusted/1",
                    )
                ]
            }
        )
        result = learn_forward.learn(self.vault, fetcher=fetcher, now=1_700_000_000.0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.written), 1)
        entry_text = result.written[0].read_text(encoding="utf-8")
        self.assertIn("evaluator_classification:", entry_text)

    def test_a_scan_cycle_touches_nothing_outside_the_watchlist_and_cache(self):
        fetcher = _fixture_fetcher(
            {
                "trusted-feed": [
                    self.fl.Candidate(
                        slug="trusted-feed",
                        title="A genuinely new technique",
                        body=(
                            "trusted-feed describes a genuinely new technique worth adopting, "
                            "with enough detail here to clear the substantiveness floor."
                        ),
                        url="https://example.com/trusted/1",
                    )
                ]
            }
        )
        pre = _snapshot(self.vault)
        learn_forward.learn(self.vault, fetcher=fetcher, now=1_700_000_000.0)
        post = _snapshot(self.vault)

        # A scan writes ONLY into the watchlist, and only into its current home,
        # `Projects/agentm/_watchlist`; the fetch cache sits in the engine state
        # dir setUp points at the scratch directory, outside the vault. The
        # watchlist's retired memory-space homes (`memory/`, `personal/`,
        # `personal-private/`) and the old `_meta/` cache count as stray writes:
        # agentm must not write there any more. The home is named here rather
        # than asked of agentm's watchlist_root(), so a resolver that hands back
        # a retired home fails this check instead of vouching for itself.
        watchlist = ("Projects", "agentm", "_watchlist")
        new_or_changed = {p for p in pre.keys() | post.keys() if pre.get(p) != post.get(p)}
        self.assertTrue(new_or_changed, "the scan wrote nothing, so this check would prove nothing")
        for rel in new_or_changed:
            self.assertEqual(
                Path(rel).parts[: len(watchlist)],
                watchlist,
                f"unexpected write outside Projects/agentm/_watchlist: {rel}",
            )

    def test_main_cli_smoke(self):
        # main() takes no fetcher, so stub agentm's default one; otherwise the
        # scan sends a real GET to the fixture source's URL.
        with mock.patch.object(self.fl, "default_fetcher", _fixture_fetcher({})):
            rc = learn_forward.main(["--vault-path", str(self.vault)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
