#!/usr/bin/env python3
"""Tests for resolve_install_order.py — the dependency-first install ordering
`bootstrap.sh` hands to `agy`, which resolves no cross-plugin deps itself.

Every fixture here is deliberately ADVERSARIAL about names: the dependent sorts
alphabetically BEFORE the plugin it requires. The shipped catalog happens to
sort the other way round (`development-lifecycle` precedes all six of its
dependents), so a test built only on real data would pass against plain
`sorted()` and prove nothing.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from resolve_install_order import CycleError, install_order, main, resolve_target, build_index  # noqa: E402

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "resolve_install_order.py"
_REAL_MARKETPLACE = _HERE.parent / "dist" / "claude-code" / ".claude-plugin" / "marketplace.json"
_DEFAULT_SET = _HERE.parent / "dist" / "default-set.json"


def mk(plugins: list[dict], renames: dict | None = None) -> dict:
    """A minimal marketplace render — only the keys this resolver reads."""
    out: dict = {"name": "crickets", "plugins": plugins}
    if renames:
        out["renames"] = renames
    return out


def plugin(name: str, *, requires: list[str] | None = None,
           capabilities: list[str] | None = None) -> dict:
    entry: dict = {"name": name}
    if requires:
        entry["dependencies"] = sorted(requires)
    if capabilities:
        entry["capabilities"] = list(capabilities)
    return entry


class TestAdversarialOrdering(unittest.TestCase):
    """The cases plain alphabetical order gets wrong."""

    def test_dependent_that_sorts_first_still_installs_second(self) -> None:
        market = mk([
            plugin("aardvark", requires=["zebra-power"]),
            plugin("zulu", capabilities=["zebra-power"]),
        ])
        self.assertEqual(install_order(market, ["aardvark", "zulu"]), ["zulu", "aardvark"])

    def test_transitive_chain_reverses_alphabetical_order(self) -> None:
        market = mk([
            plugin("alpha", requires=["mid-cap"]),
            plugin("mid", requires=["zeta-cap"], capabilities=["mid-cap"]),
            plugin("zeta", capabilities=["zeta-cap"]),
        ])
        self.assertEqual(install_order(market, ["alpha", "mid", "zeta"]),
                         ["zeta", "mid", "alpha"])

    def test_independent_plugins_stay_alphabetical(self) -> None:
        """Dependency order where declared; alphabetical (deterministic) where not."""
        market = mk([plugin("c"), plugin("a"), plugin("b")])
        self.assertEqual(install_order(market, ["c", "a", "b"]), ["a", "b", "c"])

    def test_input_order_does_not_change_the_result(self) -> None:
        market = mk([
            plugin("aardvark", requires=["zebra-power"]),
            plugin("zulu", capabilities=["zebra-power"]),
        ])
        self.assertEqual(install_order(market, ["zulu", "aardvark"]),
                         install_order(market, ["aardvark", "zulu"]))


class TestCapabilityResolution(unittest.TestCase):
    """A `requires:` names a capability, which need not be a plugin's own name."""

    def test_capability_name_differs_from_the_directory_name(self) -> None:
        """`code-review`-shaped: the provider declares a capability only."""
        market = mk([
            plugin("apples", requires=["adversarial-review"]),
            plugin("code-review", capabilities=["adversarial-review"]),
        ])
        self.assertEqual(install_order(market, ["apples", "code-review"]),
                         ["code-review", "apples"])

    def test_old_capability_name_of_a_renamed_plugin_still_resolves(self) -> None:
        """The declare-both-names rename mechanism (crickets-composition.md):
        `maintenance` still answers to `github-ci`, so an old `requires:` holds."""
        market = mk([
            plugin("alpha", requires=["github-ci"]),
            plugin("maintenance", capabilities=["github-ci", "ci-repair", "maintenance"]),
        ])
        self.assertEqual(install_order(market, ["alpha", "maintenance"]),
                         ["maintenance", "alpha"])

    def test_marketplace_rename_chain_resolves_through_both_hops(self) -> None:
        """`status-line-meter` -> `token-audit` -> `tokens`, with the final
        plugin declaring neither old name as a capability."""
        market = mk(
            [plugin("alpha", requires=["status-line-meter"]), plugin("tokens")],
            renames={"status-line-meter": "token-audit", "token-audit": "tokens"},
        )
        self.assertEqual(install_order(market, ["alpha", "tokens"]), ["tokens", "alpha"])

    def test_a_plugin_slug_wins_over_another_plugin_declaring_that_name(self) -> None:
        market = mk([
            plugin("alpha", requires=["privacy"]),
            plugin("privacy", capabilities=["pii"]),
            plugin("impostor", capabilities=["privacy"]),
        ])
        index = build_index(market)
        self.assertEqual(resolve_target("privacy", index, {"privacy", "impostor"}), "privacy")

    def test_ambiguous_capability_prefers_a_provider_in_the_install_set(self) -> None:
        market = mk([
            plugin("gdrive-store", capabilities=["storage-backend"]),
            plugin("sqlite-store", capabilities=["storage-backend"]),
        ])
        index = build_index(market)
        self.assertEqual(resolve_target("storage-backend", index, {"sqlite-store"}),
                         "sqlite-store")


class TestDegradedInputs(unittest.TestCase):
    """Edges that cannot be honored are dropped; only a cycle is fatal."""

    def test_edge_pointing_outside_a_curated_set_is_dropped(self) -> None:
        market = mk([
            plugin("aardvark", requires=["zebra-power"]),
            plugin("zulu", capabilities=["zebra-power"]),
        ])
        self.assertEqual(install_order(market, ["aardvark"]), ["aardvark"])

    def test_unresolvable_requires_is_dropped_not_fatal(self) -> None:
        market = mk([plugin("aardvark", requires=["nothing-provides-this"])])
        self.assertEqual(install_order(market, ["aardvark"]), ["aardvark"])

    def test_plugin_missing_from_the_marketplace_is_still_installed(self) -> None:
        market = mk([plugin("known")])
        self.assertEqual(install_order(market, ["known", "unknown"]), ["known", "unknown"])

    def test_empty_set(self) -> None:
        self.assertEqual(install_order(mk([plugin("a")]), []), [])


class TestCycles(unittest.TestCase):
    """Loud, never a quiet fallback to alphabetical."""

    def test_two_plugin_cycle_raises(self) -> None:
        market = mk([
            plugin("a", requires=["b-cap"], capabilities=["a-cap"]),
            plugin("b", requires=["a-cap"], capabilities=["b-cap"]),
        ])
        with self.assertRaises(CycleError) as ctx:
            install_order(market, ["a", "b"])
        self.assertIn("a", str(ctx.exception))
        self.assertIn("b", str(ctx.exception))

    def test_three_plugin_cycle_raises(self) -> None:
        market = mk([
            plugin("a", requires=["c-cap"], capabilities=["a-cap"]),
            plugin("b", requires=["a-cap"], capabilities=["b-cap"]),
            plugin("c", requires=["b-cap"], capabilities=["c-cap"]),
        ])
        with self.assertRaises(CycleError):
            install_order(market, ["a", "b", "c"])

    def test_self_requiring_plugin_raises(self) -> None:
        market = mk([plugin("a", requires=["a-cap"], capabilities=["a-cap"])])
        with self.assertRaises(CycleError):
            install_order(market, ["a"])

    def test_a_cycle_elsewhere_does_not_silently_drop_clean_plugins(self) -> None:
        """Never emit a partial order — the caller would install an incomplete set."""
        market = mk([
            plugin("a", requires=["b-cap"], capabilities=["a-cap"]),
            plugin("b", requires=["a-cap"], capabilities=["b-cap"]),
            plugin("clean"),
        ])
        with self.assertRaises(CycleError):
            install_order(market, ["a", "b", "clean"])


class TestCli(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(_SCRIPT), *args],
                              capture_output=True, text=True, timeout=30)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _market_file(self, market: dict) -> Path:
        path = self.tmp / "marketplace.json"
        path.write_text(json.dumps(market), encoding="utf-8")
        return path

    def test_prints_one_plugin_per_line_in_order(self) -> None:
        path = self._market_file(mk([
            plugin("aardvark", requires=["zebra-power"]),
            plugin("zulu", capabilities=["zebra-power"]),
        ]))
        result = self._run(str(path), "aardvark", "zulu")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["zulu", "aardvark"])

    def test_cycle_exits_1_and_names_the_plugins(self) -> None:
        path = self._market_file(mk([
            plugin("a", requires=["b-cap"], capabilities=["a-cap"]),
            plugin("b", requires=["a-cap"], capabilities=["b-cap"]),
        ]))
        result = self._run(str(path), "a", "b")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("cycle", result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_missing_marketplace_exits_2(self) -> None:
        result = self._run(str(self.tmp / "nope.json"), "a")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot read", result.stderr)

    def test_no_arguments_exits_2_with_usage(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)


@unittest.skipUnless(_REAL_MARKETPLACE.is_file() and _DEFAULT_SET.is_file(),
                     "dist/ not generated — run `python3 scripts/generate.py build`")
class TestShippedCatalog(unittest.TestCase):
    """The synthetic cases prove the algorithm; these prove today's catalog."""

    def setUp(self) -> None:
        self.market = json.loads(_REAL_MARKETPLACE.read_text(encoding="utf-8"))
        self.wanted = json.loads(_DEFAULT_SET.read_text(encoding="utf-8"))["plugins"]

    def test_every_declared_dependency_installs_before_its_dependent(self) -> None:
        order = install_order(self.market, self.wanted)
        self.assertCountEqual(order, self.wanted)
        index = build_index(self.market)
        position = {name: i for i, name in enumerate(order)}
        checked = 0
        for entry in self.market["plugins"]:
            name = entry["name"]
            if name not in position:
                continue
            for target in entry.get("dependencies") or []:
                provider = resolve_target(str(target), index, set(self.wanted))
                if provider in position:
                    self.assertLess(position[provider], position[name],
                                    f"{name} requires {target} ({provider}) but installs first")
                    checked += 1
        self.assertGreater(checked, 0, "no requires: edges found — fixture is not exercising anything")

    def test_the_catalog_has_no_cycle(self) -> None:
        install_order(self.market, self.wanted)  # raises CycleError if it does


if __name__ == "__main__":
    unittest.main()
