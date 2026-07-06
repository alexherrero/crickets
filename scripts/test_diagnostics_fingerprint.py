#!/usr/bin/env python3
"""Tests for src/diagnostics/scripts/fingerprint.py (crickets wave-c-diagnostics, task 1).

Exercises the fingerprint normalizer's core guarantee: two failures that are the
same underlying incident (differing only in volatile tokens -- absolute paths,
PIDs, timestamps, stdlib-frame noise) collapse to the same fingerprint, while a
genuinely different error class or in-app root frame produces a different one.

stdlib only -- no pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SRC = _ROOT / "src" / "diagnostics" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


fp = _load("diagnostics_fingerprint", _SRC / "fingerprint.py")

_TB_A = '''Traceback (most recent call last):
  File "/Users/alex/proj/src/diagnostics/scripts/recall.py", line 42, in classify
    raise ValueError("bad exit code: 137")
ValueError: bad exit code: 137
'''

_TB_A_OTHER_MACHINE = '''Process 98765 at 2026-07-06T11:22:33Z crashed:
Traceback (most recent call last):
  File "/home/ci-runner/workspace/src/diagnostics/scripts/recall.py", line 42, in classify
    raise ValueError("bad exit code: 137")
ValueError: bad exit code: 137
'''

_TB_DIFFERENT_CLASS = '''Traceback (most recent call last):
  File "/Users/alex/proj/src/diagnostics/scripts/recall.py", line 42, in classify
    raise TypeError("bad exit code: 137")
TypeError: bad exit code: 137
'''

_TB_DIFFERENT_ROOT_FRAME = '''Traceback (most recent call last):
  File "/Users/alex/proj/src/diagnostics/scripts/writer.py", line 88, in write_entry
    raise ValueError("bad exit code: 137")
ValueError: bad exit code: 137
'''

_TB_STDLIB_TAIL_A = '''Traceback (most recent call last):
  File "/Users/alex/proj/src/diagnostics/scripts/recall.py", line 42, in classify
    result = json.loads(payload)
  File "/usr/lib/python3.11/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
'''

_TB_STDLIB_TAIL_B = '''Traceback (most recent call last):
  File "/Users/alex/proj/src/diagnostics/scripts/recall.py", line 42, in classify
    result = json.loads(payload)
  File "/opt/homebrew/lib/python3.12/json/__init__.py", line 299, in loads
    return _default_decoder.decode(s)
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
'''


class FingerprintNormalizerTests(unittest.TestCase):
    def test_volatile_tokens_collapse_to_same_fingerprint(self):
        fp_a, algo_a = fp.compute_fingerprint(_TB_A)
        fp_b, algo_b = fp.compute_fingerprint(_TB_A_OTHER_MACHINE)
        self.assertEqual(fp_a, fp_b)
        self.assertEqual(algo_a, algo_b)

    def test_different_error_class_yields_different_fingerprint(self):
        fp_a, _ = fp.compute_fingerprint(_TB_A)
        fp_c, _ = fp.compute_fingerprint(_TB_DIFFERENT_CLASS)
        self.assertNotEqual(fp_a, fp_c)

    def test_different_root_in_app_frame_yields_different_fingerprint(self):
        fp_a, _ = fp.compute_fingerprint(_TB_A)
        fp_d, _ = fp.compute_fingerprint(_TB_DIFFERENT_ROOT_FRAME)
        self.assertNotEqual(fp_a, fp_d)

    def test_stdlib_frame_noise_is_excluded_from_signature(self):
        fp_g, _ = fp.compute_fingerprint(_TB_STDLIB_TAIL_A)
        fp_h, _ = fp.compute_fingerprint(_TB_STDLIB_TAIL_B)
        self.assertEqual(fp_g, fp_h)

    def test_deterministic_across_repeated_runs(self):
        results = {fp.compute_fingerprint(_TB_A) for _ in range(50)}
        self.assertEqual(len(results), 1)

    def test_fp_algo_is_versioned(self):
        _, algo = fp.compute_fingerprint(_TB_A)
        self.assertEqual(algo, fp.FP_ALGO)
        self.assertRegex(algo, r"^v\d+$")


if __name__ == "__main__":
    unittest.main()
